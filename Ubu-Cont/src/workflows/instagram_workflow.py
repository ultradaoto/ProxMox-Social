"""
Instagram Workflow - Complete posting workflow for Instagram with OSP Color Boxes

This workflow uses the On-Screen Prompter (OSP) system where colored boxes guide
the Qwen2.5-VL vision model through the Instagram posting process.

Color Code:
- GREEN boxes = Primary action buttons (New Post, SUCCESS)
- RED boxes = Selection/menu items (Post type, Resize, 4:5 ratio)
- BLUE boxes = Navigation buttons (Select from computer, Next, Share)
- RIGHT SIDE buttons = System controls (COPY FILE LOCATION, COPY BODY, SUCCESS, FAIL)

Steps:
1. Click GREEN box around + button (New Post)
2. Click RED box containing "Post" (NEW POST)
3. Click BLUE box "Select from computer"
4. Click RIGHT side "COPY FILE LOCATION"
5. Click "File name:" text box and paste path
6. Click "Open" button
7. Click RED box for Resize
8. Click RED box with "4:5" ratio
9. Click BLUE box "Next" (first)
10. Click BLUE box "Next" (second)
11. Click RIGHT side "COPY BODY"
12. Click caption area and paste body
13. Click BLUE box "Share"
14. Verify success
15. Click SUCCESS or FAIL button
"""

import asyncio
from typing import List, Optional

from src.workflows.async_base_workflow import AsyncBaseWorkflow, StepResult, StepStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class InstagramWorkflow(AsyncBaseWorkflow):
    """Workflow for posting to Instagram using OSP color-coded boxes"""

    @property
    def platform_name(self) -> str:
        return "Instagram"

    @property
    def steps(self) -> List[str]:
        return [
            "click_new_post_green",         # Step 1: Click GREEN box (+ button)
            "select_post_type_red",         # Step 2: Click RED box "Post"
            "select_from_computer_blue",    # Step 3: Click BLUE box "Select from computer"
            "copy_file_location",           # Step 4: Click RIGHT "COPY FILE LOCATION"
            "paste_file_path",              # Step 5: Click File name box and paste
            "click_open_button",            # Step 6: Click Open button
            "click_resize_red",             # Step 7: Click RED box Resize
            "select_4_5_ratio_red",         # Step 8: Click RED box "4:5"
            "click_next_1_blue",            # Step 9: Click BLUE box "Next" (first)
            "click_next_2_blue",            # Step 10: Click BLUE box "Next" (second)
            "copy_body_text",               # Step 11: Click RIGHT "COPY BODY"
            "paste_body_text",              # Step 12: Click caption area and paste
            "click_share_blue",             # Step 13: Click BLUE box "Share"
            "verify_post_success",          # Step 14: Verify "SUCCESSFUL POST"
            "click_success_or_fail"         # Step 15: Click SUCCESS or FAIL button
        ]

    async def _execute_step(self, step_name: str) -> StepResult:
        """Execute a single step in the Instagram OSP workflow."""

        # ==================== STEP 1: CLICK NEW POST (GREEN BOX) ====================
        if step_name == "click_new_post_green":
            logger.info("Looking for GREEN box around + button (New Post)...")

            screenshot = await self.take_screenshot("step01_green_new_post")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Find the GREEN box with "New Post" tag
            element = await self.vision.find_element(
                screenshot,
                "GREEN box that surrounds a + button on the left side. There is a green tag above it saying 'New Post'. Click the CENTER of the GREEN box."
            )

            if not element:
                return StepResult(StepStatus.FAILED, "GREEN New Post box not found")

            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked GREEN New Post box at ({element.x}, {element.y})")

            await asyncio.sleep(2)
            return StepResult(StepStatus.SUCCESS, "Clicked New Post")

        # ==================== STEP 2: SELECT POST TYPE (RED BOX) ====================
        elif step_name == "select_post_type_red":
            logger.info("Looking for RED box containing 'Post'...")

            screenshot = await self.take_screenshot("step02_red_post_type")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Find the RED box with "Post" text
            element = await self.vision.find_element(
                screenshot,
                "RED box that contains the word 'Post'. There is a red tag above it saying 'NEW POST'. Click the CENTER of the RED box."
            )

            if not element:
                return StepResult(StepStatus.FAILED, "RED Post type box not found")

            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked RED Post type at ({element.x}, {element.y})")

            await asyncio.sleep(2)
            return StepResult(StepStatus.SUCCESS, "Selected Post type")

        # ==================== STEP 3: SELECT FROM COMPUTER (BLUE BOX) ====================
        elif step_name == "select_from_computer_blue":
            logger.info("Looking for BLUE box 'Select from computer'...")

            screenshot = await self.take_screenshot("step03_blue_select_computer")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Find the BLUE box with "Select from computer"
            element = await self.vision.find_element(
                screenshot,
                "BLUE box in the popup that contains text 'Select from computer'. Click the CENTER of the BLUE box."
            )

            if not element:
                return StepResult(StepStatus.FAILED, "BLUE Select from computer box not found")

            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked BLUE Select from computer at ({element.x}, {element.y})")

            await asyncio.sleep(2.5)  # Wait for File Explorer to open
            return StepResult(StepStatus.SUCCESS, "File Explorer opened")

        # ==================== STEP 4: COPY FILE LOCATION ====================
        elif step_name == "copy_file_location":
            logger.info("Looking for 'COPY FILE LOCATION' button on RIGHT side...")

            screenshot = await self.take_screenshot("step04_copy_file_location")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Find the button on RIGHT side
            element = await self.vision.find_element(
                screenshot,
                "button on the RIGHT side of the screen that says 'COPY FILE LOCATION'. Click the CENTER of that button."
            )

            if not element:
                return StepResult(StepStatus.FAILED, "COPY FILE LOCATION button not found")

            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked COPY FILE LOCATION at ({element.x}, {element.y})")

            await asyncio.sleep(0.5)  # Wait for clipboard
            return StepResult(StepStatus.SUCCESS, "File location copied to clipboard")

        # ==================== STEP 5: PASTE FILE PATH ====================
        elif step_name == "paste_file_path":
            logger.info("Looking for 'File name:' text box...")

            screenshot = await self.take_screenshot("step05_file_name_box")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Find the File name text box
            element = await self.vision.find_element(
                screenshot,
                "text input box labeled 'File name:' at the bottom of the Windows File Explorer dialog. Click in the CENTER of that text box."
            )

            if not element:
                return StepResult(StepStatus.FAILED, "File name text box not found")

            # Click in the text box
            await self.input.click_at(element.x, element.y)
            await asyncio.sleep(0.3)

            # Paste the file path
            await self.input.paste()
            logger.info(f"Pasted file path at ({element.x}, {element.y})")

            await asyncio.sleep(0.5)
            return StepResult(StepStatus.SUCCESS, "File path pasted")

        # ==================== STEP 6: CLICK OPEN BUTTON ====================
        elif step_name == "click_open_button":
            logger.info("Looking for 'Open' button...")

            screenshot = await self.take_screenshot("step06_open_button")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Find the Open button
            element = await self.vision.find_element(
                screenshot,
                "the 'Open' button at the bottom right of the Windows File Explorer dialog. Click the CENTER of the Open button."
            )

            if not element:
                return StepResult(StepStatus.FAILED, "Open button not found")

            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked Open button at ({element.x}, {element.y})")

            await asyncio.sleep(3)  # Wait for image upload
            return StepResult(StepStatus.SUCCESS, "Image uploaded")

        # ==================== STEP 7: CLICK RESIZE (RED BOX) ====================
        elif step_name == "click_resize_red":
            logger.info("Looking for RED box with RESIZE tag...")

            screenshot = await self.take_screenshot("step07_red_resize")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Find the RED box with RESIZE tag
            element = await self.vision.find_element(
                screenshot,
                "RED box with a red tag above it saying 'RESIZE'. Click the CENTER of the RED box (not the tag, the box itself)."
            )

            if not element:
                return StepResult(StepStatus.FAILED, "RED Resize box not found")

            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked RED Resize at ({element.x}, {element.y})")

            await asyncio.sleep(1)
            return StepResult(StepStatus.SUCCESS, "Clicked Resize")

        # ==================== STEP 8: SELECT 4:5 RATIO (RED BOX) ====================
        elif step_name == "select_4_5_ratio_red":
            logger.info("Looking for RED box with '4:5'...")

            screenshot = await self.take_screenshot("step08_red_4_5_ratio")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Find the RED box with 4:5
            element = await self.vision.find_element(
                screenshot,
                "RED box that contains '4:5' text. There is a red tag above it saying '4:5 RATIO SELECT'. Click the CENTER of the RED box."
            )

            if not element:
                return StepResult(StepStatus.FAILED, "RED 4:5 ratio box not found")

            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked RED 4:5 ratio at ({element.x}, {element.y})")

            await asyncio.sleep(1.5)
            return StepResult(StepStatus.SUCCESS, "Selected 4:5 ratio")

        # ==================== STEP 9: CLICK NEXT 1 (BLUE BOX) ====================
        elif step_name == "click_next_1_blue":
            logger.info("Looking for first BLUE 'Next' box...")

            screenshot = await self.take_screenshot("step09_blue_next_1")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Find the BLUE box with Next
            element = await self.vision.find_element(
                screenshot,
                "BLUE rectangle that contains the text 'Next'. There is a blue tag above it saying 'NEXT'. Click the CENTER of the BLUE rectangle."
            )

            if not element:
                return StepResult(StepStatus.FAILED, "BLUE Next button (1) not found")

            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked BLUE Next (1) at ({element.x}, {element.y})")

            await asyncio.sleep(2)
            return StepResult(StepStatus.SUCCESS, "Clicked Next (1)")

        # ==================== STEP 10: CLICK NEXT 2 (BLUE BOX) ====================
        elif step_name == "click_next_2_blue":
            logger.info("Looking for second BLUE 'Next' box...")

            screenshot = await self.take_screenshot("step10_blue_next_2")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Find another BLUE box with Next
            element = await self.vision.find_element(
                screenshot,
                "BLUE rectangle that contains the text 'Next'. Click the CENTER of the BLUE rectangle."
            )

            if not element:
                return StepResult(StepStatus.FAILED, "BLUE Next button (2) not found")

            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked BLUE Next (2) at ({element.x}, {element.y})")

            await asyncio.sleep(2)
            return StepResult(StepStatus.SUCCESS, "Clicked Next (2)")

        # ==================== STEP 11: COPY BODY TEXT ====================
        elif step_name == "copy_body_text":
            logger.info("Looking for 'COPY BODY' button on RIGHT side...")

            screenshot = await self.take_screenshot("step11_copy_body")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Find the COPY BODY button on RIGHT side
            element = await self.vision.find_element(
                screenshot,
                "button on the RIGHT side of the screen that says 'COPY BODY'. Click the CENTER of that button."
            )

            if not element:
                return StepResult(StepStatus.FAILED, "COPY BODY button not found")

            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked COPY BODY at ({element.x}, {element.y})")

            await asyncio.sleep(0.5)  # Wait for clipboard
            return StepResult(StepStatus.SUCCESS, "Body text copied to clipboard")

        # ==================== STEP 12: PASTE BODY TEXT ====================
        elif step_name == "paste_body_text":
            logger.info("Looking for caption paste area...")

            screenshot = await self.take_screenshot("step12_paste_body")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Find the caption area
            element = await self.vision.find_element(
                screenshot,
                "area that says 'Click here and Paste BODY' or similar caption input area. Click the CENTER of that text input area."
            )

            if not element:
                return StepResult(StepStatus.FAILED, "Caption paste area not found")

            # Click in the caption area
            await self.input.click_at(element.x, element.y)
            await asyncio.sleep(0.3)

            # Paste the body text
            await self.input.paste()
            logger.info(f"Pasted body text at ({element.x}, {element.y})")

            await asyncio.sleep(1)
            return StepResult(StepStatus.SUCCESS, "Body text pasted")

        # ==================== STEP 13: CLICK SHARE (BLUE BOX) ====================
        elif step_name == "click_share_blue":
            logger.info("Looking for BLUE 'Share' box...")

            screenshot = await self.take_screenshot("step13_blue_share")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Find the BLUE box with Share
            element = await self.vision.find_element(
                screenshot,
                "BLUE rectangle that contains the text 'Share'. There is a blue tag above it saying 'NEXT'. Click the CENTER of the BLUE rectangle."
            )

            if not element:
                return StepResult(StepStatus.FAILED, "BLUE Share button not found")

            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked BLUE Share at ({element.x}, {element.y})")

            await asyncio.sleep(5)  # Wait for post to complete
            return StepResult(StepStatus.SUCCESS, "Clicked Share")

        # ==================== STEP 14: VERIFY SUCCESS ====================
        elif step_name == "verify_post_success":
            logger.info("Verifying post was successful...")

            screenshot = await self.take_screenshot("step14_verify_success")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            # Ask vision: Check for success message
            state = await self.vision.verify_screen_state(
                screenshot,
                "Does the page show 'SUCCESSFUL POST' or similar success message? Answer YES if success, NO if failed or error."
            )

            if state.is_match:
                logger.info("Post confirmed successful!")
                self.set_step_data("post_successful", True)
                return StepResult(StepStatus.SUCCESS, "Post confirmed successful")
            else:
                # Check for error
                error = await self.vision.check_for_error_dialog(screenshot)
                if error:
                    logger.error(f"Error detected: {error}")
                    self.set_step_data("post_successful", False)
                    return StepResult(StepStatus.SUCCESS, f"Post failed: {error}")

                # Ambiguous - check more carefully
                logger.warning("Success confirmation unclear, checking again...")
                self.set_step_data("post_successful", False)
                return StepResult(StepStatus.SUCCESS, "Post status uncertain")

        # ==================== STEP 15: CLICK SUCCESS OR FAIL ====================
        elif step_name == "click_success_or_fail":
            post_successful = self.get_step_data("post_successful", True)

            screenshot = await self.take_screenshot("step15_final_report")
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")

            if post_successful:
                logger.info("Looking for large GREEN 'SUCCESS' button on RIGHT side...")

                element = await self.vision.find_element(
                    screenshot,
                    "large GREEN button on the RIGHT side of the screen that says 'SUCCESS'. Click the CENTER of that green button."
                )

                if not element:
                    # Try alternate description
                    element = await self.vision.find_element(
                        screenshot,
                        "button indicating success on the right panel, possibly green colored"
                    )

                if not element:
                    return StepResult(StepStatus.FAILED, "SUCCESS button not found")

                await self.input.click_at(element.x, element.y)
                logger.info(f"Clicked SUCCESS button at ({element.x}, {element.y})")

                return StepResult(StepStatus.SUCCESS, "Reported success to API")

            else:
                logger.info("Looking for 'FAIL' button on RIGHT side...")

                element = await self.vision.find_element(
                    screenshot,
                    "button on the RIGHT side of the screen that says 'FAIL'. Click the CENTER of that button."
                )

                if not element:
                    # Try alternate description
                    element = await self.vision.find_element(
                        screenshot,
                        "button indicating failure on the right panel"
                    )

                if not element:
                    return StepResult(StepStatus.FAILED, "FAIL button not found")

                await self.input.click_at(element.x, element.y)
                logger.info(f"Clicked FAIL button at ({element.x}, {element.y})")

                return StepResult(StepStatus.SUCCESS, "Reported failure to API")

        # Unknown step
        else:
            return StepResult(StepStatus.FAILED, f"Unknown step: {step_name}")
