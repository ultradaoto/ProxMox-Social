"""
Social Dashboard Queue Fetcher

Polls the Sterling Social Dashboard API for pending posts that require
GUI automation (Facebook, Instagram, TikTok, YouTube) and downloads
them for the computer-use agent to process.

Usage:
    python fetcher.py              # Run continuously
    python fetcher.py --once       # Single fetch cycle
    python fetcher.py --status     # Check connection status
"""

import os
import sys
import json
import time
import logging
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from functools import wraps

import requests
import schedule
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://sterlingcooley.com')
API_KEY = os.getenv('API_KEY', '')
QUEUE_DIR = Path(os.getenv('QUEUE_DIR', 'C:/PostQueue'))
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL_MINUTES', 5))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Setup logging
def setup_logging():
    """Configure logging with file and console output."""
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"fetcher_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('fetcher')

logger = setup_logging()


class APIError(Exception):
    """API communication error."""
    pass


class QueueFetcher:
    """
    Fetches pending posts from Social Dashboard and prepares them for posting.

    Flow:
    1. Poll /api/queue/pending for due posts
    2. For each post, create a job folder
    3. Download all media files
    4. Write job.json with metadata
    5. Computer-use agent picks up from here
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': API_KEY,
            'User-Agent': 'SocialWorker/1.0',
            'Accept': 'application/json'
        })

        # Queue directories
        self.pending_dir = QUEUE_DIR / 'pending'
        self.in_progress_dir = QUEUE_DIR / 'in_progress'
        self.completed_dir = QUEUE_DIR / 'completed'
        self.failed_dir = QUEUE_DIR / 'failed'

        # Create directories
        for d in [self.pending_dir, self.in_progress_dir,
                  self.completed_dir, self.failed_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Stats
        self.stats = {
            'total_fetched': 0,
            'total_downloaded': 0,
            'last_fetch': None,
            'errors': 0
        }

    def check_connection(self) -> Dict[str, Any]:
        """
        Test connection to the dashboard API.

        Returns:
            Status dictionary with connection info
        """
        try:
            response = self.session.get(
                f"{DASHBOARD_URL}/api/queue/pending",
                timeout=10
            )

            return {
                'connected': response.status_code == 200,
                'status_code': response.status_code,
                'dashboard_url': DASHBOARD_URL,
                'api_key_set': bool(API_KEY),
                'response_time_ms': response.elapsed.total_seconds() * 1000
            }

        except requests.exceptions.ConnectionError:
            return {
                'connected': False,
                'error': 'Connection refused - is the dashboard running?',
                'dashboard_url': DASHBOARD_URL
            }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e),
                'dashboard_url': DASHBOARD_URL
            }

    def fetch_pending(self) -> List[Dict[str, Any]]:
        """
        Fetch list of pending posts from dashboard.

        Returns:
            List of post dictionaries
        """
        try:
            response = self.session.get(
                f"{DASHBOARD_URL}/api/queue/pending",
                timeout=30
            )

            if response.status_code == 401:
                raise APIError("Invalid API key")
            elif response.status_code == 404:
                raise APIError("Queue API endpoint not found - is it implemented?")

            response.raise_for_status()

            posts = response.json()
            logger.debug(f"API returned {len(posts)} pending posts")
            return posts

        except requests.exceptions.Timeout:
            logger.error("Request timed out fetching pending posts")
            self.stats['errors'] += 1
            return []
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to {DASHBOARD_URL}")
            self.stats['errors'] += 1
            return []
        except APIError as e:
            logger.error(f"API error: {e}")
            self.stats['errors'] += 1
            return []
        except Exception as e:
            logger.error(f"Failed to fetch pending posts: {e}")
            self.stats['errors'] += 1
            return []

    def download_media(self, media_id: str, save_path: Path) -> bool:
        """
        Download a media file from the dashboard.

        Args:
            media_id: Media file ID
            save_path: Local path to save file

        Returns:
            True if download succeeded
        """
        try:
            response = self.session.get(
                f"{DASHBOARD_URL}/api/queue/media/{media_id}",
                timeout=300,  # 5 min timeout for large videos
                stream=True
            )
            response.raise_for_status()

            # Get file size for progress
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Log progress for large files
                    if total_size > 10_000_000:  # 10MB+
                        progress = (downloaded / total_size) * 100
                        if downloaded % (total_size // 10) < 8192:
                            logger.debug(f"Download progress: {progress:.0f}%")

            # Verify file was written
            if save_path.stat().st_size == 0:
                logger.error(f"Downloaded file is empty: {save_path}")
                return False

            logger.info(f"Downloaded: {save_path.name} ({save_path.stat().st_size:,} bytes)")
            self.stats['total_downloaded'] += 1
            return True

        except Exception as e:
            logger.error(f"Failed to download media {media_id}: {e}")
            return False

    def job_exists(self, post_id: str) -> bool:
        """Check if a job already exists for this post ID."""
        # Check all queue directories
        for directory in [self.pending_dir, self.in_progress_dir,
                         self.completed_dir, self.failed_dir]:
            for job_dir in directory.iterdir():
                if job_dir.is_dir() and post_id in job_dir.name:
                    return True
        return False

    def create_job(self, post: Dict[str, Any]) -> Optional[str]:
        """
        Create a job folder for a pending post.

        Structure:
            C:\\PostQueue\\pending\\job_{timestamp}_{id}\\
                job.json        # Job metadata and instructions
                media_1.jpg     # First media file
                media_2.mp4     # Second media file (if any)

        Args:
            post: Post dictionary from API

        Returns:
            Job ID if created, None if failed
        """
        post_id = post.get('id', '')

        # Check for duplicates
        if self.job_exists(post_id):
            logger.debug(f"Job already exists for post {post_id}")
            return None

        # Generate job ID
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        short_id = post_id[:8] if len(post_id) > 8 else post_id
        job_id = f"job_{timestamp}_{short_id}"
        job_dir = self.pending_dir / job_id

        try:
            job_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Creating job: {job_id}")

            # Download media files
            media_files = []
            for i, media in enumerate(post.get('media', [])):
                # Determine file extension
                filename = media.get('filename', f'media_{i+1}')
                ext = Path(filename).suffix or self._guess_extension(media.get('type', 'image'))
                local_name = f"media_{i+1}{ext}"
                local_path = job_dir / local_name

                if self.download_media(media['id'], local_path):
                    media_files.append({
                        'index': i + 1,
                        'type': media.get('type', 'image'),
                        'local_path': local_name,
                        'original_filename': filename
                    })
                else:
                    # Failed to download - cleanup and abort
                    logger.error(f"Failed to download media, aborting job {job_id}")
                    self._cleanup_job(job_dir)
                    return None

            # Build job.json
            job_data = {
                'id': post_id,
                'job_id': job_id,
                'platform': post.get('platform', '').lower(),
                'scheduled_time': post.get('scheduled_time'),
                'caption': post.get('caption', ''),
                'media': media_files,
                'link': post.get('link'),
                'hashtags': post.get('hashtags', []),
                'mentions': post.get('mentions', []),

                # Job metadata
                'status': 'pending',
                'created_at': datetime.now().isoformat(),
                'attempts': 0,
                'max_attempts': 3,

                # Platform-specific options
                'options': post.get('options', {})
            }

            # Write job.json
            job_file = job_dir / 'job.json'
            with open(job_file, 'w', encoding='utf-8') as f:
                json.dump(job_data, f, indent=2, ensure_ascii=False)

            # Write a signal file for the poster to detect new jobs
            signal_file = job_dir / '.ready'
            signal_file.touch()

            logger.info(f"Job created successfully: {job_id} ({post['platform']})")
            self.stats['total_fetched'] += 1

            return job_id

        except Exception as e:
            logger.error(f"Failed to create job for {post_id}: {e}")
            self._cleanup_job(job_dir)
            return None

    def _guess_extension(self, media_type: str) -> str:
        """Guess file extension from media type."""
        extensions = {
            'image': '.jpg',
            'video': '.mp4',
            'gif': '.gif',
            'png': '.png',
            'jpeg': '.jpg',
            'mp4': '.mp4',
            'mov': '.mov',
            'webp': '.webp'
        }
        return extensions.get(media_type.lower(), '.bin')

    def _cleanup_job(self, job_dir: Path):
        """Remove a failed job directory."""
        try:
            import shutil
            if job_dir.exists():
                shutil.rmtree(job_dir)
        except Exception as e:
            logger.error(f"Failed to cleanup {job_dir}: {e}")

    def run_once(self):
        """Execute a single fetch cycle."""
        logger.info("="*50)
        logger.info("Starting fetch cycle")
        logger.info(f"Dashboard: {DASHBOARD_URL}")

        self.stats['last_fetch'] = datetime.now().isoformat()

        # Fetch pending posts
        pending = self.fetch_pending()

        if not pending:
            logger.info("No pending posts found")
            return

        logger.info(f"Found {len(pending)} pending posts")

        # Process each post
        created = 0
        for post in pending:
            job_id = self.create_job(post)
            if job_id:
                created += 1

        logger.info(f"Created {created} new jobs")
        logger.info(f"Stats: {json.dumps(self.stats, indent=2)}")

    def run_forever(self):
        """Run fetch loop on schedule."""
        logger.info("="*60)
        logger.info("  SOCIAL DASHBOARD QUEUE FETCHER")
        logger.info("="*60)
        logger.info(f"Dashboard URL: {DASHBOARD_URL}")
        logger.info(f"Queue Directory: {QUEUE_DIR}")
        logger.info(f"Poll Interval: {POLL_INTERVAL} minutes")
        logger.info(f"API Key Set: {'Yes' if API_KEY else 'NO - PLEASE SET API_KEY'}")
        logger.info("="*60)

        if not API_KEY:
            logger.error("API_KEY not set! Please configure .env file")
            return

        # Run immediately on start
        self.run_once()

        # Schedule regular runs
        schedule.every(POLL_INTERVAL).minutes.do(self.run_once)

        logger.info(f"Scheduled to run every {POLL_INTERVAL} minutes")
        logger.info("Press Ctrl+C to stop")

        try:
            while True:
                schedule.run_pending()
                time.sleep(30)  # Check schedule every 30 seconds
        except KeyboardInterrupt:
            logger.info("Shutting down...")

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        def count_jobs(directory: Path) -> int:
            return len([d for d in directory.iterdir() if d.is_dir()])

        return {
            'pending': count_jobs(self.pending_dir),
            'in_progress': count_jobs(self.in_progress_dir),
            'completed': count_jobs(self.completed_dir),
            'failed': count_jobs(self.failed_dir),
            'stats': self.stats
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Social Dashboard Queue Fetcher'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run single fetch cycle and exit'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Check connection status and exit'
    )
    parser.add_argument(
        '--queue',
        action='store_true',
        help='Show queue status and exit'
    )

    args = parser.parse_args()

    fetcher = QueueFetcher()

    if args.status:
        status = fetcher.check_connection()
        print("\nConnection Status:")
        print("-" * 40)
        for key, value in status.items():
            print(f"  {key}: {value}")
        sys.exit(0 if status.get('connected') else 1)

    elif args.queue:
        status = fetcher.get_queue_status()
        print("\nQueue Status:")
        print("-" * 40)
        print(f"  Pending:     {status['pending']}")
        print(f"  In Progress: {status['in_progress']}")
        print(f"  Completed:   {status['completed']}")
        print(f"  Failed:      {status['failed']}")
        sys.exit(0)

    elif args.once:
        fetcher.run_once()

    else:
        fetcher.run_forever()


if __name__ == '__main__':
    main()
