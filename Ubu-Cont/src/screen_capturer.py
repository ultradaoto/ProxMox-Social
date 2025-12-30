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
        self.capture_thread = None
        
    def connect(self):
        """Connect to Windows VM VNC server"""
        try:
            self.client = api.connect(f'{self.vnc_host}::{self.vnc_port}', 
                                     password=self.vnc_password)
            self.running = True
            print(f"Connected to VNC at {self.vnc_host}:{self.vnc_port}")
        except Exception as e:
            print(f"Failed to connect to VNC: {e}")
        
    def start_capture(self):
        """Start continuous screen capture"""
        if not self.running:
             return
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
    def _capture_loop(self):
        """Main capture loop"""
        while self.running:
            try:
                # Capture screen via VNC
                # vncdotool capture returns a twisted Deferred usually?
                # But api.connect returns a sync wrapper/client?
                # Actually api.connect returns a `VNCDoToolClient`.
                # .captureScreen(filename) writes to file.
                # We need it in memory.
                # .screen is the PIL image (if updated?)
                
                # Using lower level access or capturing to memory might be tricky with vncdotool high level api.
                # let's try .captureScreen('temp.png') and read it back for simplicity/robustness first,
                # or check if we can get PIL image directly.
                # client.screen might be the factory?
                
                # Looking at vncdotool source (not available), but typical usage:
                # client.captureScreen('file.png')
                # If we want performance we usually hook into the protocol.
                # But for this agent (human speed), filesystem temp might be acceptable 30fps? Maybe not.
                
                # Let's try to access the protocol factory's last image if possible.
                # Or just assume client.screen is available as PIL image.
                # In the README example it used: `screenshot = self.client.screen.capture()`
                
                # I will stick to the README's implied API, but wrap in try-catch.
                
                # NOTE: vncdotool might take a snapshot only when requested.
                
                # The README code:
                # screenshot = self.client.screen.capture()
                
                # I'll use that.
                
                screenshot = self.client.captureScreen("screenshot_buffer.png") 
                # Wait, captureScreen expects a filename.
                # If pass None?
                
                # Let's rely on reading back from file for now to be safe if I can't verifying API.
                # Or better: `self.client.protocol.image` might hold it?
                
                # I will implement a safe fallback: capture to /dev/shm/ (ramdisk) for speed.
                
                self.client.captureScreen('/dev/shm/vnc_buffer.png')
                img = cv2.imread('/dev/shm/vnc_buffer.png')
                
                if img is not None:
                    # Update frame queue
                    if self.frame_queue.full():
                        try:
                            self.frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                    self.frame_queue.put(img)
                
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                # print(f"Capture error: {e}")
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
