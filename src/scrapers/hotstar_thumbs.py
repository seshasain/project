import os
import logging
from playwright.sync_api import sync_playwright
import time

# Map of serial names to their Hotstar URLs
SERIAL_URL_MAP = {
    'Brahmamudi': 'https://www.hotstar.com/in/shows/brahma-mudi/1260129377',
    'Karthika Deepam': 'https://www.hotstar.com/in/shows/karthika-deepam/15457',
    'Illu Illalu Pillalu': 'https://www.hotstar.com/in/shows/illu-illalu-pillalu/1271339098'
}

def get_serial_thumbnail(url: str) -> str:
    """Get the thumbnail URL for a serial by scraping the Hotstar show page."""
    if not url:
        logging.error("No URL provided for thumbnail extraction")
        return None
    
    try:
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            
            # Create new page
            page = context.new_page()
            
            # Go to URL
            page.goto(url, wait_until='networkidle')
            
            # Wait for content to load
            page.wait_for_timeout(5000)  # Wait 5 seconds for dynamic content
            
            # Save page content for debugging
            with open('page_source.html', 'w', encoding='utf-8') as f:
                f.write(page.content())
            
            # Try different selectors to find the thumbnail
            selectors = [
                'img._21vZ2G_wEIYD0ldl4ro03R',
                'img[class*="_21vZ2G_wEIYD0ldl4ro03R"]',
                'img[class*="w-full"]',
                'article img'
            ]
            
            for selector in selectors:
                try:
                    elements = page.query_selector_all(selector)
                    for element in elements:
                        src = element.get_attribute('src')
                        if src and ('hotstar.com/image/upload' in src or 'hotstar.com/content' in src):
                            logging.info(f"Successfully extracted thumbnail URL using selector {selector}: {src}")
                            return src
                except Exception as e:
                    logging.debug(f"Selector {selector} failed: {str(e)}")
                    continue
            
            logging.error("Could not find thumbnail image element on the page")
            return None
            
    except Exception as e:
        logging.error(f"Error extracting thumbnail: {str(e)}")
        return None

def get_episode_thumbnail(url: str, episode_title: str = None) -> str:
    """Get the thumbnail URL for a specific episode from Hotstar."""
    if not url:
        logging.error("No URL provided for thumbnail extraction")
        return None
    
    try:
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            
            # Create new page
            page = context.new_page()
            
            # Go to URL
            page.goto(url, wait_until='networkidle')
            
            # Wait for content to load
            page.wait_for_timeout(5000)  # Wait 5 seconds for dynamic content
            
            # Save page content for debugging
            with open('episode_page_source.html', 'w', encoding='utf-8') as f:
                f.write(page.content())
            
            # If episode title is provided, look for that specific episode
            if episode_title:
                try:
                    article = page.query_selector(f'article:has-text("{episode_title}")')
                    if article:
                        img = article.query_selector('img')
                        if img:
                            src = img.get_attribute('src')
                            if src and ('hotstar.com/image/upload' in src or 'hotstar.com/content' in src):
                                logging.info(f"Found thumbnail for episode '{episode_title}': {src}")
                                return src
                except Exception as e:
                    logging.debug(f"Could not find episode with title '{episode_title}': {str(e)}")
            
            # If no episode title provided or not found, get the latest episode thumbnail
            selectors = [
                'article img._21vZ2G_wEIYD0ldl4ro03R',
                'article img[class*="_21vZ2G_wEIYD0ldl4ro03R"]',
                'article img[class*="w-full"]',
                'article img'
            ]
            
            for selector in selectors:
                try:
                    elements = page.query_selector_all(selector)
                    for img in elements:
                        src = img.get_attribute('src')
                        if src and ('hotstar.com/image/upload' in src or 'hotstar.com/content' in src):
                            article = img.evaluate('node => node.closest("article")')
                            title = article.query_selector('h3')
                            title_text = title.text_content() if title else "Unknown Episode"
                            logging.info(f"Found thumbnail for episode '{title_text}': {src}")
                            return src
                except Exception as e:
                    logging.debug(f"Selector {selector} failed: {str(e)}")
                    continue
            
            logging.error("Could not find any episode thumbnail on the page")
            return None
            
    except Exception as e:
        logging.error(f"Error extracting episode thumbnail: {str(e)}")
        return None

def get_serial_episode_thumbnail(serial_name: str, episode_title: str = None) -> str:
    """Get the thumbnail URL for a specific serial's episode using the serial name."""
    if not serial_name:
        logging.error("No serial name provided")
        return None
    
    # Get URL for the serial
    url = SERIAL_URL_MAP.get(serial_name)
    if not url:
        logging.error(f"No URL mapping found for serial: {serial_name}")
        return None
    
    # Try to get episode thumbnail first
    thumbnail_url = get_episode_thumbnail(url, episode_title)
    if thumbnail_url:
        return thumbnail_url
    
    # If episode thumbnail not found, fall back to serial thumbnail
    return get_serial_thumbnail(url) 