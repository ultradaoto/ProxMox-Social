# WINDOWS10-FETCHER.md
# Social Dashboard Queue Fetcher - Windows 10 Implementation

**Machine**: Windows 10 (Sterling's home computer)
**Purpose**: Poll social.sterlingcooley.com API for pending posts and download content locally
**Language**: Python with `requests` library (NO Playwright, NO browser automation)

---

## Critical Security Constraint

```python
# ═══════════════════════════════════════════════════════════════════════════════
#  SECURITY: DOMAIN ALLOWLIST - THIS IS NON-NEGOTIABLE
# ═══════════════════════════════════════════════════════════════════════════════
#
#  The Windows 10 Fetcher can ONLY access ONE domain:
#
#      social.sterlingcooley.com
#
#  ANY attempt to access another domain MUST raise an error and be blocked.
#  This includes redirects, embedded URLs, or any other mechanism.
#
# ═══════════════════════════════════════════════════════════════════════════════

ALLOWED_DOMAINS = frozenset([
    'social.sterlingcooley.com',
])
```

**Why this matters**: 
- No Playwright/Selenium = no browser fingerprint
- No social media access = cannot get banned
- Single domain = minimal attack surface
- Simple HTTP requests only = predictable behavior

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│           WINDOWS 10 FETCHER (C:\SocialWorker)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  fetcher.py - Main Polling Loop                         │   │
│  │                                                         │   │
│  │  Every 5 minutes:                                       │   │
│  │  1. GET /api/queue/gui/pending                          │   │
│  │  2. For each pending post:                              │   │
│  │     a. Create job folder                                │   │
│  │     b. GET /api/queue/gui/media/:id (download image)    │   │
│  │     c. Save job.json with instructions                  │   │
│  │  3. Log results                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  OUTPUTS TO:                                                    │
│                                                                 │
│  C:\PostQueue\                                                  │
│  ├── pending\           # Jobs waiting to be posted             │
│  │   └── job_20250102_143022_abc123\                           │
│  │       ├── job.json   # Post metadata & instructions          │
│  │       └── media_1.jpg # Downloaded image/video               │
│  ├── in_progress\       # Currently being processed             │
│  ├── completed\         # Successfully posted                   │
│  └── failed\            # Failed posts for review               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
            │
            │ HTTPS (polling, X-API-Key header)
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│        social.sterlingcooley.com (DigitalOcean Droplet)         │
│        See: DROPLET-API.md                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
C:\SocialWorker\
├── .env                    # Configuration (API key, URLs)
├── fetcher.py              # Main fetcher script
├── healthcheck.py          # Connectivity test script
├── requirements.txt        # Python dependencies
├── setup_worker.ps1        # One-click deployment script
├── venv\                   # Python virtual environment
└── logs\
    ├── fetcher.log         # Main log file
    ├── fetcher_stdout.log  # Service stdout (if running as service)
    └── fetcher_stderr.log  # Service stderr

C:\PostQueue\
├── pending\                # New jobs from fetcher
├── in_progress\            # Being processed by poster
├── completed\              # Successfully posted
└── failed\                 # Failed (for retry/review)
```

---

## Configuration

### .env File (C:\SocialWorker\.env)

```env
# ═══════════════════════════════════════════════════════════════════════════════
# SOCIAL DASHBOARD FETCHER CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# The ONLY domain this fetcher is allowed to contact
DASHBOARD_URL=https://social.sterlingcooley.com

# API Authentication Key (must match server's WINDOWS_WORKER_API_KEY)
API_KEY=your-api-key-ending-in-61ce

# Local directory for downloaded jobs
QUEUE_DIR=C:\PostQueue

# How often to poll the API (in minutes)
POLL_INTERVAL=5

# Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

### requirements.txt

```text
# Minimal dependencies - NO browser automation libraries
requests>=2.31.0
schedule>=1.2.0
python-dotenv>=1.0.0
```

**Explicitly NOT included**:
- ❌ playwright
- ❌ selenium
- ❌ pyppeteer
- ❌ Any browser automation

---

## Complete Fetcher Code

### fetcher.py

```python
"""
Social Dashboard Queue Fetcher for Windows 10
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Downloads pending posts from social.sterlingcooley.com and saves them
to C:\PostQueue\pending\ for processing.

SECURITY: This script can ONLY access social.sterlingcooley.com
          No other domains are permitted.

TESTING MODE: Polls every 1 minute with verbose console output.
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

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://social.sterlingcooley.com')
API_KEY = os.getenv('API_KEY', '')
QUEUE_DIR = Path(os.getenv('QUEUE_DIR', 'C:/PostQueue'))
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '1'))  # 1 minute for testing
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG')

# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY: DOMAIN ALLOWLIST - DO NOT MODIFY
# ═══════════════════════════════════════════════════════════════════════════════

ALLOWED_DOMAINS = frozenset([
    'social.sterlingcooley.com',
])


class SecurityError(Exception):
    """Raised when a security constraint is violated."""
    pass


def is_allowed_url(url: str) -> bool:
    """Check if URL is in the allowed domain list."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if ':' in domain:
            domain = domain.split(':')[0]
        return domain in ALLOWED_DOMAINS
    except Exception:
        return False


def safe_request(method: str, url: str, **kwargs) -> requests.Response:
    """Make an HTTP request, but ONLY to allowed domains."""
    if not is_allowed_url(url):
        raise SecurityError(
            f"BLOCKED: Domain not in allowlist. URL: {url}\n"
            f"Allowed domains: {ALLOWED_DOMAINS}"
        )
    kwargs.setdefault('allow_redirects', False)
    response = requests.request(method, url, **kwargs)
    if response.is_redirect:
        redirect_url = response.headers.get('Location', '')
        if redirect_url and not is_allowed_url(redirect_url):
            raise SecurityError(f"BLOCKED: Redirect to disallowed domain: {redirect_url}")
    return response


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING SETUP - VERBOSE FOR TESTING
# ═══════════════════════════════════════════════════════════════════════════════

log_dir = Path('C:/SocialWorker/logs')
log_dir.mkdir(parents=True, exist_ok=True)

# Configure logging to both file and console with VERBOSE output
logging.basicConfig(
    level=logging.DEBUG,  # Most verbose for testing
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_dir / 'fetcher.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)  # Print to console
    ]
)
logger = logging.getLogger('fetcher')


# ═══════════════════════════════════════════════════════════════════════════════
# VISUAL OUTPUT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def print_banner():
    """Print startup banner."""
    print("\n" + "=" * 70)
    print("   SOCIAL DASHBOARD QUEUE FETCHER - TESTING MODE")
    print("=" * 70)
    print(f"   Dashboard URL:  {DASHBOARD_URL}")
    print(f"   Queue Dir:      {QUEUE_DIR}")
    print(f"   Poll Interval:  {POLL_INTERVAL} minute(s)")
    print(f"   API Key:        {'*' * 20}{API_KEY[-4:] if len(API_KEY) > 4 else 'NOT SET'}")
    print("=" * 70)
    print()


def print_cycle_header(cycle_num: int):
    """Print header for each fetch cycle."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print("\n" + "-" * 70)
    print(f"   FETCH CYCLE #{cycle_num} | {now}")
    print("-" * 70)


def print_result(status: str, message: str):
    """Print formatted result."""
    symbols = {
        'success': '✓',
        'info': 'ℹ',
        'warning': '⚠',
        'error': '✗',
    }
    symbol = symbols.get(status, '•')
    print(f"   {symbol} {message}")


# ═══════════════════════════════════════════════════════════════════════════════
# QUEUE FETCHER CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class QueueFetcher:
    """Fetches pending posts from the Social Dashboard API."""
    
    def __init__(self):
        """Initialize the fetcher."""
        self.pending_dir = QUEUE_DIR / 'pending'
        self.in_progress_dir = QUEUE_DIR / 'in_progress'
        self.completed_dir = QUEUE_DIR / 'completed'
        self.failed_dir = QUEUE_DIR / 'failed'
        self.cycle_count = 0
        
        # Create directories
        for d in [self.pending_dir, self.in_progress_dir, 
                  self.completed_dir, self.failed_dir]:
            d.mkdir(parents=True, exist_ok=True)
    
    def fetch_pending_posts(self) -> List[Dict[str, Any]]:
        """Fetch list of pending posts from the dashboard API."""
        url = f"{DASHBOARD_URL}/api/queue/gui/pending"
        
        print_result('info', f"Requesting: GET {url}")
        logger.debug(f"Making request to: {url}")
        
        try:
            start_time = time.time()
            
            response = safe_request(
                'GET', url,
                headers={
                    'X-API-Key': API_KEY,
                    'User-Agent': 'SocialWorker-Fetcher/1.0'
                },
                timeout=30
            )
            
            elapsed = time.time() - start_time
            
            # Log response details
            print_result('info', f"Response: HTTP {response.status_code} ({elapsed:.2f}s)")
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                try:
                    posts = response.json()
                    print_result('success', f"Found {len(posts)} pending post(s)")
                    
                    # Log post details
                    for i, post in enumerate(posts):
                        print_result('info', f"  Post {i+1}: {post.get('platform', '?')} - {post.get('id', '?')}")
                        logger.debug(f"Post {i+1} data: {json.dumps(post, indent=2)}")
                    
                    return posts
                except json.JSONDecodeError as e:
                    print_result('error', f"Invalid JSON response: {e}")
                    logger.error(f"JSON decode error: {e}")
                    logger.debug(f"Raw response: {response.text[:500]}")
                    return []
            
            elif response.status_code == 204:
                print_result('info', "No pending posts (204 No Content)")
                return []
            
            elif response.status_code == 401:
                print_result('error', "Authentication FAILED (401 Unauthorized)")
                print_result('error', "Check that API_KEY matches WINDOWS_WORKER_API_KEY on server")
                logger.error("API authentication failed - check API_KEY in .env")
                return []
            
            elif response.status_code == 404:
                print_result('error', "Endpoint NOT FOUND (404)")
                print_result('error', "The /api/queue/gui/pending route may not be registered on server")
                logger.error("Endpoint not found - route may not be registered")
                return []
            
            else:
                print_result('warning', f"Unexpected status: {response.status_code}")
                logger.warning(f"Unexpected response: {response.status_code}")
                logger.debug(f"Response body: {response.text[:500]}")
                return []
                
        except SecurityError as e:
            print_result('error', f"SECURITY VIOLATION: {e}")
            logger.error(f"Security error: {e}")
            return []
        
        except requests.exceptions.Timeout:
            print_result('error', "Request TIMED OUT (30s)")
            logger.error("Request timed out after 30 seconds")
            return []
        
        except requests.exceptions.ConnectionError as e:
            print_result('error', f"CONNECTION ERROR: Could not reach {DASHBOARD_URL}")
            print_result('error', f"Details: {str(e)[:100]}")
            logger.error(f"Connection error: {e}")
            return []
        
        except Exception as e:
            print_result('error', f"UNEXPECTED ERROR: {type(e).__name__}: {e}")
            logger.exception(f"Unexpected error: {e}")
            return []
    
    def download_media(self, media_id: str, save_path: Path) -> bool:
        """Download a media file from the dashboard."""
        url = f"{DASHBOARD_URL}/api/queue/gui/media/{media_id}"
        
        print_result('info', f"Downloading media: {media_id}")
        logger.debug(f"Downloading from: {url}")
        
        try:
            response = safe_request(
                'GET', url,
                headers={'X-API-Key': API_KEY},
                timeout=120,
                stream=True
            )
            
            if response.status_code == 200:
                content_length = response.headers.get('Content-Length', 'unknown')
                print_result('info', f"  File size: {content_length} bytes")
                
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                actual_size = save_path.stat().st_size
                print_result('success', f"  Saved to: {save_path} ({actual_size} bytes)")
                return True
            
            elif response.status_code == 404:
                print_result('warning', f"  Media not found: {media_id}")
                return False
            
            else:
                print_result('error', f"  Download failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print_result('error', f"  Download error: {e}")
            logger.exception(f"Error downloading media: {e}")
            return False
    
    def create_job(self, post: Dict[str, Any]) -> bool:
        """Create a job folder for a pending post."""
        post_id = post.get('id', 'unknown')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        job_id = f"job_{timestamp}_{post_id}"
        job_dir = self.pending_dir / job_id
        
        print_result('info', f"Creating job: {job_id}")
        
        try:
            # Check for duplicates
            existing = list(self.pending_dir.glob(f"*_{post_id}"))
            if existing:
                print_result('warning', f"  Job already exists: {existing[0].name}")
                return False
            
            job_dir.mkdir(parents=True, exist_ok=True)
            
            # Build job metadata
            # Start with all original post data to ensure we capture everything
            job_data = post.copy()
            
            # Update/Override with local specific fields
            job_data.update({
                'job_id': job_id,
                'media': [],  # Will be populated with local paths below
                'status': 'pending',
                'downloaded_at': datetime.now().isoformat(),
                'fetched_from': DASHBOARD_URL
            })
            
            # Ensure essential fields exist even if missing from API
            defaults = {
                'caption': '',
                'hashtags': [],
                'account': 'personal',
                'media_source': post.get('media', []) # Keep original media metadata
            }
            for k, v in defaults.items():
                if k not in job_data:
                    job_data[k] = v
            
            # Download media files
            media_items = post.get('media', [])
            for i, media in enumerate(media_items, 1):
                media_id = media.get('id')
                original_filename = media.get('filename', f'media_{i}.jpg')
                ext = Path(original_filename).suffix or '.jpg'
                local_filename = f"media_{i}{ext}"
                local_path = job_dir / local_filename
                
                if media_id and self.download_media(media_id, local_path):
                    job_data['media'].append({
                        'type': media.get('type', 'image'),
                        'local_path': local_filename,
                        'original_filename': original_filename,
                        'media_id': media_id
                    })
            
            # Save job.json
            job_file = job_dir / 'job.json'
            with open(job_file, 'w', encoding='utf-8') as f:
                json.dump(job_data, f, indent=2, ensure_ascii=False)
            
            print_result('success', f"  Job created: {job_dir}")
            print_result('info', f"    Platform: {job_data.get('platform', 'unknown')}")
            print_result('info', f"    Media files: {len(job_data['media'])}")
            
            caption = job_data.get('caption', '')
            caption_preview = caption[:50] + '...' if caption and len(caption) > 50 else caption
            print_result('info', f"    Caption: {caption_preview}")
            
            return True
            
        except Exception as e:
            print_result('error', f"  Job creation failed: {e}")
            logger.exception(f"Error creating job: {e}")
            
            if job_dir.exists():
                try:
                    import shutil
                    shutil.rmtree(job_dir)
                except Exception:
                    pass
            
            return False
    
    def run_once(self) -> int:
        """Run a single fetch cycle."""
        self.cycle_count += 1
        print_cycle_header(self.cycle_count)
        
        posts = self.fetch_pending_posts()
        
        if not posts:
            print_result('info', "Nothing to download this cycle")
            return 0
        
        created = 0
        for post in posts:
            if self.create_job(post):
                created += 1
        
        print_result('success', f"Cycle complete: {created} job(s) created")
        return created
    
    def run_forever(self):
        """Run the fetch loop continuously."""
        print_banner()
        
        print("Starting continuous fetch loop...")
        print(f"Will poll every {POLL_INTERVAL} minute(s)")
        print("Press Ctrl+C to stop\n")
        
        # Run immediately
        self.run_once()
        
        # Schedule regular runs
        schedule.every(POLL_INTERVAL).minutes.do(self.run_once)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(10)  # Check schedule every 10 seconds
        except KeyboardInterrupt:
            print("\n\nFetcher stopped by user (Ctrl+C)")
            logger.info("Fetcher stopped by user")


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def health_check() -> bool:
    """Test connectivity to the dashboard API."""
    print("\n" + "=" * 70)
    print("   SOCIAL DASHBOARD FETCHER - HEALTH CHECK")
    print("=" * 70)
    print()
    
    print(f"   Dashboard URL:  {DASHBOARD_URL}")
    print(f"   Queue Dir:      {QUEUE_DIR}")
    print(f"   API Key:        {'*' * 16}{API_KEY[-4:] if len(API_KEY) > 4 else 'NOT SET!'}")
    print()
    
    # Check 1: API key is set
    if not API_KEY or API_KEY == 'PUT_YOUR_API_KEY_HERE':
        print("   ✗ FAIL: API_KEY is not set in .env file")
        return False
    print("   ✓ API key is configured")
    
    # Check 2: Queue directory exists
    if not QUEUE_DIR.exists():
        print(f"   ✗ FAIL: Queue directory does not exist: {QUEUE_DIR}")
        return False
    print(f"   ✓ Queue directory exists")
    
    # Check 3: API connectivity
    url = f"{DASHBOARD_URL}/api/queue/gui/pending"
    print(f"\n   Testing API connection...")
    print(f"   URL: {url}")
    
    try:
        start_time = time.time()
        response = safe_request(
            'GET', url,
            headers={'X-API-Key': API_KEY},
            timeout=15
        )
        elapsed = time.time() - start_time
        
        print(f"   Response: HTTP {response.status_code} ({elapsed:.2f}s)")
        
        if response.status_code == 200:
            posts = response.json()
            print(f"\n   ✓ SUCCESS: API connection working!")
            print(f"   ✓ Found {len(posts)} pending post(s)")
            return True
        
        elif response.status_code == 204:
            print(f"\n   ✓ SUCCESS: API connection working!")
            print(f"   ✓ No pending posts (this is fine)")
            return True
        
        elif response.status_code == 401:
            print(f"\n   ✗ FAIL: Authentication failed (401)")
            print(f"   ✗ Your API_KEY doesn't match the server's WINDOWS_WORKER_API_KEY")
            return False
        
        elif response.status_code == 404:
            print(f"\n   ✗ FAIL: Endpoint not found (404)")
            print(f"   ✗ The /api/queue/gui/pending route is not registered on server")
            return False
        
        else:
            print(f"\n   ✗ FAIL: Unexpected status code: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except SecurityError as e:
        print(f"\n   ✗ FAIL: Security error - {e}")
        return False
    
    except requests.exceptions.ConnectionError as e:
        print(f"\n   ✗ FAIL: Could not connect to {DASHBOARD_URL}")
        print(f"   Error: {str(e)[:100]}")
        return False
    
    except requests.exceptions.Timeout:
        print(f"\n   ✗ FAIL: Connection timed out (15s)")
        return False
    
    except Exception as e:
        print(f"\n   ✗ FAIL: Unexpected error - {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Social Dashboard Queue Fetcher',
        epilog='SECURITY: Only accesses social.sterlingcooley.com'
    )
    parser.add_argument('--once', action='store_true', help='Fetch once and exit')
    parser.add_argument('--health', action='store_true', help='Test connectivity')
    args = parser.parse_args()
    
    if args.health:
        success = health_check()
        print("\n" + "=" * 70)
        sys.exit(0 if success else 1)
    
    if not API_KEY or API_KEY == 'PUT_YOUR_API_KEY_HERE':
        print("ERROR: API_KEY not set!")
        print("Edit C:\\SocialWorker\\.env and set your API key")
        sys.exit(1)
    
    fetcher = QueueFetcher()
    
    if args.once:
        count = fetcher.run_once()
        print(f"\nFetched {count} job(s)")
    else:
        fetcher.run_forever()


if __name__ == '__main__':
    main()
```

---

## Setup Scripts

### setup_worker.ps1

```powershell
# ═══════════════════════════════════════════════════════════════════════════════
# SOCIAL WORKER SETUP SCRIPT
# Run this as Administrator on the Windows 10 machine
# ═══════════════════════════════════════════════════════════════════════════════

Write-Host "Setting up Social Dashboard Queue Fetcher..." -ForegroundColor Cyan

# Create directories
Write-Host "Creating directories..."
New-Item -ItemType Directory -Force -Path "C:\SocialWorker" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\SocialWorker\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\PostQueue\pending" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\PostQueue\in_progress" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\PostQueue\completed" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\PostQueue\failed" | Out-Null

# Change to worker directory
Set-Location C:\SocialWorker

# Create virtual environment
Write-Host "Creating Python virtual environment..."
python -m venv venv

# Activate and install dependencies
Write-Host "Installing dependencies..."
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install requests schedule python-dotenv

# Copy files (assumes files are in current directory when running script)
# Or prompt user to copy files manually

Write-Host ""
Write-Host "=" * 60
Write-Host "SETUP COMPLETE" -ForegroundColor Green
Write-Host "=" * 60
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Copy fetcher.py to C:\SocialWorker\"
Write-Host "2. Create C:\SocialWorker\.env with your API key"
Write-Host "3. Run: python fetcher.py --health"
Write-Host ""
```

### healthcheck.py

```python
"""
Simple health check script.
Run this to verify connectivity before starting the fetcher.
"""
import sys
sys.path.insert(0, 'C:/SocialWorker')

from fetcher import health_check

if __name__ == '__main__':
    success = health_check()
    print()
    if success:
        print("Ready to run fetcher!")
        print("  python fetcher.py --once    # Test single fetch")
        print("  python fetcher.py           # Run continuously")
    else:
        print("Fix the issues above before running fetcher.")
    sys.exit(0 if success else 1)
```

---

## API Endpoints Expected

The fetcher expects these endpoints on social.sterlingcooley.com:

### GET /api/queue/gui/pending

**Request:**
```http
GET /api/queue/gui/pending HTTP/1.1
Host: social.sterlingcooley.com
X-API-Key: {WINDOWS_WORKER_API_KEY}
```

**Response (200 OK with posts):**
```json
[
  {
    "id": "abc123",
    "platform": "instagram",
    "scheduled_time": "2025-01-02T14:30:00Z",
    "caption": "Check out my new project! 🚀",
    "hashtags": ["#coding", "#ai"],
    "account": "personal",
    "link": null,
    "media": [
      {
        "id": "media_xyz789",
        "type": "image",
        "filename": "project_screenshot.jpg"
      }
    ]
  }
]
```

**Response (204 No Content):**
Empty - no pending posts

**Response (401 Unauthorized):**
```json
{"error": "Invalid API key"}
```

### GET /api/queue/gui/media/{media_id}

**Request:**
```http
GET /api/queue/gui/media/media_xyz789 HTTP/1.1
Host: social.sterlingcooley.com
X-API-Key: {WINDOWS_WORKER_API_KEY}
```

**Response (200 OK):**
Binary file data (image/video)

**Response (404 Not Found):**
```json
{"error": "Media not found"}
```

---

## Job.json Format

When a job is created, job.json contains:

```json
{
  "id": "abc123",
  "job_id": "job_20250102_143022_abc123",
  "platform": "instagram",
  "scheduled_time": "2025-01-02T14:30:00Z",
  "caption": "Check out my new project! 🚀",
  "hashtags": ["#coding", "#ai"],
  "account": "personal",
  "link": null,
  "media": [
    {
      "type": "image",
      "local_path": "media_1.jpg",
      "original_filename": "project_screenshot.jpg",
      "media_id": "media_xyz789"
    }
  ],
  "status": "pending",
  "created_at": "2025-01-02T14:30:22.123456",
  "fetched_from": "https://social.sterlingcooley.com"
}
```

---

## Usage

### Test Connectivity
```powershell
cd C:\SocialWorker
.\venv\Scripts\Activate.ps1
python fetcher.py --health
```

**Expected Output:**
```
============================================================
SOCIAL DASHBOARD FETCHER - HEALTH CHECK
============================================================

Dashboard URL: https://social.sterlingcooley.com
Queue Directory: C:\PostQueue
API Key: ****************************61ce

✓ API key is configured
✓ Queue directory exists: C:\PostQueue

Testing API connection: https://social.sterlingcooley.com/api/queue/gui/pending
✓ API connection successful (200 OK)
  Found 0 pending post(s)
```

### Fetch Once (Testing)
```powershell
python fetcher.py --once
```

### Run Continuously
```powershell
python fetcher.py
```

### Install as Windows Service
```powershell
# As Administrator
choco install nssm -y

nssm install SocialFetcher "C:\SocialWorker\venv\Scripts\python.exe" "C:\SocialWorker\fetcher.py"
nssm set SocialFetcher AppDirectory "C:\SocialWorker"
nssm set SocialFetcher AppStdout "C:\SocialWorker\logs\fetcher_stdout.log"
nssm set SocialFetcher AppStderr "C:\SocialWorker\logs\fetcher_stderr.log"
nssm set SocialFetcher AppRotateFiles 1
nssm set SocialFetcher AppRotateBytes 10485760

Start-Service SocialFetcher
```

---

## Troubleshooting

### "Connection refused" or "Connection error"
- Check that social.sterlingcooley.com is accessible from this machine
- Test: `curl https://social.sterlingcooley.com` or `Invoke-WebRequest https://social.sterlingcooley.com`
- Check firewall settings

### "401 Unauthorized"
- API key doesn't match server's WINDOWS_WORKER_API_KEY
- Check .env file has correct API_KEY value
- Check server logs for authentication errors

### "Security violation" errors
- The fetcher is trying to access a URL outside social.sterlingcooley.com
- This should never happen unless there's a bug or the server returned a bad redirect
- Check server responses for unexpected redirect URLs

### Jobs created but media missing
- Check logs for download errors
- Verify /api/queue/gui/media/:id endpoint is working on server
- Test: `curl -H "X-API-Key: your-key" https://social.sterlingcooley.com/api/queue/gui/media/test-id`

### Fetcher runs but no jobs created
- Check that posts are actually pending in the dashboard
- Posts must have scheduled_time <= now AND status = 'queued'
- Check dashboard database to verify post state

---

## Debugging Commands

```powershell
# Check pending jobs folder
Get-ChildItem C:\PostQueue\pending

# View latest job
Get-ChildItem C:\PostQueue\pending | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { Get-Content "$($_.FullName)\job.json" }

# View fetcher logs
Get-Content C:\SocialWorker\logs\fetcher.log -Tail 50

# Watch logs in real-time
Get-Content C:\SocialWorker\logs\fetcher.log -Wait

# Check service status (if running as service)
Get-Service SocialFetcher
```