# Quick Start Guide - New Architecture

## What Changed

You now have a **deterministic Python-based system** where:
- **Ubuntu** = Brain (knows all the steps)
- **Vision** = Eyes (finds buttons and fields)
- **Windows 10** = Cockpit (just displays and receives commands)

## Immediate Next Steps

### 1. Windows 10 Cleanup (5 minutes)

On your **Windows 10 VM**, run these PowerShell scripts:

```powershell
# Stop and disable old automation
cd C:\Users\ultra\Development\ProxMox\W10-Drivers\scripts
.\disable_old_automation.ps1

# Verify Windows 10 is ready
.\verify_cockpit_ready.ps1

# Optionally archive old code (doesn't delete, just moves)
.\archive_old_code.ps1
```

**Manual tasks:**
- Open Chrome → `chrome://extensions/` → Disable OSP extension
- Verify you're logged into Instagram, Facebook, etc.
- Create `C:\PostQueue\pending\` folder if missing

---

### 2. Ubuntu Setup (10 minutes)

On your **Ubuntu VM**:

#### Install Dependencies

```bash
cd ~/social-automation  # or wherever you cloned ProxMox/Ubu-Cont
pip install -r requirements.txt
```

#### Install Ollama (Vision Model)

```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull the vision model (this may take a few minutes)
ollama pull qwen2.5-vl:7b

# Verify it's installed
ollama list
```

#### Configure Settings

```bash
cd ~/social-automation
cp config/settings.yaml.example config/settings.yaml  # if example doesn't exist, settings.yaml is already there
nano config/settings.yaml
```

Update these key values:
- `vnc.host` → Your Windows 10 IP (e.g., 192.168.100.20)
- `input.proxmox_host` → Your Proxmox host IP (e.g., 192.168.100.1)
- `api.base_url` → Your social dashboard API URL

---

### 3. Test Individual Components (5 minutes)

Test each component separately:

```bash
cd ~/social-automation/src

# Test 1: VNC Capture
python vnc_capture.py
# Should save screenshot to /tmp/test_capture.png

# Test 2: Vision Finder (uses screenshot from test 1)
python vision_finder.py
# Should analyze the screenshot

# Test 3: Input Injector
python input_injector.py
# Should move mouse and type on Windows 10

# Test 4: Full system check
python main_orchestrator.py --test-connection
# Should verify all connections
```

**Expected Results:**
- ✅ VNC capture creates a screenshot
- ✅ Vision model can analyze the screenshot
- ✅ Mouse moves on Windows 10 screen
- ✅ All connections report OK

---

### 4. Test Instagram Workflow (10 minutes)

Create a test post manually:

1. **Place test image on Windows 10:**
   ```
   C:\PostQueue\pending\test_image.jpg
   ```

2. **Run Instagram workflow test:**
   ```bash
   cd ~/social-automation/src
   python workflows/instagram.py
   ```

3. **Watch it work:**
   - Opens Instagram
   - Clicks Create
   - Selects file
   - Enters caption
   - Posts

**If it fails:**
- Check logs in console output
- Screenshot is saved to `/tmp/debug_*.png` at failure point
- Review step that failed

---

### 5. Run Full Orchestrator (Production)

Once testing succeeds:

```bash
# Start orchestrator in foreground (for testing)
python src/main_orchestrator.py

# Or run in background
nohup python src/main_orchestrator.py > logs/orchestrator.log 2>&1 &

# Or set up as systemd service (recommended)
sudo cp ai-agent.service /etc/systemd/system/social-orchestrator.service
# Edit service file paths
sudo systemctl daemon-reload
sudo systemctl start social-orchestrator
sudo systemctl enable social-orchestrator
```

**Monitor it:**
```bash
# Watch logs
tail -f /var/log/social-automation/orchestrator.log

# Check status
sudo systemctl status social-orchestrator
```

---

## Troubleshooting Quick Fixes

### VNC Connection Fails
```bash
# Test from Ubuntu
vncviewer 192.168.100.20:5900

# If fails, check Windows 10:
# - VNC server running?
# - Firewall allows port 5900?
```

### Vision Model Not Working
```bash
# Check Ollama is running
ollama list

# If not installed:
curl https://ollama.ai/install.sh | sh
ollama pull qwen2.5-vl:7b
```

### Input Commands Don't Work
```bash
# Test Proxmox host reachable
ping 192.168.100.1

# Test input API
curl -X POST http://192.168.100.1:8888/mouse/move \
  -H "Content-Type: application/json" \
  -d '{"x": 500, "y": 500}'
```

### Workflow Fails at Specific Step
```python
# Add debug logging to the step
logger.info(f"Current screen state:")
screenshot = self.capture.capture()
screenshot.save("/tmp/debug_step.png")
# Inspect /tmp/debug_step.png manually
```

---

## File Locations Reference

### Ubuntu (Ubu-Cont/)
```
src/
├── vnc_capture.py          # Screen capture
├── vision_finder.py        # Element finding
├── input_injector.py       # Mouse/keyboard
├── main_orchestrator.py    # Main loop
└── workflows/
    ├── base_workflow.py    # Base class
    └── instagram.py        # Instagram posting

config/
└── settings.yaml           # Configuration

requirements.txt            # Python dependencies
```

### Windows 10 (W10-Drivers/)
```
scripts/
├── disable_old_automation.ps1   # Stop old system
├── verify_cockpit_ready.ps1     # Check readiness
└── archive_old_code.ps1         # Archive old files

C:\PostQueue\
├── pending\                     # New posts
├── processing\                  # Currently posting
└── completed\                   # Finished posts
```

---

## Success Criteria

You'll know it's working when:
- ✅ Ubuntu can capture Windows 10 screen via VNC
- ✅ Vision model can find UI elements (buttons, fields)
- ✅ Ubuntu can move mouse and type on Windows 10
- ✅ Instagram workflow completes a test post
- ✅ Orchestrator polls API and processes queue

---

## What to Expect

### First Run
- May be slow while vision model warms up
- Some steps might timeout initially (adjust in settings.yaml)
- Watch logs carefully to see what's happening

### After Tuning
- Posts should complete in 30-60 seconds
- Vision finds elements reliably
- Errors are clearly logged with reasons

### If Things Go Wrong
- Old Windows automation is DISABLED not deleted (can restore)
- Ubuntu code is NEW (no impact on old system)
- Windows 10 is just a display (easy to reset/snapshot)

---

## Next Steps After Success

1. **Add more platforms**
   - Copy `workflows/instagram.py` to `workflows/facebook.py`
   - Implement Facebook-specific steps
   - Register in `main_orchestrator.py`

2. **Improve vision accuracy**
   - Use more specific element descriptions
   - Add retry logic for flaky UI
   - Cache common vision queries

3. **Optimize performance**
   - Reduce step timeouts for known operations
   - Use smaller vision model (`qwen2.5-vl:3b`) if too slow
   - Run on GPU if available

4. **Production hardening**
   - Set up log rotation
   - Add health monitoring
   - Configure alerts for failures
   - Take VM snapshots before major changes

---

## Getting Help

1. **Check logs first:**
   ```bash
   tail -100 /var/log/social-automation/orchestrator.log
   ```

2. **Review documentation:**
   - `README-NEW-ARCHITECTURE.md` - Full documentation
   - `docs/UBU-PY-VISION-NEW.md` - Technical details
   - `docs/W10-SIMPLER-COCPIT.md` - Windows 10 role

3. **Debug systematically:**
   - Test VNC capture independently
   - Test vision finder on saved screenshots
   - Test input injection with simple commands
   - Then test full workflow

---

## You're Ready!

Run through steps 1-4 above, and you should have a working system within 30 minutes.

The key insight: **Vision is just eyes. Python is the brain. Windows is just a monitor.**

Good luck! 🚀
