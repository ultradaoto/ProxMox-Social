"""
Social Dashboard Queue Fetcher for Windows 10

Downloads pending posts from social.sterlingcooley.com and saves them
to C:\PostQueue\pending\ for the Ubuntu Poster to process.

Also monitors C:\PostQueue\completed and C:\PostQueue\failed to sync
status back to the API.

SECURITY: This script can ONLY access social.sterlingcooley.com
          No other domains are permitted.
"""
import os
import sys
import json
import time
import shutil
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

def safe_request(method: str, url: str, headers=None, json=None, timeout=30, **kwargs) -> requests.Response:
    """
    Make HTTP request ONLY if URL is in allowed domains.
    Raises SecurityError if domain is not allowed.
    """
    if not is_allowed_url(url):
        raise SecurityError(f"BLOCKED: Domain not in allowlist: {url}")
    
    return requests.request(method, url, headers=headers, json=json, timeout=timeout, **kwargs)

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
    Syncs completed/failed jobs back to API.
    """
    
    def __init__(self):
        self.pending_dir = QUEUE_DIR / 'pending'
        self.completed_dir = QUEUE_DIR / 'completed'
        self.failed_dir = QUEUE_DIR / 'failed'
        self.archived_dir = QUEUE_DIR / 'archived'
        
        for d in [self.pending_dir, self.completed_dir, self.failed_dir, self.archived_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
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
    
    # -------------------------------------------------------------------------
    # FETCHING LOGIC
    # -------------------------------------------------------------------------

    def fetch_pending_posts(self) -> List[Dict[str, Any]]:
        """Fetch list of pending posts from dashboard API."""
        url = f"{DASHBOARD_URL}/api/queue/gui/pending"
        
        try:
            response = safe_request('GET', url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            posts = response.json()
            
            # DIAGNOSTIC LOGGING
            for post in posts:
                logger.info(f"[FETCHER] API returned post:")
                logger.info(f"[FETCHER]   id = {post.get('id')}")
                logger.info(f"[FETCHER]   All keys = {list(post.keys())}")
                # Log full post but truncate media/body if too long to keep logs cleaner
                safe_post = post.copy()
                if 'media' in safe_post: safe_post['media'] = f"[{len(safe_post['media'])} items...]"
                logger.info(f"[FETCHER]   Full post (summary) = {json.dumps(safe_post)}")
                
            return posts
        except SecurityError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch pending posts: {e}")
            return []
    
    def download_media(self, media_id: str, save_path: Path) -> bool:
        """Download a media file from the dashboard."""
        url = f"{DASHBOARD_URL}/api/queue/gui/media/{media_id}"
        
        try:
            response = safe_request(
                'GET', url, headers=self._get_headers(),
                timeout=120, stream=True
            )
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"Failed to download media {media_id}: {e}")
            return False
    
    def job_exists(self, post_id: str) -> bool:
        """Check if a job already exists for this post (in any state)."""
        # Check active folders
        for state_dir in [self.pending_dir, self.completed_dir, self.failed_dir]:
            if state_dir.exists():
                for job_dir in state_dir.iterdir():
                    if job_dir.is_dir() and post_id in job_dir.name:
                        return True
        # Check archive (optional, but good to prevent reprocessing old jobs)
        if self.archived_dir.exists():
             for sub in ['completed', 'failed']:
                 sub_dir = self.archived_dir / sub
                 if sub_dir.exists():
                    for job_dir in sub_dir.iterdir():
                        if job_dir.is_dir() and post_id in job_dir.name:
                            return True
        return False
    
    def create_job(self, post: Dict[str, Any]) -> bool:
        """Create a job folder for a pending post."""
        post_id = post.get('id', 'unknown')
        
        if self.job_exists(post_id):
            return False
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        job_id = f"job_{timestamp}_{post_id}"
        job_dir = self.pending_dir / job_id
        
        try:
            job_dir.mkdir(parents=True, exist_ok=True)
            
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
                    logger.error(f"Failed to download media for job {job_id}")
                    shutil.rmtree(job_dir)
                    return False
            
            # Start with full API data to preserve all fields
            job_data = post.copy()
            
            # Update with local processing details
            job_data.update({
                'job_id': job_id,
                'media': media_files, # Overwrite media with local paths
                'status': 'pending',
                'created_at': datetime.now().isoformat(),
                'fetched_from': DASHBOARD_URL,
            })
            
            with open(job_dir / 'job.json', 'w', encoding='utf-8') as f:
                json.dump(job_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Created job: {job_id} ({post.get('platform')})")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to create job for {post_id}: {e}")
            if job_dir.exists():
                shutil.rmtree(job_dir)
            return False

    # -------------------------------------------------------------------------
    # SYNCING LOGIC
    # -------------------------------------------------------------------------

    def sync_completed_jobs(self):
        """Process jobs in the completed directory."""
        if not self.completed_dir.exists():
            return

        for job_dir in self.completed_dir.iterdir():
            if not job_dir.is_dir():
                continue
            
            try:
                # Read ID
                job_json = job_dir / 'job.json'
                if not job_json.exists():
                    logger.warning(f"No job.json found in {job_dir}")
                    continue
                    
                with open(job_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                post_id = data.get('id')
                if not post_id:
                    continue

                # Notify API
                logger.info(f"Syncing completion for job {job_dir.name}...")
                url = f"{DASHBOARD_URL}/api/queue/gui/complete"
                payload = {
                    'id': post_id,
                    'status': 'success',
                    'completed_at': datetime.now().isoformat()
                }
                
                response = safe_request('POST', url, headers=self._get_headers(), json=payload, timeout=30)
                
                if response.ok:
                    self._archive_job(job_dir, 'completed')
                    logger.info(f"[SYNC] Successfully synced job {post_id} as complete")
                elif response.status_code == 404:
                    self._archive_job(job_dir, 'completed')
                    logger.warning(f"[SYNC] Job {post_id} not found on server (404). Archiving local copy to stop retries.")
                else:
                    logger.error(f"[SYNC] Failed to sync completion for {post_id}: {response.status_code} - {response.text}")

            except Exception as e:
                logger.error(f"Error processing completed job {job_dir.name}: {e}")

    def sync_failed_jobs(self):
        """Process jobs in the failed directory."""
        if not self.failed_dir.exists():
            return

        for job_dir in self.failed_dir.iterdir():
            if not job_dir.is_dir():
                continue
            
            try:
                # Read ID
                job_json = job_dir / 'job.json'
                if not job_json.exists():
                    continue
                    
                with open(job_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                post_id = data.get('id')
                
                # DIAGNOSTIC LOGGING
                logger.info(f"[SYNC] Processing Job folder: {job_dir.name}")
                logger.info(f"[SYNC] job.json 'id' field: {post_id}")
                
                # Read Reason
                reason = "Unknown failure"
                reason_file = job_dir / 'failure_reason.txt'
                if reason_file.exists():
                    with open(reason_file, 'r', encoding='utf-8') as f:
                        reason = f.read().strip()

                # Notify API
                logger.info(f"Syncing failure for job {job_dir.name}...")
                url = f"{DASHBOARD_URL}/api/queue/gui/failed"
                payload = {
                    'id': post_id,
                    'status': 'failed',
                    'error': reason,
                    'failed_at': datetime.now().isoformat()
                }
                
                response = safe_request('POST', url, headers=self._get_headers(), json=payload, timeout=30)
                
                if response.ok:
                    self._archive_job(job_dir, 'failed')
                    logger.info(f"[SYNC] Successfully synced job {post_id} as failed")
                elif response.status_code == 404:
                    self._archive_job(job_dir, 'failed')
                    logger.warning(f"[SYNC] Job {post_id} not found on server (404). Archiving local copy to stop retries.")
                else:
                    logger.error(f"[SYNC] Failed to sync failure for {post_id}: {response.status_code} - {response.text}")

            except Exception as e:
                logger.error(f"Error processing failed job {job_dir.name}: {e}")

    def _archive_job(self, job_dir: Path, status_subdir: str):
        """Move job to archive."""
        target_dir = self.archived_dir / status_subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        
        target_path = target_dir / job_dir.name
        if target_path.exists():
            shutil.rmtree(target_path)
            
        shutil.move(str(job_dir), str(target_path))

    # -------------------------------------------------------------------------
    # RUN LOOP
    # -------------------------------------------------------------------------
    
    def run_once(self) -> int:
        """Single fetch and sync cycle."""
        logger.info("--- Cycle Start ---")
        
        # 1. Sync local status to API
        self.sync_completed_jobs()
        self.sync_failed_jobs()
        
        # 2. Fetch new posts
        posts = self.fetch_pending_posts()
        created = 0
        if posts:
            for post in posts:
                if self.create_job(post):
                    created += 1
            if created > 0:
                logger.info(f"Created {created} new job(s)")
        else:
            logger.info("No new pending posts")
            
        logger.info("--- Cycle End ---")
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
                time.sleep(30)
        except KeyboardInterrupt:
            logger.info("Fetcher stopped by user")


# =============================================================================
# HEALTH CHECK
# =============================================================================

def health_check() -> bool:
    """Test connectivity to dashboard API."""
    url = f"{DASHBOARD_URL}/api/queue/gui/pending"
    try:
        response = safe_request('GET', url, headers={'X-API-Key': API_KEY}, timeout=10)
        if response.status_code == 200:
            print(f"[OK] API connection successful: {DASHBOARD_URL}")
            return True
        else:
            print(f"[FAIL] Connection failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Social Dashboard Queue Fetcher')
    parser.add_argument('--once', action='store_true', help='Fetch once and exit')
    parser.add_argument('--health', action='store_true', help='Test API connectivity')
    args = parser.parse_args()
    
    if args.health:
        sys.exit(0 if health_check() else 1)
    
    if not API_KEY:
        logger.error("API_KEY not set")
        sys.exit(1)
    
    fetcher = QueueFetcher()
    
    if args.once:
        fetcher.run_once()
    else:
        fetcher.run_forever()


if __name__ == '__main__':
    main()
