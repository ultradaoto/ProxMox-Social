# UBUNTU-TEST-SKOOL.md
# Ubuntu Agent: Test Mode for Skool Posting

## OVERVIEW

We're testing the computer-use posting system using a **mock Skool page** hosted on the social dashboard. This allows us to verify the entire workflow works without posting to the real Skool.com.

**Test Page URL:**
```
https://social.sterlingcooley.com/test/skool
```

This page mimics the Skool.com interface and accepts posts just like the real thing, but doesn't actually publish anywhere.

---

## YOUR MISSION

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TEST MODE WORKFLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Poll API for ALL pending Skool posts                                    │
│     GET /api/queue/gui/pending                                              │
│     Filter: platform === "skool"                                            │
│                                                                             │
│  2. For EACH Skool post:                                                    │
│     a. Navigate Windows browser to: /test/skool                             │
│     b. Execute posting workflow on the test page                            │
│     c. Verify success via vision                                            │
│     d. Call API to mark complete: POST /api/queue/gui/complete              │
│     e. Move to next post                                                    │
│                                                                             │
│  3. Continue until all Skool posts are processed                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## IMPORTANT: TEST PAGE vs PRODUCTION

| Mode | URL | Purpose |
|------|-----|---------|
| **TEST** | `https://social.sterlingcooley.com/test/skool` | Safe testing, no real posts |
| Production | `https://www.skool.com/{group}` | Real posting (later) |

**For now, ALWAYS use the test page.** We'll switch to production URLs once testing is complete.

---

## WORKFLOW DETAILS

### Step 1: Get ALL Pending Skool Posts

```python
import requests

API_URL = "https://social.sterlingcooley.com"
API_KEY = "your-api-key"

def get_pending_skool_posts():
    """Fetch all pending posts, filter for Skool platform."""
    response = requests.get(
        f"{API_URL}/api/queue/gui/pending",
        headers={"X-API-Key": API_KEY},
        timeout=30
    )
    
    if response.status_code == 200:
        all_posts = response.json()
        # Filter for Skool posts only
        skool_posts = [p for p in all_posts if p.get('platform') == 'skool']
        print(f"Found {len(skool_posts)} pending Skool posts")
        return skool_posts
    
    elif response.status_code == 204:
        print("No pending posts")
        return []
    
    else:
        print(f"API error: {response.status_code}")
        return []
```

### Step 2: Process Each Post (One at a Time)

```python
def process_all_skool_posts():
    """Process all pending Skool posts sequentially."""
    
    posts = get_pending_skool_posts()
    
    if not posts:
        print("Nothing to post!")
        return
    
    print(f"\n{'='*60}")
    print(f"  PROCESSING {len(posts)} SKOOL POST(S)")
    print(f"{'='*60}\n")
    
    for i, post in enumerate(posts, 1):
        post_id = post.get('id')
        caption = post.get('caption', '')[:50]
        
        print(f"\n[{i}/{len(posts)}] Post ID: {post_id}")
        print(f"         Caption: {caption}...")
        
        try:
            # Execute the posting workflow
            success = execute_test_post(post)
            
            if success:
                # Mark as complete in API
                mark_post_complete(post_id)
                print(f"         ✓ COMPLETED")
            else:
                # Mark as failed in API
                mark_post_failed(post_id, "Posting verification failed")
                print(f"         ✗ FAILED")
                
        except Exception as e:
            mark_post_failed(post_id, str(e))
            print(f"         ✗ ERROR: {e}")
        
        # Brief pause between posts
        time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"  ALL POSTS PROCESSED")
    print(f"{'='*60}\n")
```

### Step 3: Execute Test Post (Navigate to Test Page)

```python
TEST_PAGE_URL = "https://social.sterlingcooley.com/test/skool"

def execute_test_post(post: dict) -> bool:
    """
    Execute posting workflow against the TEST page.
    
    This controls Windows via VNC/QMP to:
    1. Navigate browser to test page
    2. Fill in the post form
    3. Submit
    4. Verify success
    
    Returns True if successful, False otherwise.
    """
    post_id = post.get('id')
    caption = post.get('caption', '')
    has_media = len(post.get('media', [])) > 0
    
    print(f"         Navigating to test page...")
    
    # Step 1: Navigate to test page
    # (Use your existing VNC/QMP code to control Windows browser)
    navigate_browser_to(TEST_PAGE_URL)
    wait(2000)  # Wait for page load
    
    # Step 2: Capture screen and verify we're on the test page
    screen = capture_vnc_screenshot()
    analysis = analyze_with_vision(
        screen, 
        "Are we on the Skool test page? Do you see a post composer or create post area?"
    )
    
    if "error" in analysis.lower() or "not found" in analysis.lower():
        print(f"         Failed to load test page")
        return False
    
    print(f"         Test page loaded")
    
    # Step 3: Find and click the post input area
    click_element("The text area or input field to write a new post")
    wait(500)
    
    # Step 4: Type the caption
    print(f"         Typing caption...")
    type_text(caption, humanize=True)
    wait(500)
    
    # Step 5: Handle media upload if present
    if has_media:
        print(f"         Uploading media...")
        # Click upload button
        click_element("The image upload button or add photo button")
        wait(500)
        
        # The media file is on Windows at:
        # C:\PostQueue\pending\job_XXXXX_{post_id}\media_1.jpg
        # Type the path in the file dialog
        media_path = f"C:\\PostQueue\\pending\\*_{post_id}\\media_1.jpg"
        type_text(media_path, humanize=False)
        press_key("Enter")
        wait(2000)  # Wait for upload
    
    # Step 6: Click the Post/Submit button
    print(f"         Submitting post...")
    click_element("The Post or Submit button to publish the post")
    wait(3000)  # Wait for submission
    
    # Step 7: Verify success
    screen = capture_vnc_screenshot()
    verification = analyze_with_vision(
        screen,
        "Was the post submitted successfully? "
        "Look for: success message, post appearing in feed, or confirmation. "
        "Reply SUCCESS if posted, or FAILED if there's an error."
    )
    
    if "SUCCESS" in verification.upper():
        print(f"         Post verified successful")
        return True
    else:
        print(f"         Verification: {verification}")
        return False
```

### Step 4: Report Completion to API

```python
def mark_post_complete(post_id: str):
    """
    Tell the API that this post was successfully published.
    
    POST /api/queue/gui/complete
    Body: {"id": "post-id-here"}
    """
    response = requests.post(
        f"{API_URL}/api/queue/gui/complete",
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "id": post_id
        },
        timeout=30
    )
    
    if response.status_code == 200:
        print(f"         API updated: marked complete")
    else:
        print(f"         API update failed: {response.status_code}")


def mark_post_failed(post_id: str, error: str, retry: bool = True):
    """
    Tell the API that this post failed.
    
    POST /api/queue/gui/failed
    Body: {"id": "post-id", "error": "reason", "retry": true/false}
    """
    response = requests.post(
        f"{API_URL}/api/queue/gui/failed",
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "id": post_id,
            "error": error,
            "retry": retry
        },
        timeout=30
    )
    
    if response.status_code == 200:
        print(f"         API updated: marked failed")
    else:
        print(f"         API update failed: {response.status_code}")
```

---

## COMPLETE MAIN SCRIPT

```python
#!/usr/bin/env python3
"""
Ubuntu Poster Controller - Test Mode
Posts all pending Skool posts to the test page.
"""

import time
import requests
from datetime import datetime

# Configuration
API_URL = "https://social.sterlingcooley.com"
API_KEY = "your-api-key-here"
TEST_PAGE_URL = "https://social.sterlingcooley.com/test/skool"

# Import your existing computer-use modules
from vision_controller import VisionController
from input_controller import InputController

# Initialize controllers
vision = VisionController(vnc_host="192.168.100.X", vnc_port=5900)
input_ctrl = InputController(qmp_socket="/path/to/qmp.sock")


def get_pending_skool_posts():
    """Fetch all pending Skool posts from API."""
    try:
        response = requests.get(
            f"{API_URL}/api/queue/gui/pending",
            headers={"X-API-Key": API_KEY},
            timeout=30
        )
        
        if response.status_code == 200:
            all_posts = response.json()
            return [p for p in all_posts if p.get('platform') == 'skool']
        return []
    except Exception as e:
        print(f"API Error: {e}")
        return []


def mark_complete(post_id: str):
    """Mark post as successfully published."""
    requests.post(
        f"{API_URL}/api/queue/gui/complete",
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        json={"id": post_id},
        timeout=30
    )


def mark_failed(post_id: str, error: str):
    """Mark post as failed."""
    requests.post(
        f"{API_URL}/api/queue/gui/failed",
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        json={"id": post_id, "error": error, "retry": True},
        timeout=30
    )


def navigate_to_test_page():
    """Navigate Windows browser to the test page."""
    # Ctrl+L to focus address bar
    input_ctrl.key_combo(['ctrl', 'l'])
    time.sleep(0.3)
    
    # Type URL
    input_ctrl.type_text(TEST_PAGE_URL, humanize=False)
    time.sleep(0.2)
    
    # Press Enter
    input_ctrl.press_key('Return')
    time.sleep(3)  # Wait for page load


def find_and_click(element_description: str) -> bool:
    """Use vision to find element and click it."""
    screenshot = vision.capture_screen()
    
    prompt = f"""Find this UI element: {element_description}

Return the X,Y coordinates of the CENTER of this element.
Screen resolution is 1920x1080.
Format: X,Y (just numbers, nothing else)"""
    
    result = vision.analyze_screen(screenshot, prompt)
    
    try:
        x, y = map(int, result.strip().split(','))
        input_ctrl.click(x, y)
        return True
    except:
        print(f"Could not find element: {element_description}")
        return False


def verify_post_success() -> bool:
    """Check if post was successful via vision."""
    screenshot = vision.capture_screen()
    
    result = vision.analyze_screen(
        screenshot,
        "Was a post just submitted successfully? "
        "Look for success indicators like: post visible in feed, success message, "
        "or confirmation. Respond with just 'YES' or 'NO'."
    )
    
    return "YES" in result.upper()


def post_to_test_page(post: dict) -> bool:
    """Execute the full posting workflow for one post."""
    post_id = post['id']
    caption = post.get('caption', '')
    has_media = len(post.get('media', [])) > 0
    
    # Navigate to test page
    navigate_to_test_page()
    
    # Click compose area
    if not find_and_click("The text input area to write a new post"):
        return False
    time.sleep(0.5)
    
    # Type caption
    input_ctrl.type_text(caption, humanize=True)
    time.sleep(0.5)
    
    # Handle media if present
    if has_media:
        if not find_and_click("The image upload or add photo button"):
            return False
        time.sleep(0.5)
        
        # Type file path in dialog
        media_path = f"C:\\PostQueue\\pending\\*_{post_id}\\media_1.jpg"
        input_ctrl.type_text(media_path, humanize=False)
        input_ctrl.press_key('Return')
        time.sleep(2)
    
    # Click post button
    if not find_and_click("The Post or Submit button"):
        return False
    time.sleep(3)
    
    # Verify success
    return verify_post_success()


def main():
    """Main entry point - process all pending Skool posts."""
    print("\n" + "=" * 60)
    print("  UBUNTU POSTER - TEST MODE")
    print("  Target: " + TEST_PAGE_URL)
    print("=" * 60 + "\n")
    
    # Get pending posts
    posts = get_pending_skool_posts()
    
    if not posts:
        print("No pending Skool posts. Exiting.")
        return
    
    print(f"Found {len(posts)} pending Skool post(s)\n")
    
    # Process each post
    success_count = 0
    fail_count = 0
    
    for i, post in enumerate(posts, 1):
        post_id = post['id']
        print(f"[{i}/{len(posts)}] Processing: {post_id}")
        
        try:
            if post_to_test_page(post):
                mark_complete(post_id)
                print(f"         ✓ SUCCESS - marked complete\n")
                success_count += 1
            else:
                mark_failed(post_id, "Post verification failed")
                print(f"         ✗ FAILED\n")
                fail_count += 1
        except Exception as e:
            mark_failed(post_id, str(e))
            print(f"         ✗ ERROR: {e}\n")
            fail_count += 1
        
        time.sleep(2)  # Pause between posts
    
    # Summary
    print("=" * 60)
    print(f"  COMPLETE: {success_count} success, {fail_count} failed")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
```

---

## API ENDPOINTS YOU'LL USE

| Endpoint | Method | Purpose | Body |
|----------|--------|---------|------|
| `/api/queue/gui/pending` | GET | Get pending posts | - |
| `/api/queue/gui/complete` | POST | Mark post done | `{"id": "post-id"}` |
| `/api/queue/gui/failed` | POST | Mark post failed | `{"id": "post-id", "error": "reason", "retry": true}` |

---

## TEST CHECKLIST

Before running:
- [ ] Test page exists at `/test/skool`
- [ ] At least one Skool post is pending in the database
- [ ] Windows browser is open
- [ ] VNC connection to Windows works
- [ ] QMP input injection works
- [ ] API key is configured

Run sequence:
1. Run the script
2. Watch it navigate to the test page
3. Watch it type the caption
4. Watch it click Post
5. Verify it calls the API to mark complete
6. Check the dashboard - post should show as "published"

---

## EXPECTED CONSOLE OUTPUT

```
============================================================
  UBUNTU POSTER - TEST MODE
  Target: https://social.sterlingcooley.com/test/skool
============================================================

Found 3 pending Skool post(s)

[1/3] Processing: post-abc123
         Navigating to test page...
         Typing caption...
         Submitting post...
         ✓ SUCCESS - marked complete

[2/3] Processing: post-def456
         Navigating to test page...
         Typing caption...
         Uploading media...
         Submitting post...
         ✓ SUCCESS - marked complete

[3/3] Processing: post-ghi789
         Navigating to test page...
         Typing caption...
         Submitting post...
         ✗ FAILED

============================================================
  COMPLETE: 2 success, 1 failed
============================================================
```

---

## NEXT STEPS AFTER TESTING

Once the test page workflow works:

1. **Switch to real Skool.com** - Change `TEST_PAGE_URL` to the actual group URL
2. **Add more platforms** - Instagram, Facebook, TikTok
3. **Set up continuous monitoring** - Poll every 5 minutes instead of one-shot
4. **Add retry logic** - Retry failed posts after a delay

For now, focus on getting the test page workflow working end-to-end!