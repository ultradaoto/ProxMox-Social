
import requests
from PIL import Image
from io import BytesIO
import time
import sys

def get_frame():
    """Get current frame from VNC stream."""
    try:
        response = requests.get("http://localhost:5555/frame", timeout=2)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
        else:
            print(f"Failed to get frame: Status {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching frame: {e}")
        return None

if __name__ == "__main__":
    print("Testing connection to VNC Live Stream...")
    # Wait a bit for server to start if running immediately after
    time.sleep(2)
    
    img = get_frame()
    if img:
        print(f"SUCCESS: Captured frame of size {img.size}")
        img.save("test_live_capture.png")
        print("Saved to test_live_capture.png")
    else:
        print("FAILURE: Could not capture frame.")
