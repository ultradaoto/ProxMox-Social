├── VM1: Ubuntu AI Controller
│   ├── Vision AI (Qwen-VL 72B 4-bit)
│   ├── Human behavior simulator
│   ├── Sends commands to Input Router
│   └── Captures screen via Spice/VNC

FOLDER 2: UBU-CONT (Ubuntu AI Controller VM)
Purpose
Ubuntu VM that runs computer vision AI and controls the virtual mouse/keyboard.

> [!IMPORTANT]
> **Update 12/29/2025**: We are currently opting to use **API calls (OpenRouter)** for AI vision and decision making instead of running local models (Ollama/OmniParser). This simplifies deployment and reduces local resource usage. Local model instructions below are kept for reference but are optional.

Prerequisites
Ubuntu 22.04 LTS VM

NVIDIA GPU passthrough (recommended for AI)

16GB+ RAM, 8+ CPU cores

Setup Steps
1. Install Base System
bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y \
    python3-pip \
    python3-venv \
    git \
    wget \
    curl \
    vim \
    tmux \
    net-tools \
    xdotool \
    scrot \
    python3-tk \
    python3-dev \
    build-essential
2. Create Python Environment
bash
cd ~
python3 -m venv ai-control
source ai-control/bin/activate
3. Install AI/Computer Vision Dependencies
bash
pip install --upgrade pip

# Core automation
pip install openadapt==0.46.0
pip install pyautogui==0.9.54
pip install pynput==1.7.6
pip install mouse==0.7.1
pip install keyboard==0.13.5

# Human-like movement
pip install human-mouse==1.1.2
pip install pyclick==1.3.4
pip install bezmouse==0.1.0

# Computer vision
pip install opencv-python==4.9.0.80
pip install Pillow==10.1.0
pip install pytesseract==0.3.10
pip install ultralytics==8.0.196  # YOLOv8
pip install easyocr==1.7.1

# Remote control
pip install pyvnc==0.2.0
pip install tightvnc==1.3.10
pip install python-xlib==0.33

# Communication
pip install redis==5.0.1
pip install zmq==0.0.0
pip install msgpack==1.0.7
4. Install Ollama for Local Vision Models
bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5-vl:7b
ollama pull llama3.2-vision:11b
5. Clone Vision Models
bash
cd ~
git clone https://github.com/microsoft/OmniParser
cd OmniParser
pip install -r requirements.txt

# Download pretrained models
wget https://github.com/microsoft/OmniParser/releases/download/v2.0/omniparser_v2.pt
6. Create Virtual Mouse Controller
bash
mkdir -p ~/ai-control/src
cd ~/ai-control/src
nano virtual_mouse_controller.py
python
#!/usr/bin/env python3
"""
Virtual Mouse Controller - Sends human-like input to Windows VM
"""
import socket
import json
import time
import random
import math
import threading
from datetime import datetime
from human_mouse import HumanMouse

class VirtualMouseController:
    def __init__(self, host='192.168.100.1', port=8888):
        self.host = host
        self.port = port
        self.mouse = HumanMouse()
        self.current_x = 960  # Center of 1920x1080
        self.current_y = 540
        self.connected = False
        
    def connect(self):
        """Connect to Proxmox host's virtual input bridge"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        self.connected = True
        print(f"Connected to virtual input at {self.host}:{self.port}")
    
    def move_to(self, target_x, target_y, duration=None):
        """Move mouse with human-like trajectory"""
        if not self.connected:
            self.connect()
            
        # Generate human-like trajectory
        trajectory = self.mouse.move(
            (self.current_x, self.current_y),
            (target_x, target_y),
            duration=duration
        )
        
        # Send movement commands
        for point in trajectory:
            self._send_mouse_move(point[0], point[1])
            self.current_x, self.current_y = point
            time.sleep(random.uniform(0.001, 0.005))  # Human timing
        
    def click(self, button='left', clicks=1):
        """Human-like click with random delays"""
        for i in range(clicks):
            # Move slightly before click (natural hand tremor)
            self._send_mouse_move(
                self.current_x + random.randint(-2, 2),
                self.current_y + random.randint(-2, 2)
            )
            
            # Press
            self._send_mouse_button(button, 'down')
            time.sleep(random.uniform(0.05, 0.15))  # Human click duration
            
            # Release
            self._send_mouse_button(button, 'up')
            
            # Between multiple clicks
            if i < clicks - 1:
                time.sleep(random.uniform(0.1, 0.3))
    
    def scroll(self, amount, direction='down'):
        """Natural scrolling with acceleration"""
        scroll_amt = abs(amount)
        if direction == 'up':
            scroll_amt = -scroll_amt
            
        # Natural scroll: fast start, slow end
        steps = max(3, int(scroll_amt / 50))
        for i in range(steps):
            step_size = int(scroll_amt / steps * (1 - (i / steps) * 0.5))
            self._send_mouse_wheel(step_size)
            time.sleep(random.uniform(0.01, 0.03))
    
    def _send_mouse_move(self, x, y):
        """Send movement command to virtual device"""
        cmd = {
            'type': 'mouse_move',
            'x': int(x),
            'y': int(y),
            'timestamp': datetime.now().isoformat()
        }
        self._send_command(cmd)
    
    def _send_mouse_button(self, button, action):
        cmd = {
            'type': 'mouse_button',
            'button': button,
            'action': action,
            'timestamp': datetime.now().isoformat()
        }
        self._send_command(cmd)
    
    def _send_mouse_wheel(self, delta):
        cmd = {
            'type': 'mouse_wheel',
            'delta': delta,
            'timestamp': datetime.now().isoformat()
        }
        self._send_command(cmd)
    
    def _send_command(self, cmd):
        try:
            self.socket.send(json.dumps(cmd).encode() + b'\n')
        except:
            self.connected = False
            raise

class VirtualKeyboardController:
    def __init__(self, host='192.168.100.1', port=8889):
        self.host = host
        self.port = port
        self.connected = False
        
    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        self.connected = True
    
    def type_text(self, text, wpm=40):
        """Type text with human-like speed variations"""
        if not self.connected:
            self.connect()
        
        words = text.split()
        for word in words:
            # Type each word
            for char in word:
                self._send_key(char, 'press')
                
                # Human typing speed with natural variation
                base_delay = 60 / (wpm * 5)  # Average delay per character
                delay = random.normalvariate(base_delay, base_delay * 0.3)
                time.sleep(max(0.01, delay))
            
            # Space between words
            self._send_key('space', 'press')
            time.sleep(random.uniform(0.1, 0.3))
    
    def _send_key(self, key, action):
        cmd = {
            'type': 'keyboard',
            'key': key,
            'action': action,
            'timestamp': datetime.now().isoformat()
        }
        self.socket.send(json.dumps(cmd).encode() + b'\n')
7. Create Screen Capture from Windows VM
bash
nano screen_capturer.py
python
#!/usr/bin/env python3
"""
Captures screen from Windows VM via VNC/Spice
"""
import cv2
import numpy as np
import threading
import queue
import time
from vncdotool import api

class WindowsVMCapturer:
    def __init__(self, vnc_host='192.168.100.100', vnc_port=5900, 
                 vnc_password='your_password'):
        self.vnc_host = vnc_host
        self.vnc_port = vnc_port
        self.vnc_password = vnc_password
        self.client = None
        self.frame_queue = queue.Queue(maxsize=1)
        self.running = False
        
    def connect(self):
        """Connect to Windows VM VNC server"""
        self.client = api.connect(f'{self.vnc_host}:{self.vnc_port}', 
                                 password=self.vnc_password)
        self.running = True
        print(f"Connected to VNC at {self.vnc_host}:{self.vnc_port}")
        
    def start_capture(self):
        """Start continuous screen capture"""
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
    def _capture_loop(self):
        """Main capture loop"""
        while self.running:
            try:
                # Capture screen via VNC
                screenshot = self.client.screen.capture()
                
                # Convert to OpenCV format
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                
                # Update frame queue
                if self.frame_queue.full():
                    self.frame_queue.get_nowait()
                self.frame_queue.put(img)
                
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                print(f"Capture error: {e}")
                time.sleep(1)
                
    def get_latest_frame(self):
        """Get latest captured frame"""
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None
            
    def disconnect(self):
        """Disconnect from VNC"""
        self.running = False
        if self.client:
            self.client.disconnect()
8. Create Main AI Agent
bash
nano main_ai_agent.py
python
#!/usr/bin/env python3
"""
Main AI Agent - Orchestrates vision, decision making, and control
"""
import time
import json
import logging
from datetime import datetime
from pathlib import Path

from screen_capturer import WindowsVMCapturer
from virtual_mouse_controller import VirtualMouseController, VirtualKeyboardController
from vision_processor import VisionProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIComputerAgent:
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Initialize components
        self.capturer = WindowsVMCapturer(**self.config['vnc'])
        self.mouse = VirtualMouseController(**self.config['mouse'])
        self.keyboard = VirtualKeyboardController(**self.config['keyboard'])
        self.vision = VisionProcessor(**self.config['vision'])
        
        self.running = False
        self.action_history = []
        
    def start(self):
        """Start the AI agent"""
        logger.info("Starting AI Computer Agent")
        
        # Connect to Windows VM
        self.capturer.connect()
        self.capturer.start_capture()
        
        self.mouse.connect()
        self.keyboard.connect()
        
        self.running = True
        self._main_loop()
        
    def _main_loop(self):
        """Main agent loop"""
        logger.info("Agent running...")
        
        while self.running:
            try:
                # 1. Capture screen
                frame = self.capturer.get_latest_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue
                
                # 2. Process with vision AI
                analysis = self.vision.analyze(frame)
                
                # 3. Make decision based on current task
                action = self._decide_action(analysis)
                
                # 4. Execute action with human-like behavior
                if action:
                    self._execute_action(action)
                    
                    # Log action
                    self.action_history.append({
                        'timestamp': datetime.now().isoformat(),
                        'action': action,
                        'screenshot': f"screenshots/{int(time.time())}.png"
                    })
                    
                    # Save screenshot periodically
                    if len(self.action_history) % 10 == 0:
                        cv2.imwrite(f"screenshots/{int(time.time())}.png", frame)
                
                # 5. Brief pause (human reaction time)
                time.sleep(random.uniform(0.5, 1.5))
                
            except KeyboardInterrupt:
                logger.info("Agent stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(1)
                
    def _decide_action(self, analysis):
        """Decision logic based on current task"""
        # Example: Click on login button if found
        for element in analysis.elements:
            if element.label == 'login_button' and element.confidence > 0.8:
                return {
                    'type': 'click',
                    'x': element.center_x,
                    'y': element.center_y,
                    'button': 'left',
                    'clicks': 1
                }
        
        # Example: Scroll if at bottom of page
        if analysis.scroll_position > 0.9:  # 90% scrolled
            return {
                'type': 'scroll',
                'amount': 300,
                'direction': 'up'
            }
        
        return None
        
    def _execute_action(self, action):
        """Execute action with human-like variations"""
        if action['type'] == 'click':
            # Add small random offset (natural hand imprecision)
            offset_x = random.randint(-3, 3)
            offset_y = random.randint(-3, 3)
            
            self.mouse.move_to(
                action['x'] + offset_x,
                action['y'] + offset_y,
                duration=random.uniform(0.3, 0.8)
            )
            
            # Brief pause before click
            time.sleep(random.uniform(0.1, 0.3))
            
            self.mouse.click(
                button=action.get('button', 'left'),
                clicks=action.get('clicks', 1)
            )
            
        elif action['type'] == 'type':
            self.keyboard.type_text(
                action['text'],
                wpm=random.randint(35, 60)
            )
            
        elif action['type'] == 'scroll':
            self.mouse.scroll(
                action['amount'],
                direction=action.get('direction', 'down')
            )

if __name__ == "__main__":
    agent = AIComputerAgent('config.json')
    agent.start()
9. Create Configuration File
bash
nano config.json
json
{
    "vnc": {
        "vnc_host": "192.168.100.100",
        "vnc_port": 5900,
        "vnc_password": "secure_password_here"
    },
    "mouse": {
        "host": "192.168.100.1",
        "port": 8888
    },
    "keyboard": {
        "host": "192.168.100.1",
        "port": 8889
    },
    "vision": {
        "api_key": "sk-or-your-actual-api-key-here",
        "model_name": "qwen/qwen-2.5-vl-72b-instruct",
        "confidence_threshold": 0.05
    },
    "behavior": {
        "min_think_time": 0.5,
        "max_think_time": 2.0,
        "typing_error_rate": 0.02,
        "mouse_tremor_level": 1.5
    }
}
10. Create Systemd Service for Agent
bash
sudo nano /etc/systemd/system/ai-agent.service
ini
[Unit]
Description=AI Computer Control Agent
After=network.target
Wants=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/ai-control
Environment="PATH=/home/ubuntu/ai-control/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/ubuntu/ai-control/bin/python /home/ubuntu/ai-control/src/main_ai_agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
Startup Instructions
bash
# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable ai-agent
sudo systemctl start ai-agent

# Check logs
journalctl -u ai-agent -f