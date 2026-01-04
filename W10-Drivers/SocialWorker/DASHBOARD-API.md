# Dashboard API Specification

This document specifies the API endpoints that need to be implemented on your Social Dashboard (social.sterlingcooley.com) for the Windows Social Worker to function.

## Authentication

All endpoints require API key authentication via header:

```
X-API-Key: your-secret-api-key
```

Generate a secure random key and store it as an environment variable on both:
- Dashboard server: `WINDOWS_WORKER_API_KEY`
- Windows machine: `API_KEY`

---

## Required Endpoints

### GET /api/queue/pending

Returns posts scheduled for GUI automation that are due for posting.

**Request:**
```http
GET /api/queue/pending HTTP/1.1
Host: social.sterlingcooley.com
X-API-Key: your-secret-key
```

**Response (200 OK):**
```json
[
  {
    "id": "post_abc123",
    "platform": "instagram",
    "scheduled_time": "2024-12-24T14:30:00Z",
    "caption": "Check out my new project! 🚀\n\nThis is amazing content...",
    "media": [
      {
        "id": "media_001",
        "type": "image",
        "filename": "project.jpg"
      }
    ],
    "link": "https://example.com/project",
    "hashtags": ["#coding", "#project"],
    "mentions": ["@friend"],
    "options": {
      "page_url": "https://facebook.com/mypage"
    }
  }
]
```

**Filtering Logic:**
- `scheduled_time <= NOW` (due for posting)
- `status = 'scheduled'` (not yet posted)
- `platform IN ('facebook', 'instagram', 'tiktok', 'youtube')` (GUI platforms only)

**Platform Values:**
- `instagram` - Post via Meta Business Suite
- `facebook` - Post to Facebook Page
- `tiktok` - Post via tiktok.com/upload
- `youtube` - Upload via YouTube Studio

---

### GET /api/queue/media/{media_id}

Downloads a media file for posting.

**Request:**
```http
GET /api/queue/media/media_001 HTTP/1.1
Host: social.sterlingcooley.com
X-API-Key: your-secret-key
```

**Response (200 OK):**
- `Content-Type`: Appropriate MIME type (image/jpeg, video/mp4, etc.)
- `Content-Disposition`: `attachment; filename="original_filename.jpg"`
- Body: Binary file data

**Response Codes:**
- `200` - File downloaded successfully
- `404` - Media not found
- `401` - Invalid API key

---

### POST /api/queue/complete

Marks a post as successfully published.

**Request:**
```http
POST /api/queue/complete HTTP/1.1
Host: social.sterlingcooley.com
X-API-Key: your-secret-key
Content-Type: application/json

{
  "id": "post_abc123",
  "platform_post_id": "ig_123456789",
  "screenshot": "base64_encoded_png_data..."
}
```

**Fields:**
- `id` (required): Post ID from the pending queue
- `platform_post_id` (optional): ID returned by the platform after posting
- `screenshot` (optional): Base64-encoded PNG of the success screen

**Response (200 OK):**
```json
{
  "success": true
}
```

**Server Actions:**
1. Update post status to `'published'`
2. Set `published_at` timestamp
3. Store `platform_post_id` if provided
4. Save screenshot for audit trail

---

### POST /api/queue/failed

Marks a post as failed with error details.

**Request:**
```http
POST /api/queue/failed HTTP/1.1
Host: social.sterlingcooley.com
X-API-Key: your-secret-key
Content-Type: application/json

{
  "id": "post_abc123",
  "error": "Login required - session expired",
  "screenshot": "base64_encoded_png_data...",
  "retry": true
}
```

**Fields:**
- `id` (required): Post ID
- `error` (required): Error message
- `screenshot` (optional): Screenshot showing the error
- `retry` (optional): Whether to retry later (default: false)

**Response (200 OK):**
```json
{
  "success": true
}
```

**Server Actions:**
1. If `retry=true`, set status to `'retry'`
2. If `retry=false`, set status to `'failed'`
3. Store error message
4. Increment `error_count`
5. Save screenshot for debugging

---

### GET /api/queue/status/{post_id}

Get current status of a specific post.

**Request:**
```http
GET /api/queue/status/post_abc123 HTTP/1.1
Host: social.sterlingcooley.com
X-API-Key: your-secret-key
```

**Response (200 OK):**
```json
{
  "id": "post_abc123",
  "status": "published",
  "scheduled_time": "2024-12-24T14:30:00Z",
  "published_at": "2024-12-24T14:32:15Z",
  "platform_post_id": "ig_123456789",
  "last_error": null
}
```

**Status Values:**
- `draft` - Not yet scheduled
- `scheduled` - Scheduled for posting
- `in_progress` - Currently being posted
- `published` - Successfully posted
- `failed` - Failed permanently
- `retry` - Will be retried

---

## Database Schema Additions

Add these fields to your existing Post model:

```python
class Post(db.Model):
    # ... existing fields ...

    # Queue system fields
    status = db.Column(db.String(20), default='draft')
    # Values: draft, scheduled, in_progress, published, failed, retry

    platform_post_id = db.Column(db.String(100))  # ID from platform
    published_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    error_count = db.Column(db.Integer, default=0)
```

---

## Example Flask Implementation

```python
from flask import Blueprint, jsonify, request, send_file
from functools import wraps
from datetime import datetime
import os

queue_api = Blueprint('queue', __name__, url_prefix='/api/queue')

API_KEY = os.environ.get('WINDOWS_WORKER_API_KEY')

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-API-Key')
        if key != API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated


@queue_api.route('/pending')
@require_api_key
def get_pending():
    now = datetime.utcnow()

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
        'link': post.link,
        'hashtags': post.hashtags or [],
        'mentions': post.mentions or [],
        'options': post.options or {}
    } for post in pending])


@queue_api.route('/media/<media_id>')
@require_api_key
def download_media(media_id):
    media = Media.query.get_or_404(media_id)
    return send_file(
        media.file_path,
        as_attachment=True,
        download_name=media.filename
    )


@queue_api.route('/complete', methods=['POST'])
@require_api_key
def mark_complete():
    data = request.json
    post = Post.query.get_or_404(data['id'])

    post.status = 'published'
    post.published_at = datetime.utcnow()

    if data.get('platform_post_id'):
        post.platform_post_id = data['platform_post_id']

    db.session.commit()
    return jsonify({'success': True})


@queue_api.route('/failed', methods=['POST'])
@require_api_key
def mark_failed():
    data = request.json
    post = Post.query.get_or_404(data['id'])

    post.status = 'retry' if data.get('retry') else 'failed'
    post.last_error = data.get('error')
    post.error_count = (post.error_count or 0) + 1

    db.session.commit()
    return jsonify({'success': True})


@queue_api.route('/status/<post_id>')
@require_api_key
def get_status(post_id):
    post = Post.query.get_or_404(post_id)
    return jsonify({
        'id': post.id,
        'status': post.status,
        'scheduled_time': post.scheduled_time.isoformat() + 'Z' if post.scheduled_time else None,
        'published_at': post.published_at.isoformat() + 'Z' if post.published_at else None,
        'platform_post_id': post.platform_post_id,
        'last_error': post.last_error
    })
```

---

## Testing the API

After implementing, test with curl:

```bash
# Check pending posts
curl -H "X-API-Key: your-key" https://social.sterlingcooley.com/api/queue/pending

# Mark a post complete
curl -X POST -H "X-API-Key: your-key" -H "Content-Type: application/json" \
  -d '{"id": "test_123"}' \
  https://social.sterlingcooley.com/api/queue/complete
```

Or use the healthcheck on Windows:

```powershell
cd C:\SocialWorker
.\venv\Scripts\python.exe healthcheck.py --quick
```
