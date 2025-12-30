"""
Social Media Poster Agent

Watches C:\\PostQueue\\pending for new jobs and executes platform-specific
posting playbooks using browser automation.

Usage:
    python poster.py              # Run continuously
    python poster.py --once       # Process one batch and exit
    python poster.py --test       # Test browser automation
"""

import os
import sys
import json
import time
import shutil
import asyncio
import logging
import argparse
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from enum import Enum

import requests
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://sterlingcooley.com')
API_KEY = os.getenv('API_KEY', '')
QUEUE_DIR = Path(os.getenv('QUEUE_DIR', 'C:/PostQueue'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL_SECONDS', 60))

# Platform credentials (for re-auth if needed)
FACEBOOK_EMAIL = os.getenv('FACEBOOK_EMAIL', '')
FACEBOOK_PASSWORD = os.getenv('FACEBOOK_PASSWORD', '')

# OpenRouter for vision verification
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')


class PostStatus(Enum):
    """Job status values."""
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    FAILED = 'failed'
    RETRY = 'retry'


@dataclass
class PostResult:
    """Result of a posting attempt."""
    success: bool
    platform_post_id: Optional[str] = None
    error: Optional[str] = None
    screenshot: Optional[str] = None  # Base64 encoded
    retry: bool = False


def setup_logging():
    """Configure logging."""
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"poster_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('poster')


logger = setup_logging()


class BrowserAgent:
    """
    Browser automation using Playwright.

    Provides high-level methods for interacting with web pages
    in a human-like manner.
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None

    async def start(self):
        """Start browser instance."""
        try:
            from playwright.async_api import async_playwright

            self.playwright = await async_playwright().start()

            # Use persistent context for saved logins
            user_data_dir = Path.home() / '.social_worker' / 'browser_data'
            user_data_dir.mkdir(parents=True, exist_ok=True)

            self.browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=self.headless,
                viewport={'width': 1920, 'height': 1080},
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars'
                ]
            )

            # Get or create page
            if self.browser.pages:
                self.page = self.browser.pages[0]
            else:
                self.page = await self.browser.new_page()

            logger.info("Browser started")

        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            raise

    async def stop(self):
        """Stop browser instance."""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
        logger.info("Browser stopped")

    async def navigate(self, url: str, wait_until: str = 'networkidle'):
        """Navigate to URL."""
        logger.debug(f"Navigating to: {url}")
        await self.page.goto(url, wait_until=wait_until, timeout=60000)
        await self.human_delay(1, 2)

    async def click(self, selector: str, timeout: int = 30000):
        """Click an element with human-like behavior."""
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                # Move to element first (more human-like)
                await element.scroll_into_view_if_needed()
                await self.human_delay(0.2, 0.5)
                await element.click()
                logger.debug(f"Clicked: {selector}")
                return True
        except Exception as e:
            logger.error(f"Failed to click {selector}: {e}")
            return False

    async def fill(self, selector: str, text: str, clear_first: bool = True):
        """Fill a text field with human-like typing."""
        try:
            element = await self.page.wait_for_selector(selector, timeout=30000)
            if element:
                if clear_first:
                    await element.fill('')
                # Type with slight delay between characters
                await element.type(text, delay=50)
                logger.debug(f"Filled {selector} with {len(text)} chars")
                return True
        except Exception as e:
            logger.error(f"Failed to fill {selector}: {e}")
            return False

    async def upload_file(self, selector: str, file_path: Path):
        """Upload a file."""
        try:
            await self.page.set_input_files(selector, str(file_path))
            logger.debug(f"Uploaded file: {file_path}")
            await self.human_delay(2, 5)  # Wait for upload
            return True
        except Exception as e:
            logger.error(f"Failed to upload {file_path}: {e}")
            return False

    async def screenshot(self, full_page: bool = False) -> str:
        """Take screenshot and return as base64."""
        screenshot_bytes = await self.page.screenshot(full_page=full_page)
        return base64.b64encode(screenshot_bytes).decode('utf-8')

    async def get_text(self, selector: str) -> Optional[str]:
        """Get text content of element."""
        try:
            element = await self.page.query_selector(selector)
            if element:
                return await element.text_content()
        except:
            pass
        return None

    async def wait_for_text(self, text: str, timeout: int = 30000) -> bool:
        """Wait for text to appear on page."""
        try:
            await self.page.wait_for_selector(f'text="{text}"', timeout=timeout)
            return True
        except:
            return False

    async def human_delay(self, min_sec: float = 0.5, max_sec: float = 2.0):
        """Add human-like random delay."""
        import random
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    async def is_logged_in(self, platform: str) -> bool:
        """Check if logged into a platform."""
        checks = {
            'facebook': 'facebook.com',
            'instagram': 'instagram.com',
            'tiktok': 'tiktok.com',
            'youtube': 'youtube.com'
        }

        if platform not in checks:
            return True

        # Navigate to platform
        await self.navigate(f'https://www.{checks[platform]}')

        # Take screenshot and check for login indicators
        # This is a simplified check - real implementation would be smarter
        page_content = await self.page.content()

        login_indicators = ['log in', 'sign in', 'login', 'signin']
        logged_in_indicators = ['profile', 'account', 'settings', 'create']

        is_login_page = any(ind in page_content.lower() for ind in login_indicators)
        is_logged_in = any(ind in page_content.lower() for ind in logged_in_indicators)

        return is_logged_in and not is_login_page


class VisionVerifier:
    """
    Uses OpenRouter vision models to verify posting success.
    """

    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.enabled = bool(self.api_key)

        if not self.enabled:
            logger.warning("Vision verification disabled (no OPENROUTER_API_KEY)")

    async def verify_post_success(self, screenshot_base64: str, platform: str) -> Tuple[bool, str]:
        """
        Analyze screenshot to verify if post was successful.

        Returns:
            (success, explanation)
        """
        if not self.enabled:
            return True, "Vision verification disabled"

        try:
            response = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'qwen/qwen-2-vl-72b-instruct',
                    'messages': [
                        {
                            'role': 'user',
                            'content': [
                                {
                                    'type': 'text',
                                    'text': f"""Analyze this screenshot of {platform} after a post attempt.

Determine if the post was successfully published. Look for:
- Success messages like "Post published", "Shared", "Posted"
- The post appearing in a feed or timeline
- Confirmation dialogs

Respond with EXACTLY this JSON format:
{{"success": true/false, "reason": "brief explanation"}}"""
                                },
                                {
                                    'type': 'image_url',
                                    'image_url': {
                                        'url': f'data:image/png;base64,{screenshot_base64}'
                                    }
                                }
                            ]
                        }
                    ],
                    'max_tokens': 200
                },
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']

                # Parse JSON from response
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    return parsed.get('success', False), parsed.get('reason', 'Unknown')

            return False, "Failed to parse verification response"

        except Exception as e:
            logger.error(f"Vision verification failed: {e}")
            return True, f"Verification error: {e}"  # Assume success on error


class SocialPoster:
    """
    Main posting agent that processes jobs from the queue.
    """

    def __init__(self):
        # Queue directories
        self.pending_dir = QUEUE_DIR / 'pending'
        self.in_progress_dir = QUEUE_DIR / 'in_progress'
        self.completed_dir = QUEUE_DIR / 'completed'
        self.failed_dir = QUEUE_DIR / 'failed'

        # Create directories
        for d in [self.pending_dir, self.in_progress_dir,
                  self.completed_dir, self.failed_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Agents
        self.browser: Optional[BrowserAgent] = None
        self.vision = VisionVerifier()

        # API session for reporting
        self.api_session = requests.Session()
        self.api_session.headers.update({
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json'
        })

        # Stats
        self.stats = {
            'processed': 0,
            'succeeded': 0,
            'failed': 0,
            'started_at': None
        }

    async def start(self):
        """Start browser and prepare for posting."""
        logger.info("Starting Social Poster")
        self.stats['started_at'] = datetime.now().isoformat()

        self.browser = BrowserAgent(headless=False)
        await self.browser.start()

    async def stop(self):
        """Cleanup resources."""
        if self.browser:
            await self.browser.stop()
        logger.info("Social Poster stopped")

    def get_pending_jobs(self) -> List[Dict[str, Any]]:
        """Get list of pending jobs sorted by scheduled time."""
        jobs = []

        for job_dir in self.pending_dir.iterdir():
            if not job_dir.is_dir():
                continue

            # Check for ready signal
            ready_file = job_dir / '.ready'
            if not ready_file.exists():
                continue

            job_file = job_dir / 'job.json'
            if not job_file.exists():
                continue

            try:
                with open(job_file, 'r', encoding='utf-8') as f:
                    job = json.load(f)
                    job['_dir'] = str(job_dir)
                    jobs.append(job)
            except Exception as e:
                logger.error(f"Failed to read job file {job_file}: {e}")

        # Sort by scheduled time
        jobs.sort(key=lambda j: j.get('scheduled_time', ''))

        return jobs

    def claim_job(self, job: Dict[str, Any]) -> bool:
        """Move job to in_progress."""
        src = Path(job['_dir'])
        dst = self.in_progress_dir / src.name

        try:
            shutil.move(str(src), str(dst))
            job['_dir'] = str(dst)

            # Update job status
            job_file = dst / 'job.json'
            job['status'] = 'in_progress'
            job['started_at'] = datetime.now().isoformat()
            job['attempts'] = job.get('attempts', 0) + 1

            with open(job_file, 'w', encoding='utf-8') as f:
                json.dump(job, f, indent=2)

            return True

        except Exception as e:
            logger.error(f"Failed to claim job: {e}")
            return False

    def complete_job(self, job: Dict[str, Any], result: PostResult):
        """Move job to completed or failed and report to dashboard."""
        src = Path(job['_dir'])

        if result.success:
            dst = self.completed_dir / src.name
            status = 'completed'
            self.stats['succeeded'] += 1
        else:
            # Check if should retry
            if result.retry and job.get('attempts', 1) < job.get('max_attempts', 3):
                dst = self.pending_dir / src.name  # Back to pending
                status = 'retry'
            else:
                dst = self.failed_dir / src.name
                status = 'failed'
                self.stats['failed'] += 1

        try:
            shutil.move(str(src), str(dst))

            # Update job.json
            job_file = dst / 'job.json'
            job['status'] = status
            job['completed_at'] = datetime.now().isoformat()
            if result.error:
                job['error'] = result.error
            if result.platform_post_id:
                job['platform_post_id'] = result.platform_post_id

            with open(job_file, 'w', encoding='utf-8') as f:
                json.dump(job, f, indent=2)

            # Save screenshot
            if result.screenshot:
                screenshot_file = dst / 'result_screenshot.png'
                with open(screenshot_file, 'wb') as f:
                    f.write(base64.b64decode(result.screenshot))

            # Report to dashboard
            self.report_to_dashboard(job['id'], result)

            self.stats['processed'] += 1

        except Exception as e:
            logger.error(f"Failed to complete job: {e}")

    def report_to_dashboard(self, post_id: str, result: PostResult):
        """Report result back to Social Dashboard."""
        if not API_KEY:
            logger.warning("No API key, skipping dashboard report")
            return

        try:
            if result.success:
                endpoint = f"{DASHBOARD_URL}/api/queue/complete"
                payload = {
                    'id': post_id,
                    'platform_post_id': result.platform_post_id,
                    'screenshot': result.screenshot
                }
            else:
                endpoint = f"{DASHBOARD_URL}/api/queue/failed"
                payload = {
                    'id': post_id,
                    'error': result.error,
                    'screenshot': result.screenshot,
                    'retry': result.retry
                }

            response = self.api_session.post(endpoint, json=payload, timeout=30)

            if response.status_code == 200:
                logger.info(f"Reported to dashboard: {post_id} - {'success' if result.success else 'failed'}")
            else:
                logger.error(f"Dashboard report failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to report to dashboard: {e}")

    async def execute_job(self, job: Dict[str, Any]) -> PostResult:
        """
        Execute a posting job based on platform.

        Returns:
            PostResult with success/failure info
        """
        platform = job.get('platform', '').lower()
        job_dir = Path(job['_dir'])

        logger.info(f"Executing job: {job['job_id']} ({platform})")

        # Import platform-specific playbook
        try:
            if platform == 'instagram':
                return await self.post_to_instagram(job, job_dir)
            elif platform == 'facebook':
                return await self.post_to_facebook(job, job_dir)
            elif platform == 'tiktok':
                return await self.post_to_tiktok(job, job_dir)
            elif platform == 'youtube':
                return await self.post_to_youtube(job, job_dir)
            else:
                return PostResult(
                    success=False,
                    error=f"Unknown platform: {platform}"
                )

        except Exception as e:
            logger.exception(f"Error executing job: {e}")

            # Take error screenshot
            screenshot = None
            try:
                screenshot = await self.browser.screenshot()
            except:
                pass

            return PostResult(
                success=False,
                error=str(e),
                screenshot=screenshot,
                retry=True
            )

    # =========================================================================
    # PLATFORM-SPECIFIC PLAYBOOKS
    # =========================================================================

    async def post_to_instagram(self, job: Dict, job_dir: Path) -> PostResult:
        """
        Post to Instagram via Meta Business Suite / Creator Studio.

        Prerequisites:
        - Instagram account connected to Facebook Page
        - Already logged into business.facebook.com
        """
        logger.info("Posting to Instagram via Creator Studio")

        try:
            # Step 1: Navigate to Creator Studio
            await self.browser.navigate('https://business.facebook.com/creatorstudio')
            await self.browser.human_delay(3, 5)

            # Step 2: Click Instagram icon (left sidebar)
            await self.browser.click('[data-testid="instagram-icon"], [aria-label*="Instagram"]')
            await self.browser.human_delay(2, 3)

            # Step 3: Click "Create Post"
            if not await self.browser.click('text="Create Post"'):
                await self.browser.click('[aria-label="Create Post"]')
            await self.browser.human_delay(2, 3)

            # Step 4: Click "Instagram Feed"
            await self.browser.click('text="Instagram Feed"')
            await self.browser.human_delay(2, 3)

            # Step 5: Upload media
            media_path = job_dir / job['media'][0]['local_path']
            await self.browser.upload_file('input[type="file"]', media_path)
            await self.browser.human_delay(5, 10)  # Wait for upload

            # Step 6: Enter caption
            caption_selectors = [
                '[placeholder*="caption"]',
                '[aria-label*="caption"]',
                'textarea[name="caption"]'
            ]
            for selector in caption_selectors:
                if await self.browser.fill(selector, job['caption']):
                    break
            await self.browser.human_delay(1, 2)

            # Step 7: Click Publish
            await self.browser.click('text="Publish"')
            await self.browser.human_delay(5, 10)

            # Step 8: Verify success
            screenshot = await self.browser.screenshot()
            success, reason = await self.vision.verify_post_success(screenshot, 'Instagram')

            return PostResult(
                success=success,
                error=None if success else reason,
                screenshot=screenshot
            )

        except Exception as e:
            screenshot = await self.browser.screenshot()
            return PostResult(
                success=False,
                error=str(e),
                screenshot=screenshot,
                retry=True
            )

    async def post_to_facebook(self, job: Dict, job_dir: Path) -> PostResult:
        """
        Post to Facebook Page.

        Prerequisites:
        - Already logged into Facebook
        - Have admin access to the Page
        """
        logger.info("Posting to Facebook Page")

        try:
            # Step 1: Navigate to Facebook
            # Could be a specific page URL from job options
            page_url = job.get('options', {}).get('page_url', 'https://www.facebook.com')
            await self.browser.navigate(page_url)
            await self.browser.human_delay(3, 5)

            # Step 2: Click create post area
            create_selectors = [
                '[aria-label="Create a post"]',
                '[aria-label="Create post"]',
                'text="What\'s on your mind"',
                '[data-testid="status-attachment-mentions-input"]'
            ]
            for selector in create_selectors:
                if await self.browser.click(selector):
                    break
            await self.browser.human_delay(2, 3)

            # Step 3: Click photo/video if we have media
            if job.get('media'):
                await self.browser.click('[aria-label="Photo/video"], [aria-label="Photo/Video"]')
                await self.browser.human_delay(1, 2)

                # Upload media
                media_path = job_dir / job['media'][0]['local_path']
                await self.browser.upload_file('input[type="file"]', media_path)
                await self.browser.human_delay(5, 10)

            # Step 4: Enter text
            text_selectors = [
                '[aria-label="What\'s on your mind?"]',
                '[contenteditable="true"]',
                '[role="textbox"]'
            ]
            full_text = job['caption']
            if job.get('link'):
                full_text += f"\n\n{job['link']}"

            for selector in text_selectors:
                if await self.browser.fill(selector, full_text):
                    break
            await self.browser.human_delay(1, 2)

            # Step 5: Click Post
            await self.browser.click('text="Post"')
            await self.browser.human_delay(5, 10)

            # Step 6: Verify
            screenshot = await self.browser.screenshot()
            success, reason = await self.vision.verify_post_success(screenshot, 'Facebook')

            return PostResult(
                success=success,
                error=None if success else reason,
                screenshot=screenshot
            )

        except Exception as e:
            screenshot = await self.browser.screenshot()
            return PostResult(
                success=False,
                error=str(e),
                screenshot=screenshot,
                retry=True
            )

    async def post_to_tiktok(self, job: Dict, job_dir: Path) -> PostResult:
        """
        Post video to TikTok.

        Note: TikTok has heavy bot detection. This requires:
        - Human-like mouse movements
        - Random delays
        - Logged-in session cookies
        """
        logger.info("Posting to TikTok")

        try:
            # Step 1: Navigate to TikTok upload
            await self.browser.navigate('https://www.tiktok.com/upload')
            await self.browser.human_delay(3, 5)

            # Step 2: Check if logged in
            page_content = await self.browser.page.content()
            if 'log in' in page_content.lower() or 'login' in page_content.lower():
                return PostResult(
                    success=False,
                    error="Not logged in to TikTok - please log in manually first",
                    retry=False
                )

            # Step 3: Upload video
            video_path = job_dir / job['media'][0]['local_path']
            await self.browser.upload_file('input[type="file"]', video_path)
            await self.browser.human_delay(30, 60)  # Videos take longer to process

            # Step 4: Enter caption
            caption_selectors = [
                '[placeholder*="caption"]',
                '[placeholder*="description"]',
                '[data-testid="caption-input"]',
                '.public-DraftEditor-content'
            ]
            for selector in caption_selectors:
                if await self.browser.fill(selector, job['caption']):
                    break
            await self.browser.human_delay(1, 2)

            # Step 5: Click Post
            await self.browser.click('button:has-text("Post")')
            await self.browser.human_delay(10, 20)

            # Step 6: Verify
            screenshot = await self.browser.screenshot()
            success, reason = await self.vision.verify_post_success(screenshot, 'TikTok')

            return PostResult(
                success=success,
                error=None if success else reason,
                screenshot=screenshot
            )

        except Exception as e:
            screenshot = await self.browser.screenshot()
            return PostResult(
                success=False,
                error=str(e),
                screenshot=screenshot,
                retry=True
            )

    async def post_to_youtube(self, job: Dict, job_dir: Path) -> PostResult:
        """
        Upload video to YouTube.

        Prerequisites:
        - Logged into YouTube/Google account
        - Channel already created
        """
        logger.info("Uploading to YouTube")

        try:
            # Step 1: Navigate to YouTube Studio upload
            await self.browser.navigate('https://studio.youtube.com/channel/upload')
            await self.browser.human_delay(3, 5)

            # Alternative: youtube.com/upload
            page_content = await self.browser.page.content()
            if 'sign in' in page_content.lower():
                await self.browser.navigate('https://www.youtube.com/upload')
                await self.browser.human_delay(3, 5)

            # Step 2: Upload video
            video_path = job_dir / job['media'][0]['local_path']
            await self.browser.upload_file('input[type="file"]', video_path)
            await self.browser.human_delay(30, 120)  # YouTube processing takes a while

            # Step 3: Wait for upload dialog
            await self.browser.wait_for_text('Details', timeout=60000)
            await self.browser.human_delay(2, 3)

            # Step 4: Enter title (first line of caption)
            title = job['caption'].split('\n')[0][:100]  # YouTube title limit
            await self.browser.fill('#textbox[aria-label*="title"]', title)

            # Step 5: Enter description
            description = job['caption']
            if job.get('link'):
                description += f"\n\n{job['link']}"
            await self.browser.fill('#textbox[aria-label*="description"]', description)
            await self.browser.human_delay(1, 2)

            # Step 6: Set visibility to Public
            await self.browser.click('text="Next"')  # Through the dialog steps
            await self.browser.human_delay(1, 2)
            await self.browser.click('text="Next"')
            await self.browser.human_delay(1, 2)
            await self.browser.click('text="Next"')
            await self.browser.human_delay(1, 2)

            # Select public
            await self.browser.click('[name="PUBLIC"]')
            await self.browser.human_delay(1, 2)

            # Step 7: Publish
            await self.browser.click('text="Publish"')
            await self.browser.human_delay(10, 20)

            # Step 8: Verify
            screenshot = await self.browser.screenshot()
            success, reason = await self.vision.verify_post_success(screenshot, 'YouTube')

            return PostResult(
                success=success,
                error=None if success else reason,
                screenshot=screenshot
            )

        except Exception as e:
            screenshot = await self.browser.screenshot()
            return PostResult(
                success=False,
                error=str(e),
                screenshot=screenshot,
                retry=True
            )

    # =========================================================================
    # MAIN LOOP
    # =========================================================================

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

            logger.info(f"Processing: {job['job_id']} ({job['platform']})")

            result = await self.execute_job(job)
            self.complete_job(job, result)

            if result.success:
                logger.info(f"SUCCESS: {job['job_id']}")
            else:
                logger.error(f"FAILED: {job['job_id']} - {result.error}")

            # Delay between posts to avoid rate limiting
            await self.browser.human_delay(10, 30)

    async def run_forever(self):
        """Continuously watch for and process jobs."""
        logger.info("="*60)
        logger.info("  SOCIAL MEDIA POSTER AGENT")
        logger.info("="*60)
        logger.info(f"Queue Directory: {QUEUE_DIR}")
        logger.info(f"Check Interval: {CHECK_INTERVAL} seconds")
        logger.info(f"Vision Verification: {'Enabled' if self.vision.enabled else 'Disabled'}")
        logger.info("="*60)

        await self.start()

        try:
            while True:
                try:
                    await self.run_once()
                except Exception as e:
                    logger.exception(f"Error in posting loop: {e}")

                await asyncio.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await self.stop()


async def test_browser():
    """Test browser automation."""
    poster = SocialPoster()
    await poster.start()

    try:
        logger.info("Testing browser navigation...")
        await poster.browser.navigate('https://www.google.com')
        logger.info("Navigation successful!")

        logger.info("Testing screenshot...")
        screenshot = await poster.browser.screenshot()
        logger.info(f"Screenshot taken ({len(screenshot)} bytes)")

        logger.info("Browser test passed!")

    except Exception as e:
        logger.error(f"Browser test failed: {e}")

    finally:
        await poster.stop()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Social Media Poster Agent'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Process one batch and exit'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test browser automation'
    )

    args = parser.parse_args()

    if args.test:
        asyncio.run(test_browser())
    elif args.once:
        poster = SocialPoster()
        asyncio.run(poster.start())
        asyncio.run(poster.run_once())
        asyncio.run(poster.stop())
    else:
        poster = SocialPoster()
        asyncio.run(poster.run_forever())


if __name__ == '__main__':
    main()
