from google.cloud import texttospeech
import json
import os
import argparse
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/tts.log'),
        logging.StreamHandler()
    ]
)

# Set the environment variable for Google Cloud credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.join('config', 'credentials', 'socials-1731059809421-acd5f79c7acb.json')

def synthesize_text(text, client, voice, audio_config):
    """Convert text to speech using Google Cloud TTS"""
    try:
        synthesis_input = texttospeech.SynthesisInput(text=text)
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        return response.audio_content
    except Exception as e:
        logging.error(f"Error synthesizing text: {e}")
        return None

def batch_paragraphs(paragraphs, max_bytes=4800):  # Using 4800 to be safe
    """Split text into batches to comply with Google Cloud TTS limits"""
    batches = []
    current_batch = []
    current_size = 0
    
    for paragraph in paragraphs:
        paragraph_size = len(paragraph.encode('utf-8'))
        if current_size + paragraph_size + len('\n\n') > max_bytes:
            if current_batch:  # Save current batch if it exists
                batches.append('\n\n'.join(current_batch))
            current_batch = [paragraph]
            current_size = paragraph_size
        else:
            current_batch.append(paragraph)
            current_size += paragraph_size + len('\n\n')
    
    if current_batch:  # Don't forget the last batch
        batches.append('\n\n'.join(current_batch))
    
    return batches

def process_article(input_file, output_file):
    """Process a single article JSON file and convert to speech"""
    try:
        # Read the JSON file
        with open(input_file, 'r', encoding='utf-8') as file:
            data = json.load(file)

        # Get the first article's content
        if not data or len(data) == 0:
            logging.error("No articles found in the JSON file")
            return False

        article = data[0]
        article_content = article['content']
        
        # If content is already a list, use it directly
        if isinstance(article_content, list):
            content_parts = article_content
        else:
            # Try different separators if content is a string
            content_parts = []
            # First try splitting by '...'
            if '...' in article_content:
                content_parts = [p.strip() for p in article_content.split('...') if p.strip()]
            # If that didn't work, try splitting by newlines
            if not content_parts:
                content_parts = [p.strip() for p in article_content.split('\n') if p.strip()]
            # If still no parts, use the whole content as one part
            if not content_parts:
                content_parts = [article_content]

        # Initialize Text-to-Speech client
        client = texttospeech.TextToSpeechClient()

        # Build the voice request
        voice = texttospeech.VoiceSelectionParams(
            language_code="te-IN",  # Telugu (India)
            name="te-IN-Standard-B"  # Specific voice requested
        )

        # Select the type of audio file
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        # Process text in optimal batches
        batched_text = batch_paragraphs(content_parts)
        total_batches = len(batched_text)
        total_bytes = sum(len(text.encode('utf-8')) for text in batched_text)

        logging.info(f"Starting audio generation for {total_batches} batches (Total size: {total_bytes/1024:.2f}KB)")

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        processed_bytes = 0
        start_time = time.time()

        with open(output_file, "wb") as out:
            for i, text_batch in enumerate(batched_text, 1):
                batch_size = len(text_batch.encode('utf-8'))
                logging.info(f"Processing batch {i}/{total_batches} ({batch_size/1024:.2f}KB)")
                logging.info(f"Content preview: {text_batch[:100]}...")  # Log first 100 chars
                
                # Generate audio for each batch
                audio_content = synthesize_text(text_batch, client, voice, audio_config)
                if audio_content:
                    out.write(audio_content)
                    out.flush()  # Ensure content is written to disk
                    os.fsync(out.fileno())  # Force write to disk
                    
                    processed_bytes += batch_size
                    progress = (processed_bytes / total_bytes) * 100
                    elapsed_time = time.time() - start_time
                    speed = processed_bytes / elapsed_time if elapsed_time > 0 else 0
                    eta = (total_bytes - processed_bytes) / speed if speed > 0 else 0
                    
                    logging.info(f"Progress: {progress:.1f}% | Speed: {speed/1024:.1f}KB/s | ETA: {eta:.1f}s")
                    logging.info(f"Processed batch {i}/{total_batches} (Size: {batch_size/1024:.2f}KB)")
                else:
                    logging.error(f"Failed to process batch {i}/{total_batches}")
                    return False

        # Verify the file exists and has content
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            total_time = time.time() - start_time
            final_size = os.path.getsize(output_file)
            logging.info(f'Audio generation completed in {total_time:.1f}s')
            logging.info(f'Final audio file size: {final_size/1024:.2f}KB')
            logging.info(f'Average speed: {(total_bytes/total_time)/1024:.1f}KB/s')
            logging.info(f'Audio file has been generated as {output_file}')
            return True
        else:
            logging.error(f'Audio file generation failed or file is empty: {output_file}')
            return False

    except Exception as e:
        logging.error(f"Error processing article: {e}")
        return False

def process_articles_batch(input_file, output_file):
    """Process a batch of articles from a JSON file and convert to speech"""
    try:
        # Read the JSON file
        with open(input_file, 'r', encoding='utf-8') as file:
            articles = json.load(file)

        if not articles:
            logging.error("No articles found in the JSON file")
            return False

        # Initialize Text-to-Speech client
        client = texttospeech.TextToSpeechClient()

        # Build the voice request
        voice = texttospeech.VoiceSelectionParams(
            language_code="te-IN",  # Telugu (India)
            name="te-IN-Standard-B"  # Specific voice requested
        )

        # Select the type of audio file
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, "wb") as out:
            for article in articles:
                # Process each article's content
                content_parts = article['content']
                if isinstance(content_parts, str):
                    content_parts = content_parts.split('...')
                
                # Process text in optimal batches
                batched_text = batch_paragraphs(content_parts)

                for i, text_batch in enumerate(batched_text, 1):
                    # Generate audio for each batch
                    audio_content = synthesize_text(text_batch, client, voice, audio_config)
                    if audio_content:
                        out.write(audio_content)
                        logging.info(f"Processed batch {i} of {len(batched_text)} (size: {len(text_batch.encode('utf-8'))} bytes)")
                    else:
                        logging.error(f"Failed to process batch {i}")
                        continue

        logging.info(f'Audio file has been generated as {output_file}')
        return True

    except Exception as e:
        logging.error(f"Error processing articles batch: {e}")
        return False

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Convert article JSON to speech')
    parser.add_argument('--input', required=True, help='Input JSON file path')
    parser.add_argument('--output', required=True, help='Output MP3 file path')
    args = parser.parse_args()

    # Ensure input file exists
    if not os.path.exists(args.input):
        logging.error(f"Input file not found: {args.input}")
        return 1

    # Process the article
    output_path = os.path.join('data', 'audio', args.output)
    if process_article(args.input, output_path):
        return 0
    return 1

if __name__ == "__main__":
    # Ensure log directory exists
    os.makedirs('logs', exist_ok=True)
    exit(main()) 