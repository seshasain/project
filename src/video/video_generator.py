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
from typing import Optional, Tuple, List
import math
from ..scrapers.hotstar_thumbs import get_serial_episode_thumbnail

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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
    'WIDTH': 1280,  # Changed from 1920 to 1280 (720p)
    'HEIGHT': 720,  # Changed from 1080 to 720
    'FPS': 30,
    'CRF': 20,  # Slightly adjusted for 720p
    'AUDIO_BITRATE': '192k',  # Adjusted for 720p
    'PRESET': 'medium',  # Changed from slow to medium for faster encoding
    'CHUNK_DURATION': 120,  # Process in 2-minute chunks
    'MAX_CHUNKS': 5  # Maximum number of chunks to process
}

VISUALIZER_SETTINGS = {
    'SIZE': 600,  # Reduced from 800 to fit 720p better
    'CENTER': 300,  # Adjusted center point (SIZE/2)
    'RADIUS': 250,  # Adjusted radius for new size
    'WAVE_COLOR': 'white'
}

DISC_SETTINGS = {
    'SIZE': 100,  # Reduced from 250 to fit 720p better
    'CENTER': 50,  # Adjusted center point (SIZE/2)
    'RADIUS': 45,  # Reduced radius to make black border thinner
    'ROTATION_SPEED': 1.0  # Kept same rotation speed
}

TEXT_SETTINGS = {
    'FONT': '/System/Library/Fonts/Supplemental/Verdana.ttf',
    'TITLE': {
        'SIZE': 48,  # Reduced from 60 for 720p
        'Y_POS': 30,  # Adjusted position
        'BOX_BORDER': 2  # Reduced border thickness
    },
    'DATE': {
        'SIZE': 36,  # Reduced from 42 for 720p
        'Y_POS': 80,  # Adjusted position
        'BOX_BORDER': 4  # Reduced border thickness
    },
    'CHANNEL': {
        'SIZE': 60,  # Reduced from 36 for 720p
        'Y_POS': 'h-40',  # Adjusted position from bottom
        'BOX_BORDER': 4  # Reduced border thickness
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
    
    try:
        logger.info(f"Processing chunk {chunk_index + 1}/{total_chunks}")
        duration = get_audio_duration(audio_chunk)
        
        # Find available system font
        try:
            font_path = find_system_font()
            TEXT_SETTINGS['FONT'] = font_path
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
            
        if not os.path.exists(disc_path):
            logger.error(f"Disc image not found at {disc_path}")
            return False
            
        # Define progress stages for this chunk
        stages = [
            ("Setting up filters", 10),
            ("Preparing command", 10),
            ("Encoding chunk", 80)
        ]
        total_progress = sum(weight for _, weight in stages)
        
        # Initialize progress tracking
        progress = tqdm(
            total=total_progress,
            desc=f"Chunk {chunk_index + 1}/{total_chunks}: {stages[0][0]}",
            unit="%",
            position=chunk_index
        )
        
        # Create filter chain
        filter_chain = create_filter_chain(serial_name, duration)
        filter_complex = ';'.join(filter_chain)
        
        # Update progress
        progress.update(10)
        progress.set_description(f"Chunk {chunk_index + 1}/{total_chunks}: {stages[1][0]}")
        
        # Construct FFmpeg command with disc_path as input 0 and image_path as input 2
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', disc_path,  # Input 0: Rotating disc image (serial-specific from tn folder)
            '-i', audio_chunk,  # Input 1: Audio
            '-loop', '1',
            '-i', image_path,  # Input 2: Background image (Hotstar thumbnail)
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
            output_path
        ]
        
        # Update progress
        progress.update(10)
        progress.set_description(f"Chunk {chunk_index + 1}/{total_chunks}: {stages[2][0]}")
        
        # Run FFmpeg command with timeout and stall detection
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        start_time = time.time()
        timeout = duration * 2  # 2x the expected duration
        last_progress_time = time.time()
        
        while True:
            if process.poll() is not None:
                break
                
            if time.time() - start_time > timeout:
                logger.error(f"Chunk {chunk_index + 1} processing timed out")
                process.kill()
                return False
                
            if time.time() - last_progress_time > 30:
                logger.error(f"Chunk {chunk_index + 1} processing stalled")
                process.kill()
                return False
                
            line = process.stderr.readline()
            if not line:
                time.sleep(0.1)
                continue
                
            if "time=" in line:
                try:
                    time_str = line.split("time=")[1].split()[0]
                    current_time = sum(float(x) * 60 ** i for i, x in enumerate(reversed(time_str.split(":"))))
                    progress_percent = min(80, int((current_time / duration) * 80))
                    progress.update(progress_percent - progress.n + 20)
                    last_progress_time = time.time()
                    logger.debug(f"Chunk {chunk_index + 1} progress: {progress_percent}%")
                except:
                    pass
                    
        return_code = process.wait()
        
        if return_code != 0:
            stderr_output = process.stderr.read()
            logger.error(f"FFmpeg Error in chunk {chunk_index + 1} (return code {return_code}):\n{stderr_output}")
            return False
            
        progress.update(total_progress - progress.n)
        logger.info(f"Chunk {chunk_index + 1}/{total_chunks} processed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error processing chunk {chunk_index + 1}: {str(e)}")
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