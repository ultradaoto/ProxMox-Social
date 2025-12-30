# Social Worker

Automated social media posting system for Windows 10. Bridges your Social Dashboard with platforms that require GUI automation (Facebook, Instagram, TikTok, YouTube).

## Architecture

```
Sterling's Social Dashboard          Windows 10 Worker
(sterlingcooley.com/social)         (This Machine)
        │                                   │
        │  POST /api/queue/pending          │
        │ ◄─────────────────────────────────┤  Queue Fetcher
        │                                   │  (polls every 5 min)
        │  GET /api/queue/media/{id}        │
        │ ◄─────────────────────────────────┤
        │                                   │
        │                           ┌───────┴───────┐
        │                           │ C:\PostQueue  │
        │                           │ ├── pending   │
        │                           │ ├── in_prog   │
        │                           │ ├── completed │
        │                           │ └── failed    │
        │                           └───────┬───────┘
        │                                   │
        │                                   │  Social Poster
        │                                   │  (browser automation)
        │  POST /api/queue/complete         │
        │ ◄─────────────────────────────────┤
        │                                   │
```

## Components

| File | Description |
|------|-------------|
| `fetcher.py` | Polls dashboard API for pending posts, downloads media |
| `poster.py` | Browser automation agent with platform playbooks |
| `healthcheck.py` | System diagnostics and connectivity testing |
| `install_services.ps1` | Windows service installation |
| `DASHBOARD-API.md` | API spec for your dashboard implementation |

## Quick Start

### 1. Install Dependencies

```powershell
# Create working directory
mkdir C:\SocialWorker
cd C:\SocialWorker

# Copy files
Copy-Item .\* C:\SocialWorker\

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install packages
pip install -r requirements.txt

# Install browser
playwright install chromium
```

### 2. Configure

```powershell
# Copy example config
Copy-Item .env.example .env

# Edit with your settings
notepad .env
```

**Required settings:**
- `DASHBOARD_URL` - Your Social Dashboard URL
- `API_KEY` - API key matching your dashboard

### 3. Implement Dashboard API

See `DASHBOARD-API.md` for the required endpoints on your server.

### 4. Test

```powershell
# Check connectivity
python healthcheck.py

# Test fetcher (single run)
python fetcher.py --once

# Test browser automation
python poster.py --test
```

### 5. Install as Services

```powershell
# Run as Administrator
.\install_services.ps1

# Check status
.\install_services.ps1 -Status

# Start services
.\install_services.ps1 -Start
```

## Usage

### Manual Operation

```powershell
# Fetch pending posts (runs once)
python fetcher.py --once

# Process pending jobs (runs once)
python poster.py --once

# Check queue status
python fetcher.py --queue

# Full health check
python healthcheck.py
```

### Service Operation

```powershell
# Start services
.\install_services.ps1 -Start

# Stop services
.\install_services.ps1 -Stop

# Check status
.\install_services.ps1 -Status

# Uninstall
.\install_services.ps1 -Uninstall
```

## Platform Support

| Platform | Method | Status |
|----------|--------|--------|
| Instagram | Meta Business Suite | Implemented |
| Facebook | Page posting | Implemented |
| TikTok | tiktok.com/upload | Implemented |
| YouTube | YouTube Studio | Implemented |

### Prerequisites by Platform

**Instagram:**
- Instagram Business account linked to Facebook Page
- Logged into business.facebook.com

**Facebook:**
- Admin access to target Page
- Logged into facebook.com

**TikTok:**
- Logged into tiktok.com
- Note: Heavy bot detection, may need manual sessions

**YouTube:**
- Logged into Google/YouTube account
- Channel already created

## Queue Structure

```
C:\PostQueue\
├── pending\           # New jobs from fetcher
│   └── job_20241224_143000_abc123\
│       ├── job.json   # Job metadata
│       └── media_1.jpg
├── in_progress\       # Currently being posted
├── completed\         # Successfully posted
└── failed\            # Failed posts (for review)
```

### Job File Format

```json
{
  "id": "post_abc123",
  "job_id": "job_20241224_143000_abc123",
  "platform": "instagram",
  "caption": "Check out my project!",
  "media": [
    {"local_path": "media_1.jpg", "type": "image"}
  ],
  "status": "pending",
  "attempts": 0
}
```

## Troubleshooting

### "Cannot connect to dashboard"
- Check DASHBOARD_URL in .env
- Verify API endpoint is implemented
- Test with: `curl -H "X-API-Key: key" https://your-url/api/queue/pending`

### "Browser automation fails"
- Run `playwright install chromium`
- Test with: `python poster.py --test`
- Check if platforms need fresh login

### "Not logged in to platform"
1. Run poster.py manually (not as service)
2. Browser opens and you can see login page
3. Log in manually
4. Session is saved in `~/.social_worker/browser_data`

### Service won't start
- Check logs in `C:\SocialWorker\logs\`
- For poster: configure service to run as your user account
- Run `.\install_services.ps1 -Status` to check

## Vision Verification

The poster can use AI vision to verify posts were successful. Set `OPENROUTER_API_KEY` in .env to enable.

Uses `qwen/qwen-2-vl-72b-instruct` via OpenRouter to analyze screenshots.

## Security Notes

- API key should be long random string (32+ chars)
- `.env` file should not be committed to git
- Browser data in `~/.social_worker` contains session cookies
- Consider running poster as dedicated Windows user
