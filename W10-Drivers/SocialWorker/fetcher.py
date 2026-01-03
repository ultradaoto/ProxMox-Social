"""
Social Dashboard Queue Fetcher for Windows 10

Downloads pending posts from social.sterlingcooley.com and saves them
to C:\PostQueue\pending\ for the Ubuntu Poster to process.

SECURITY: This script can ONLY access social.sterlingcooley.com
          No other domains are permitted.
"""
import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from typing import Optional, List, Dict, Any

import requests
import schedule
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://social.sterlingcooley.com')
API_KEY = os.getenv('API_KEY', '')
QUEUE_DIR = Path(os.getenv('QUEUE_DIR', 'C:/PostQueue'))
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '5'))  # minutes

# =============================================================================
# SECURITY: DOMAIN ALLOWLIST - DO NOT MODIFY
# =============================================================================

ALLOWED_DOMAINS = frozenset([
    'social.sterlingcooley.com',
])

def is_allowed_url(url: str) -> bool:
    """Check if URL is in the allowed domain list."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        return domain in ALLOWED_DOMAINS
    except Exception:
        return False

def safe_request(method: str, url: str, **kwargs) -> requests.Response:
    """
    Make HTTP request ONLY if URL is in allowed domains.
    Raises SecurityError if domain is not allowed.
    """
    if not is_allowed_url(url):
        raise SecurityError(f"BLOCKED: Domain not in allowlist: {url}")
    
    return requests.request(method, url, **kwargs)

class SecurityError(Exception):
    """Raised when attempting to access a non-allowed domain."""
    pass

# =============================================================================
# LOGGING
# =============================================================================

LOG_DIR = Path('C:/SocialWorker/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'fetcher.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('fetcher')

# =============================================================================
# QUEUE FETCHER
# =============================================================================

class QueueFetcher:
    """
    Fetches pending posts from Social Dashboard API.
    Downloads media and creates job folders for the Poster.
    """
    
    def __init__(self):
        self.pending_dir = QUEUE_DIR / 'pending'
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        
        # Verify dashboard URL is allowed
        if not is_allowed_url(DASHBOARD_URL):
            raise SecurityError(f"Dashboard URL not in allowlist: {DASHBOARD_URL}")
        
        logger.info(f"Fetcher initialized")
        logger.info(f"  Dashboard: {DASHBOARD_URL}")
        logger.info(f"  Queue dir: {QUEUE_DIR}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json',
        }
    
    def fetch_pending_posts(self) -> List[Dict[str, Any]]:
        """
        Fetch list of pending posts from dashboard API.
        
        Returns:
            List of post dictionaries
        """
        url = f"{DASHBOARD_URL}/api/queue/gui/pending"
        
        try:
            response = safe_request('GET', url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            
            posts = response.json()
            logger.info(f"Fetched {len(posts)} pending post(s)")
            return posts
            
        except SecurityError:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch pending posts: {e}")
            return []
    
    def download_media(self, media_id: str, save_path: Path) -> bool:
        """
        Download a media file from the dashboard.
        
        Args:
            media_id: Media ID from the post
            save_path: Local path to save the file
            
        Returns:
            True if successful
        """
        url = f"{DASHBOARD_URL}/api/queue/gui/media/{media_id}"
        
        try:
            response = safe_request(
                'GET', url,
                headers=self._get_headers(),
                timeout=120,  # Longer timeout for large files
                stream=True
            )
            response.raise_for_status()
            
            # Write file in chunks
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"Downloaded media: {save_path.name} ({save_path.stat().st_size} bytes)")
            return True
            
        except SecurityError:
            raise
        except Exception as e:
            logger.error(f"Failed to download media {media_id}: {e}")
            return False
    
    def job_exists(self, post_id: str) -> bool:
        """Check if a job already exists for this post (in any state)."""
        for state_dir in ['pending', 'in_progress', 'completed', 'failed']:
            state_path = QUEUE_DIR / state_dir
            if state_path.exists():
                for job_dir in state_path.iterdir():
                    if job_dir.is_dir() and post_id in job_dir.name:
                        return True
        return False
    
    def create_job(self, post: Dict[str, Any]) -> bool:
        """
        Create a job folder for a pending post.
        
        Structure:
            C:\PostQueue\pending\job_{timestamp}_{id}\
                job.json       - All post metadata
                media_1.jpg    - Downloaded image
                media_2.mp4    - Downloaded video (if any)
        
        Args:
            post: Post dictionary from API
            
        Returns:
            True if job created successfully
        """
        post_id = post.get('id', 'unknown')
        
        # Check for duplicates
        if self.job_exists(post_id):
            logger.debug(f"Job already exists for post {post_id}, skipping")
            return False
        
        # Create job folder
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        job_id = f"job_{timestamp}_{post_id}"
        job_dir = self.pending_dir / job_id
        
        try:
            job_dir.mkdir(parents=True, exist_ok=True)
            
            # Download media files
            media_files = []
            for i, media in enumerate(post.get('media', [])):
                media_id = media.get('id')
                filename = media.get('filename', f'media_{i+1}')
                ext = Path(filename).suffix or '.jpg'
                local_name = f"media_{i+1}{ext}"
                local_path = job_dir / local_name
                
                if self.download_media(media_id, local_path):
                    media_files.append({
                        'type': media.get('type', 'image'),
                        'local_path': local_name,
                        'original_filename': filename,
                    })
                else:
                    # Failed to download - cleanup and abort
                    logger.error(f"Failed to download media for job {job_id}")
                    self._cleanup_job(job_dir)
                    return False
            
            # Write job.json
            job_data = {
                'id': post_id,
                'job_id': job_id,
                'platform': post.get('platform', ''),
                'scheduled_time': post.get('scheduled_time', ''),
                'caption': post.get('caption', ''),
                'media': media_files,
                'link': post.get('link'),
                'status': 'pending',
                'created_at': datetime.now().isoformat(),
                'fetched_from': DASHBOARD_URL,
            }
            
            job_file = job_dir / 'job.json'
            with open(job_file, 'w', encoding='utf-8') as f:
                json.dump(job_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Created job: {job_id} ({post.get('platform')})")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to create job for {post_id}: {e}")
            self._cleanup_job(job_dir)
            return False
    
    def _cleanup_job(self, job_dir: Path):
        """Remove a partially created job folder."""
        try:
            if job_dir.exists():
                import shutil
                shutil.rmtree(job_dir)
        except Exception as e:
            logger.error(f"Failed to cleanup job folder: {e}")
    
    def run_once(self) -> int:
        """
        Single fetch cycle.
        
        Returns:
            Number of jobs created
        """
        logger.info("Checking for pending posts...")
        
        posts = self.fetch_pending_posts()
        if not posts:
            logger.info("No pending posts")
            return 0
        
        created = 0
        for post in posts:
            if self.create_job(post):
                created += 1
        
        logger.info(f"Created {created} new job(s)")
        return created
    
    def run_forever(self):
        """Run fetch loop continuously."""
        logger.info(f"Starting fetcher loop (polling every {POLL_INTERVAL} minutes)")
        
        # Run immediately on start
        self.run_once()
        
        # Schedule regular runs
        schedule.every(POLL_INTERVAL).minutes.do(self.run_once)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)  # Check schedule every 30 seconds
        except KeyboardInterrupt:
            logger.info("Fetcher stopped by user")


# =============================================================================
# HEALTH CHECK
# =============================================================================

def health_check() -> bool:
    """
    Test connectivity to dashboard API.
    
    Returns:
        True if connection successful
    """
    url = f"{DASHBOARD_URL}/api/queue/gui/pending"
    
    try:
        response = safe_request(
            'GET', url,
            headers={'X-API-Key': API_KEY},
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"[OK] API connection successful")
            print(f"  URL: {DASHBOARD_URL}")
            print(f"  Status: {response.status_code}")
            return True
        elif response.status_code == 401:
            print(f"[FAIL] API key invalid or missing")
            return False
        else:
            print(f"[FAIL] Unexpected status: {response.status_code}")
            return False
            
    except SecurityError as e:
        print(f"[FAIL] Security error: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Connection failed: {e}")
        return False


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Social Dashboard Queue Fetcher',
        epilog='SECURITY: Only accesses social.sterlingcooley.com'
    )
    parser.add_argument('--once', action='store_true',
                        help='Fetch once and exit')
    parser.add_argument('--health', action='store_true',
                        help='Test API connectivity')
    args = parser.parse_args()
    
    if args.health:
        sys.exit(0 if health_check() else 1)
    
    # Verify API key is set
    if not API_KEY:
        logger.error("API_KEY not set in environment or .env file")
        sys.exit(1)
    
    fetcher = QueueFetcher()
    
    if args.once:
        count = fetcher.run_once()
        print(f"Fetched {count} job(s)")
    else:
        fetcher.run_forever()


if __name__ == '__main__':
    main()
