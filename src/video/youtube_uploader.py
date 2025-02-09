"""
YouTube Uploader Module

This module provides functionality to upload videos to YouTube using the YouTube Data API v3.
It handles authentication, credential management, and video uploads with progress tracking.
"""

import os
import logging
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from tqdm import tqdm
import time
from datetime import datetime, timedelta
import requests
from ..scrapers.hotstar_thumbs import get_serial_episode_thumbnail

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class YouTubeUploader:
    """Class to handle YouTube video uploads."""
    
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    TOKEN_EXPIRY_BUFFER = 300  # 5 minutes buffer before token expiry
    
    def __init__(self, client_secrets_file='client_secrets.json', token_file='token.pickle'):
        """
        Initialize the YouTube uploader.
        
        Args:
            client_secrets_file: Path to the client secrets JSON file from Google Cloud Console
            token_file: Path to save/load authentication tokens
        """
        self.client_secrets_file = client_secrets_file
        self.token_file = token_file
        self.credentials = None
        self.youtube = None
        self._initialize_service()

    def _initialize_service(self):
        """Initialize and return YouTube API service with automatic token refresh."""
        try:
            self.credentials = self._get_credentials()
            self.youtube = build('youtube', 'v3', credentials=self.credentials)
        except Exception as e:
            logger.error(f"Error initializing YouTube service: {e}")
            raise

    def _get_credentials(self):
        """Get and refresh credentials as needed."""
        creds = None
        
        # Load existing credentials if available
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'rb') as token:
                    creds = pickle.load(token)
            except Exception as e:
                logger.warning(f"Error loading credentials from {self.token_file}: {e}")
                # If token file is corrupted, remove it
                os.remove(self.token_file)
        
        # Check if credentials need refresh
        if creds and self._should_refresh_token(creds):
            try:
                logger.info("Refreshing access token...")
                creds.refresh(Request())
                self._save_credentials(creds)
            except Exception as e:
                logger.warning(f"Error refreshing token: {e}")
                creds = None
        
        # If no valid credentials available, get new ones
        if not creds or not creds.valid:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file,
                    self.SCOPES
                )
                creds = flow.run_local_server(port=0)
                self._save_credentials(creds)
            except Exception as e:
                logger.error(f"Error getting new credentials: {e}")
                raise
        
        return creds

    def _should_refresh_token(self, creds):
        """Check if token should be refreshed."""
        if not creds.expiry:
            return False
            
        # Refresh if token will expire within buffer time
        return datetime.utcnow() + timedelta(seconds=self.TOKEN_EXPIRY_BUFFER) >= creds.expiry

    def _save_credentials(self, creds):
        """Save credentials to token file."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(self.token_file)), exist_ok=True)
            
            # Save credentials
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
            logger.info(f"Credentials saved to {self.token_file}")
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")

    def _ensure_valid_service(self):
        """Ensure YouTube service is valid and refresh if needed."""
        try:
            if self._should_refresh_token(self.credentials):
                logger.info("Refreshing YouTube service...")
                self._initialize_service()
        except Exception as e:
            logger.error(f"Error ensuring valid service: {e}")
            raise

    def _download_thumbnail(self, url: str) -> str:
        """Download thumbnail from URL and save temporarily."""
        try:
            response = requests.get(url)
            if response.status_code == 200:
                # Create temp directory if it doesn't exist
                os.makedirs('data/temp', exist_ok=True)
                thumbnail_path = f'data/temp/thumb_{int(time.time())}.jpg'
                
                with open(thumbnail_path, 'wb') as f:
                    f.write(response.content)
                return thumbnail_path
        except Exception as e:
            logger.error(f"Error downloading thumbnail: {e}")
        return None

    def upload_video(self, 
                    video_file: str, 
                    title: str, 
                    description: str,
                    tags: list = None,
                    privacy_status: str = 'private',
                    made_for_kids: bool = False,
                    serial_name: str = None,
                    episode_title: str = None) -> str:
        """
        Upload a video to YouTube with thumbnail in a single request.
        
        Args:
            video_file: Path to the video file
            title: Video title
            description: Video description
            tags: List of tags/keywords
            privacy_status: Video privacy status ('private', 'unlisted', or 'public')
            made_for_kids: Whether the video is made for kids
            serial_name: Name of the serial for thumbnail fetching
            episode_title: Title of the episode for thumbnail fetching
            
        Returns:
            str: YouTube video ID if successful, None otherwise
        """
        # Ensure service is valid before upload
        self._ensure_valid_service()
        
        if not os.path.exists(video_file):
            logger.error(f"Video file not found: {video_file}")
            return None
            
        try:
            # Default tags if none provided
            if tags is None:
                tags = ['Telugu Serial', 'Daily Update', 'Episode Review']
            
            # Get thumbnail if serial name is provided
            thumbnail_path = None
            if serial_name:
                logger.info(f"Fetching thumbnail for {serial_name}")
                thumbnail_url = get_serial_episode_thumbnail(serial_name, episode_title)
                if thumbnail_url:
                    logger.info(f"Found thumbnail URL: {thumbnail_url}")
                    thumbnail_path = self._download_thumbnail(thumbnail_url)
                    if not thumbnail_path:
                        logger.warning("Failed to download thumbnail")
                else:
                    logger.warning("No thumbnail URL found")
            
            # Prepare the video upload request
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags,
                    'categoryId': '24'  # Entertainment category
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'selfDeclaredMadeForKids': made_for_kids
                }
            }
            
            # Create MediaFileUpload objects
            video_media = MediaFileUpload(
                video_file,
                mimetype='video/mp4',
                resumable=True,
                chunksize=1024*1024  # 1MB chunks
            )
            
            # Create the upload request
            request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=video_media
            )
            
            # Upload the video with progress tracking and automatic retry
            response = None
            progress = tqdm(total=100, desc="Uploading to YouTube")
            retries = 3
            
            while response is None and retries > 0:
                try:
                    status, response = request.next_chunk()
                    if status:
                        progress.update(int(status.progress() * 100) - progress.n)
                except Exception as e:
                    retries -= 1
                    if retries == 0:
                        raise
                    logger.warning(f"Upload chunk failed, retrying... ({e})")
                    time.sleep(1)  # Wait before retry
                    self._ensure_valid_service()  # Refresh service if needed
            
            progress.close()
            
            if response:
                video_id = response['id']
                
                # Set thumbnail if available
                if thumbnail_path:
                    try:
                        thumbnail_media = MediaFileUpload(
                            thumbnail_path,
                            mimetype='image/jpeg',
                            resumable=False
                        )
                        
                        self.youtube.thumbnails().set(
                            videoId=video_id,
                            media_body=thumbnail_media
                        ).execute()
                        
                        logger.info("Successfully set custom thumbnail")
                    except Exception as e:
                        logger.warning(f"Failed to set thumbnail: {e}")
                    finally:
                        # Clean up thumbnail file
                        try:
                            os.remove(thumbnail_path)
                        except:
                            pass
                
                video_url = f"https://youtu.be/{video_id}"
                logger.info(f"Video uploaded successfully: {video_url}")
                return video_id
            else:
                logger.error("Upload failed - no response received")
                return None
            
        except Exception as e:
            logger.error(f"Error uploading to YouTube: {e}")
            if thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    os.remove(thumbnail_path)
                except:
                    pass
            return None

    def get_video_url(self, video_id: str) -> str:
        """Get the URL for a YouTube video."""
        return f"https://youtu.be/{video_id}" 