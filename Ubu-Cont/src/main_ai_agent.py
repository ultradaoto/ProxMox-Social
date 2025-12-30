#!/usr/bin/env python3
"""
Main AI Agent - Orchestrates vision, decision making, and control
"""
import time
import json
import logging
import random
import cv2
from datetime import datetime
from pathlib import Path

from screen_capturer import WindowsVMCapturer
from virtual_mouse_controller import VirtualMouseController, VirtualKeyboardController
from vision_processor import VisionProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIComputerAgent:
    def __init__(self, config_path='config.json'):
        # Load config
        config_file = Path(config_path)
        if not config_file.is_absolute():
            config_file = Path(__file__).parent.parent / config_path
            
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        # Initialize components
        self.capturer = WindowsVMCapturer(**self.config['vnc'])
        self.mouse = VirtualMouseController(**self.config['mouse'])
        self.keyboard = VirtualKeyboardController(**self.config['keyboard'])
        self.vision = VisionProcessor(**self.config['vision'])
        
        self.running = False
        self.action_history = []
        
        # Create screenshot dir
        Path("screenshots").mkdir(exist_ok=True)
        
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
            # Check for "login" in label case-insensitive
            if 'login' in element.label.lower(): # and element.confidence > 0.8:
                logger.info(f"Found login element: {element.label}")
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
        logger.info(f"Executing action: {action['type']}")
        
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
