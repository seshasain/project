import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os
import re
import logging

class HTScraper:
    def __init__(self):
        self.base_url = "https://telugu.hindustantimes.com/topic/telugu-tv-serials/news"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'te-IN,te;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        self.config = self._load_config()
        self.logger = logging.getLogger(__name__)
        
    def _load_config(self):
        """Load serial configuration from config file"""
        config_path = os.path.join('config', 'serials_config.json')
        with open(config_path, 'r') as f:
            return json.load(f)

    def fetch_article_content(self, article_url):
        """Fetch and extract content from an article page"""
        try:
            self.logger.info(f"Fetching content from: {article_url}")
            response = requests.get(article_url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Initialize content list and seen text set for deduplication
            content = []
            seen_text = set()
            is_first = True  # Flag to track first content section
            
            # Helper function to clean and deduplicate text
            def process_text(text, is_first_section):
                # Remove prefix up until colon only for the first section
                if is_first_section and ':' in text:
                    text = text.split(':', 1)[1]
                
                text = re.sub(r'\s+', ' ', text.strip())
                text = text.replace('\n', ' ').replace('\t', ' ')
                
                # Only return text if it's long enough and not seen before
                return text if len(text) > 20 and text not in seen_text else None
            
            # Extract main content
            article_body = soup.select_one('div.detail-content, div.storyDetail, div.newsContent, div.storyBody')
            if article_body:
                # Remove unwanted elements
                for unwanted in article_body.select('script, style, iframe, .advertisement, .social-share, .story-share, .whats_app_banner, h2.story-summary, div.storyIntro, div.storyHighlights'):
                    unwanted.decompose()
                
                # First try specific content containers
                content_sections = article_body.select('div.description, div.content-text, div.story-description, div[itemprop="articleBody"]')
                
                if content_sections:
                    for section in content_sections:
                        # Process each paragraph within the section
                        for p in section.find_all(['p', 'div'], recursive=False):
                            text = process_text(p.get_text(), is_first)
                            if text:
                                content.append(text)
                                seen_text.add(text)
                                is_first = False  # Set to False after first valid content
                else:
                    # Fallback to direct paragraph extraction
                    paragraphs = article_body.find_all('p', class_=lambda x: x is None or not any(c in str(x).lower() for c in ['ad', 'share', 'social', 'banner']))
                    
                    for p in paragraphs:
                        text = process_text(p.get_text(), is_first)
                        if text:
                            content.append(text)
                            seen_text.add(text)
                            is_first = False  # Set to False after first valid content
            
            if content:
                self.logger.info(f"Extracted {len(content)} unique content sections")
                # Join content with "..." and ensure proper spacing
                final_content = ' ... '.join(content)
                # Clean up any multiple spaces or dots
                final_content = re.sub(r'\s+\.{3}\s+', ' ... ', final_content)
                final_content = re.sub(r'\.{3,}', '...', final_content)

                # Add intro message
                intro_msg = "హాయ్ ఫ్రెండ్స్, ఎలా ఉన్నారు?, వెల్కమ్ టూ రాఘవ రాం రివ్యూస్ ఛానల్... "
                final_content = intro_msg + final_content

                # Add mid message after a period in the middle
                mid_msg = " వీడియో కొనసాగించే ముందు, మీరు గనుక ఇంకా, రాఘవ రాం రివ్యూస్ ఛానల్ కి సబ్స్క్రయిబ్ చేసుకోపోతే, ఇలాంటి అమేజింగ్ రివ్యూస్ కోసం, ఇప్పుడే మన ఛానల్ కి సబ్స్క్రయిబ్ చేసుకోండి...ఇక రివ్యూ కొనసాగిద్దాం... "
                # Find the middle period
                periods = [m.start() for m in re.finditer(r'\.', final_content)]
                if periods:
                    mid_point = periods[len(periods)//2]
                    final_content = final_content[:mid_point+1] + mid_msg + final_content[mid_point+1:]

                # Add outro message
                outro_msg = " ఇది ఫ్రెండ్స్, ఈరోజు జరిగిన ఎపిసోడ్...ఈరోజు రివ్యూ మీకు ఎలా అనిపించింది? రివ్యూ నచ్చితే ఒక లైక్ చేయండి...ఇంకా ఈరోజు జరిగిన ఎపిసోడ్ పై మీ ఒపీనియన్ ని కామెంట్ చేయండి...ఇలానే రోజు ఎపిసోడ్స్ చూడటానికి వెంటనే ఈ ఛానల్ కి సబ్స్క్రయిబ్ చేయండి.మళ్ళి తరువాతి ఎపిసోడ్ లో కలుదాం!"
                final_content = final_content + outro_msg

                return final_content
            else:
                self.logger.warning("No valid content found")
                return None
            
        except Exception as e:
            self.logger.error(f"Error fetching article content: {e}")
            return None

    def fetch_articles(self, serial_config):
        try:
            response = requests.get(self.base_url, headers=self.headers)
            response.raise_for_status()
            self.logger.info(f"Response status code: {response.status_code}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []
            
            # Find all article cards within the infinite scroll component
            article_cards = soup.select('div.infinite-scroll-component div.topicList')
            self.logger.info(f"Found {len(article_cards)} article cards")
            
            for i, card in enumerate(article_cards, 1):
                self.logger.debug(f"\n--- Processing article card {i} ---")
                article_data = {}
                
                # Extract article ID from the div's id attribute
                article_id = card.get('id', '')
                if article_id:
                    self.logger.debug(f"Found article ID: {article_id}")
                    article_data['id'] = article_id
                else:
                    self.logger.debug("No article ID found")
                    continue
                
                # Extract title from h2.listingNewsCont div
                title_element = card.select_one('h2.listingNewsCont div')
                if title_element:
                    title = title_element.text.strip()
                    article_data['title'] = title
                    self.logger.info("Found article title")
                    
                    # Skip if serial_config is provided and title doesn't match
                    if serial_config:
                        if not (serial_config["url_pattern"].lower() in title.lower() or 
                               serial_config["title_pattern"].lower() in title.lower()):
                            self.logger.info(f"Skipping - title doesn't match serial pattern: {serial_config['url_pattern']}")
                            continue
                        else:
                            self.logger.info("Title matches serial pattern!")
                            
                            # Check if title contains "Episode" or "Serial"
                            if not re.search(r'episode|serial', title, re.IGNORECASE):
                                self.logger.info("Skipping - title doesn't contain 'Episode' or 'Serial'")
                                continue
                            
                            # Extract date from relNewsTime paragraph
                            date_element = card.select_one('p.relNewsTime')
                            if date_element:
                                published_date = date_element.text.strip()
                                try:
                                    # Parse the date to validate format
                                    article_date = datetime.strptime(published_date, '%A, %B %d, %Y')
                                    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                                    
                                    # Compare dates
                                    if article_date.date() == today.date():
                                        article_data['date'] = published_date  # Store the date in article_data
                                        self.logger.info(f"Extracted article date: {published_date}")
                                        
                                        # Create URL-friendly slug from title
                                        title_slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
                                        title_slug = re.sub(r'\s+', '-', title_slug.strip())
                                        
                                        # Extract month and day for URL
                                        month = article_date.strftime('%B').lower()
                                        day = article_date.day
                                        
                                        # Add appropriate suffix
                                        if 10 <= day <= 20:
                                            suffix = 'th'
                                        else:
                                            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
                                        
                                        date_url = f"{month}-{day}{suffix}"
                                        
                                        article_url = f"https://telugu.hindustantimes.com/entertainment/{serial_config['url_pattern']}-serial-today-episode-{date_url}-{title_slug}-star-maa-{serial_config['url_pattern']}-{article_id}.html"
                                        article_data['url'] = article_url
                                        self.logger.info("Constructed article URL")
                                        
                                        # Fetch article content
                                        self.logger.info(f"\nFetching content from article URL")
                                        content = self.fetch_article_content(article_url)
                                        if content:
                                            self.logger.info("Successfully extracted content")
                                            article_data['content'] = content
                                        else:
                                            self.logger.warning("Failed to extract content")
                                            continue
                                    else:
                                        self.logger.info(f"Article date {article_date.date()} doesn't match today's date {today.date()}")
                                        continue
                                except ValueError as e:
                                    self.logger.error(f"Error parsing date: {e}")
                                    continue
                            else:
                                self.logger.info("No date element found")
                                continue
                    
                else:
                    self.logger.info("No title element found")
                    continue
                
                # Extract image details
                img_element = card.select_one('img[title]')
                if img_element:
                    article_data['image_title'] = img_element.get('title', '').strip()
                    srcset = img_element.get('srcset', '')
                    if srcset:
                        # Get the 2x resolution image URL
                        image_urls = dict(url.strip().split(' ') for url in srcset.split(','))
                        if '2x' in image_urls:
                            image_url = image_urls['2x']
                            if image_url.startswith('/_next'):
                                image_url = 'https://telugu.hindustantimes.com' + image_url
                            article_data['image_url'] = image_url
                            self.logger.info("Extracted image URL")
                
                if article_data and article_data.get('title'):
                    articles.append(article_data)
                    self.logger.info("Added article to list")
                else:
                    self.logger.warning("Article data incomplete - skipping")
            
            return articles
        
        except requests.RequestException as e:
            self.logger.error(f"Error fetching articles: {e}")
            return []

    def save_articles(self, articles, serial_config):
        """Save articles to JSON file"""
        date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{serial_config['url_pattern']}_{date_str}.json"
        
        output_dir = os.path.join('data', 'json')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Saved {len(articles)} articles to {filepath}")
        return filepath 