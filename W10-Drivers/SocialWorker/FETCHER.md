# FETCHER.md - Windows 10 Content Fetcher

## Overview

The Fetcher runs on **Windows 10** and has ONE job: download pending posts from your Social Dashboard and save them locally for the Poster (running on Ubuntu) to use.

**CRITICAL SECURITY RULE**: Playwright/requests on this machine can ONLY access `social.sterlingcooley.com`. No other domains. Ever. This machine will be controlled by external HID input for actual social media posting.

```
┌─────────────────────────────────────────────────────────────────┐
│                         WINDOWS 10 VM                            │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  FETCHER (this component)                                 │  │
│   │  - Polls social.sterlingcooley.com/api/queue/pending     │  │
│   │  - Downloads media files                                  │  │
│   │  - Saves jobs to C:\PostQueue\pending\                    │  │
│   │  - NEVER touches Facebook, Instagram, or any other site  │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  REAL CHROME BROWSER (manual/HID controlled)              │  │
│   │  - Opened and controlled by Ubuntu via HID input          │  │
│   │  - Logs into Facebook, Instagram normally                 │  │
│   │  - Receives mouse/keyboard from virtual Logitech device   │  │
│   │  - NO automation libraries touch this browser             │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  C:\PostQueue\                                            │  │
│   │  ├── pending\        ← Fetcher writes here                │  │
│   │  ├── in_progress\    ← Ubuntu moves jobs here             │  │
│   │  ├── completed\      ← Success                            │  │
│   │  └── failed\         ← Failures                           │  │
│   └──────────────────────────────────────────────────────────┘  │
│                              ▲                                   │
│                              │ VNC screen capture                │
│                              │ Virtual HID input                 │
│                              ▼                                   │
└──────────────────────────────┼───────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │     UBUNTU VM       │
                    │   (Poster/AI)       │
                    └─────────────────────┘
```

---

## Security: Domain Allowlist

The Fetcher uses a strict domain allowlist. This is non-negotiable.

```python
# ONLY these domains are allowed
ALLOWED_DOMAINS = [
    'social.sterlingcooley.com',
]

# If any code tries to access another domain, it MUST fail
```

---

## Installation

### Step 1: Create Directory Structure

```powershell
# Create directories
mkdir C:\SocialWorker
mkdir C:\SocialWorker\logs
mkdir C:\PostQueue
mkdir C:\PostQueue\pending
mkdir C:\PostQueue\in_progress
mkdir C:\PostQueue\completed
mkdir C:\PostQueue\failed
```

### Step 2: Create Virtual Environment

```powershell
cd C:\SocialWorker
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies

Create `C:\SocialWorker\requirements.txt`:

```text
# Fetcher dependencies - minimal footprint
requests>=2.31.0
schedule>=1.2.0
python-dotenv>=1.0.0
```

```powershell
pip install -r requirements.txt
```

**NOTE**: We use `requests` instead of Playwright for the Fetcher. It's simpler and has no browser fingerprint. The Fetcher only needs to make HTTP API calls.

### Step 4: Create Configuration

Create `C:\SocialWorker\.env`:

```env
# Social Dashboard API
DASHBOARD_URL=https://social.sterlingcooley.com
API_KEY=your-api-key-ending-in-61ce

# Local paths
QUEUE_DIR=C:\PostQueue

# Polling interval (minutes)
POLL_INTERVAL=5
```

---

## Fetcher Code

Create `C:\SocialWorker\fetcher.py`:

```python
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
            print(f"✓ API connection successful")
            print(f"  URL: {DASHBOARD_URL}")
            print(f"  Status: {response.status_code}")
            return True
        elif response.status_code == 401:
            print(f"✗ API key invalid or missing")
            return False
        else:
            print(f"✗ Unexpected status: {response.status_code}")
            return False
            
    except SecurityError as e:
        print(f"✗ Security error: {e}")
        return False
    except Exception as e:
        print(f"✗ Connection failed: {e}")
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
```

---

## Usage

### Test Connectivity

```powershell
cd C:\SocialWorker
.\venv\Scripts\Activate.ps1

python fetcher.py --health
# Expected: ✓ API connection successful
```

### Fetch Once (Testing)

```powershell
python fetcher.py --once
# Expected: Fetched X job(s)

# Check results
Get-ChildItem C:\PostQueue\pending
```

### Run Continuously

```powershell
python fetcher.py
# Polls every 5 minutes
```

### Install as Windows Service

```powershell
# As Administrator
choco install nssm -y

nssm install SocialFetcher "C:\SocialWorker\venv\Scripts\python.exe" "C:\SocialWorker\fetcher.py"
nssm set SocialFetcher AppDirectory "C:\SocialWorker"
nssm set SocialFetcher AppStdout "C:\SocialWorker\logs\fetcher_stdout.log"
nssm set SocialFetcher AppStderr "C:\SocialWorker\logs\fetcher_stderr.log"

Start-Service SocialFetcher
```

---

## Job Folder Structure

When a post is fetched, the Fetcher creates:

```
C:\PostQueue\pending\job_20241230_143022_abc123\
├── job.json          # Metadata for the Poster
└── media_1.jpg       # Downloaded image/video
```

### job.json Format

```json
{
  "id": "abc123",
  "job_id": "job_20241230_143022_abc123",
  "platform": "facebook",
  "scheduled_time": "2024-12-30T14:30:00Z",
  "caption": "Check out my new project! 🚀",
  "media": [
    {
      "type": "image",
      "local_path": "media_1.jpg",
      "original_filename": "project_screenshot.jpg"
    }
  ],
  "link": "https://example.com/project",
  "status": "pending",
  "created_at": "2024-12-30T14:30:22.123456",
  "fetched_from": "https://social.sterlingcooley.com"
}
```

---

## Security Notes

1. **Domain Allowlist**: The `ALLOWED_DOMAINS` set contains ONLY `social.sterlingcooley.com`. Any attempt to access other URLs will raise a `SecurityError`.

2. **No Browser Automation**: This script uses `requests` library only - no Playwright, no Selenium, no browser fingerprint.

3. **No Social Media Access**: The Fetcher NEVER touches Facebook, Instagram, Twitter, or any social platform. That's the Poster's job via HID input.

4. **API Key Security**: Store the API key in `.env` file, not in code. The `.env` file should not be committed to version control.

---

## Troubleshooting

### "API key invalid"
- Check `.env` file has correct `API_KEY`
- Verify key on dashboard matches

### "Connection failed"
- Check Windows firewall allows outbound HTTPS
- Verify `social.sterlingcooley.com` is reachable
- Check DNS resolution

### "SecurityError: Domain not in allowlist"
- This is correct behavior - the code is blocking access to non-allowed domains
- If you need to add a domain, modify `ALLOWED_DOMAINS` (but think carefully first)

### Jobs not appearing
- Check dashboard has posts scheduled for "now" or past
- Verify posts are for GUI platforms (facebook, instagram)
- Check fetcher logs: `C:\SocialWorker\logs\fetcher.log`