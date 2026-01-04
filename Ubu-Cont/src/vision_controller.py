import os
import sys
import json
import time
import base64
import logging
import cv2
import numpy as np
from PIL import Image
from io import BytesIO
from vncdotool import api
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VisionController")

class VisionController:
    def __init__(self, config_path=None):
        """Initialize VisionController with config."""
        if config_path is None:
            # Default to ../config.json relative to this script
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, '..', 'config.json')
        
        self.config = self._load_config(config_path)
        
        # VNC Config
        self.vnc_host = self.config['vnc']['vnc_host']
        self.vnc_port = self.config['vnc']['vnc_port']
        self.vnc_password = self.config['vnc']['vnc_password']
        
        # Vision Config
        self.api_key = self.config['vision']['api_key']
        self.model_name = self.config['vision']['model_name']
        
        # Initialize OpenAI Client
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        
        logger.info(f"VisionController initialized. VNC: {self.vnc_host}:{self.vnc_port}, Model: {self.model_name}")

    def _load_config(self, path):
        """Load configuration from JSON file."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}")
            raise

    def capture_screen(self, save_path=None) -> np.ndarray:
        """
        Capture the screen via VNC.
        Prioritizes local VNC Live Stream server (localhost:5555).
        Falls back to direct VNC connection.
        Returns the image as a numpy array (OpenCV format: BGR).
        """
        # 1. Try Local Stream Server
        try:
            import requests
            response = requests.get("http://localhost:5555/frame", timeout=1.0)
            if response.status_code == 200:
                # Convert bytes to numpy array (BGR for OpenCV)
                file_bytes = np.frombuffer(response.content, np.uint8)
                img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                
                if img is not None:
                    # logger.info("Captured screen via VNC Stream Server.")
                    if save_path:
                        cv2.imwrite(save_path, img)
                    return img
        except Exception:
            # logger.debug(f"Stream server not available ({e}), falling back to direct VNC match.")
            pass

        # 2. Fallback: Direct VNC Connection
        temp_file = "temp_capture.png"
        
        try:
            logger.info(f"Connecting to VNC {self.vnc_host}::{self.vnc_port} (Fallback)...")
            client = api.connect(f'{self.vnc_host}::{self.vnc_port}', password=self.vnc_password)
            
            # Refresh to ensure fresh frame
            # Wait for VNC to render (User suggestion: 3s)
            time.sleep(3)
            client.refreshScreen()
            time.sleep(0.5) 
            
            client.captureScreen(temp_file)
            client.disconnect()
            
            # Read back using cv2
            img = cv2.imread(temp_file)
            
            if img is None:
                raise Exception("Captured image is empty or invalid.")
                
            # Check for black screen issues
            if img.mean() < 5:
                logger.warning("Captured screen is very dark (possible black screen).")
            
            if save_path:
                cv2.imwrite(save_path, img)
                logger.info(f"Screenshot saved to {save_path}")
            
            # Cleanup temp file if not same as save_path
            if save_path != temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
                
            return img
            
        except Exception as e:
            logger.error(f"VNC Capture failed: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise

    def analyze_screen(self, prompt: str, image_path=None, image_array=None) -> str:
        """
        Send screen content to VLM for analysis.
        Uses image_path if provided, otherwise uses image_array.
        If neither, captures a new screenshot.
        """
        if image_path:
            # Read from file
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        elif image_array is not None:
            # Convert BGR (cv2) to RGB (PIL) to Base64
            img_rgb = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            buff = BytesIO()
            pil_img.save(buff, format="JPEG")
            encoded_string = base64.b64encode(buff.getvalue()).decode('utf-8')
        else:
            # Capture new
            img = self.capture_screen()
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            buff = BytesIO()
            pil_img.save(buff, format="JPEG")
            encoded_string = base64.b64encode(buff.getvalue()).decode('utf-8')

        logger.info(f"Sending request to {self.model_name}...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded_string}"
                                }
                            }
                        ]
                    }
                ]
            )
            result = response.choices[0].message.content
            logger.info("Analysis complete.")
            return result
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return f"Error: {e}"

    def find_element(self, description: str) -> tuple[int, int]:
        """
        Ask VLM to find coordinates of an element.
        Returns (x, y) tuple.
        """
        prompt = f"""Find this UI element on screen: "{description}"
        
        Return ONLY the approximate X,Y coordinates of the center of this element.
        Format: "X,Y" (e.g., "500,300"). 
        Do not add any other text.
        """
        
        result = self.analyze_screen(prompt)
        
        try:
            # Clean up response
            clean_result = result.strip().replace('"', '').replace("'", "")
            if ":" in clean_result:
                clean_result = clean_result.split(":")[-1].strip()
            
            parts = clean_result.split(',')
            x = int(float(parts[0].strip()))
            y = int(float(parts[1].strip()))
            logger.info(f"Found element '{description}' at ({x}, {y})")
            return (x, y)
        except Exception as e:
            logger.error(f"Failed to parse coordinates from '{result}': {e}")
            raise

if __name__ == "__main__":
    # Simple test
    vc = VisionController()
    print("Capturing screen...")
    vc.capture_screen("test_capture.png")
    print("Analyzing...")
    res = vc.analyze_screen("Describe what you see on the screen.", image_path="test_capture.png")
    print(f"Result: {res}")
