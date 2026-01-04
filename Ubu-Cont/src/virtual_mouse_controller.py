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
        self.socket = None
        
    def connect(self):
        """Connect to Proxmox host's virtual input bridge"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"Connected to virtual input at {self.host}:{self.port}")
        except Exception as e:
            print(f"Failed to connect to mouse controller: {e}")
            self.connected = False
    
    def move_to(self, target_x, target_y, duration=None):
        """Move mouse with human-like trajectory"""
        if not self.connected:
            self.connect()
            if not self.connected: 
                return
            
        # Calculate steps based on distance
        dist = math.hypot(target_x - self.current_x, target_y - self.current_y)
        steps = max(5, int(dist / 5)) # 5px steps approximately
        
        # Generate human-like trajectory using HumanMouse
        try:
            start = (int(self.current_x), int(self.current_y))
            end = (int(target_x), int(target_y))
            # generate_trajectory returns (x, y, timestamp)
            points = self.mouse.generate_trajectory(start, end)
            trajectory = [(p[0], p[1]) for p in points]
        except Exception as e:
            print(f"Error generating trajectory: {e}")
            # Fallback to direct move
            trajectory = [(target_x, target_y)]

        # Send movement commands
        for px, py in trajectory:
            self._send_mouse_move(px, py)
            self.current_x, self.current_y = px, py
            time.sleep(random.uniform(0.001, 0.005))  # Human timing
        
    def click(self, button='left', clicks=1):
        """Human-like click with random delays"""
        if not self.connected:
            self.connect()
            if not self.connected: 
                return

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
        if not self.connected:
            self.connect()
            if not self.connected: 
                return

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
        """Send movement command to virtual device (Absolute Positioning)"""
        cmd = {
            'type': 'abs',
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
            if self.socket:
                self.socket.send(json.dumps(cmd).encode() + b'\n')
        except:
            self.connected = False
            # raise

class VirtualKeyboardController:
    def __init__(self, host='192.168.100.1', port=8889):
        self.host = host
        self.port = port
        self.connected = False
        self.socket = None
        
    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
        except Exception as e:
            print(f"Failed to connect to keyboard controller: {e}")
            self.connected = False
    
    def type_text(self, text, wpm=40):
        """Type text with human-like speed variations"""
        if not self.connected:
            self.connect()
            if not self.connected:
                return
        
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
        try:
            if self.socket:
                self.socket.send(json.dumps(cmd).encode() + b'\n')
        except:
            self.connected = False
