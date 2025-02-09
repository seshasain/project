import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os
import re

class HTScraper:
    def __init__(self):
        self.base_url = "https://telugu.hindustantimes.com/topic/telugu-tv-serials/news"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'te-IN,te;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        self.config = self._load_config()
        
    def _load_config(self):
        """Load serial configuration from config file"""
        config_path = os.path.join('config', 'serials_config.json')
        with open(config_path, 'r') as f:
            return json.load(f)

    def fetch_article_content(self, article_url):
        """Fetch and extract content from an article page"""
        try:
            print(f"Fetching content from: {article_url}")
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
                print(f"Extracted {len(content)} unique content sections")
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
                print("No valid content found")
                return None
            
        except Exception as e:
            print(f"Error fetching article content: {e}")
            return None

    def fetch_articles(self, serial_config):
        try:
            response = requests.get(self.base_url, headers=self.headers)
            response.raise_for_status()
            print(f"Response status code: {response.status_code}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []
            
            # Find all article cards within the infinite scroll component
            article_cards = soup.select('div.infinite-scroll-component div.topicList')
            print(f"Found {len(article_cards)} article cards")
            
            for i, card in enumerate(article_cards, 1):
                print(f"\n--- Processing article card {i} ---")
                article_data = {}
                
                # Extract article ID from the div's id attribute
                article_id = card.get('id', '')
                if article_id:
                    print(f"Found article ID: {article_id}")
                    article_data['id'] = article_id
                else:
                    print("No article ID found")
                    continue
                
                # Extract title from h2.listingNewsCont div
                title_element = card.select_one('h2.listingNewsCont div')
                if title_element:
                    title = title_element.text.strip()
                    article_data['title'] = title
                    print("Found article title")
                    
                    # Skip if serial_config is provided and title doesn't match
                    if serial_config:
                        # Create a list of possible patterns to match
                        base_patterns = [
                            serial_config["url_pattern"].lower(),
                            serial_config["title_pattern"].lower(),
                            serial_config["url_pattern"].lower().replace('-', ' '),
                            serial_config["title_pattern"].lower().replace(' ', '-'),
                            serial_config["url_pattern"].lower().replace('-', ''),
                            serial_config["title_pattern"].lower().replace(' ', ''),
                            serial_config["url_pattern"].lower().split('-')[0],  # Match first word
                            serial_config["title_pattern"].lower().split(' ')[0]  # Match first word
                        ]
                        
                        # Add patterns with numbers
                        patterns = []
                        for pattern in base_patterns:
                            patterns.append(pattern)
                            patterns.append(pattern + ' 2')  # For serials with "2" after name
                            patterns.append(pattern + '2')   # For serials with "2" after name without space
                        
                        # Clean up the title for matching
                        clean_title = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
                        clean_title = re.sub(r'\s+', ' ', clean_title).strip()  # Normalize spaces
                        print(f"\nDebug - Original title: {title}")
                        print(f"Debug - Cleaned title: {clean_title}")
                        print(f"Debug - Patterns to match: {patterns}")
                        
                        # Check each pattern individually
                        matched_pattern = None
                        for pattern in patterns:
                            if pattern in clean_title:
                                matched_pattern = pattern
                                break
                        
                        if not matched_pattern:
                            print(f"Debug - No patterns matched the title")
                            continue
                        else:
                            print(f"Debug - Matched pattern: {matched_pattern}")
                            
                            # Check if title contains relevant keywords (case-insensitive)
                            keywords = ['episode', 'serial', 'today', 'latest', 'watch', 'update']
                            matched_keywords = [k for k in keywords if k in clean_title]
                            
                            if not matched_keywords:
                                print(f"Debug - No keywords found in title. Looking for: {keywords}")
                                continue
                            else:
                                print(f"Debug - Matched keywords: {matched_keywords}")
                            
                            # Extract date from relNewsTime element
                            date_element = card.select_one('p.relNewsTime')
                            if date_element:
                                date_text = date_element.text.strip()  # e.g. "Tuesday, February 4, 2025"
                                article_data['date'] = date_text
                                print("Extracted article date:", date_text)
                                
                                # Extract month and day for URL
                                date_match = re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d+)', date_text)
                                if date_match:
                                    month = date_match.group(0).split()[0]
                                    day = int(date_match.group(1))
                                    # Add appropriate suffix
                                    if 10 <= day <= 20:
                                        suffix = 'th'
                                    else:
                                        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
                                    date_str = f"{month}-{day}{suffix}".lower()
                                    
                                    # Create URL-friendly slug from title
                                    title_slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
                                    title_slug = re.sub(r'\s+', '-', title_slug.strip())
                                    
                                    # Construct the URL
                                    article_url = f"https://telugu.hindustantimes.com/entertainment/{serial_config['url_pattern']}-serial-today-episode-{date_str}-{title_slug}-star-maa-{serial_config['url_pattern']}-{article_id}.html"
                                    article_data['url'] = article_url
                                    print("Constructed article URL")
                                    
                                    # Fetch article content
                                    print(f"\nFetching content from article URL")
                                    content = self.fetch_article_content(article_url)
                                    if content:
                                        print("Successfully extracted content")
                                        article_data['content'] = content
                                        articles.append(article_data)  # Add the article to the list
                                        print("Added article to list")
                                    else:
                                        print("Failed to extract content")
                                else:
                                    print("Could not extract date from relNewsTime")
                            else:
                                print("No date element found")
                    
                else:
                    print("No title element found")
                    continue
                
                # Extract image details
                img_element = card.select_one('img[title]')
                if img_element:
                    article_data['image_title'] = img_element.get('title', '').strip()
                    # First try srcset
                    srcset = img_element.get('srcset', '')
                    if srcset:
                        # Get the highest resolution image URL
                        image_urls = []
                        for url_part in srcset.split(','):
                            parts = url_part.strip().split(' ')
                            if len(parts) >= 2:
                                url, size = parts[0], parts[1]
                                image_urls.append((url, size))
                        if image_urls:
                            image_url = image_urls[-1][0]  # Get the last (highest resolution) URL
                            if image_url.startswith('/_next'):
                                image_url = 'https://telugu.hindustantimes.com' + image_url
                            article_data['image_url'] = image_url
                            print("Extracted image URL from srcset")
                    # Fallback to src attribute
                    if 'image_url' not in article_data:
                        src = img_element.get('src', '')
                        if src:
                            if src.startswith('/_next'):
                                src = 'https://telugu.hindustantimes.com' + src
                            article_data['image_url'] = src
                            print("Extracted image URL from src")
                
                if article_data and article_data.get('title'):
                    # Extract date from title with more flexible pattern
                    date_match = re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+(?:st|nd|rd|th)?', article_data['title'], re.IGNORECASE)
                    if date_match:
                        date_str = date_match.group(0).lower()
                        # Add suffix if missing
                        if not any(suffix in date_str for suffix in ['st', 'nd', 'rd', 'th']):
                            day = int(re.search(r'\d+', date_str).group())
                            if 10 <= day <= 20:
                                suffix = 'th'
                            else:
                                suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
                            date_str = re.sub(r'(\d+)', r'\1' + suffix, date_str)
                        # Create URL-friendly slug
                        date_str = date_str.replace(' ', '-')
                        article_data['date_str'] = date_str
                        articles.append(article_data)
                        print("Added article to list")
                    else:
                        print("Could not extract date from title")
                else:
                    print("Article data incomplete - skipping")
            
            return articles
        
        except requests.RequestException as e:
            print(f"Error fetching articles: {e}")
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
        
        print(f"Saved {len(articles)} articles to {filepath}")
        return filepath

def get_patterns_for_serial(serial_name):
    # Convert serial name to lowercase and replace spaces with hyphens for base pattern
    base_pattern = serial_name.lower()
    base_pattern_hyphenated = base_pattern.replace(" ", "-")
    base_pattern_no_spaces = base_pattern.replace(" ", "")

    # Create variations of the pattern
    patterns = []
    
    # Add base patterns
    patterns.extend([
        base_pattern,  # e.g. "karthika deepam"
        base_pattern_hyphenated,  # e.g. "karthika-deepam"
        base_pattern_no_spaces,  # e.g. "karthikadeepam"
    ])
    
    # Add patterns with "2" variations
    patterns.extend([
        f"{pattern} 2" for pattern in patterns  # With space
    ])
    patterns.extend([
        f"{pattern}2" for pattern in patterns[:3]  # Without space
    ])
    
    # Add shorter patterns for some serials
    if "karthika deepam" in base_pattern:
        patterns.extend(["karthika", "karthika 2", "karthika2"])
    elif "illu illalu pillalu" in base_pattern:
        patterns.extend(["illu", "illu 2", "illu2"])
    
    return list(set(patterns))  # Remove any duplicates

def process_serial(serial_name, url_pattern, title_pattern, output_dir, hotstar_url=None):
    print(f"Processing {serial_name}...")
    
    # Get patterns for this serial
    patterns = get_patterns_for_serial(serial_name)
    
    response = requests.get(url_pattern)
    if response.status_code != 200:
        print(f"Failed to fetch articles for {serial_name}")
        return None

    print(f"Response status code: {response.status_code}")
    
    soup = BeautifulSoup(response.content, 'html.parser')
    article_cards = soup.find_all('div', class_='article-card')
    
    print(f"Found {len(article_cards)} article cards\n")
    
    articles = []
    for i, card in enumerate(article_cards, 1):
        print(f"--- Processing article card {i} ---")
        
        # Extract article ID
        article_id = None
        article_link = card.find('a', href=True)
        if article_link:
            article_id = extract_article_id(article_link['href'])
            print(f"Found article ID: {article_id}")

        # Extract title
        title_element = card.find('h2')
        if not title_element:
            print("No title found")
            continue
            
        original_title = title_element.text.strip()
        print(f"\nDebug - Original title: {original_title}")
        
        # Clean the title
        cleaned_title = clean_title(original_title).lower()
        print(f"Debug - Cleaned title: {cleaned_title}")
        
        # Debug print patterns
        print(f"Debug - Patterns to match: {patterns}")
        
        # Check if title matches any pattern
        matched_pattern = None
        for pattern in patterns:
            if pattern in cleaned_title:
                matched_pattern = pattern
                print(f"Debug - Matched pattern: {pattern}")
                break
                
        if not matched_pattern:
            print("Debug - No patterns matched the title\n")
            continue
            
        # Check for keywords
        keywords = ['episode', 'serial', 'today', 'latest', 'watch', 'update']
        matched_keywords = [keyword for keyword in keywords if keyword in cleaned_title]
        
        if matched_keywords:
            print(f"Debug - Matched keywords: {matched_keywords}")
        else:
            print("Debug - No keywords found in title. Looking for: {keywords}\n")
            continue

        # Extract date from relNewsTime
        date_element = card.find('p', class_='relNewsTime')
        if date_element:
            article_date = date_element.text.strip()
            print(f"Extracted article date: {article_date}")
        else:
            print("Could not find date element")
            continue

        # Construct article URL
        article_url = None
        if article_id:
            article_url = construct_article_url(title_pattern, article_id)
            print("Constructed article URL\n")

        if not article_url:
            print("Could not construct article URL")
            continue

        # Extract content
        print(f"Fetching content from article URL")
        print(f"Fetching content from: {article_url}")
        
        article_content = extract_article_content(article_url)
        if not article_content:
            print("Could not extract content")
            continue
            
        print(f"Extracted {len(article_content)} unique content sections")
        print("Successfully extracted content")

        # Create article data
        article_data = {
            'id': article_id,
            'title': original_title,
            'date': article_date,
            'url': article_url,
            'content': article_content
        }
        
        # Add article to list
        articles.append(article_data)
        print("Added article to list")

        # Extract image URL
        image_element = card.find('img')
        if image_element and 'src' in image_element.attrs:
            print("Extracted image URL from src")
            article_data['image_url'] = image_element['src']
            articles.append(article_data)
            print("Added article to list")
        else:
            print("Could not extract image URL")

    # Save articles to JSON file
    if articles:
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{serial_name.lower().replace(' ', '-')}_{current_time}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
            
        print(f"Saved {len(articles)} articles to {filepath}")
        return filepath 