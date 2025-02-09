import schedule
import time
from datetime import datetime
import json
import os
import subprocess
import logging
import signal
import sys
from src.scrapers.ht_scraper import HTScraper
from src.video.video_generator import create_video_from_audio_and_image
from src.video.youtube_uploader import YouTubeUploader
from tqdm import tqdm
import re
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle

# Configure logging with more detailed format and rotation
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
log_file = 'logs/serial_scheduler.log'
max_bytes = 10 * 1024 * 1024  # 10MB
backup_count = 5

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Add YouTube API scopes
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

class GracefulExit:
    def __init__(self):
        self.kill_now = False
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        logger.info("Received shutdown signal. Performing cleanup...")
        self.kill_now = True

class ConsoleProgress:
    def __init__(self, desc="Processing"):
        self.desc = desc
        self.progress = None
        
    def start(self, total=100):
        self.progress = tqdm(total=total, desc=self.desc, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}')
        
    def update(self, n=1):
        if self.progress:
            self.progress.update(n)
            
    def set_description(self, desc):
        if self.progress:
            self.progress.set_description(desc)
            
    def close(self):
        if self.progress:
            self.progress.close()

class SerialProcessor:
    def __init__(self):
        try:
            self.scraper = HTScraper()
            self.processed_serials = set()
            self.data_dir = os.path.join('data', 'json')
            self.tracking_file = os.path.join(self.data_dir, 'processed_serials.json')
            self.config = self._load_config()
            self.target_serials = self.config['target_serials']
            self.load_processed_serials()
            self.error_count = {}  # Track errors per serial
            self.max_retries = 3  # Maximum number of retries per serial
            self.youtube_uploader = YouTubeUploader()  # Initialize YouTube uploader
        except Exception as e:
            logger.error(f"Failed to initialize SerialProcessor: {str(e)}")
            raise

    def _load_config(self):
        """Load serial configuration"""
        logger.info("Loading serial configuration...")
        try:
            config_path = os.path.join('config', 'serials_config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
            logger.info("Configuration loaded successfully")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file not found at {config_path}")
            raise
        except json.JSONDecodeError:
            logger.error("Invalid JSON in configuration file")
            raise
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            raise

    def load_processed_serials(self):
        """Load the list of processed serials for today"""
        try:
            if os.path.exists(self.tracking_file):
                with open(self.tracking_file, 'r') as f:
                    data = json.load(f)
                    today = datetime.now().strftime('%Y-%m-%d')
                    self.processed_serials = set(data.get(today, []))
                    logger.info(f"Loaded {len(self.processed_serials)} processed serials for today")
            else:
                self.processed_serials = set()
                logger.info("No processed serials found for today")
        except Exception as e:
            logger.error(f"Error loading processed serials: {e}")
            self.processed_serials = set()

    def save_processed_serials(self):
        """Save the list of processed serials for today"""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            today = datetime.now().strftime('%Y-%m-%d')
            data = {}
            if os.path.exists(self.tracking_file):
                with open(self.tracking_file, 'r') as f:
                    data = json.load(f)
            data[today] = list(self.processed_serials)
            
            # Create backup before saving
            if os.path.exists(self.tracking_file):
                backup_file = f"{self.tracking_file}.bak"
                os.replace(self.tracking_file, backup_file)
            
            with open(self.tracking_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Successfully saved {len(self.processed_serials)} processed serials")
        except Exception as e:
            logger.error(f"Error saving processed serials: {e}")
            if os.path.exists(f"{self.tracking_file}.bak"):
                os.replace(f"{self.tracking_file}.bak", self.tracking_file)
                logger.info("Restored tracking file from backup")

    def should_retry(self, serial_name):
        """Determine if we should retry processing a serial"""
        return self.error_count.get(serial_name, 0) < self.max_retries

    def process_serial(self, serial_name):
        """Process a single serial"""
        if serial_name in self.processed_serials:
            logger.info(f"{serial_name} already processed today")
            return False

        if not self.should_retry(serial_name):
            logger.warning(f"Skipping {serial_name} - max retries exceeded")
            return False

        serial_id = self.target_serials.get(serial_name)
        if not serial_id:
            logger.error(f"Serial ID not found for {serial_name}")
            return False

        try:
            serial_config = self.config['serials'][serial_id]
            logger.info(f"Processing {serial_name}...")
            progress = ConsoleProgress(f"Processing {serial_name}")
            progress.start(total=5)  # Updated total to include upload step

            serial_slug = serial_name.lower().replace(' ', '_')
            today_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Audio processing
            progress.set_description("Generating new audio")
            audio_dir = os.path.join('data', 'audio')
            os.makedirs(audio_dir, exist_ok=True)
            
            articles = self.scraper.fetch_articles(serial_config)
            if not articles:
                logger.warning("No articles found")
                self.error_count[serial_name] = self.error_count.get(serial_name, 0) + 1
                progress.close()
                return False

            today = datetime.now()
            today_str_format = today.strftime('%A, %B %d, %Y')  # Format: Thursday, February 6, 2025

            today_articles = []
            for article in articles:
                pub_date = article.get('date', article.get('published_date', ''))
                title = article.get('title', '')
                logger.info(f"Checking article - Title: {title}")
                logger.info(f"Published Date: {pub_date}")
                logger.info(f"Expected Date: {today_str_format}")
                
                # Try to parse the published date
                try:
                    if pub_date:
                        pub_date_clean = pub_date.strip()
                        # Try to parse the date to ensure it's valid
                        pub_date_obj = datetime.strptime(pub_date_clean, '%A, %B %d, %Y')
                        today_date_obj = today.replace(hour=0, minute=0, second=0, microsecond=0)
                        
                        if pub_date_obj.date() == today_date_obj.date() and re.search(r'episode|serial', title, re.IGNORECASE):
                            logger.info(f"Found matching article for today: {title}")
                            today_articles.append(article)
                        else:
                            if pub_date_obj.date() != today_date_obj.date():
                                logger.debug(f"Date mismatch - Expected: {today_date_obj.date()}, Got: {pub_date_obj.date()}")
                            elif not re.search(r'episode|serial', title, re.IGNORECASE):
                                logger.debug("Missing 'episode' or 'serial' in title")
                    else:
                        logger.debug("Missing published date")
                except ValueError as e:
                    logger.error(f"Error parsing date: {e} - Published date: {pub_date}")
                    continue

            if not today_articles:
                logger.warning("No today's articles found")
                self.error_count[serial_name] = self.error_count.get(serial_name, 0) + 1
                progress.close()
                return False

            json_file = self.scraper.save_articles(today_articles, serial_config)
            audio_file = os.path.join('data', 'audio', f"{serial_slug}_{today_str}.mp3")
            
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(os.path.dirname(script_dir))
                tts_script = os.path.join(project_root, 'src', 'audio', 'text_to_speech.py')
                
                # Use the same Python interpreter that's running this script
                python_executable = sys.executable
                
                # Set PYTHONPATH to include the project root
                env = os.environ.copy()
                env['PYTHONPATH'] = project_root
                
                # Run the text-to-speech script and wait for completion
                result = subprocess.run([
                    python_executable,
                    tts_script,
                    '--input', json_file,
                    '--output', f"{serial_slug}_{today_str}.mp3"  # Just pass the filename, not the full path
                ], check=True, capture_output=True, text=True, env=env)
                
                # Wait for the file to exist and be non-empty
                max_wait = 60  # Maximum seconds to wait
                wait_time = 0
                last_size = 0
                consecutive_same_size = 0
                
                while wait_time < max_wait:
                    if os.path.exists(audio_file):
                        current_size = os.path.getsize(audio_file)
                        if current_size > 0:
                            if current_size == last_size:
                                consecutive_same_size += 1
                                # If file size hasn't changed for 5 seconds, consider it complete
                                if consecutive_same_size >= 5:
                                    logger.info(f"Audio file generation complete. Size: {current_size/1024:.2f}KB")
                                    break
                            else:
                                consecutive_same_size = 0
                                last_size = current_size
                                logger.info(f"Audio file growing... Current size: {current_size/1024:.2f}KB")
                    time.sleep(1)
                    wait_time += 1
                    logger.info(f"Waiting for audio file generation... ({wait_time}s)")
                
                if wait_time >= max_wait:
                    logger.error("Timeout waiting for audio file generation")
                    self.error_count[serial_name] = self.error_count.get(serial_name, 0) + 1
                    progress.close()
                    return False
                
                # Double check the file is valid
                if not os.path.exists(audio_file) or os.path.getsize(audio_file) == 0:
                    logger.error("Audio file is missing or empty after generation")
                    self.error_count[serial_name] = self.error_count.get(serial_name, 0) + 1
                    progress.close()
                    return False
                
                logger.info(f"Successfully generated audio at {audio_file}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Error generating audio: {e.stderr}")
                self.error_count[serial_name] = self.error_count.get(serial_name, 0) + 1
                progress.close()
                return False
            
            progress.update()
            
            # Video generation
            progress.set_description("Generating video")
            video_dir = os.path.join('data', 'video')
            os.makedirs(video_dir, exist_ok=True)
            video_file = os.path.join(video_dir, f"{serial_slug}_{today_str}.mp4")
            
            # Get the episode title from the first article
            episode_title = today_articles[0].get('title') if today_articles else None
            
            # Try to create video with Hotstar thumbnail
            if create_video_from_audio_and_image(
                audio_file, 
                None,  # No image path - will fetch from Hotstar
                video_file, 
                serial_name=serial_name,
                episode_title=episode_title
            ):
                logger.info(f"Created video: {os.path.basename(video_file)}")
                progress.update()
                
                # Mark as processed
                self.processed_serials.add(serial_name)
                self.save_processed_serials()
                
                # Reset error count on success
                self.error_count[serial_name] = 0
                
                # After successful video generation, upload to YouTube
                progress.set_description("Uploading to YouTube")
                today_date = datetime.now().strftime("%B %d, %Y")
                video_title = f"{serial_name} - {today_date} - Today Episode FullReview"
                description = f"{serial_name} Telugu Serial Review for {today_date}\nDaily updates and reviews of your favorite Telugu serials.\n\n#TeluguSerial #{serial_name.replace(' ', '')}"
                
                # Add serial-specific tags
                tags = [
                    f'{serial_name} Full Serial',
                    f'{serial_name} Episode Review',
                    f'{serial_name} Today Episode Review',
                    'Telugu Serial',
                    'Daily Update',
                    'Episode Review',
                    serial_name,
                    f'{serial_name} Serial',
                    f'{serial_name} Review',
                    'Telugu Daily Serial',
                    'Star Maa Serials'
                ]
                
                video_id = self.youtube_uploader.upload_video(
                    video_file=video_file,
                    title=video_title,
                    description=description,
                    tags=tags,
                    privacy_status='public',
                    made_for_kids=False
                )
                
                if video_id:
                    video_url = self.youtube_uploader.get_video_url(video_id)
                    logger.info(f"Video uploaded successfully: {video_url}")
                    progress.update()
                else:
                    logger.error("Failed to upload video to YouTube")
                    self.error_count[serial_name] = self.error_count.get(serial_name, 0) + 1
                    progress.close()
                    return False

                progress.set_description("Completed")
                progress.update()
                progress.close()
                return True
            else:
                logger.error("Video generation failed")
                self.error_count[serial_name] = self.error_count.get(serial_name, 0) + 1
                progress.close()
                return False

        except Exception as e:
            logger.error(f"Error processing {serial_name}: {str(e)}", exc_info=True)
            self.error_count[serial_name] = self.error_count.get(serial_name, 0) + 1
            progress.close()
            return False

    def check_serials(self):
        """Check all unprocessed serials"""
        try:
            current_hour = datetime.now().hour
            
            if len(self.processed_serials) == len(self.target_serials):
                logger.info("All serials processed for today")
                return

            unprocessed = [s for s in self.target_serials if s not in self.processed_serials]
            logger.info(f"Processing {len(unprocessed)} remaining serials...")
            
            for serial_name in unprocessed:
                if self.process_serial(serial_name):
                    logger.info(f"Successfully processed {serial_name}")
                else:
                    logger.warning(f"Could not process {serial_name}")
                    
            logger.info("Scheduler cycle completed")
        except Exception as e:
            logger.error(f"Error in check_serials: {str(e)}", exc_info=True)

def cleanup():
    """Perform cleanup operations"""
    logger.info("Performing cleanup operations...")
    try:
        # Keep only the last 5 days of logs
        log_dir = 'logs'
        if os.path.exists(log_dir):
            log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
            log_files.sort(key=lambda x: os.path.getmtime(os.path.join(log_dir, x)), reverse=True)
            # Keep the last 5 log files
            for log_file in log_files[5:]:
                try:
                    os.remove(os.path.join(log_dir, log_file))
                    logger.info(f"Removed old log file: {log_file}")
                except Exception as e:
                    logger.error(f"Error removing log file {log_file}: {e}")

        # Clean up old JSON files (keep last 2 days)
        json_dir = os.path.join('data', 'json')
        if os.path.exists(json_dir):
            json_files = [f for f in os.listdir(json_dir) if f.endswith('.json') and f != 'processed_serials.json']
            json_files.sort(key=lambda x: os.path.getmtime(os.path.join(json_dir, x)), reverse=True)
            # Keep files from the last 2 days
            two_days_ago = time.time() - (2 * 24 * 60 * 60)
            for json_file in json_files:
                file_path = os.path.join(json_dir, json_file)
                if os.path.getmtime(file_path) < two_days_ago:
                    try:
                        os.remove(file_path)
                        logger.info(f"Removed old JSON file: {json_file}")
                    except Exception as e:
                        logger.error(f"Error removing JSON file {json_file}: {e}")

        # Clean up old audio files (keep last 2 days)
        audio_dir = os.path.join('data', 'audio')
        if os.path.exists(audio_dir):
            audio_files = [f for f in os.listdir(audio_dir) if f.endswith('.mp3')]
            audio_files.sort(key=lambda x: os.path.getmtime(os.path.join(audio_dir, x)), reverse=True)
            # Keep files from the last 2 days
            for audio_file in audio_files:
                file_path = os.path.join(audio_dir, audio_file)
                if os.path.getmtime(file_path) < two_days_ago:
                    try:
                        os.remove(file_path)
                        logger.info(f"Removed old audio file: {audio_file}")
                    except Exception as e:
                        logger.error(f"Error removing audio file {audio_file}: {e}")

        # Clean up old video files (keep last 2 days)
        video_dir = os.path.join('data', 'video')
        if os.path.exists(video_dir):
            video_files = [f for f in os.listdir(video_dir) if f.endswith('.mp4')]
            video_files.sort(key=lambda x: os.path.getmtime(os.path.join(video_dir, x)), reverse=True)
            # Keep files from the last 2 days
            for video_file in video_files:
                file_path = os.path.join(video_dir, video_file)
                if os.path.getmtime(file_path) < two_days_ago:
                    try:
                        os.remove(file_path)
                        logger.info(f"Removed old video file: {video_file}")
                    except Exception as e:
                        logger.error(f"Error removing video file {video_file}: {e}")

        logger.info("Cleanup completed successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def main():
    try:
        # Ensure all required directories exist
        for directory in ['logs', 'data/json', 'data/audio', 'data/video']:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Ensured directory exists: {directory}")
        
        # Initialize graceful exit handler
        graceful_exit = GracefulExit()
        
        processor = SerialProcessor()
        
        # Schedule the job to run every 10 minutes
        schedule.every(10).minutes.do(processor.check_serials)
        logger.info("Scheduled job to run every 10 minutes")
        
        # Run immediately on start
        processor.check_serials()
        
        # Keep the script running
        while not graceful_exit.kill_now:
            schedule.run_pending()
            time.sleep(60)  # Sleep for 1 minute between checks
        
        # Perform cleanup when exiting
        cleanup()
        
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 