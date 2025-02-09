import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os
import re

# Add serial configurations
SERIALS = {
    '1': {
        'name': 'Gunde Ninda Gudi Gantalu',
        'url_pattern': 'gunde-ninda-gudi-gantalu',
        'title_pattern': 'Gunde Ninda Gudi Gantalu'
    },
    '2': {
        'name': 'Brahmamudi',
        'url_pattern': 'brahmamudi',
        'title_pattern': 'Brahmamudi'
    },
    '3': {
        'name': 'Karthika Deepam',
        'url_pattern': 'karthika-deepam',
        'title_pattern': 'Karthika Deepam'
    },
    '4': {
        'name': 'Illu Illalu Pillalu',
        'url_pattern': 'illu-illalu-pillalu',
        'title_pattern': 'Illu Illalu Pillalu'
    }
}

def select_serial():
    """Let user select which serial to fetch"""
    print("\nAvailable Serials:")
    for key, serial in SERIALS.items():
        print(f"{key}. {serial['name']}")
    
    while True:
        choice = input("\nEnter the number of the serial you want to fetch (or 'q' to quit): ")
        if choice.lower() == 'q':
            return None
        if choice in SERIALS:
            return SERIALS[choice]
        print("Invalid choice. Please try again.")

class HTScraper:
    def __init__(self):
        self.base_url = "https://telugu.hindustantimes.com/topic/telugu-tv-serials/news"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'te-IN,te;q=0.9,en-US;q=0.8,en;q=0.7'
        }

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

    def fetch_articles(self, serial_config=None):
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
                        if not (serial_config["url_pattern"].lower() in title.lower() or 
                               serial_config["title_pattern"].lower() in title.lower()):
                            print(f"Skipping - title doesn't match serial pattern: {serial_config['url_pattern']}")
                            continue
                        else:
                            print("Title matches serial pattern!")
                            
                            # Check if title contains "Episode" (case-insensitive)
                            if not re.search(r'episode', title, re.IGNORECASE):
                                print("Skipping - title doesn't contain 'Episode'")
                                continue
                            
                            # Extract date from title (e.g., "February 3rd")
                            date_match = re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+(?:st|nd|rd|th)', title)
                            if date_match:
                                date_str = date_match.group(0).lower().replace(' ', '-')
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
                                else:
                                    print("Failed to extract content")
                            else:
                                print("Could not extract date from title")
                                continue
                    
                else:
                    print("No title element found")
                    continue
                
                # Extract date from p.relNewsTime
                date_element = card.select_one('p.relNewsTime')
                if date_element:
                    article_data['date'] = date_element.text.strip()
                    print("Extracted article date")
                
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
                            print("Extracted image URL")
                
                if article_data and article_data.get('title'):
                    articles.append(article_data)
                    print("Added article to list")
                else:
                    print("Article data incomplete - skipping")
            
            return articles
        
        except requests.RequestException as e:
            print(f"Error fetching articles: {e}")
            return []

    def save_articles(self, articles, serial_config=None, filename=None):
        if not filename:
            date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            prefix = serial_config['url_pattern'] if serial_config else 'ht_serials'
            filename = f'{prefix}_{date_str}.json'
        
        output_dir = 'data'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        
        print(f"Saved {len(articles)} articles to {filepath}")
        return filepath

class HTSerialsScraper:
    def __init__(self):
        self.url = "https://telugu.hindustantimes.com/topic/serials-review"
        self.output_dir = "images"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'te-IN,te;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def extract_serial_info(self, article_div):
        """Extract information from a single serial article div"""
        try:
            # Get the article content div
            content_div = article_div.find('div', class_='topic_topicCardContent__gSEhO')
            if not content_div:
                return None
                
            # Get the title/content
            title = content_div.get_text(strip=True)
            
            # Get the date
            date_p = article_div.find('p', class_='relNewsTime')
            date = date_p.get_text(strip=True) if date_p else None
            
            # Get the image
            img_span = article_div.find('span', style=lambda x: x and 'box-sizing:border-box;display:inline-block' in x)
            if img_span:
                img = img_span.find('img')
                if img:
                    img_url = None
                    # Extract the actual image URL from srcset
                    srcset = img.get('srcset', '')
                    if srcset:
                        # Get the highest resolution URL
                        urls = srcset.split(',')
                        if urls:
                            last_url = urls[-1].strip().split(' ')[0]
                            img_url = 'https://telugu.hindustantimes.com' + last_url
                    
                    # If no srcset, try src
                    if not img_url:
                        src = img.get('src', '')
                        if src:
                            img_url = 'https://telugu.hindustantimes.com' + src
                    
                    return {
                        'title': title,
                        'date': date,
                        'image_url': img_url
                    }
            
            return None
            
        except Exception as e:
            print(f"Error extracting serial info: {str(e)}")
            return None
    
    def download_image(self, img_url, title):
        """Download an image and save it with a sanitized filename"""
        try:
            if not img_url:
                return None
                
            # Create sanitized filename from title
            filename = re.sub(r'[^\w\s-]', '', title)
            filename = re.sub(r'[-\s]+', '_', filename)
            filename = f"{filename}.jpg"
            filepath = os.path.join(self.output_dir, filename)
            
            # Download the image
            response = requests.get(img_url, headers=self.headers)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"Downloaded: {filepath}")
                return filepath
            else:
                print(f"Failed to download image: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error downloading image: {str(e)}")
            return None
    
    def scrape_serials(self):
        try:
            print("Fetching HT Telugu serials page...")
            response = requests.get(self.url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all serial article cards
            article_cards = soup.find_all('div', class_='topic_topicCard__hznQ7')
            
            results = []
            for card in article_cards:
                serial_info = self.extract_serial_info(card)
                if serial_info:
                    # Download the image
                    image_path = self.download_image(serial_info['image_url'], serial_info['title'])
                    serial_info['local_image_path'] = image_path
                    results.append(serial_info)
            
            # Save results to JSON
            with open('serials_data.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            print(f"\nProcessed {len(results)} serials")
            return results
            
        except Exception as e:
            print(f"Error scraping serials: {str(e)}")
            return []

def main():
    # Let user select which serial to fetch
    serial_config = select_serial()
    if not serial_config:
        print("Exiting...")
        return

    scraper = HTScraper()
    print(f"\nFetching articles for {serial_config['name']}...")
    articles = scraper.fetch_articles(serial_config)
    
    if articles:
        # Get today's date components for comparison
        today = datetime.now()
        today_month = today.strftime('%B')  # Full month name
        today_day = today.day
        today_suffix = 'th' if 11 <= today_day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(today_day % 10, 'th')
        today_format = f"{today_month} {today_day}{today_suffix}"
        print(f"\nFiltering articles for today's date format: {today_format}")
        
        # Filter articles that have today's date in title
        today_articles = []
        for article in articles:
            title = article.get('title', '')
            
            # Look for date pattern like "February 3rd Episode" in title
            date_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d+)(st|nd|rd|th)\s+Episode', title, re.IGNORECASE)
            if date_match:
                month, day, suffix = date_match.groups()
                article_date = f"{month} {day}{suffix}"
                if article_date.lower() == today_format.lower():
                    today_articles.append(article)
                    print(f"Found matching article with date: {article_date}")
        
        if today_articles:
            print(f"\nFound {len(today_articles)} articles for today")
            filepath = scraper.save_articles(today_articles, serial_config)
            print(f"\nSummary:")
            print(f"Total articles saved: {len(today_articles)}")
            print(f"Data saved to: {filepath}")
        else:
            print("\nNo articles found for today's date.")
    else:
        print("No matching articles were found or there was an error fetching the articles.")

if __name__ == "__main__":
    main() 