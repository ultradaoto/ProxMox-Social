import time
import logging
import json
from typing import Dict, Any

# Controllers
from api_monitor import APIMonitor
from vision_controller import VisionController
from input_controller import InputController

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PlaybookExecutor")

class PlaybookExecutor:
    def __init__(self):
        self.api = APIMonitor()
        self.vision = VisionController()
        self.input = InputController()
        self.input.connect()
        
    def execute_post(self, post: Dict[str, Any]) -> bool:
        """
        Execute a post based on its platform.
        """
        platform = post.get('platform', 'unknown').lower()
        logger.info(f"Executing post {post.get('id')} for platform: {platform}")
        
        # Determine playbook based on platform
        # The user mentioned SKOOL and DeSci link.
        if "skool" in platform:
            return self.run_skool_playbook(post)
        elif "instagram" in platform:
            logger.warning("Instagram playbook not yet implemented.")
            return False
        else:
            logger.warning(f"No playbook for platform: {platform}")
            return False

    def run_skool_playbook(self, post: Dict[str, Any]) -> bool:
        """
        Execute the Skool posting workflow on the TEST page.
        Target: https://social.sterlingcooley.com/test/skool/
        """
        try:
            # 1. Setup Data
            # FORCE TEST URL
            group_url = "https://social.sterlingcooley.com/test/skool/" 
                 
            caption = post.get('caption', '')
            media_files = post.get('media', [])
            post_id = post.get('id')
            
            # Split Title and Body 
            lines = caption.split('\n')
            title = lines[0] if lines else "New Post"
            body = "\n".join(lines[1:]) if len(lines) > 1 else caption
            
            logger.info(f"Step 1: Navigate to TEST URL: {group_url}")
            self._navigate_to_url(group_url)
            time.sleep(5) # Wait for load
            
            # Verify we are on Test Page (Optional but good)
            # check = self.vision.analyze_screen("Are we on the Skool test page? Answer YES or NO.")
            
            # 2. Click "Write something..." / Title Area
            logger.info("Step 2: Find 'Write something' / Title input")
            # Note: On the real Skool, clicking "Write something..." reveals the Title and Body inputs.
            coords = self.vision.find_element("The text area or button that says 'Write something...' to start a post.")
            self.input.click('left') # Ensure focus on VNC
            self.input.move_to(coords[0], coords[1])
            self.input.click('left')
            time.sleep(1)
            
            # 3. Type Title
            logger.info(f"Step 3: Type Title: {title[:20]}...")
            self.input.type_text(title)
            time.sleep(0.5)
            
            # Move to body
            self.input.hotkey('tab')
            time.sleep(0.5)
            
            # 4. Type Body
            logger.info(f"Step 4: Type Body ({len(body)} chars)")
            self.input.type_text(body)
            time.sleep(1)
            
            # 5. Upload Media
            if media_files:
                logger.info("Step 5: Upload Media")
                # Look for image/paperclip icon
                upload_btn = self.vision.find_element("The image upload icon or paperclip icon in the post editor.")
                self.input.move_to(upload_btn[0], upload_btn[1])
                self.input.click('left')
                time.sleep(1.5)
                
                # Use Wildcard Path Strategy
                # Path: C:\PostQueue\pending\*_{post_id}\media_1.jpg
                wildcard_path = f"C:\\PostQueue\\pending\\*_{post_id}\\media_1.jpg"
                logger.info(f"  Typing path: {wildcard_path}")
                
                self.input.type_text(wildcard_path)
                time.sleep(1.0)
                self.input.hotkey('enter')
                
                # Wait for upload to process
                logger.info("  Waiting for upload...")
                time.sleep(5.0) 
            
            # 6. Select "Send e-mail"
            logger.info("Step 6: Select 'Email this post'")
            try:
                # Toggle usually says "Email this post"
                email_toggle = self.vision.find_element("The 'Email this post' checkbox or toggle.")
                self.input.move_to(email_toggle[0], email_toggle[1])
                self.input.click('left')
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Could not find Email toggle: {e}")
            
            time.sleep(1)
            
            # 7. Click Post
            logger.info("Step 7: Click Post")
            post_btn = self.vision.find_element("The 'Post' button to submit the post.")
            self.input.move_to(post_btn[0], post_btn[1])
            self.input.click('left')
            time.sleep(5) # Wait longer for post to complete
            
            # 8. Verify
            verification = self.vision.analyze_screen("Did the post submit successfully? Answer SUCCESS or FAILED.")
            if "SUCCESS" in verification.upper():
                self.api.report_success(post['id'])
                return True
            else:
                self.api.report_failure(post['id'], verification)
                return False
                
        except Exception as e:
            logger.error(f"Playbook execution failed: {e}")
            self.api.report_failure(post['id'], str(e))
            return False

    def _navigate_to_url(self, url):
        # Focus Address Bar (Ctrl+L)
        self.input.hotkey('ctrl', 'l')
        time.sleep(0.5)
        # Type URL
        self.input.type_text(url)
        time.sleep(0.5)
        self.input.hotkey('enter')

if __name__ == "__main__":
    # Test stub
    pe = PlaybookExecutor()
    # Mock post
    mock_post = {
        "id": "test-123",
        "platform": "skool_desci",
        "group_url": "https://www.skool.com/desci",
        "caption": "Test Title\n\nThis is a test body.",
        "media": []
    }
    # pe.execute_post(mock_post)
