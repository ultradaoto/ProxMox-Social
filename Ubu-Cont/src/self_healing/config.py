"""
Configuration for self-healing system.
"""
import os
import json
from pathlib import Path

# Load API key from config.json (same as vision controller)
def _load_api_key():
    """Load API key from config.json or environment."""
    # Try environment first
    key = os.getenv("OPENROUTER_API_KEY", "")
    if key:
        return key
    
    # Try config.json
    config_path = Path(__file__).parent.parent.parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
                return config.get("vision", {}).get("api_key", "")
        except Exception:
            pass
    
    return ""

OPENROUTER_API_KEY = _load_api_key()
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Vision model for locating elements
VISION_MODEL = "qwen/qwen-2.5-vl-72b-instruct"

# Self-healing behavior
MAX_HEALING_ATTEMPTS = 3
CONFIDENCE_THRESHOLD = 0.70
SIMILARITY_FAILURE_THRESHOLD = 0.30  # Below 30% = definitely broken

# Paths
RECORDINGS_DIR = "/home/ultra/proxmox-social/Ubu-Cont/recordings"
WORKFLOW_BACKUP_DIR = "/home/ultra/proxmox-social/Ubu-Cont/recordings/backups"
DATABASE_PATH = "/home/ultra/proxmox-social/Ubu-Cont/workflow-validation/validation.db"

# Screen resolution (Windows 10 VM)
SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 1200

# Action descriptions for each platform workflow
# These help the AI understand what button to find
WORKFLOW_ACTION_DESCRIPTIONS = {
    "instagram_default": {
        0: "Click OPEN URL button on the OSP panel (right side)",
        1: "Click the '+' create new post button in Instagram",
        2: "Click 'Post' in the create menu",
        3: "Click the photo/image area to select media",
        4: "Click COPY FILE LOCATION on OSP panel",
        5: "Click the file name input field",
        6: "Click Open button in file dialog",
        7: "Click Next button after selecting media",
        8: "Click Next button after filters",
        9: "Click the caption text area",
        10: "Click COPY BODY on OSP panel",
        11: "Paste caption text (Ctrl+V)",
        12: "Click Share button to publish",
        13: "Click SUCCESS button on OSP panel",
        14: "Close tab (Ctrl+W focus click)",
    },
    "facebook_default": {
        0: "Click OPEN URL button on the OSP panel",
        1: "Click 'What's on your mind?' to open post composer",
        2: "Click COPY BODY on OSP panel",
        3: "Click in the post text area",
        4: "Click Photo/Video button to add media",
        5: "Click COPY FILE LOCATION on OSP panel",
        6: "Click file name input in file dialog",
        7: "Click Open button",
        8: "Click Post button to publish",
        9: "Click SUCCESS on OSP panel",
    },
    "linkedin_default": {
        0: "Click OPEN URL on OSP panel",
        1: "Click Start a post area",
        2: "Click COPY FILE LOCATION on OSP panel",
        3: "Click Add media button",
        4: "Click file name input",
        5: "Click Done/Next after media",
        6: "Click the post text area",
        7: "Click COPY BODY on OSP panel",
        8: "Click Post button",
        9: "Click SUCCESS on OSP panel",
    },
    "skool_default": {
        0: "Click OPEN URL on OSP panel",
        1: "Click new post area",
        2: "Click COPY BODY on OSP panel", 
        3: "Click text input area",
        4: "Click Post button",
        5: "Click SUCCESS on OSP panel",
    }
}

DEFAULT_ACTION_DESCRIPTION = "Click the button or interactive element for this workflow step"
