# Windows 10 Worker - API Integration Guide

This document describes how the Windows 10 automation worker should interact with the SC-Social API at `https://social.sterlingcooley.com`.

## Table of Contents

- [Authentication](#authentication)
- [Post Lifecycle](#post-lifecycle)
- [API Endpoints](#api-endpoints)
  - [GET /api/queue/gui/pending](#get-apiqueueguipending)
  - [GET /api/queue/gui/media/:id](#get-apiqueueguimediaid)
  - [POST /api/queue/gui/complete](#post-apiqueueguicomplete)
  - [POST /api/queue/gui/failed](#post-apiqueueguifailed)
  - [POST /api/queue/gui/heartbeat](#post-apiqueueguiheartbeat)
  - [POST /api/queue/gui/batch-report](#post-apiqueueguibatch-report)
- [Recommended Worker Architecture](#recommended-worker-architecture)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)

---

## Authentication

All API requests require the `X-API-Key` header:

```python
HEADERS = {
    "X-API-Key": "your-api-key-here",
    "Content-Type": "application/json"
}
```

The API key is stored in the worker's environment variables as `WINDOWS_WORKER_API_KEY`.

---

## Post Lifecycle

Posts follow a simple lifecycle with **NO RETRIES**:

```
┌───────────┐     ┌────────┐     ┌───────────┐
│ scheduled │ ──► │ queued │ ──► │ published │
└───────────┘     └────────┘     └───────────┘
                       │
                       ▼
                  ┌────────┐
                  │ failed │
                  └────────┘
```

| Status | Description |
|--------|-------------|
| `scheduled` | Post is waiting for its scheduled time |
| `queued` | Post is ready for worker to process |
| `published` | Post was successfully published |
| `failed` | Post failed (no retries - investigate manually) |

**Important:** There are no retries. If a post fails, it stays failed. This prevents queue blockage.

---

## API Endpoints

### GET /api/queue/gui/pending

**Purpose:** Fetch posts that are ready to be processed.

**When to call:** Poll every 30-60 seconds when worker is idle.

```python
import requests

response = requests.get(
    "https://social.sterlingcooley.com/api/queue/gui/pending",
    headers={"X-API-Key": API_KEY}
)

posts = response.json()
# Returns: List of post objects
```

**Response Example:**
```json
[
  {
    "id": "9e246ac8-b04b-458e-90ee-6ae69339aa34",
    "platform": "instagram_ultra",
    "platform_url": "https://www.instagram.com/ultraskool/",
    "scheduled_time": "2026-01-20T17:00:00.000Z",
    "caption": "Check out this amazing post! #health #wellness",
    "title": null,
    "email_members": false,
    "media": [
      {
        "id": "9e246ac8-b04b-458e-90ee-6ae69339aa34",
        "type": "image",
        "filename": "post_image.jpg",
        "url": null
      }
    ],
    "link": null,
    "hashtags": ["#health", "#wellness"],
    "mentions": [],
    "options": {
      "platform_url": "https://www.instagram.com/ultraskool/"
    }
  }
]
```

**Behavior:**
- Returns up to 10 posts at a time
- Only returns posts with `scheduled_time <= NOW`
- Automatically marks returned posts as `queued`
- Empty array `[]` means no posts are ready

**Worker Logic:**
```python
def poll_for_posts():
    response = requests.get(
        f"{API_BASE}/api/queue/gui/pending",
        headers=HEADERS
    )
    
    if response.status_code == 200:
        posts = response.json()
        for post in posts:
            process_post(post)
    
    # Sleep before next poll
    time.sleep(30)
```

---

### GET /api/queue/gui/media/:id

**Purpose:** Download media file for a post.

**When to call:** After receiving a post with media.

```python
def download_media(post_id, save_path):
    response = requests.get(
        f"https://social.sterlingcooley.com/api/queue/gui/media/{post_id}",
        headers={"X-API-Key": API_KEY},
        stream=True
    )
    
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    
    return False
```

**Response:**
- `200 OK` - Binary file stream with appropriate Content-Type
- `302 Redirect` - If media is external URL (follow redirect)
- `404 Not Found` - Media doesn't exist

---

### POST /api/queue/gui/complete

**Purpose:** Mark a post as successfully published.

**When to call:** ONLY after confirmed successful publication.

```python
def mark_complete(post_id, platform_post_id=None, screenshot_base64=None):
    response = requests.post(
        "https://social.sterlingcooley.com/api/queue/gui/complete",
        headers=HEADERS,
        json={
            "id": post_id,
            "platform_post_id": platform_post_id,  # Optional: ID from platform
            "screenshot": screenshot_base64         # Optional: Base64 PNG
        }
    )
    return response.json()
```

**Request Body:**
```json
{
  "id": "9e246ac8-b04b-458e-90ee-6ae69339aa34",
  "platform_post_id": "123456789",
  "screenshot": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**Response:**
```json
{
  "success": true
}
```

**Idempotent:** If called multiple times for same post, just acknowledges:
```json
{
  "success": true,
  "message": "Already published"
}
```

---

### POST /api/queue/gui/failed

**Purpose:** Mark a post as failed.

**When to call:** When post cannot be published.

**⚠️ IMPORTANT:** Failed posts are NOT retried. Only call this when you've exhausted all options.

```python
def mark_failed(post_id, error_message, screenshot_base64=None):
    response = requests.post(
        "https://social.sterlingcooley.com/api/queue/gui/failed",
        headers=HEADERS,
        json={
            "id": post_id,
            "error": error_message,
            "screenshot": screenshot_base64  # Optional
        }
    )
    return response.json()
```

**Request Body:**
```json
{
  "id": "9e246ac8-b04b-458e-90ee-6ae69339aa34",
  "error": "[Step: login] Could not find login button",
  "screenshot": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**Response:**
```json
{
  "success": true,
  "status": "failed"
}
```

**Idempotent:** Multiple calls for same post just acknowledge:
```json
{
  "success": true,
  "message": "Post already failed"
}
```

**Diagnostic Reports (No Post ID):**
If you need to report a general error (not tied to a specific post), omit the `id`:

```python
# Report worker-level error
requests.post(
    f"{API_BASE}/api/queue/gui/failed",
    headers=HEADERS,
    json={
        "error": "Browser crashed during initialization"
    }
)
# Returns: {"success": true, "message": "Diagnostic log received"}
```

---

### POST /api/queue/gui/heartbeat

**Purpose:** Report that worker is alive without touching the database.

**When to call:** Every 60 seconds while worker is running.

```python
def send_heartbeat():
    response = requests.post(
        "https://social.sterlingcooley.com/api/queue/gui/heartbeat",
        headers=HEADERS
    )
    return response.json()
```

**Response:**
```json
{
  "success": true,
  "server_time": "2026-01-20T10:15:30.123Z",
  "message": "Heartbeat received"
}
```

**Use Cases:**
- Prove worker is online
- Check API connectivity
- Sync server time
- NO database writes = fast & cheap

---

### POST /api/queue/gui/batch-report

**Purpose:** Send multiple diagnostic messages at once.

**When to call:** Periodically to upload accumulated logs.

```python
def send_batch_report(reports):
    response = requests.post(
        "https://social.sterlingcooley.com/api/queue/gui/batch-report",
        headers=HEADERS,
        json={
            "worker_id": "windows-worker-1",
            "reports": reports
        }
    )
    return response.json()

# Example usage
reports = [
    {"type": "info", "message": "Worker started", "timestamp": "2026-01-20T10:00:00Z"},
    {"type": "info", "message": "Processing post abc123", "timestamp": "2026-01-20T10:01:00Z"},
    {"type": "warning", "message": "Slow network detected", "timestamp": "2026-01-20T10:01:30Z"},
    {"type": "error", "message": "OSP detection failed", "timestamp": "2026-01-20T10:02:00Z"},
]

send_batch_report(reports)
```

**Request Body:**
```json
{
  "worker_id": "windows-worker-1",
  "reports": [
    {"type": "info", "message": "Worker started", "timestamp": "2026-01-20T10:00:00Z"},
    {"type": "error", "message": "OSP detection failed", "timestamp": "2026-01-20T10:02:00Z"}
  ]
}
```

**Report Types:**
- `info` - Informational (silently accepted, not logged)
- `warning` - Warning (silently accepted, not logged)
- `error` - Error (logged on server for debugging)

**Response:**
```json
{
  "success": true,
  "received": 4
}
```

---

## Recommended Worker Architecture

```python
import asyncio
import aiohttp
from datetime import datetime

class SocialWorker:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://social.sterlingcooley.com"
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        self.reports = []  # Accumulate diagnostic reports
    
    async def run(self):
        """Main worker loop"""
        while True:
            try:
                # Send heartbeat
                await self.heartbeat()
                
                # Poll for posts
                posts = await self.get_pending_posts()
                
                if posts:
                    for post in posts:
                        await self.process_post(post)
                else:
                    # No posts, wait before next poll
                    await asyncio.sleep(30)
                
                # Send accumulated reports periodically
                if len(self.reports) >= 10:
                    await self.flush_reports()
                    
            except Exception as e:
                self.log_error(f"Worker error: {e}")
                await asyncio.sleep(60)  # Wait before retry
    
    async def heartbeat(self):
        """Send heartbeat to prove worker is alive"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/queue/gui/heartbeat",
                headers=self.headers
            ) as resp:
                return await resp.json()
    
    async def get_pending_posts(self):
        """Fetch posts ready for processing"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/api/queue/gui/pending",
                headers=self.headers
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
    
    async def process_post(self, post):
        """Process a single post"""
        post_id = post["id"]
        platform = post["platform"]
        
        self.log_info(f"Processing {post_id} for {platform}")
        
        try:
            # Download media if present
            if post.get("media"):
                media_path = await self.download_media(post_id)
            
            # Perform platform-specific posting
            result = await self.post_to_platform(post)
            
            # Mark as complete
            await self.mark_complete(post_id, result.get("post_id"))
            self.log_info(f"Successfully posted {post_id}")
            
        except Exception as e:
            # Mark as failed (NO RETRIES)
            await self.mark_failed(post_id, str(e))
            self.log_error(f"Failed to post {post_id}: {e}")
    
    async def mark_complete(self, post_id, platform_post_id=None):
        """Mark post as successfully published"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/queue/gui/complete",
                headers=self.headers,
                json={"id": post_id, "platform_post_id": platform_post_id}
            ) as resp:
                return await resp.json()
    
    async def mark_failed(self, post_id, error):
        """Mark post as failed"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/queue/gui/failed",
                headers=self.headers,
                json={"id": post_id, "error": error}
            ) as resp:
                return await resp.json()
    
    def log_info(self, message):
        self.reports.append({
            "type": "info",
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def log_error(self, message):
        self.reports.append({
            "type": "error", 
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def flush_reports(self):
        """Send accumulated reports to server"""
        if not self.reports:
            return
            
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/queue/gui/batch-report",
                headers=self.headers,
                json={"worker_id": "windows-worker-1", "reports": self.reports}
            ) as resp:
                self.reports = []  # Clear after sending
                return await resp.json()

# Run the worker
if __name__ == "__main__":
    worker = SocialWorker(api_key="your-api-key")
    asyncio.run(worker.run())
```

---

## Error Handling

### Network Errors

```python
import requests
from requests.exceptions import RequestException

def safe_api_call(method, url, **kwargs):
    """Wrapper with retry for network errors only"""
    max_attempts = 3
    
    for attempt in range(max_attempts):
        try:
            response = method(url, timeout=30, **kwargs)
            return response
        except RequestException as e:
            if attempt < max_attempts - 1:
                time.sleep(5 * (attempt + 1))  # Backoff
                continue
            raise
```

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| `200` | Success | Process response |
| `400` | Bad request | Fix request format |
| `401` | Unauthorized | Check API key |
| `404` | Not found | Post/media doesn't exist |
| `500` | Server error | Retry after delay |

---

## Best Practices

### DO ✅

1. **Poll at reasonable intervals** - Every 30-60 seconds when idle
2. **Send heartbeats** - Every 60 seconds to prove you're alive
3. **Use batch-report for logs** - Don't spam individual requests
4. **Mark complete/failed promptly** - Don't leave posts in `queued` forever
5. **Handle network errors** - Retry network failures, not business logic failures
6. **Log locally** - Keep detailed local logs for debugging

### DON'T ❌

1. **Don't retry failed posts** - The system has no retry logic by design
2. **Don't call /failed repeatedly** - It's idempotent but wasteful
3. **Don't poll too frequently** - Max once per 10 seconds
4. **Don't send screenshots for every failure** - Only when useful for debugging
5. **Don't ignore responses** - Check for success/error messages

---

## Platform-Specific URLs

The worker should navigate to these URLs for each platform:

| Platform | URL |
|----------|-----|
| `facebook_personal` | https://www.facebook.com/sterlingcooleypersonal |
| `facebook_page` | https://facebook.com/VagusNerveProgram/ |
| `facebook_group` | https://www.facebook.com/groups/383702078807725 |
| `instagram_vagus` | https://instagram.com/vegasschoolultra |
| `instagram_ultra` | https://www.instagram.com/ultraskool/ |
| `instagram_personal` | https://instagram.com/sterlingcooley1 |
| `tiktok_personal` | https://tiktok.com/@sterlingcooley |

These URLs are also returned in the `platform_url` field of each post.

---

## Server-Side Cleanup

The server automatically cleans up old posts:

| Status | Retention | Notes |
|--------|-----------|-------|
| `failed` | 3 days | Deleted from database |
| `published` | 14 days | Deleted from database |
| Media files | 7 days | Deleted from disk |

**You don't need to manage cleanup** - the server handles it automatically every hour.

---

## Questions?

If you encounter issues:

1. Check PM2 logs on server: `pm2 logs sc-social --lines 100`
2. Run diagnostics: `./diagnose_queue.sh`
3. Check queue status: `./fix_stuck_queue.sh`

---

*Last updated: 2026-01-20*
*API Version: 2.0 (No Retry)*
