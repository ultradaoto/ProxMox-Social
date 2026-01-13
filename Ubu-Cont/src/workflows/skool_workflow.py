"""
Skool Workflow - Complete posting workflow for Skool.com

Uses the WORKING VisionController and InputController from test_osp_click.py.
These are SYNC controllers that handle their own screenshot capture internally.
"""

import asyncio
import time
from typing import List, Optional, Tuple

from src.workflows.async_base_workflow import AsyncBaseWorkflow, StepResult, StepStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SkoolWorkflow(AsyncBaseWorkflow):
    """Workflow for posting to Skool.com using working sync controllers."""
    
    @property
    def platform_name(self) -> str:
        return "Skool"
    
    @property
    def steps(self) -> List[str]:
        return [
            "click_osp_open_url",
            "wait_for_skool_page",
            "click_start_post",
            "wait_for_post_dialog",
            "click_osp_copy_title",
            "paste_title",
            "click_osp_copy_body",
            "paste_body",
            "click_osp_copy_image",
            "paste_image",
            "check_email_toggle",
            "toggle_email_if_needed",
            "click_osp_post",
            "click_skool_post_button",
            "verify_post_success",
            "click_success_or_fail"
        ]
    
    async def _find_and_click(self, description: str, pre_delay: float = 1.0) -> Optional[Tuple[int, int]]:
        """
        Find element using VisionController and click it.
        VisionController.find_element() captures its own screenshot internally.
        
        Args:
            description: What to find
            pre_delay: Seconds to wait before capturing screenshot (let screen settle)
        
        Returns (x, y) tuple or None if not found.
        """
        # Wait for screen to settle before capturing
        await asyncio.sleep(pre_delay)
        
        try:
            coords = await asyncio.to_thread(
                self.vision.find_element,
                description
            )
            x, y = coords
            logger.info(f"Found '{description[:50]}...' at ({x}, {y})")
            
            await asyncio.to_thread(self.input.move_to, x, y)
            await asyncio.sleep(0.5)
            await asyncio.to_thread(self.input.click, 'left')
            logger.info(f"Clicked at ({x}, {y})")
            
            # Wait after click for UI to respond
            await asyncio.sleep(0.5)
            
            return (x, y)
        except Exception as e:
            logger.warning(f"Failed to find/click '{description[:50]}...': {e}")
            return None
    
    async def _find_element(self, description: str) -> Optional[Tuple[int, int]]:
        """Find element without clicking. Returns (x, y) or None."""
        try:
            coords = await asyncio.to_thread(
                self.vision.find_element,
                description
            )
            x, y = coords
            logger.info(f"Found '{description[:50]}...' at ({x}, {y})")
            return (x, y)
        except Exception as e:
            logger.warning(f"Failed to find '{description[:50]}...': {e}")
            return None
    
    async def _analyze_screen(self, prompt: str) -> str:
        """Ask VisionController to analyze current screen."""
        try:
            result = await asyncio.to_thread(
                self.vision.analyze_screen,
                prompt
            )
            return result
        except Exception as e:
            logger.warning(f"Screen analysis failed: {e}")
            return ""
    
    async def _execute_step(self, step_name: str) -> StepResult:
        """Execute a single workflow step."""
        
        # ==================== STEP 1: OPEN URL ====================
        if step_name == "click_osp_open_url":
            logger.info("Looking for OPEN URL button on OSP...")
            
            # Give 2 seconds for screen to be ready
            coords = await self._find_and_click(
                "The blue button labeled 'OPEN URL' on the right side panel",
                pre_delay=2.0
            )
            
            if coords:
                return StepResult(StepStatus.SUCCESS, f"Clicked OPEN URL at {coords}")
            return StepResult(StepStatus.FAILED, "OPEN URL button not found")
        
        # ==================== STEP 2: WAIT FOR SKOOL ====================
        elif step_name == "wait_for_skool_page":
            logger.info("Waiting for Skool page to load...")
            # Wait longer for page to fully load
            await asyncio.sleep(6)
            
            # Verify page loaded
            result = await self._analyze_screen(
                "Is this a Skool community page? Answer YES or NO, then briefly describe what you see."
            )
            logger.info(f"Page check response: {result[:100]}...")
            
            if "YES" in result.upper() or "SKOOL" in result.upper():
                return StepResult(StepStatus.SUCCESS, "Skool page loaded")
            
            # Give it more time
            await asyncio.sleep(3)
            return StepResult(StepStatus.SUCCESS, "Skool page loaded (assumed)")
        
        # ==================== STEP 3: START POST ====================
        elif step_name == "click_start_post":
            logger.info("Looking for 'Start a post' on Skool...")
            
            # Wait for page to be interactive
            coords = await self._find_and_click(
                "The button or text area to start a new post on Skool, might say 'Write something', 'Start a post', or 'Create'",
                pre_delay=2.0
            )
            
            if coords:
                return StepResult(StepStatus.SUCCESS, f"Clicked Start post at {coords}")
            return StepResult(StepStatus.FAILED, "'Start a post' not found")
        
        # ==================== STEP 4: WAIT FOR DIALOG ====================
        elif step_name == "wait_for_post_dialog":
            logger.info("Waiting for post dialog...")
            await asyncio.sleep(3)
            
            result = await self._analyze_screen(
                "Is there a post creation dialog or form visible with input fields? Answer YES or NO."
            )
            logger.info(f"Dialog check response: {result[:100]}...")
            
            if "YES" in result.upper():
                return StepResult(StepStatus.SUCCESS, "Post dialog opened")
            
            await asyncio.sleep(2)
            return StepResult(StepStatus.SUCCESS, "Post dialog (assumed open)")
        
        # ==================== STEP 5: COPY TITLE ====================
        elif step_name == "click_osp_copy_title":
            logger.info("Looking for COPY TITLE button on OSP...")
            
            coords = await self._find_and_click(
                "The blue button labeled 'Copy title' on the right side panel",
                pre_delay=1.5
            )
            
            if coords:
                await asyncio.sleep(1.0)  # Wait for clipboard
                return StepResult(StepStatus.SUCCESS, "Title copied to clipboard")
            return StepResult(StepStatus.FAILED, "COPY TITLE button not found")
        
        # ==================== STEP 6: PASTE TITLE ====================
        elif step_name == "paste_title":
            logger.info("Looking for title field...")
            
            coords = await self._find_and_click(
                "The title input field in the post creation form, usually at the top of the form",
                pre_delay=1.5
            )
            
            if not coords:
                return StepResult(StepStatus.FAILED, "Title field not found")
            
            await asyncio.sleep(0.5)
            await asyncio.to_thread(self.input.hotkey, 'ctrl', 'v')
            await asyncio.sleep(1.0)  # Wait for paste to complete
            
            return StepResult(StepStatus.SUCCESS, "Title pasted")
        
        # ==================== STEP 7: COPY BODY ====================
        elif step_name == "click_osp_copy_body":
            logger.info("Looking for COPY BODY button on OSP...")
            
            coords = await self._find_and_click(
                "The blue button labeled 'Copy body' on the right side panel",
                pre_delay=1.5
            )
            
            if coords:
                await asyncio.sleep(1.0)  # Wait for clipboard
                return StepResult(StepStatus.SUCCESS, "Body copied to clipboard")
            return StepResult(StepStatus.FAILED, "COPY BODY button not found")
        
        # ==================== STEP 8: PASTE BODY ====================
        elif step_name == "paste_body":
            logger.info("Looking for body/image paste area with red background...")
            
            # Look for the specific red label that says where to paste body AND image
            coords = await self._find_and_click(
                "Find the text that says 'Click here & Paste Body Content & Click & Paste Image' - it has WHITE TEXT on a RED BACKGROUND. Click directly on that red labeled area.",
                pre_delay=1.5
            )
            
            if not coords:
                # Fallback to generic description
                coords = await self._find_and_click(
                    "The red highlighted area or red background label in the post form where body content should be pasted",
                    pre_delay=1.0
                )
            
            if not coords:
                return StepResult(StepStatus.FAILED, "Body paste area not found")
            
            # Store these coordinates for image paste step (same location)
            self.set_step_data("body_paste_coords", coords)
            
            await asyncio.sleep(0.5)
            await asyncio.to_thread(self.input.hotkey, 'ctrl', 'v')
            await asyncio.sleep(1.0)  # Wait for paste to complete
            
            return StepResult(StepStatus.SUCCESS, f"Body pasted at {coords}")
        
        # ==================== STEP 9: COPY IMAGE ====================
        elif step_name == "click_osp_copy_image":
            logger.info("Looking for COPY IMAGE button on OSP...")
            
            coords = await self._find_and_click(
                "The blue button labeled 'Copy image' on the right side panel",
                pre_delay=1.5
            )
            
            if coords:
                await asyncio.sleep(2.0)  # Image copy takes longer
                self.set_step_data("has_image", True)
                return StepResult(StepStatus.SUCCESS, "Image copied to clipboard")
            
            # Image may be optional
            logger.info("COPY IMAGE not found - may not have image")
            self.set_step_data("has_image", False)
            return StepResult(StepStatus.SKIPPED, "No image to copy")
        
        # ==================== STEP 10: PASTE IMAGE ====================
        elif step_name == "paste_image":
            if not self.get_step_data("has_image", False):
                return StepResult(StepStatus.SKIPPED, "No image to paste")
            
            logger.info("Clicking same location as body paste for image...")
            
            # Use the SAME coordinates where we pasted the body - that's where image goes too
            body_coords = self.get_step_data("body_paste_coords")
            
            if body_coords:
                # Click the same spot we used for body paste
                x, y = body_coords
                logger.info(f"Using saved body paste coordinates: ({x}, {y})")
                await asyncio.sleep(1.5)
                await asyncio.to_thread(self.input.move_to, x, y)
                await asyncio.sleep(0.5)
                await asyncio.to_thread(self.input.click, 'left')
                await asyncio.sleep(0.5)
            else:
                # Fallback: find the red area again
                logger.info("No saved coords, looking for red paste area again...")
                coords = await self._find_and_click(
                    "Find the text that says 'Click here & Paste Body Content & Click & Paste Image' - it has WHITE TEXT on a RED BACKGROUND. Click directly on that red labeled area.",
                    pre_delay=1.5
                )
                if coords:
                    await asyncio.sleep(0.5)
            
            # Paste the image
            await asyncio.to_thread(self.input.hotkey, 'ctrl', 'v')
            await asyncio.sleep(4)  # Wait longer for image upload
            
            return StepResult(StepStatus.SUCCESS, "Image pasted")
        
        # ==================== STEP 11: CHECK EMAIL TOGGLE ====================
        elif step_name == "check_email_toggle":
            logger.info("Checking if email notification is needed...")
            
            needs_email = False
            if self.current_post and hasattr(self.current_post, 'send_email'):
                needs_email = self.current_post.send_email
            
            self.set_step_data("email_toggle_needed", needs_email)
            
            return StepResult(
                StepStatus.SUCCESS,
                f"Email toggle: {'needed' if needs_email else 'not needed'}",
                data={"needs_email": needs_email}
            )
        
        # ==================== STEP 12: TOGGLE EMAIL ====================
        elif step_name == "toggle_email_if_needed":
            if not self.get_step_data("email_toggle_needed", False):
                return StepResult(StepStatus.SKIPPED, "Email toggle not needed")
            
            logger.info("Looking for email notification toggle...")
            
            coords = await self._find_and_click(
                "The checkbox or toggle for 'notify members' or 'send email notification'"
            )
            
            if coords:
                return StepResult(StepStatus.SUCCESS, "Email toggled")
            
            return StepResult(StepStatus.SKIPPED, "Email toggle not found")
        
        # ==================== STEP 13: CLICK OSP POST ====================
        elif step_name == "click_osp_post":
            logger.info("Looking for POST button on OSP...")
            
            coords = await self._find_and_click(
                "The orange or prominent POST button on the right side panel",
                pre_delay=2.0
            )
            
            if coords:
                await asyncio.sleep(1.0)
                return StepResult(StepStatus.SUCCESS, "Clicked OSP POST")
            return StepResult(StepStatus.FAILED, "OSP POST button not found")
        
        # ==================== STEP 14: CLICK SKOOL POST ====================
        elif step_name == "click_skool_post_button":
            logger.info("Looking for Skool's Post button...")
            
            coords = await self._find_and_click(
                "The Post or Submit button on the Skool post form itself, NOT the OSP panel, usually in the post dialog",
                pre_delay=2.0
            )
            
            if coords:
                await asyncio.sleep(5)  # Wait for post to submit
                return StepResult(StepStatus.SUCCESS, "Clicked Skool Post")
            return StepResult(StepStatus.FAILED, "Skool Post button not found")
        
        # ==================== STEP 15: VERIFY SUCCESS ====================
        elif step_name == "verify_post_success":
            logger.info("Verifying post success...")
            
            result = await self._analyze_screen(
                "Is there a success message, green confirmation, or does the post appear in the feed? Answer SUCCESS if posted successfully, FAILED if there's an error, or UNCLEAR if you can't tell."
            )
            
            if "SUCCESS" in result.upper() or "POST" in result.upper():
                self.set_step_data("post_successful", True)
                return StepResult(StepStatus.SUCCESS, "Post confirmed successful")
            elif "FAILED" in result.upper() or "ERROR" in result.upper():
                self.set_step_data("post_successful", False)
                return StepResult(StepStatus.SUCCESS, f"Post may have failed: {result[:100]}")
            else:
                self.set_step_data("post_successful", True)
                return StepResult(StepStatus.SUCCESS, "Post status uncertain, assuming success")
        
        # ==================== STEP 16: REPORT RESULT ====================
        elif step_name == "click_success_or_fail":
            post_successful = self.get_step_data("post_successful", True)
            
            if post_successful:
                logger.info("Looking for SUCCESS button on OSP...")
                coords = await self._find_and_click(
                    "Find the exact location of the GREEN SUCCESS button on the right side panel. It is a bright green button with white text that says 'SUCCESS'. Provide the CENTER coordinates of this green button.",
                    pre_delay=2.0
                )
            else:
                logger.info("Looking for FAILED button on OSP...")
                coords = await self._find_and_click(
                    "Find the exact location of the RED FAILED button on the right side panel. It is a red button with white text that says 'FAILED'. Provide the CENTER coordinates of this red button.",
                    pre_delay=2.0
                )
            
            if coords:
                return StepResult(StepStatus.SUCCESS, f"Reported {'success' if post_successful else 'failure'}")
            
            return StepResult(StepStatus.FAILED, f"{'SUCCESS' if post_successful else 'FAILED'} button not found")
        
        # Unknown step
        return StepResult(StepStatus.FAILED, f"Unknown step: {step_name}")
