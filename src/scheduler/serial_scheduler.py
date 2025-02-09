import schedule
import time
from datetime import datetime
import json
import os
import subprocess
import logging
from src.scrapers.ht_scraper import HTScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/serial_scheduler.log'),
        logging.StreamHandler()
    ]
)

class SerialScheduler:
    def __init__(self):
        self.scraper = HTScraper()
        self.processed_serials = set()
        self.data_dir = os.path.join('data', 'json')
        self.tracking_file = os.path.join(self.data_dir, 'processed_serials.json')
        self.config = self._load_config()
        self.target_serials = self.config['target_serials']
        self.load_processed_serials()

    def _load_config(self):
        """Load serial configuration"""
        config_path = os.path.join('config', 'serials_config.json')
        with open(config_path, 'r') as f:
            return json.load(f)

    def load_processed_serials(self):
        """Load the list of processed serials for today"""
        try:
            if os.path.exists(self.tracking_file):
                with open(self.tracking_file, 'r') as f:
                    data = json.load(f)
                    # Only load today's processed serials
                    today = datetime.now().strftime('%Y-%m-%d')
                    self.processed_serials = set(data.get(today, []))
            else:
                self.processed_serials = set()
        except Exception as e:
            logging.error(f"Error loading processed serials: {e}")
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
            with open(self.tracking_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logging.error(f"Error saving processed serials: {e}")

    def process_serial(self, serial_name):
        """Process a single serial"""
        if serial_name in self.processed_serials:
            logging.info(f"{serial_name} already processed today")
            return False

        serial_id = self.target_serials.get(serial_name)
        if not serial_id:
            logging.error(f"Serial ID not found for {serial_name}")
            return False

        serial_config = self.config['serials'][serial_id]
        logging.info(f"Processing {serial_name}...")

        try:
            # Fetch articles
            articles = self.scraper.fetch_articles(serial_config)
            if not articles:
                logging.info(f"No articles found for {serial_name}")
                return False

            # Get today's date format
            today = datetime.now()
            today_month = today.strftime('%B')
            today_day = today.day
            today_suffix = 'th' if 11 <= today_day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(today_day % 10, 'th')
            today_format = f"{today_month} {today_day}{today_suffix}"

            # Filter today's articles
            today_articles = []
            for article in articles:
                title = article.get('title', '')
                if today_format.lower() in title.lower() and "Episode" in title:
                    today_articles.append(article)

            if not today_articles:
                logging.info(f"No today's articles found for {serial_name}")
                return False

            # Save articles
            json_file = self.scraper.save_articles(today_articles, serial_config)
            
            # Run text-to-speech conversion
            try:
                # Create output filename based on serial and date
                today_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_mp3 = f"{serial_name.lower()}_{today_str}.mp3"
                
                # Run t.py with specific JSON file and output MP3 name
                subprocess.run([
                    'python', 'src/audio/t.py',
                    '--input', json_file,
                    '--output', output_mp3
                ], check=True)
                logging.info(f"Successfully generated audio for {serial_name} at {output_mp3}")
                
                # Mark as processed
                self.processed_serials.add(serial_name)
                self.save_processed_serials()
                return True
            except subprocess.CalledProcessError as e:
                logging.error(f"Error running text-to-speech for {serial_name}: {e}")
                return False

        except Exception as e:
            logging.error(f"Error processing {serial_name}: {e}")
            return False

    def check_serials(self):
        """Check all unprocessed serials"""
        current_hour = datetime.now().hour
        if not (8 <= current_hour < 15):  # Only run between 8 AM and 3 PM
            logging.info("Outside operating hours (8 AM - 3 PM)")
            return

        if len(self.processed_serials) == len(self.target_serials):
            logging.info("All serials processed for today")
            return

        for serial_name in self.target_serials:
            if serial_name not in self.processed_serials:
                if self.process_serial(serial_name):
                    logging.info(f"Successfully processed {serial_name}")
                else:
                    logging.info(f"Could not process {serial_name} at this time")

def main():
    # Ensure all required directories exist
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data/json', exist_ok=True)
    os.makedirs('data/audio', exist_ok=True)
    
    scheduler = SerialScheduler()
    
    # Schedule the job to run every 10 minutes
    schedule.every(10).minutes.do(scheduler.check_serials)
    
    # Run immediately on start
    scheduler.check_serials()
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Sleep for 1 minute between checks

if __name__ == "__main__":
    main() 