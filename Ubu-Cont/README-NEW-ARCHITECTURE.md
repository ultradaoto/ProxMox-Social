# Ubuntu Controller - New Simplified Architecture

## Overview

This is the **new simplified architecture** where:

- ✅ **Ubuntu = The Brain** - All logic, decisions, and orchestration
- ✅ **Vision = The Eyes** - Finds UI elements, doesn't make decisions
- ✅ **Windows 10 = The Cockpit** - Just displays and receives input
- ✅ **Python = The Script** - Deterministic workflows, no AI guessing

## Architecture Comparison

### OLD (Complex, Unreliable)
```
Windows 10 runs AI → Reads OSP overlays → Decides what to do → Acts
```

### NEW (Simple, Reliable)
```
Ubuntu knows steps → Vision finds elements → Ubuntu commands Windows
```

## Components

### Core Modules (src/)

| File | Purpose |
|------|---------|
| `vnc_capture.py` | Captures Windows 10 screen via VNC |
| `vision_finder.py` | Uses Ollama Qwen2.5-VL to find UI elements |
| `input_injector.py` | Sends mouse/keyboard commands via HTTP |
| `main_orchestrator.py` | Main loop, polls API, dispatches workflows |

### Workflows (src/workflows/)

| File | Purpose |
|------|---------|
| `base_workflow.py` | Base class with retry logic, state management |
| `instagram.py` | Instagram posting workflow (step-by-step) |
| `facebook.py` | Facebook workflow (TODO) |
| `tiktok.py` | TikTok workflow (TODO) |
| `skool.py` | Skool workflow (TODO) |

## Installation

### 1. Install Dependencies

```bash
cd ~/social-automation
pip install -r requirements.txt
```

### 2. Install Ollama

```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull vision model
ollama pull qwen2.5-vl:7b

# Verify
ollama list
```

### 3. Configure Settings

```bash
cp config/settings.yaml.example config/settings.yaml
nano config/settings.yaml
```

Update:
- VNC host/port for Windows 10 VM
- Proxmox host IP for input injection
- API base URL for social dashboard
- Logging paths

### 4. Verify Connections

```bash
# Test VNC capture
python src/vnc_capture.py

# Test vision finder (requires screenshot from above)
python src/vision_finder.py

# Test input injection
python src/input_injector.py

# Test full system
python src/main_orchestrator.py --test-connection
```

## Usage

### Start the Orchestrator

```bash
# Run in foreground
python src/main_orchestrator.py

# Run in background
nohup python src/main_orchestrator.py > logs/orchestrator.log 2>&1 &

# As systemd service (recommended)
sudo systemctl start social-orchestrator
sudo systemctl enable social-orchestrator
```

### Process a Single Post (Testing)

```bash
# Process specific post ID
python src/main_orchestrator.py --post-id "abc123"
```

### Monitor Logs

```bash
# Follow orchestrator log
tail -f /var/log/social-automation/orchestrator.log

# View recent errors
grep ERROR /var/log/social-automation/orchestrator.log | tail -20
```

## How It Works

### Main Loop Flow

```
1. Poll API for pending posts (every 60 seconds)
2. If post found:
   a. Determine platform (instagram, facebook, etc.)
   b. Load appropriate workflow
   c. Execute workflow step-by-step
   d. Report success/failure to API
3. Repeat
```

### Workflow Execution

```python
# Example: Instagram posting

Step 1: Navigate to instagram.com
  → Input: Type URL, press Enter
  → Vision: Wait for page to load

Step 2: Click Create button
  → Vision: Find "Create" button
  → Input: Click at coordinates

Step 3: Select media file
  → Vision: Find "Select from computer" button
  → Input: Click, type file path, press Enter

... (continue through all steps)

Step N: Verify success
  → Vision: Check for success message
  → Report to API
```

### Vision Usage Pattern

```python
# Vision finds elements - Python decides what to do with them

# Example 1: Find and click
element = vision.find_element(screenshot, "blue Post button")
if element:
    input.click(element.x, element.y)

# Example 2: Verify state
matches, explanation = vision.verify_state(
    screenshot,
    "Instagram upload dialog is visible"
)
if matches:
    proceed_to_next_step()

# Example 3: Wait for element to appear
element = workflow.wait_for_element("Next button", timeout=10)
if element:
    input.click(element.x, element.y)
```

## Adding New Platforms

### 1. Create Workflow File

```python
# src/workflows/facebook.py

from enum import Enum
from .base_workflow import BaseWorkflow, PostContent

class FacebookStep(Enum):
    NAVIGATE = "navigate"
    CLICK_CREATE = "click_create"
    # ... define all steps
    DONE = "done"

class FacebookWorkflow(BaseWorkflow):
    def get_platform_name(self) -> str:
        return "Facebook"
    
    def get_initial_step(self):
        return FacebookStep.NAVIGATE
    
    def execute_step(self, step, content):
        if step == FacebookStep.NAVIGATE:
            return self._step_navigate()
        # ... implement all steps
```

### 2. Register in Orchestrator

```python
# src/main_orchestrator.py

from workflows.facebook import FacebookWorkflow

# In __init__:
self.workflows = {
    "instagram": InstagramWorkflow(...),
    "facebook": FacebookWorkflow(...),  # Add here
}
```

### 3. Test Workflow

```python
# Test script
from workflows.facebook import FacebookWorkflow

workflow = FacebookWorkflow(capture, vision, input)
test_content = PostContent(
    post_id="test",
    media_path="C:\\PostQueue\\test.jpg",
    caption="Test post",
    hashtags=["test"],
    platform="facebook"
)

success = workflow.execute(test_content)
```

## Debugging

### Vision Not Finding Elements

```python
# Save screenshot for manual inspection
screenshot = capture.capture()
screenshot.save("/tmp/debug_screen.png")

# Test vision on saved image
from PIL import Image
img = Image.open("/tmp/debug_screen.png")
element = vision.find_element(img, "your description here")
print(element)
```

### Input Commands Not Working

```bash
# Test Proxmox host reachability
ping 192.168.100.1

# Test input API directly
curl -X POST http://192.168.100.1:8888/mouse/move \
  -H "Content-Type: application/json" \
  -d '{"x": 500, "y": 500}'
```

### Workflow Stuck

```bash
# Check orchestrator status
ps aux | grep orchestrator

# Check recent logs
tail -50 /var/log/social-automation/orchestrator.log

# Restart orchestrator
sudo systemctl restart social-orchestrator
```

## Configuration Reference

### settings.yaml

```yaml
vnc:
  host: "192.168.100.20"  # Windows 10 VM IP
  port: 5900              # VNC port
  password: null          # VNC password if required

vision:
  model: "qwen2.5-vl:7b"  # Ollama model
  ollama_host: "http://localhost:11434"

input:
  proxmox_host: "192.168.100.1"  # Proxmox on vmbr1
  api_port: 8888                 # Input API port

workflows:
  max_retries: 3      # Retries per step
  step_timeout: 30    # Max seconds per step

api:
  base_url: "https://social.sterlingcooley.com/api"
  api_key: ""         # Optional API key
  poll_interval: 60   # Seconds between checks

logging:
  level: "INFO"
  file: "/var/log/social-automation/orchestrator.log"
```

## Performance Tips

1. **Vision Model Speed**
   - Use smaller model for faster responses: `qwen2.5-vl:3b`
   - Run Ollama on GPU if available
   - Cache common vision queries (future feature)

2. **Network Latency**
   - Ensure VMs are on same Proxmox host
   - Use internal bridge (vmbr1) not routed network
   - Monitor network saturation

3. **Workflow Efficiency**
   - Reduce step timeouts for known-fast operations
   - Increase timeouts for video uploads
   - Adjust retries based on platform reliability

## Troubleshooting

### Problem: Vision model too slow

**Solution:**
```bash
# Use smaller/faster model
ollama pull qwen2.5-vl:3b

# Update config
nano config/settings.yaml
# Change: model: "qwen2.5-vl:3b"
```

### Problem: VNC connection fails

**Solution:**
```bash
# Test VNC from Ubuntu
vncviewer 192.168.100.20:5900

# Check Windows 10 firewall allows VNC
# Check VNC server running on Windows
```

### Problem: Posts stuck in queue

**Solution:**
```bash
# Check orchestrator is running
ps aux | grep orchestrator

# Check for errors
grep ERROR /var/log/social-automation/orchestrator.log

# Restart orchestrator
sudo systemctl restart social-orchestrator
```

### Problem: Workflow fails at specific step

**Solution:**
```python
# Add debugging to workflow step
def _step_click_button(self):
    logger.info("Attempting to click button...")
    
    # Save screenshot for inspection
    screenshot = self.capture.capture()
    screenshot.save(f"/tmp/debug_{int(time.time())}.png")
    
    # Try to find element
    element = self.vision.find_element(screenshot, "button description")
    logger.info(f"Found element: {element}")
    
    if element:
        return self.input.click(element.x, element.y)
    return False
```

## Migration from Old Architecture

See `docs/MIGRATION_GUIDE.md` for step-by-step migration instructions.

## Architecture Benefits

### Old System Issues
- ❌ Vision model tried to "understand" instructions
- ❌ Unpredictable behavior based on AI interpretation
- ❌ Hard to debug when AI made wrong decisions
- ❌ OSP overlays added complexity
- ❌ Windows had too much responsibility

### New System Advantages
- ✅ Vision only finds elements (simple, reliable)
- ✅ Python code is deterministic (predictable)
- ✅ Easy to debug (step-by-step logging)
- ✅ No complex overlays needed
- ✅ Clear separation of concerns

## Support

For issues or questions:
1. Check logs: `/var/log/social-automation/orchestrator.log`
2. Review this README
3. Check `docs/` folder for detailed guides
4. See `AGENTS.md` for overall project architecture
