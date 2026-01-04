import sys
import os
import json
import base64
import requests
from pathlib import Path

# Load Config
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
        API_KEY = config['vision']['api_key']
        MODEL = config['vision']['model_name']
except Exception as e:
    print(f"Error loading config: {e}")
    sys.exit(1)

# Image Path
DEFAULT_IMG = "OmniParser/imgs/windows_home.png"
img_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IMG

if not os.path.exists(img_path):
    print(f"Image not found: {img_path}")
    print(f"Available images in workspace:")
    os.system("find .. -name '*.png' | head -5")
    sys.exit(1)

print(f"Testing Vision API with image: {img_path}")
print(f"Model: {MODEL}")

# Encode Image
with open(img_path, "rb") as image_file:
    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

# Prepare Request
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://proxmox-social.local", # Optional OpenRouter headers
    "X-Title": "Proxmox Social Agent"
}

prompt = """
Look at this desktop screenshot. 
1. Find the location of the Google Chrome icon. 
2. Determine if I should single-click or double-click it to open it (usually double-click for desktop icons, single for taskbar).
Return a JSON object:
{
  "chrome_icon": {
    "found": boolean,
    "box_2d": [ymin, xmin, ymax, xmax], // 0-1000 normalized
    "location_description": "taskbar" or "desktop"
  },
  "suggested_action": "single_click" or "double_click",
  "reasoning": "string"
}
"""

payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_string}"}}
            ]
        }
    ],
    "response_format": {"type": "json_object"}
}

try:
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        data=json.dumps(payload),
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content']
        print("\n--- API RESPONSE ---")
        print(content)
        print("\n--- TEST RESULT: SUCCESS ---")
    else:
        print(f"\n--- API ERROR: {response.status_code} ---")
        print(response.text)
        print("\n--- TEST RESULT: FAILED ---")

except Exception as e:
    print(f"\n--- EXCEPTION ---")
    print(str(e))
    print("\n--- TEST RESULT: FAILED ---")
