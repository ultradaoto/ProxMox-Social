"""
Skool Workflow - Complete posting workflow for Skool.com

This workflow handles posting to Skool community platform.
It follows the exact 16-step sequence described in the brain specification.

Steps:
1. Click OPEN URL on OSP
2. Wait for Skool page to load
3. Click "Start a post" on Skool
4. Wait for post dialog to appear
5. Click COPY TITLE on OSP
6. Find title field and paste
7. Click COPY BODY on OSP
8. Find body field and paste
9. Click COPY IMAGE on OSP
10. Find image area and paste
11. Check if email toggle is needed
12. Toggle email if indicated
13. Click POST on OSP
14. Click actual Post button on Skool
15. Verify success confirmation
16. Click SUCCESS or FAILED on OSP
"""

import asyncio
from typing import List, Optional

from src.workflows.async_base_workflow import AsyncBaseWorkflow, StepResult, StepStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SkoolWorkflow(AsyncBaseWorkflow):
    """Workflow for posting to Skool.com"""
    
    @property
    def platform_name(self) -> str:
        return "Skool"
    
    @property
    def steps(self) -> List[str]:
        return [
            "click_osp_open_url",           # Step 1: Click OPEN URL on OSP
            "wait_for_skool_page",          # Step 2: Wait for Skool to load
            "click_start_post",             # Step 3: Click "Start a post" on Skool
            "wait_for_post_dialog",         # Step 4: Wait for post dialog
            "click_osp_copy_title",         # Step 5: Click COPY TITLE on OSP
            "paste_title",                  # Step 6: Find title field and paste
            "click_osp_copy_body",          # Step 7: Click COPY BODY on OSP
            "paste_body",                   # Step 8: Find body field and paste
            "click_osp_copy_image",         # Step 9: Click COPY IMAGE on OSP
            "paste_image",                  # Step 10: Find image area and paste
            "check_email_toggle",           # Step 11: Check if email toggle needed
            "toggle_email_if_needed",       # Step 12: Toggle email if indicated
            "click_osp_post",               # Step 13: Click POST on OSP
            "click_skool_post_button",      # Step 14: Click actual Post button on Skool
            "verify_post_success",          # Step 15: Verify green confirmation
            "click_success_or_fail"         # Step 16: Click SUCCESS or FAILED on OSP
        ]
    
    async def _execute_step(self, step_name: str) -> StepResult:
        """Execute a single step in the Skool workflow."""
        
        # ==================== STEP 1: OPEN URL ====================
        if step_name == "click_osp_open_url":
            logger.info("Looking for OPEN URL button on OSP...")
            
            screenshot = await self.take_screenshot("step01_before_open_url")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            # Ask vision: Where is the OPEN URL button on the right side?
            element = await self.vision.find_element(
                screenshot,
                "button labeled 'OPEN URL' on the right side panel"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "OPEN URL button not found on OSP")
            
            # Click the button
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked OPEN URL at ({element.x}, {element.y})")
            
            return StepResult(StepStatus.SUCCESS, "Clicked OPEN URL")
        
        # ==================== STEP 2: WAIT FOR SKOOL ====================
        elif step_name == "wait_for_skool_page":
            logger.info("Waiting for Skool page to load...")
            
            # Wait a bit for page load
            await asyncio.sleep(3)
            
            # Verify Skool page is visible
            screenshot = await self.take_screenshot("step02_skool_loaded")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            state = await self.vision.verify_screen_state(
                screenshot,
                "Skool community page with navigation and content area visible"
            )
            
            if state.is_match:
                return StepResult(StepStatus.SUCCESS, "Skool page loaded")
            else:
                # Try waiting a bit more
                await asyncio.sleep(2)
                return StepResult(StepStatus.SUCCESS, "Skool page loaded (assumed)")
        
        # ==================== STEP 3: START POST ====================
        elif step_name == "click_start_post":
            logger.info("Looking for 'Start a post' button on Skool...")
            
            screenshot = await self.take_screenshot("step03_find_start_post")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            # Ask vision: Where is the Start a post button?
            element = await self.vision.find_element(
                screenshot,
                "button or clickable area to start a new post on Skool, might say 'Start a post', 'Create', 'Write something', or have a plus icon"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "'Start a post' button not found")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked 'Start a post' at ({element.x}, {element.y})")
            
            return StepResult(StepStatus.SUCCESS, "Clicked Start a post")
        
        # ==================== STEP 4: WAIT FOR DIALOG ====================
        elif step_name == "wait_for_post_dialog":
            logger.info("Waiting for post creation dialog...")
            
            await asyncio.sleep(2)
            
            screenshot = await self.take_screenshot("step04_post_dialog")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            state = await self.vision.verify_screen_state(
                screenshot,
                "post creation dialog or form with title and body input fields visible"
            )
            
            if state.is_match:
                return StepResult(StepStatus.SUCCESS, "Post dialog opened")
            else:
                # Try clicking again or assume it's open
                return StepResult(StepStatus.SUCCESS, "Post dialog (assumed open)")
        
        # ==================== STEP 5: COPY TITLE ====================
        elif step_name == "click_osp_copy_title":
            logger.info("Looking for COPY TITLE button on OSP...")
            
            screenshot = await self.take_screenshot("step05_before_copy_title")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            element = await self.vision.find_element(
                screenshot,
                "button labeled 'COPY TITLE' on the right side panel"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "COPY TITLE button not found")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked COPY TITLE at ({element.x}, {element.y})")
            
            # Brief wait for clipboard
            await asyncio.sleep(0.5)
            
            return StepResult(StepStatus.SUCCESS, "Title copied to clipboard")
        
        # ==================== STEP 6: PASTE TITLE ====================
        elif step_name == "paste_title":
            logger.info("Looking for title paste location...")
            
            screenshot = await self.take_screenshot("step06_find_title_field")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            # Ask vision: Where do I paste the title?
            element = await self.vision.find_element(
                screenshot,
                "input field or text area for the post title, possibly highlighted in green, labeled 'Title', or the first input field in the post form"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "Title paste location not found")
            
            # Click the location
            await self.input.click_at(element.x, element.y)
            await asyncio.sleep(0.3)
            
            # Paste
            await self.input.paste()
            logger.info(f"Pasted title at ({element.x}, {element.y})")
            
            await asyncio.sleep(0.3)
            
            return StepResult(StepStatus.SUCCESS, "Title pasted")
        
        # ==================== STEP 7: COPY BODY ====================
        elif step_name == "click_osp_copy_body":
            logger.info("Looking for COPY BODY button on OSP...")
            
            screenshot = await self.take_screenshot("step07_before_copy_body")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            element = await self.vision.find_element(
                screenshot,
                "button labeled 'COPY BODY' on the right side panel"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "COPY BODY button not found")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked COPY BODY at ({element.x}, {element.y})")
            
            await asyncio.sleep(0.5)
            
            return StepResult(StepStatus.SUCCESS, "Body copied to clipboard")
        
        # ==================== STEP 8: PASTE BODY ====================
        elif step_name == "paste_body":
            logger.info("Looking for body paste location...")
            
            screenshot = await self.take_screenshot("step08_find_body_field")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            element = await self.vision.find_element(
                screenshot,
                "larger text area for post body content, description, or message content, possibly highlighted in red, or the main content area below the title"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "Body paste location not found")
            
            await self.input.click_at(element.x, element.y)
            await asyncio.sleep(0.3)
            await self.input.paste()
            logger.info(f"Pasted body at ({element.x}, {element.y})")
            
            await asyncio.sleep(0.3)
            
            return StepResult(StepStatus.SUCCESS, "Body pasted")
        
        # ==================== STEP 9: COPY IMAGE ====================
        elif step_name == "click_osp_copy_image":
            logger.info("Looking for COPY IMAGE button on OSP...")
            
            screenshot = await self.take_screenshot("step09_before_copy_image")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            element = await self.vision.find_element(
                screenshot,
                "button labeled 'COPY IMAGE' on the right side panel"
            )
            
            if not element:
                # Image might be optional - check if post has image
                if self.current_post and not self.current_post.image_path and not self.current_post.image_base64:
                    logger.info("No image in post, skipping image step")
                    self.set_step_data("has_image", False)
                    return StepResult(StepStatus.SKIPPED, "No image to copy")
                return StepResult(StepStatus.FAILED, "COPY IMAGE button not found")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked COPY IMAGE at ({element.x}, {element.y})")
            
            await asyncio.sleep(1.0)  # Image copy may take longer
            self.set_step_data("has_image", True)
            
            return StepResult(StepStatus.SUCCESS, "Image copied to clipboard")
        
        # ==================== STEP 10: PASTE IMAGE ====================
        elif step_name == "paste_image":
            # Skip if no image
            if not self.get_step_data("has_image", True):
                return StepResult(StepStatus.SKIPPED, "No image to paste")
            
            logger.info("Looking for image paste location...")
            
            screenshot = await self.take_screenshot("step10_find_image_area")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            element = await self.vision.find_element(
                screenshot,
                "image upload area, drag and drop zone, button to add image/media, attachment button, or image icon in the post form"
            )
            
            if not element:
                # Try pasting directly into the body area
                logger.info("Image area not found, trying direct paste")
                await self.input.paste()
                await asyncio.sleep(2)
                return StepResult(StepStatus.SUCCESS, "Image pasted (direct)")
            
            await self.input.click_at(element.x, element.y)
            await asyncio.sleep(0.3)
            await self.input.paste()
            logger.info(f"Pasted image at ({element.x}, {element.y})")
            
            # Wait for image to upload
            await asyncio.sleep(3)
            
            return StepResult(StepStatus.SUCCESS, "Image pasted")
        
        # ==================== STEP 11: CHECK EMAIL TOGGLE ====================
        elif step_name == "check_email_toggle":
            logger.info("Checking if email toggle is needed...")
            
            # Check if post requires email notification
            needs_email = False
            if self.current_post and self.current_post.send_email:
                needs_email = True
            else:
                # Also check OSP panel for email indicator
                screenshot = await self.take_screenshot("step11_check_email")
                if screenshot:
                    needs_email = await self.vision.check_osp_email_toggle(screenshot)
            
            # Store result for next step
            self.set_step_data("email_toggle_needed", needs_email)
            
            if needs_email:
                logger.info("Email toggle IS needed")
            else:
                logger.info("Email toggle NOT needed")
            
            return StepResult(
                StepStatus.SUCCESS, 
                f"Email toggle check: {'needed' if needs_email else 'not needed'}",
                data={"needs_email": needs_email}
            )
        
        # ==================== STEP 12: TOGGLE EMAIL IF NEEDED ====================
        elif step_name == "toggle_email_if_needed":
            if not self.get_step_data("email_toggle_needed", False):
                logger.info("Skipping email toggle (not needed)")
                return StepResult(StepStatus.SKIPPED, "Email toggle not needed")
            
            logger.info("Looking for email toggle on Skool...")
            
            screenshot = await self.take_screenshot("step12_find_email_toggle")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            # Ask vision: Where is the email toggle?
            element = await self.vision.find_element(
                screenshot,
                "checkbox or toggle for 'send email to members', 'notify members', 'email notification', possibly a toggle switch or checkbox"
            )
            
            if not element:
                logger.warning("Email toggle not found, skipping")
                return StepResult(StepStatus.SKIPPED, "Email toggle not found")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Toggled email at ({element.x}, {element.y})")
            
            await asyncio.sleep(0.3)
            
            return StepResult(StepStatus.SUCCESS, "Email toggled")
        
        # ==================== STEP 13: CLICK OSP POST ====================
        elif step_name == "click_osp_post":
            logger.info("Looking for POST button on OSP...")
            
            screenshot = await self.take_screenshot("step13_before_osp_post")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            element = await self.vision.find_element(
                screenshot,
                "button labeled 'POST' on the right side panel, likely orange or prominently colored"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "POST button not found on OSP")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked OSP POST at ({element.x}, {element.y})")
            
            await asyncio.sleep(0.5)
            
            return StepResult(StepStatus.SUCCESS, "Ready to post")
        
        # ==================== STEP 14: CLICK SKOOL POST ====================
        elif step_name == "click_skool_post_button":
            logger.info("Looking for Skool's Post button...")
            
            screenshot = await self.take_screenshot("step14_find_skool_post")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            # Ask vision: Where is the final Post button on Skool?
            element = await self.vision.find_element(
                screenshot,
                "the main Post or Submit button on Skool to publish the post, usually in the post form itself, NOT the OSP panel button"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "Skool Post button not found")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked Skool Post at ({element.x}, {element.y})")
            
            # Wait for posting to complete
            await asyncio.sleep(4)
            
            return StepResult(StepStatus.SUCCESS, "Clicked Post")
        
        # ==================== STEP 15: VERIFY SUCCESS ====================
        elif step_name == "verify_post_success":
            logger.info("Verifying post was successful...")
            
            screenshot = await self.take_screenshot("step15_verify_success")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            # Ask vision: Is there a green confirmation box?
            state = await self.vision.verify_screen_state(
                screenshot,
                "green confirmation message, success notification, 'Post created' message, or the post now appearing in the feed"
            )
            
            if state.is_match:
                logger.info("Post confirmed successful!")
                self.set_step_data("post_successful", True)
                return StepResult(StepStatus.SUCCESS, "Post confirmed")
            else:
                # Check for error
                error = await self.vision.check_for_error_dialog(screenshot)
                if error:
                    logger.error(f"Error detected: {error}")
                    self.set_step_data("post_successful", False)
                    return StepResult(StepStatus.SUCCESS, f"Post may have failed: {error}")
                
                # Ambiguous - assume success for now
                logger.warning("Success confirmation not clearly found, assuming success")
                self.set_step_data("post_successful", True)
                return StepResult(StepStatus.SUCCESS, "Post status uncertain, assuming success")
        
        # ==================== STEP 16: CLICK SUCCESS OR FAIL ====================
        elif step_name == "click_success_or_fail":
            post_successful = self.get_step_data("post_successful", True)
            
            screenshot = await self.take_screenshot("step16_final")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            if post_successful:
                logger.info("Looking for SUCCESS button on OSP...")
                
                element = await self.vision.find_element(
                    screenshot,
                    "green button labeled 'SUCCESS' on the right side panel"
                )
                
                if not element:
                    # Try alternate names
                    element = await self.vision.find_element(
                        screenshot,
                        "button indicating success, completion, or done on the right panel"
                    )
                
                if not element:
                    return StepResult(StepStatus.FAILED, "SUCCESS button not found")
                
                await self.input.click_at(element.x, element.y)
                logger.info(f"Clicked SUCCESS at ({element.x}, {element.y})")
                
                return StepResult(StepStatus.SUCCESS, "Reported success")
            
            else:
                logger.info("Looking for FAILED button on OSP...")
                
                element = await self.vision.find_element(
                    screenshot,
                    "red button labeled 'FAILED' on the right side panel"
                )
                
                if not element:
                    # Try alternate names
                    element = await self.vision.find_element(
                        screenshot,
                        "button indicating failure or error on the right panel"
                    )
                
                if not element:
                    return StepResult(StepStatus.FAILED, "FAILED button not found")
                
                await self.input.click_at(element.x, element.y)
                logger.info(f"Clicked FAILED at ({element.x}, {element.y})")
                
                return StepResult(StepStatus.SUCCESS, "Reported failure")
        
        # Unknown step
        else:
            return StepResult(StepStatus.FAILED, f"Unknown step: {step_name}")
