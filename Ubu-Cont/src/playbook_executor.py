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
            return self.run_instagram_playbook(post)
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

    def run_instagram_playbook(self, post: Dict[str, Any]) -> bool:
        """
        Execute the Instagram posting workflow.
        Target: Instagram web interface
        """
        try:
            # 1. Setup Data
            instagram_url = "https://www.instagram.com/"

            caption = post.get('caption', '')
            media_files = post.get('media', [])
            post_id = post.get('id')

            # Instagram uses single caption (title + body combined)
            # Caption already contains both title and body from the fetcher

            logger.info(f"Step 1: Navigate to Instagram: {instagram_url}")
            self._navigate_to_url(instagram_url)
            time.sleep(5)  # Wait for load

            # 2. Click "Create" button (plus icon)
            logger.info("Step 2: Find 'Create' button")
            create_coords = self.vision.find_element("The 'Create' button or plus icon to start a new post on Instagram.")
            self.input.click('left')  # Ensure focus
            self.input.move_to(create_coords[0], create_coords[1])
            self.input.click('left')
            time.sleep(2)

            # 3. Upload Image
            logger.info("Step 3: Upload Image")
            # Look for "Select from computer" button or upload area
            upload_btn = self.vision.find_element("The 'Select from computer' button or file upload area in Instagram's create dialog.")
            self.input.move_to(upload_btn[0], upload_btn[1])
            self.input.click('left')
            time.sleep(1.5)

            # Use Wildcard Path Strategy
            # Path: C:\PostQueue\pending\*_{post_id}\media_1.jpg
            if media_files:
                wildcard_path = f"C:\\PostQueue\\pending\\*_{post_id}\\media_1.jpg"
                logger.info(f"  Typing path: {wildcard_path}")

                self.input.type_text(wildcard_path)
                time.sleep(1.0)
                self.input.hotkey('enter')

                # Wait for upload to process
                logger.info("  Waiting for upload...")
                time.sleep(4.0)
            else:
                logger.warning("No media files provided, Instagram requires images")
                return False

            # 4. Click Next (to editing screen)
            logger.info("Step 4: Click Next to editing")
            next_btn = self.vision.find_element("The 'Next' button in the top right corner of Instagram's create dialog.")
            self.input.move_to(next_btn[0], next_btn[1])
            self.input.click('left')
            time.sleep(2)

            # 5. Click Next again (to caption screen)
            logger.info("Step 5: Click Next to caption")
            next_btn2 = self.vision.find_element("The 'Next' button to proceed to the caption screen.")
            self.input.move_to(next_btn2[0], next_btn2[1])
            self.input.click('left')
            time.sleep(2)

            # 6. Add Caption
            logger.info("Step 6: Add Caption")
            caption_area = self.vision.find_element("The caption text area that says 'Write a caption...' on Instagram.")
            self.input.move_to(caption_area[0], caption_area[1])
            self.input.click('left')
            time.sleep(0.5)

            # Type caption
            logger.info(f"  Typing caption ({len(caption)} chars)")
            self.input.type_text(caption)
            time.sleep(1)

            # 7. Click Share
            logger.info("Step 7: Click Share")
            share_btn = self.vision.find_element("The 'Share' button to publish the Instagram post.")
            self.input.move_to(share_btn[0], share_btn[1])
            self.input.click('left')
            time.sleep(5)  # Wait for post to complete

            # 8. Verify
            verification = self.vision.analyze_screen("Did the Instagram post submit successfully? Answer SUCCESS or FAILED.")
            if "SUCCESS" in verification.upper():
                self.api.report_success(post['id'])
                return True
            else:
                self.api.report_failure(post['id'], verification)
                return False

        except Exception as e:
            logger.error(f"Instagram playbook execution failed: {e}")
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
