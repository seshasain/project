"""
Video Generator Module

This module provides functionality to create visually appealing videos by combining
audio tracks with static images and adding dynamic visual effects.

Features:
- Circular audio visualizer
- Rotating disc effect
- Professional text overlays
- High-quality video encoding
- Progress tracking
- Chunk-based processing for better performance
"""

import os
import subprocess
import logging
import json
from tqdm import tqdm
import time
import tempfile
import requests
import psutil
from typing import Optional, Tuple, List
import math
from ..scrapers.hotstar_thumbs import get_serial_episode_thumbnail
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_system_resources():
    """Log current system resource usage"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        logging.info(f"System Resources - CPU: {cpu_percent}%, Memory Used: {memory.percent}%, Disk Used: {disk.percent}%")
    except Exception as e:
        logging.error(f"Failed to get system resources: {e}")

def get_audio_duration(audio_path: str) -> float:
    """
    Get the duration of an audio file using ffprobe.
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        Duration in seconds
        
    Raises:
        subprocess.CalledProcessError: If ffprobe command fails
        json.JSONDecodeError: If ffprobe output is invalid
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',  # Also show streams info
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if not result.stdout:
            raise ValueError("No output from ffprobe")
            
        data = json.loads(result.stdout)
        
        # First try to get duration from format
        if 'format' in data and 'duration' in data['format']:
            return float(data['format']['duration'])
            
        # If not in format, try to get from audio stream
        if 'streams' in data:
            for stream in data['streams']:
                if stream.get('codec_type') == 'audio' and 'duration' in stream:
                    return float(stream['duration'])
                    
        raise ValueError("Could not find duration in ffprobe output")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running ffprobe: {e.stderr}")
        raise
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing ffprobe output: {e}")
        raise
    except (KeyError, ValueError) as e:
        print(f"❌ Error extracting duration: {e}")
        raise

# Constants
VIDEO_SETTINGS = {
    'WIDTH': 640,  # 360p resolution for faster processing
    'HEIGHT': 360,
    'FPS': 24,
    'CRF': 30,  # Even lower quality for faster encoding
    'AUDIO_BITRATE': '64k',  # Minimal bitrate
    'PRESET': 'ultrafast',  # Fastest preset
    'CHUNK_DURATION': 10,  # Smaller chunks (10 seconds)
    'MAX_CHUNKS': 60,  # More chunks but smaller
    'MAX_THREADS': 2,  # Match server's vCPU count
    'MEMORY_LIMIT': '512M'  # Limit memory usage per FFmpeg process
}

VISUALIZER_SETTINGS = {
    'SIZE': 300,  # Reduced for 360p
    'CENTER': 150,
    'RADIUS': 120,
    'WAVE_COLOR': 'white'
}

DISC_SETTINGS = {
    'SIZE': 60,  # Reduced size
    'CENTER': 30,
    'RADIUS': 25,
    'ROTATION_SPEED': 1.0
}

TEXT_SETTINGS = {
    'FONT': '/System/Library/Fonts/Supplemental/Verdana.ttf',
    'TITLE': {
        'SIZE': 24,  # Reduced for 360p
        'Y_POS': 15,
        'BOX_BORDER': 1
    },
    'DATE': {
        'SIZE': 18,
        'Y_POS': 45,
        'BOX_BORDER': 1
    },
    'CHANNEL': {
        'SIZE': 30,
        'Y_POS': 'h-25',
        'BOX_BORDER': 1
    }
}

# Function to find available system font
def find_system_font() -> str:
    """Find an available system font to use"""
    font_paths = [
        '/System/Library/Fonts/Supplemental/Verdana.ttf',  # macOS
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux
        'C:\\Windows\\Fonts\\verdana.ttf',  # Windows
        '/System/Library/Fonts/Helvetica.ttc',  # macOS fallback
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'  # Linux fallback
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            return font_path
            
    # If no system fonts found, raise error
    raise FileNotFoundError("No suitable system font found")

def create_filter_chain(serial_name: str, duration: float) -> List[str]:
    """
    Create the FFmpeg filter chain for video generation.
    
    Args:
        serial_name: Name of the serial to display
        duration: Duration of the video in seconds
        
    Returns:
        List of filter commands
    """
    current_date = time.strftime("%B %d, %Y")
    vs = VISUALIZER_SETTINGS
    ds = DISC_SETTINGS
    ts = TEXT_SETTINGS
    
    # Calculate fade out start time (3 seconds before end)
    fade_out_start = max(0, duration - 3)
    
    return [
        # Background: Scale only, no blur
        f"[2:v]scale={VIDEO_SETTINGS['WIDTH']}:{VIDEO_SETTINGS['HEIGHT']}[bg]",
        
        # Audio visualizer
        f"[1:a]aformat=channel_layouts=stereo,showwaves=mode=cline:s={vs['SIZE']}x{vs['SIZE']}:"
        f"colors={vs['WAVE_COLOR']}[wave]",
        
        # Circular mask for visualizer
        f"color=s={vs['SIZE']}x{vs['SIZE']}:c=black@0,format=gray,"
        f"geq='lum=if(lt((X-{vs['CENTER']})*(X-{vs['CENTER']})+(Y-{vs['CENTER']})*(Y-{vs['CENTER']}),"
        f"{vs['RADIUS']}*{vs['RADIUS']}),255,0)'[wave_mask]",
        
        "[wave][wave_mask]alphamerge[wave_circ]",
        
        # Overlay visualizer on background
        f"[bg][wave_circ]overlay=x=(W-{vs['SIZE']})/2:y=(H-{vs['SIZE']})/2[bg_wave]",
        
        # Create circular disc
        f"[0:v]scale={ds['SIZE']}:{ds['SIZE']},format=rgba[disc_scaled]",
        
        f"color=s={ds['SIZE']}x{ds['SIZE']}:c=black,format=gray,"
        f"geq='lum=if(lt((X-{ds['CENTER']})*(X-{ds['CENTER']})+(Y-{ds['CENTER']})*(Y-{ds['CENTER']}),"
        f"{ds['RADIUS']}*{ds['RADIUS']}),255,0)'[disc_mask]",
        
        "[disc_scaled][disc_mask]alphamerge[disc_circ]",
        
        # Rotate disc
        f"[disc_circ]rotate=t*{ds['ROTATION_SPEED']}:c=none[disc_rot]",
        
        # Overlay rotating disc
        f"[bg_wave][disc_rot]overlay=x=(W-{ds['SIZE']})/2:y=(H-{ds['SIZE']})/2[with_disc]",
        
        # Add fade in/out effects
        f"[with_disc]fade=in:0:30,fade=out:st={fade_out_start}:d=3[faded]",
        
        # Add text overlays
        f"[faded]drawtext=text='{serial_name or 'Telugu Serial'}':"
        f"fontfile={ts['FONT']}:fontcolor=white:fontsize={ts['TITLE']['SIZE']}:"
        f"x=(w-text_w)/2:y={ts['TITLE']['Y_POS']}:box=1:boxcolor=black@0.6:"
        f"boxborderw={ts['TITLE']['BOX_BORDER']}[with_text1]",
        
        f"[with_text1]drawtext=text='{current_date}':"
        f"fontfile={ts['FONT']}:fontcolor=white:fontsize={ts['DATE']['SIZE']}:"
        f"x=(w-text_w)/2:y={ts['DATE']['Y_POS']}:box=1:boxcolor=black@0.6:"
        f"boxborderw={ts['DATE']['BOX_BORDER']}[with_text2]",
        
        f"[with_text2]drawtext=text='Raghava Ram Reviews':"
        f"fontfile={ts['FONT']}:fontcolor=white:fontsize={ts['CHANNEL']['SIZE']}:"
        f"x=(w-text_w)/2:y={ts['CHANNEL']['Y_POS']}:box=1:boxcolor=black@0.6:"
        f"boxborderw={ts['CHANNEL']['BOX_BORDER']}[out]"
    ]

def split_audio_into_chunks(audio_path: str, temp_dir: str = None, chunk_duration: int = VIDEO_SETTINGS['CHUNK_DURATION']) -> List[str]:
    """Split audio file into chunks for parallel processing."""
    logger = logging.getLogger(__name__)
    try:
        # Get total duration
        duration = get_audio_duration(audio_path)
        num_chunks = min(VIDEO_SETTINGS['MAX_CHUNKS'], math.ceil(duration / chunk_duration))
        chunk_duration = math.ceil(duration / num_chunks)  # Adjust chunk duration for even distribution
        
        logger.info(f"Splitting {duration}s audio into {num_chunks} chunks of {chunk_duration}s each")
        
        # Create temporary directory for chunks if not provided
        if not temp_dir:
            temp_dir = os.path.join(os.path.dirname(audio_path), 'temp_chunks')
        os.makedirs(temp_dir, exist_ok=True)
        
        chunk_paths = []
        for i in range(num_chunks):
            start_time = i * chunk_duration
            output_chunk = os.path.join(temp_dir, f"chunk_{i}.mp3")
            
            cmd = [
                'ffmpeg', '-y',
                '-i', audio_path,
                '-ss', str(start_time),
                '-t', str(chunk_duration),
                '-c', 'copy',
                output_chunk
            ]
            
            logger.info(f"Creating chunk {i+1}/{num_chunks}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Error creating chunk {i+1}: {result.stderr}")
                raise Exception(f"Failed to create chunk {i+1}")
                
            chunk_paths.append(output_chunk)
            logger.info(f"Successfully created chunk {i+1}/{num_chunks}")
            
        return chunk_paths
        
    except Exception as e:
        logger.error(f"Error splitting audio: {str(e)}")
        raise

def process_video_chunk(
    audio_chunk: str,
    image_path: str,
    output_path: str,
    serial_name: Optional[str] = None,
    chunk_index: int = 0,
    total_chunks: int = 1
) -> bool:
    """Process a single video chunk with progress tracking."""
    logger = logging.getLogger(__name__)
    progress = None
    stderr_buffer = []  # Buffer to collect stderr output
    
    try:
        # Log system resources before starting
        log_system_resources()
        logger.info(f"Starting to process chunk {chunk_index + 1}/{total_chunks}")
        logger.info(f"Input paths - Audio: {audio_chunk}, Image: {image_path}, Output: {output_path}")
        
        duration = get_audio_duration(audio_chunk)
        logger.info(f"Chunk duration: {duration}s")
        
        # Find available system font
        try:
            font_path = find_system_font()
            TEXT_SETTINGS['FONT'] = font_path
            logger.info(f"Using font: {font_path}")
        except FileNotFoundError as e:
            logger.warning(f"Warning: {e}. Using default font.")
        
        # Get disc image path from tn folder using serial name
        if serial_name:
            disc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'tn', f"{serial_name}.webp")
            if not os.path.exists(disc_path):
                logger.warning(f"Serial-specific disc image not found at {disc_path}, falling back to bg.jpg")
                disc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'bg.jpg')
        else:
            disc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'bg.jpg')
        
        logger.info(f"Using disc image: {disc_path}")
        if not os.path.exists(disc_path):
            logger.error(f"Disc image not found at {disc_path}")
            return False
            
        # Create filter chain
        logger.info("Creating filter chain...")
        filter_chain = create_filter_chain(serial_name, duration)
        filter_complex = ';'.join(filter_chain)
        logger.debug(f"Filter complex: {filter_complex}")
        
        # Construct FFmpeg command with resource limits
        cmd = [
            'nice', '-n', '10',  # Lower CPU priority
            'ffmpeg', '-y',
            '-thread_queue_size', '512',  # Increase queue size
            '-loop', '1',
            '-i', disc_path,
            '-i', audio_chunk,
            '-loop', '1',
            '-i', image_path,
            '-filter_complex', filter_complex,
            '-map', '[out]',
            '-map', '1:a',
            '-c:v', 'libx264',
            '-preset', VIDEO_SETTINGS['PRESET'],
            '-crf', str(VIDEO_SETTINGS['CRF']),
            '-c:a', 'aac',
            '-b:a', VIDEO_SETTINGS['AUDIO_BITRATE'],
            '-shortest',
            '-pix_fmt', 'yuv420p',
            '-threads', str(VIDEO_SETTINGS['MAX_THREADS']),
            '-memory_limit', VIDEO_SETTINGS['MEMORY_LIMIT'],  # Add memory limit
            output_path
        ]
        
        logger.info(f"FFmpeg command: {' '.join(cmd)}")
        
        # Run FFmpeg with resource limits
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            preexec_fn=lambda: os.nice(10)  # Set nice level for child process
        )
        
        start_time = time.time()
        timeout = max(duration * 5, 120)  # At least 120 seconds or 5x duration
        last_progress_time = time.time()
        last_resource_check = time.time()
        
        while True:
            if process.poll() is not None:
                break
                
            current_time = time.time()
            
            # Check for timeout
            if current_time - start_time > timeout:
                logger.error(f"Chunk {chunk_index + 1} processing timed out after {timeout} seconds")
                process.kill()
                return False
                
            # Check for stall
            if current_time - last_progress_time > 60:  # Increased stall detection to 60 seconds
                logger.error(f"Chunk {chunk_index + 1} processing stalled - no progress for 60 seconds")
                # Log system resources when stalled
                log_system_resources()
                process.kill()
                return False
                
            # Log system resources every 60 seconds
            if current_time - last_resource_check > 60:
                log_system_resources()
                last_resource_check = current_time
                
            # Read FFmpeg output
            line = process.stderr.readline()
            if not line:
                time.sleep(0.1)
                continue
                
            # Store stderr output
            stderr_buffer.append(line)
                
            # Log FFmpeg progress
            if "time=" in line:
                try:
                    time_str = line.split("time=")[1].split()[0]
                    current_time = sum(float(x) * 60 ** i for i, x in enumerate(reversed(time_str.split(":"))))
                    progress_percent = min(100, int((current_time / duration) * 100))
                    logger.info(f"Chunk {chunk_index + 1} progress: {progress_percent}% (time: {time_str})")
                    last_progress_time = time.time()
                except Exception as e:
                    logger.error(f"Error parsing FFmpeg progress: {e}")
                    
        # Get final status
        return_code = process.wait()
        remaining_stderr = process.stderr.read() if process.stderr else ""
        if remaining_stderr:
            stderr_buffer.append(remaining_stderr)
        
        if return_code != 0:
            logger.error(f"FFmpeg Error in chunk {chunk_index + 1} (return code {return_code}):")
            logger.error("FFmpeg stderr:")
            for line in stderr_buffer:
                logger.error(line.strip())
            return False
            
        # Log final system resources
        log_system_resources()
        logger.info(f"Chunk {chunk_index + 1}/{total_chunks} processed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error processing chunk {chunk_index + 1}: {str(e)}")
        if stderr_buffer:
            logger.error("FFmpeg stderr:")
            for line in stderr_buffer:
                logger.error(line.strip())
        return False
        
    finally:
        if progress:
            progress.close()

def merge_video_chunks(chunk_paths: List[str], output_path: str) -> bool:
    """Merge processed video chunks into final video."""
    logger = logging.getLogger(__name__)
    try:
        # Create a temporary file listing all chunks
        concat_file = os.path.join(os.path.dirname(output_path), 'concat_list.txt')
        with open(concat_file, 'w') as f:
            for chunk in chunk_paths:
                f.write(f"file '{os.path.abspath(chunk)}'\n")
        
        logger.info("Merging video chunks...")
        # Merge chunks using FFmpeg concat demuxer
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Clean up temporary files
        os.remove(concat_file)
        for chunk in chunk_paths:
            os.remove(chunk)
            
        if result.returncode != 0:
            logger.error(f"Error merging chunks: {result.stderr}")
            return False
            
        logger.info("Video chunks merged successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error merging video chunks: {str(e)}")
        return False

def create_video_from_audio_and_image(
    audio_path: str,
    image_path: Optional[str],
    output_path: str,
    serial_name: Optional[str] = None,
    episode_title: Optional[str] = None
) -> bool:
    """
    Create a video from an audio file and an image.
    
    Args:
        audio_path: Path to the audio file
        image_path: Optional path to the image file. If None, will fetch from Hotstar
        output_path: Path where the output video should be saved
        serial_name: Name of the serial (e.g., 'Brahmamudi')
        episode_title: Optional title of the specific episode
        
    Returns:
        bool: True if video creation was successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Create temp directory for processing
        temp_dir = os.path.join(os.path.dirname(os.path.abspath(output_path)), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Try to get thumbnail from Hotstar first
        if serial_name:
            thumbnail_url = get_serial_episode_thumbnail(serial_name, episode_title)
            if thumbnail_url:
                # Download the thumbnail to a temporary file
                image_path = os.path.join(temp_dir, f"{serial_name}_thumbnail.jpg")
                
                response = requests.get(thumbnail_url)
                if response.status_code == 200:
                    with open(image_path, 'wb') as f:
                        f.write(response.content)
                    logger.info(f"Downloaded thumbnail from Hotstar: {thumbnail_url}")
                else:
                    logger.error(f"Failed to download thumbnail: {response.status_code}")
                    image_path = None
            else:
                logger.error("Could not fetch thumbnail from Hotstar")
                image_path = None
        
        # If no image path available, use provided image_path or fallback to bg.jpg
        if not image_path:
            if os.path.exists(image_path):
                logger.info("Using provided image path")
            else:
                bg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'bg.jpg')
                if os.path.exists(bg_path):
                    logger.info("Using fallback bg.jpg")
                    image_path = bg_path
                else:
                    logger.error("No image path provided and bg.jpg not found")
                    return False
            
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            return False
            
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return False
            
        # Get audio duration
        duration = get_audio_duration(audio_path)
        
        # Split audio into chunks for parallel processing
        chunk_paths = split_audio_into_chunks(audio_path, temp_dir=temp_dir)
        if not chunk_paths:
            logger.error("Failed to split audio into chunks")
            return False
            
        # Process each chunk
        output_chunks = []
        total_chunks = len(chunk_paths)
        
        for i, chunk_path in enumerate(chunk_paths):
            chunk_output = os.path.join(temp_dir, f"output_chunk_{i}.mp4")
            success = process_video_chunk(
                chunk_path,
                image_path,
                chunk_output,
                serial_name,
                i,
                total_chunks
            )
            
            if not success:
                logger.error(f"Failed to process chunk {i+1}/{total_chunks}")
                return False
                
            output_chunks.append(chunk_output)
            
        # Merge chunks into final video
        success = merge_video_chunks(output_chunks, output_path)
        if not success:
            logger.error("Failed to merge video chunks")
            return False
            
        # Clean up temporary files
        cleanup_temp_files(chunk_paths + output_chunks)
        if image_path and image_path.endswith('_thumbnail.jpg'):
            # Only delete the image if it was downloaded from Hotstar
            try:
                os.remove(image_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary image: {e}")
        
        # Clean up temp directory if empty
        try:
            os.rmdir(temp_dir)
        except:
            pass
        
        logger.info(f"Successfully created video: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating video: {e}")
        return False

def cleanup_temp_files(file_paths: List[str]) -> None:
    """Clean up temporary files created during video processing."""
    logger = logging.getLogger(__name__)
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to delete temporary file {file_path}: {e}")

def process_video_chunks(chunks, output_dir, thumbnail_path, bg_path):
    """Process video chunks with progress bar."""
    try:
        total_chunks = len(chunks)
        with tqdm(total=total_chunks, desc="Processing video chunks", unit="chunk") as pbar:
            for i, chunk in enumerate(chunks, 1):
                logging.info(f"Processing chunk {i}/{total_chunks}")
                output_path = output_dir / f"output_chunk_{i-1}.mp4"
                
                # Start FFmpeg process
                cmd = construct_ffmpeg_command(chunk, output_path, thumbnail_path, bg_path)
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                
                # Monitor FFmpeg progress
                while process.poll() is None:
                    time.sleep(1)
                    if process.stderr:
                        line = process.stderr.readline()
                        if "time=" in line:
                            # Update progress bar description with current time
                            try:
                                time_str = line.split("time=")[1].split()[0]
                                pbar.set_description(f"Processing chunk {i}/{total_chunks} (Time: {time_str})")
                            except:
                                pass
                
                # Check if process completed successfully
                if process.returncode != 0:
                    error_output = process.stderr.read() if process.stderr else "Unknown error"
                    logging.error(f"Failed to process chunk {i}/{total_chunks}")
                    logging.error(f"FFmpeg error: {error_output}")
                    raise Exception(f"FFmpeg failed with return code {process.returncode}")
                
                pbar.update(1)
                logging.info(f"Successfully processed chunk {i}/{total_chunks}")
        
        return True
    except Exception as e:
        logging.error(f"Error in process_video_chunks: {str(e)}")
        return False

def generate_video(audio_path, thumbnail_path=None, bg_path=None, output_path=None, serial_name=None):
    """Generate a video with audio visualization and thumbnail."""
    try:
        # Create temp directory for chunks
        temp_dir = Path("data/video/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Get audio duration
        duration = get_audio_duration(audio_path)
        if duration is None:
            logging.error("Could not determine audio duration")
            return False
            
        logging.info(f"Audio duration: {duration}s")
        
        # Split audio into chunks
        chunk_duration = 101  # seconds
        num_chunks = math.ceil(duration / chunk_duration)
        logging.info(f"Splitting {duration}s audio into {num_chunks} chunks of {chunk_duration}s each")
        
        chunks = []
        with tqdm(total=num_chunks, desc="Creating audio chunks", unit="chunk") as pbar:
            for i in range(num_chunks):
                start_time = i * chunk_duration
                output_chunk = temp_dir / f"chunk_{i}.mp3"
                
                # Use FFmpeg to split audio
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(audio_path),
                    "-ss", str(start_time),
                    "-t", str(chunk_duration),
                    str(output_chunk)
                ]
                
                logging.info(f"Creating chunk {i+1}/{num_chunks}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    chunks.append(output_chunk)
                    logging.info(f"Successfully created chunk {i+1}/{num_chunks}")
                    pbar.update(1)
                else:
                    logging.error(f"Failed to create chunk {i+1}/{num_chunks}")
                    logging.error(f"FFmpeg error: {result.stderr}")
                    return False
        
        # Process video chunks with progress bar
        success = process_video_chunks(chunks, temp_dir, thumbnail_path, bg_path)
        if not success:
            return False
            
        # Combine video chunks
        with open(temp_dir / "concat_list.txt", "w") as f:
            for i in range(len(chunks)):
                f.write(f"file 'output_chunk_{i}.mp4'\n")
        
        final_output = output_path or "output.mp4"
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(temp_dir / "concat_list.txt"),
            "-c", "copy",
            str(final_output)
        ]
        
        logging.info("Combining video chunks...")
        result = subprocess.run(concat_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logging.info("Successfully combined video chunks")
            cleanup_temp_files(temp_dir)
            return True
        else:
            logging.error("Failed to combine video chunks")
            logging.error(f"FFmpeg error: {result.stderr}")
            return False
            
    except Exception as e:
        logging.error(f"Error in generate_video: {str(e)}")
        return False