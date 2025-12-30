# SOCIAL-POSTING.md - Automated Social Media Distribution System

## Overview

This system bridges Sterling's Social Dashboard (sterlingcooley.com/social) with platforms that require GUI automation (Facebook, Instagram) via a Windows 10 computer-use agent.

**The Problem:**
- You create content once on Social Dashboard
- API-friendly platforms (Twitter, LinkedIn, Discord) work directly
- GUI-only platforms (Facebook, Instagram) need computer-use automation
- Video content (HeyGen) needs downloading and uploading

**The Solution:**
A queue-based architecture where:
1. Social Dashboard exposes a pending posts API
2. Windows 10 worker polls for due posts
3. Computer-use agent executes platform-specific posting playbooks
4. Success/failure reported back to dashboard

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    STERLING'S SOCIAL DASHBOARD                           │
│                    sterlingcooley.com/social                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌────────────────────────┐    ┌────────────────────────────────────┐  │
│   │  EXISTING FEATURES     │    │  NEW: POST QUEUE API               │  │
│   │  - Content creation    │    │                                    │  │
│   │  - Image uploads       │    │  GET  /api/queue/pending           │  │
│   │  - Video hosting       │    │  GET  /api/queue/media/{id}        │  │
│   │  - Scheduling UI       │    │  POST /api/queue/complete          │  │
│   │  - Twitter API         │    │  POST /api/queue/failed            │  │
│   │  - LinkedIn API        │    │  GET  /api/queue/status/{id}       │  │
│   │  - Discord API         │    │                                    │  │
│   └────────────────────────┘    └────────────────────────────────────┘  │
│                                              │                           │
└──────────────────────────────────────────────┼───────────────────────────┘
                                               │
                              HTTPS (authenticated, polling)
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    WINDOWS 10 POST WORKER (24/7)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌────────────────────────────────────────────────────────────────┐    │
│   │  QUEUE FETCHER SERVICE (Python, runs as Windows service)       │    │
│   │                                                                 │    │
│   │  Every 5 minutes:                                               │    │
│   │  1. GET /api/queue/pending                                      │    │
│   │  2. For each due post:                                          │    │
│   │     - Create folder C:\PostQueue\{job_id}\                      │    │
│   │     - Download media files                                      │    │
│   │     - Write job.json with all metadata                          │    │
│   │     - Signal computer-use agent                                 │    │
│   └────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│                                    ▼                                     │
│   ┌────────────────────────────────────────────────────────────────┐    │
│   │  COMPUTER-USE AGENT (integrated with existing supervisor)       │    │
│   │                                                                 │    │
│   │  Watches C:\PostQueue\ for new jobs:                            │    │
│   │  1. Read job.json                                               │    │
│   │  2. Execute platform-specific playbook                          │    │
│   │  3. Verify success with vision model                            │    │
│   │  4. Report back to dashboard API                                │    │
│   │  5. Move job to C:\PostQueue\completed\ or \failed\             │    │
│   └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│   ┌────────────────────────────────────────────────────────────────┐    │
│   │  LOCAL FOLDERS                                                  │    │
│   │                                                                 │    │
│   │  C:\PostQueue\                                                  │    │
│   │  ├── pending\              # New jobs from fetcher              │    │
│   │  │   └── job_2024...\                                           │    │
│   │  │       ├── job.json                                           │    │
│   │  │       └── media_1.jpg                                        │    │
│   │  ├── in_progress\          # Currently being posted             │    │
│   │  ├── completed\            # Successfully posted                │    │
│   │  └── failed\               # Failed (for retry/review)          │    │
│   └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Social Dashboard API Additions

Add these endpoints to your existing Social Dashboard backend:

### API Endpoints

```python
# File: api/queue.py (add to your existing Flask/Django app)

from flask import Blueprint, jsonify, request, send_file
from datetime import datetime
import os

queue_api = Blueprint('queue', __name__, url_prefix='/api/queue')

# Simple API key auth (store in environment variable)
API_KEY = os.environ.get('WINDOWS_WORKER_API_KEY', 'your-secret-key')

def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-API-Key')
        if key != API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated


@queue_api.route('/pending')
@require_api_key
def get_pending_posts():
    """
    Return posts that are:
    - Scheduled for now or earlier
    - Status is 'scheduled' (not yet posted)
    - Platform requires GUI automation (facebook, instagram)
    
    Returns:
        [
            {
                "id": "post_abc123",
                "platform": "instagram",
                "scheduled_time": "2024-12-24T14:30:00Z",
                "caption": "Check out my new project! 🚀",
                "media": [
                    {"id": "media_1", "type": "image", "filename": "project.jpg"}
                ],
                "link": "https://example.com/project"
            }
        ]
    """
    now = datetime.utcnow()
    
    # Query posts that need GUI automation
    pending = Post.query.filter(
        Post.scheduled_time <= now,
        Post.status == 'scheduled',
        Post.platform.in_(['facebook', 'instagram', 'tiktok', 'youtube'])
    ).order_by(Post.scheduled_time.asc()).limit(10).all()
    
    return jsonify([{
        'id': post.id,
        'platform': post.platform,
        'scheduled_time': post.scheduled_time.isoformat() + 'Z',
        'caption': post.text,
        'media': [
            {'id': m.id, 'type': m.type, 'filename': m.filename}
            for m in post.media
        ],
        'link': post.link
    } for post in pending])


@queue_api.route('/media/<media_id>')
@require_api_key
def download_media(media_id):
    """Download a media file by ID"""
    media = Media.query.get_or_404(media_id)
    return send_file(
        media.file_path,
        as_attachment=True,
        download_name=media.filename
    )


@queue_api.route('/complete', methods=['POST'])
@require_api_key
def mark_complete():
    """
    Mark a post as successfully published.
    
    Request body:
        {
            "id": "post_abc123",
            "platform_post_id": "optional_fb_post_id",
            "screenshot": "base64_encoded_success_screenshot"
        }
    """
    data = request.json
    post = Post.query.get_or_404(data['id'])
    
    post.status = 'published'
    post.published_at = datetime.utcnow()
    if data.get('platform_post_id'):
        post.platform_post_id = data['platform_post_id']
    if data.get('screenshot'):
        # Save success screenshot for verification
        save_screenshot(post.id, data['screenshot'])
    
    db.session.commit()
    return jsonify({'success': True})


@queue_api.route('/failed', methods=['POST'])
@require_api_key
def mark_failed():
    """
    Mark a post as failed with error details.
    
    Request body:
        {
            "id": "post_abc123",
            "error": "Login required - session expired",
            "screenshot": "base64_encoded_failure_screenshot",
            "retry": true  # Whether to retry later
        }
    """
    data = request.json
    post = Post.query.get_or_404(data['id'])
    
    post.status = 'failed' if not data.get('retry') else 'retry'
    post.last_error = data.get('error')
    post.error_count = (post.error_count or 0) + 1
    
    if data.get('screenshot'):
        save_screenshot(post.id, data['screenshot'], error=True)
    
    db.session.commit()
    return jsonify({'success': True})


@queue_api.route('/status/<post_id>')
@require_api_key
def get_status(post_id):
    """Get current status of a post"""
    post = Post.query.get_or_404(post_id)
    return jsonify({
        'id': post.id,
        'status': post.status,
        'published_at': post.published_at.isoformat() if post.published_at else None,
        'last_error': post.last_error
    })
```

### Database Schema Additions

```python
# Add these fields to your existing Post model

class Post(db.Model):
    # ... existing fields ...
    
    # New fields for queue system
    status = db.Column(db.String(20), default='draft')
    # Values: draft, scheduled, in_progress, published, failed, retry
    
    platform_post_id = db.Column(db.String(100))  # ID from the platform after posting
    published_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    error_count = db.Column(db.Integer, default=0)
```

---

## Part 2: Windows 10 Queue Fetcher

This Python service runs on your Windows 10 machine and fetches posts from the dashboard.

### Installation

```powershell
# Create project directory
mkdir C:\PostQueue
mkdir C:\PostQueue\pending
mkdir C:\PostQueue\in_progress
mkdir C:\PostQueue\completed
mkdir C:\PostQueue\failed

# Create fetcher directory
mkdir C:\SocialWorker
cd C:\SocialWorker

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install requests schedule python-dotenv
```

### Configuration

Create `C:\SocialWorker\.env`:

```env
DASHBOARD_URL=https://sterlingcooley.com
API_KEY=your-secret-api-key-here
QUEUE_DIR=C:\PostQueue
POLL_INTERVAL_MINUTES=5
```

### Queue Fetcher Service

Create `C:\SocialWorker\fetcher.py`:

```python
"""
Social Dashboard Queue Fetcher
Polls the dashboard API for pending posts and downloads them for the computer-use agent.
"""
import os
import json
import time
import logging
import requests
import schedule
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration
DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://sterlingcooley.com')
API_KEY = os.getenv('API_KEY')
QUEUE_DIR = Path(os.getenv('QUEUE_DIR', 'C:/PostQueue'))
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL_MINUTES', 5))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('C:/SocialWorker/logs/fetcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class QueueFetcher:
    """Fetches pending posts from Social Dashboard and prepares them for posting."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers['X-API-Key'] = API_KEY
        self.pending_dir = QUEUE_DIR / 'pending'
        self.pending_dir.mkdir(parents=True, exist_ok=True)
    
    def fetch_pending(self):
        """Fetch list of pending posts from dashboard."""
        try:
            response = self.session.get(
                f"{DASHBOARD_URL}/api/queue/pending",
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch pending posts: {e}")
            return []
    
    def download_media(self, media_id: str, save_path: Path) -> bool:
        """Download a media file from the dashboard."""
        try:
            response = self.session.get(
                f"{DASHBOARD_URL}/api/queue/media/{media_id}",
                timeout=120,  # Longer timeout for large files
                stream=True
            )
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded media: {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download media {media_id}: {e}")
            return False
    
    def create_job(self, post: dict) -> bool:
        """
        Create a job folder for a pending post.
        
        Structure:
            C:\PostQueue\pending\job_{timestamp}_{id}\
                job.json
                media_1.jpg
                media_2.mp4
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        job_id = f"job_{timestamp}_{post['id']}"
        job_dir = self.pending_dir / job_id
        
        # Check if job already exists (avoid duplicates)
        existing = list(self.pending_dir.glob(f"*_{post['id']}"))
        if existing:
            logger.info(f"Job already exists for post {post['id']}")
            return False
        
        try:
            job_dir.mkdir(parents=True, exist_ok=True)
            
            # Download media files
            media_files = []
            for i, media in enumerate(post.get('media', [])):
                ext = Path(media['filename']).suffix
                local_name = f"media_{i+1}{ext}"
                local_path = job_dir / local_name
                
                if self.download_media(media['id'], local_path):
                    media_files.append({
                        'type': media['type'],
                        'local_path': local_name
                    })
                else:
                    # Failed to download - cleanup and abort
                    import shutil
                    shutil.rmtree(job_dir)
                    return False
            
            # Write job.json
            job_data = {
                'id': post['id'],
                'job_id': job_id,
                'platform': post['platform'],
                'scheduled_time': post['scheduled_time'],
                'caption': post['caption'],
                'media': media_files,
                'link': post.get('link'),
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            }
            
            with open(job_dir / 'job.json', 'w', encoding='utf-8') as f:
                json.dump(job_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Created job: {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create job for {post['id']}: {e}")
            if job_dir.exists():
                import shutil
                shutil.rmtree(job_dir)
            return False
    
    def run_once(self):
        """Single fetch cycle."""
        logger.info("Checking for pending posts...")
        
        pending = self.fetch_pending()
        if not pending:
            logger.info("No pending posts")
            return
        
        logger.info(f"Found {len(pending)} pending posts")
        
        for post in pending:
            self.create_job(post)
    
    def run_forever(self):
        """Run fetch loop on schedule."""
        logger.info(f"Starting queue fetcher (polling every {POLL_INTERVAL} minutes)")
        
        # Run immediately on start
        self.run_once()
        
        # Schedule regular runs
        schedule.every(POLL_INTERVAL).minutes.do(self.run_once)
        
        while True:
            schedule.run_pending()
            time.sleep(30)  # Check schedule every 30 seconds


def main():
    """Entry point."""
    Path('C:/SocialWorker/logs').mkdir(parents=True, exist_ok=True)
    
    fetcher = QueueFetcher()
    fetcher.run_forever()


if __name__ == '__main__':
    main()
```

---

## Part 3: Platform Posting Playbooks

These are the step-by-step instructions for the computer-use agent to post to each platform.

### Instagram via Creator Studio

```python
"""
Instagram posting playbook using Meta Business Suite / Creator Studio.
This avoids the mobile-only limitation of the Instagram app.
"""

async def post_to_instagram(job: dict, browser: BrowserAgent, vision: VisionAgent):
    """
    Post to Instagram via Meta Business Suite.
    
    Prerequisites:
    - Instagram account connected to Facebook Page
    - Already logged into business.facebook.com
    
    Args:
        job: Job dictionary with caption, media, etc.
        browser: Playwright browser agent
        vision: Vision agent for verification
    """
    
    # Step 1: Navigate to Creator Studio
    await browser.navigate('https://business.facebook.com/creatorstudio')
    await asyncio.sleep(3)
    
    # Step 2: Click Instagram icon (left sidebar)
    await browser.click('[data-testid="instagram-icon"]')
    await asyncio.sleep(2)
    
    # Step 3: Click "Create Post"
    await browser.click('text="Create Post"')
    await asyncio.sleep(2)
    
    # Step 4: Click "Instagram Feed"
    await browser.click('text="Instagram Feed"')
    await asyncio.sleep(2)
    
    # Step 5: Upload image
    # The file input is hidden, so we need to set files directly
    media_path = Path(job['job_dir']) / job['media'][0]['local_path']
    await browser.page.set_input_files('input[type="file"]', str(media_path))
    await asyncio.sleep(5)  # Wait for upload
    
    # Step 6: Enter caption
    caption_box = await browser.page.query_selector('[placeholder*="caption"]')
    await caption_box.fill(job['caption'])
    
    # Step 7: Click Publish
    await browser.click('text="Publish"')
    await asyncio.sleep(5)
    
    # Step 8: Verify success
    screenshot = await browser.screenshot()
    verification = vision.analyze_screen(
        screenshot, 
        "Is there a success message or confirmation that the post was published?"
    )
    
    return 'success' in verification.lower() or 'published' in verification.lower()
```

### Facebook Page Posting

```python
"""
Facebook posting playbook for Page posts.
"""

async def post_to_facebook(job: dict, browser: BrowserAgent, vision: VisionAgent):
    """
    Post to Facebook Page.
    
    Prerequisites:
    - Already logged into Facebook
    - Have admin access to the Page
    """
    
    # Step 1: Navigate to your Facebook Page
    await browser.navigate('https://www.facebook.com/YOUR_PAGE_NAME')
    await asyncio.sleep(3)
    
    # Step 2: Click "Create Post" box
    await browser.click('[aria-label="Create a post"]')
    await asyncio.sleep(2)
    
    # Step 3: Click photo/video button
    await browser.click('[aria-label="Photo/video"]')
    await asyncio.sleep(1)
    
    # Step 4: Upload image
    media_path = Path(job['job_dir']) / job['media'][0]['local_path']
    await browser.page.set_input_files('input[type="file"]', str(media_path))
    await asyncio.sleep(5)
    
    # Step 5: Enter text
    text_box = await browser.page.query_selector('[aria-label="What\'s on your mind?"]')
    await text_box.fill(job['caption'])
    
    # Add link if present
    if job.get('link'):
        await text_box.fill(f"\n\n{job['link']}")
    
    # Step 6: Click Post
    await browser.click('text="Post"')
    await asyncio.sleep(5)
    
    # Step 7: Verify
    screenshot = await browser.screenshot()
    return vision.check_for_success(screenshot)
```

### Video Handling for TikTok/YouTube

```python
"""
Video posting requires downloading the video first, then uploading.
"""

async def post_video_to_tiktok(job: dict, browser: BrowserAgent, vision: VisionAgent):
    """
    Post video to TikTok.
    
    Note: TikTok has heavy bot detection. This may require:
    - Human-like mouse movements (pynput)
    - Random delays
    - Logged-in session cookies
    """
    
    # Step 1: Navigate to TikTok upload
    await browser.navigate('https://www.tiktok.com/upload')
    await asyncio.sleep(3)
    
    # Step 2: Check if logged in
    screenshot = await browser.screenshot()
    if 'log in' in vision.read_text(screenshot).lower():
        raise Exception("Not logged in to TikTok")
    
    # Step 3: Upload video
    video_path = Path(job['job_dir']) / job['media'][0]['local_path']
    await browser.page.set_input_files('input[type="file"]', str(video_path))
    await asyncio.sleep(30)  # Videos take longer to process
    
    # Step 4: Enter caption (TikTok calls it description)
    await browser.fill('[placeholder*="caption"], [placeholder*="description"]', job['caption'])
    
    # Step 5: Click Post
    await browser.click('button:has-text("Post")')
    await asyncio.sleep(10)
    
    # Step 6: Verify
    screenshot = await browser.screenshot()
    return vision.check_for_success(screenshot)
```

---

## Part 4: Integration with Computer-Use Supervisor

Add a new module to your existing supervisor that watches for jobs:

### src/social_poster.py

```python
"""
Social Media Posting Agent
Watches C:\PostQueue\pending for new jobs and executes platform-specific playbooks.
"""
import asyncio
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import requests

from src.browser_agent import BrowserAgent
from src.vision_agent import VisionAgent
from src.screen_monitor import ScreenMonitor

logger = logging.getLogger('social_poster')


class SocialPoster:
    """Executes social media posting jobs."""
    
    def __init__(
        self,
        queue_dir: str = "C:/PostQueue",
        dashboard_url: str = "https://sterlingcooley.com",
        api_key: str = None
    ):
        self.queue_dir = Path(queue_dir)
        self.pending_dir = self.queue_dir / 'pending'
        self.in_progress_dir = self.queue_dir / 'in_progress'
        self.completed_dir = self.queue_dir / 'completed'
        self.failed_dir = self.queue_dir / 'failed'
        
        self.dashboard_url = dashboard_url
        self.api_key = api_key
        
        # Create directories
        for d in [self.pending_dir, self.in_progress_dir, 
                  self.completed_dir, self.failed_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Agents
        self.browser: Optional[BrowserAgent] = None
        self.vision: Optional[VisionAgent] = None
    
    async def start(self):
        """Start browser and vision agents."""
        self.browser = BrowserAgent(headless=False)  # Need visible browser
        await self.browser.start()
        
        self.vision = VisionAgent()
        logger.info("Social poster started")
    
    async def stop(self):
        """Cleanup."""
        if self.browser:
            await self.browser.close()
    
    def get_pending_jobs(self) -> list:
        """Get list of pending job directories."""
        jobs = []
        for job_dir in self.pending_dir.iterdir():
            if job_dir.is_dir():
                job_file = job_dir / 'job.json'
                if job_file.exists():
                    with open(job_file) as f:
                        job = json.load(f)
                        job['job_dir'] = str(job_dir)
                        jobs.append(job)
        return jobs
    
    def claim_job(self, job: dict) -> bool:
        """Move job to in_progress."""
        src = Path(job['job_dir'])
        dst = self.in_progress_dir / src.name
        try:
            shutil.move(str(src), str(dst))
            job['job_dir'] = str(dst)
            return True
        except Exception as e:
            logger.error(f"Failed to claim job: {e}")
            return False
    
    def complete_job(self, job: dict, success: bool, error: str = None):
        """Move job to completed or failed."""
        src = Path(job['job_dir'])
        
        if success:
            dst = self.completed_dir / src.name
            status = 'completed'
        else:
            dst = self.failed_dir / src.name
            status = 'failed'
        
        try:
            shutil.move(str(src), str(dst))
            
            # Update job.json with result
            job_file = dst / 'job.json'
            with open(job_file) as f:
                job_data = json.load(f)
            
            job_data['status'] = status
            job_data['completed_at'] = datetime.now().isoformat()
            if error:
                job_data['error'] = error
            
            with open(job_file, 'w') as f:
                json.dump(job_data, f, indent=2)
            
            # Report to dashboard
            self.report_to_dashboard(job['id'], success, error)
            
        except Exception as e:
            logger.error(f"Failed to complete job: {e}")
    
    def report_to_dashboard(self, post_id: str, success: bool, error: str = None):
        """Report result back to Social Dashboard."""
        if not self.api_key:
            return
        
        try:
            endpoint = '/api/queue/complete' if success else '/api/queue/failed'
            requests.post(
                f"{self.dashboard_url}{endpoint}",
                headers={'X-API-Key': self.api_key},
                json={
                    'id': post_id,
                    'error': error
                },
                timeout=30
            )
        except Exception as e:
            logger.error(f"Failed to report to dashboard: {e}")
    
    async def execute_job(self, job: dict) -> tuple[bool, str]:
        """
        Execute a posting job.
        
        Returns:
            (success, error_message)
        """
        platform = job['platform'].lower()
        
        try:
            if platform == 'instagram':
                success = await self.post_to_instagram(job)
            elif platform == 'facebook':
                success = await self.post_to_facebook(job)
            elif platform == 'tiktok':
                success = await self.post_to_tiktok(job)
            elif platform == 'youtube':
                success = await self.post_to_youtube(job)
            else:
                return False, f"Unknown platform: {platform}"
            
            return success, None if success else "Posting failed - see screenshot"
            
        except Exception as e:
            logger.exception(f"Error posting to {platform}")
            return False, str(e)
    
    async def post_to_instagram(self, job: dict) -> bool:
        """Post to Instagram via Creator Studio."""
        # Navigate to Creator Studio
        await self.browser.navigate('https://business.facebook.com/creatorstudio')
        await asyncio.sleep(3)
        
        # ... (implement full playbook from above)
        
        return True  # Return based on verification
    
    async def post_to_facebook(self, job: dict) -> bool:
        """Post to Facebook Page."""
        # ... (implement playbook)
        return True
    
    async def post_to_tiktok(self, job: dict) -> bool:
        """Post to TikTok."""
        # ... (implement playbook)
        return True
    
    async def post_to_youtube(self, job: dict) -> bool:
        """Upload to YouTube."""
        # ... (implement playbook)
        return True
    
    async def run_once(self):
        """Process one batch of pending jobs."""
        jobs = self.get_pending_jobs()
        
        if not jobs:
            logger.debug("No pending jobs")
            return
        
        logger.info(f"Found {len(jobs)} pending jobs")
        
        for job in jobs:
            if not self.claim_job(job):
                continue
            
            logger.info(f"Processing job: {job['job_id']} ({job['platform']})")
            
            success, error = await self.execute_job(job)
            
            self.complete_job(job, success, error)
            
            if success:
                logger.info(f"Successfully posted: {job['job_id']}")
            else:
                logger.error(f"Failed to post: {job['job_id']} - {error}")
            
            # Delay between posts
            await asyncio.sleep(10)
    
    async def run_forever(self, check_interval: int = 60):
        """Continuously watch for and process jobs."""
        logger.info("Starting social poster loop")
        
        while True:
            try:
                await self.run_once()
            except Exception as e:
                logger.exception(f"Error in posting loop: {e}")
            
            await asyncio.sleep(check_interval)


async def main():
    """Entry point."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    poster = SocialPoster(
        dashboard_url=os.getenv('DASHBOARD_URL', 'https://sterlingcooley.com'),
        api_key=os.getenv('API_KEY')
    )
    
    await poster.start()
    
    try:
        await poster.run_forever()
    finally:
        await poster.stop()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

---

## Part 5: Windows Service Installation

Run both the fetcher and poster as Windows services:

### Install as Services

```powershell
# Install NSSM if not already
choco install nssm -y

# Install Queue Fetcher service
nssm install SocialFetcher "C:\SocialWorker\venv\Scripts\python.exe" "C:\SocialWorker\fetcher.py"
nssm set SocialFetcher AppDirectory "C:\SocialWorker"
nssm set SocialFetcher AppStdout "C:\SocialWorker\logs\fetcher_stdout.log"
nssm set SocialFetcher AppStderr "C:\SocialWorker\logs\fetcher_stderr.log"

# Install Social Poster service (integrates with computer-use supervisor)
nssm install SocialPoster "C:\ai-supervisor\venv\Scripts\python.exe" "-m" "src.social_poster"
nssm set SocialPoster AppDirectory "C:\ai-supervisor"
nssm set SocialPoster AppStdout "C:\ai-supervisor\logs\poster_stdout.log"
nssm set SocialPoster AppStderr "C:\ai-supervisor\logs\poster_stderr.log"

# Start services
Start-Service SocialFetcher
Start-Service SocialPoster
```

---

## Part 6: Handling HeyGen Videos

For HeyGen-generated videos:

1. **On Social Dashboard**: Store the HeyGen video URL or download and store the video file
2. **Queue Fetcher**: Downloads video file to job folder
3. **Social Poster**: Uploads to TikTok/YouTube/Instagram Reels

```python
# In your Social Dashboard, add HeyGen integration

def download_heygen_video(video_id: str) -> str:
    """Download video from HeyGen and save to media storage."""
    
    # HeyGen API to get video URL
    response = requests.get(
        f"https://api.heygen.com/v1/video/{video_id}",
        headers={"Authorization": f"Bearer {HEYGEN_API_KEY}"}
    )
    video_url = response.json()['video_url']
    
    # Download video
    video_response = requests.get(video_url, stream=True)
    
    # Save to your media storage
    filename = f"heygen_{video_id}.mp4"
    save_path = f"/path/to/media/{filename}"
    
    with open(save_path, 'wb') as f:
        for chunk in video_response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    return save_path
```

---

## Summary: What Needs to Be Built

### On Social Dashboard (Server):
1. Add `/api/queue/*` endpoints
2. Add status tracking fields to Post model
3. Add HeyGen video download integration (optional)

### On Windows 10:
1. Queue Fetcher (`C:\SocialWorker\fetcher.py`)
2. Social Poster (`C:\ai-supervisor\src\social_poster.py`)
3. Platform-specific playbooks for each social network
4. Windows services for both components

### Estimated Timeline:
- Dashboard API: 2-4 hours
- Queue Fetcher: 2-3 hours
- Social Poster base: 3-4 hours
- Platform playbooks: 2-4 hours each (Instagram, Facebook, TikTok, YouTube)
- Testing & debugging: 4-8 hours

Total: 15-30 hours depending on platform complexity

---

## Next Steps

1. **Start with the Dashboard API** - this is the foundation
2. **Build the Queue Fetcher** - simple polling service
3. **Pick ONE platform** (Facebook is usually easiest) and build that playbook
4. **Test end-to-end** with that one platform
5. **Add more platforms** one at a time
