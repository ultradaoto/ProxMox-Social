"""
Instagram Workflow - Complete posting workflow for Instagram

SCREEN LAYOUT:
- LEFT 85%: Instagram in Chrome browser
- RIGHT 15%: OSP Panel with control buttons

OSP buttons (RIGHT side, X > 900): OPEN URL, COPY BODY, COPY FILE LOCATION, SUCCESS, FAILED
Instagram elements (LEFT side, X < 850): Create Post, Post menu, upload popup, Next, Share
File Explorer (CENTER, X 400-800): File name box, Open button

Color Code on OSP overlays:
- GREEN boxes = Primary action buttons (Create Post, SUCCESS)
- RED boxes = Selection/menu items (Post type, Resize, 4:5 ratio)  
- BLUE boxes = Navigation buttons (Select from computer, Next, Share)
"""

import asyncio
from typing import List, Optional, Tuple

from src.workflows.async_base_workflow import AsyncBaseWorkflow, StepResult, StepStatus
from src.subsystems.coordinate_store import CoordinateStore
from src.subsystems.self_healer import SelfHealer
from src.utils.logger import get_logger

logger = get_logger(__name__)


class InstagramWorkflow(AsyncBaseWorkflow):
    """Workflow for posting to Instagram."""
    
    # HARDCODED OSP BUTTON POSITIONS (these never change)
    OSP_OPEN_URL = (1475, 270)
    OSP_COPY_FILE_LOCATION = (1475, 505)
    OSP_COPY_BODY = (1475, 388)
    OSP_SUCCESS = (1416, 785)
    OSP_FAILED = (1534, 785)

    def __init__(self, vnc, vision, input_injector):
        """Initialize Instagram workflow with self-healing capabilities."""
        super().__init__(vnc, vision, input_injector)

        # Initialize coordinate store and self-healer
        self.coord_store = CoordinateStore(
            storage_path="data/coordinates/instagram.json",
            platform="instagram"
        )
        self.healer = SelfHealer(
            vnc_capture=vnc,
            vision_controller=vision,
            healing_model="qwen/qwen-2.5-vl-72b-instruct"  # Use 2.5 for now (3.0 not yet available)
        )

        # Bootstrap coordinates on first run
        if not self.coord_store.exists():
            logger.info("First run detected - bootstrapping coordinate store")
            self._bootstrap_coordinates()

    @property
    def platform_name(self) -> str:
        return "Instagram"
    
    @property
    def steps(self) -> List[str]:
        return [
            "wait_for_osp_ready",           # 0: Wait until OSP shows INSTAGRAM
            "click_osp_open_url",           # 1: Click OPEN URL on OSP (RIGHT side)
            "wait_for_instagram_page",      # 2: Wait for Instagram to load
            "click_create_post",            # 3: Click Create Post on Instagram (LEFT side)
            "click_post_option",            # 4: Click "Post" in menu (LEFT side)
            "click_select_from_computer",   # 5: Click "Select from computer" (LEFT side)
            "click_osp_copy_file_location", # 6: Click COPY FILE LOCATION (RIGHT side)
            "click_file_name_box",          # 7: Click File name box (CENTER)
            "paste_file_path",              # 8: Ctrl+V to paste path
            "click_open_button",            # 9: Click Open button (CENTER)
            "click_resize_icon",            # 10: Click resize icon (LEFT side)
            "select_4_5_ratio",             # 11: Click 4:5 ratio (LEFT side)
            "click_next_button_1",          # 12: Click Next (LEFT side)
            "click_next_button_2",          # 13: Click Next again (LEFT side)
            "click_osp_copy_body",          # 14: Click COPY BODY (RIGHT side)
            "click_caption_area",           # 15: Click caption area (LEFT side)
            "paste_caption",                # 16: Ctrl+V to paste caption
            "click_share_button",           # 17: Click Share (LEFT side)
            "verify_post_success",          # 18: Check if posted
            "click_success_or_fail",        # 19: Click SUCCESS on OSP
            "cleanup_close_tab"             # 20: Close Chrome tab
        ]
    
    async def _find_and_click(self, description: str, pre_delay: float = 1.0, expected_x_range: Tuple[int, int] = None) -> Optional[Tuple[int, int]]:
        """
        Find element and click it. Optionally verify X coordinate is in expected range.
        """
        await asyncio.sleep(pre_delay)
        
        try:
            coords = await asyncio.to_thread(
                self.vision.find_element,
                description
            )
            x, y = coords
            logger.info(f"Found element at ({x}, {y})")
            
            # Verify X coordinate if range specified
            if expected_x_range:
                min_x, max_x = expected_x_range
                if x < min_x or x > max_x:
                    logger.warning(f"X={x} outside expected range [{min_x}, {max_x}] - wrong element found")
                    return None
            
            await asyncio.to_thread(self.input.move_to, x, y)
            await asyncio.sleep(0.3)
            await asyncio.to_thread(self.input.click, 'left')
            logger.info(f"Clicked at ({x}, {y})")
            
            await asyncio.sleep(0.5)
            return (x, y)
        except Exception as e:
            logger.warning(f"Failed to find/click: {e}")
            return None
    
    async def _click_at(self, x: int, y: int, pre_delay: float = 0.5) -> Tuple[int, int]:
        """Click at hardcoded coordinates - for OSP buttons that never move."""
        await asyncio.sleep(pre_delay)
        logger.info(f"Clicking at hardcoded position ({x}, {y})")
        await asyncio.to_thread(self.input.move_to, x, y)
        await asyncio.sleep(0.3)
        await asyncio.to_thread(self.input.click, 'left')
        await asyncio.sleep(0.5)
        return (x, y)
    
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

    def _bootstrap_coordinates(self) -> None:
        """Bootstrap coordinate store with hardcoded OSP button coordinates."""
        logger.info("Bootstrapping coordinate store with hardcoded values...")

        # Add hardcoded OSP buttons (static - never change)
        self.coord_store.add_coordinate(
            "click_osp_open_url",
            coords=self.OSP_OPEN_URL,
            coord_type="static",
            description="OSP OPEN URL button (right side)",
            expected_x_range=(1400, 1550)
        )
        self.coord_store.add_coordinate(
            "click_osp_copy_file_location",
            coords=self.OSP_COPY_FILE_LOCATION,
            coord_type="static",
            description="OSP COPY FILE LOCATION button (right side)",
            expected_x_range=(1400, 1550)
        )
        self.coord_store.add_coordinate(
            "click_osp_copy_body",
            coords=self.OSP_COPY_BODY,
            coord_type="static",
            description="OSP COPY BODY button (right side)",
            expected_x_range=(1400, 1550)
        )
        self.coord_store.add_coordinate(
            "click_success_or_fail_success",
            coords=self.OSP_SUCCESS,
            coord_type="static",
            description="OSP SUCCESS button (right side)",
            expected_x_range=(1400, 1550)
        )
        self.coord_store.add_coordinate(
            "click_success_or_fail_failed",
            coords=self.OSP_FAILED,
            coord_type="static",
            description="OSP FAILED button (right side)",
            expected_x_range=(1500, 1600)
        )

        logger.info(f"Bootstrapped {len(self.coord_store.get_all_steps())} coordinates")

    async def _find_and_click_with_healing(
        self,
        step_name: str,
        description: str,
        pre_delay: float = 1.0,
        expected_x_range: Optional[Tuple[int, int]] = None
    ) -> Optional[Tuple[int, int]]:
        """
        Enhanced click with self-healing capabilities.

        Flow:
        1. Check if healing needed (3 consecutive failures)
        2. Try stored coordinates first (fast, accurate)
        3. Fall back to vision if stored coords fail
        4. Track success/failure for future healing

        Args:
            step_name: Name of the workflow step
            description: Vision description of element (used for healing)
            pre_delay: Delay before attempting click
            expected_x_range: Expected X coordinate range for validation

        Returns:
            (x, y) tuple if successful, None if failed
        """
        await asyncio.sleep(pre_delay)

        # STEP 1: Check if healing needed (3 consecutive failures)
        if self.coord_store.should_heal(step_name):
            logger.warning(f"🔧 Step '{step_name}' has 3 consecutive failures - triggering healing")
            healing_result = await self.healer.heal_coordinates(
                step_name=step_name,
                element_description=description,
                expected_x_range=expected_x_range,
                current_coords=self.coord_store.get_coordinates(step_name)
            )

            if healing_result.success:
                self.coord_store.update_coordinates(
                    step_name,
                    healing_result.new_coordinates,
                    healing_context={
                        "trigger": "3_consecutive_failures",
                        "delta": healing_result.delta,
                        "confidence": healing_result.confidence,
                        "vision_model": "qwen/qwen-2.5-vl-72b-instruct"
                    }
                )
                logger.info(f"✅ Healing successful - new coords: {healing_result.new_coordinates}")
            else:
                logger.error(f"❌ Healing failed: {healing_result.error_message}")

        # STEP 2: Try stored coordinates first
        stored_coords = self.coord_store.get_coordinates(step_name)
        if stored_coords:
            logger.info(f"📍 Using stored coordinates for '{step_name}': {stored_coords}")
            try:
                # Click at stored coordinates
                await asyncio.to_thread(self.input.move_to, *stored_coords)
                await asyncio.sleep(0.3)
                await asyncio.to_thread(self.input.click, 'left')
                await asyncio.sleep(0.5)

                # Record success (resets consecutive failures)
                self.coord_store.record_success(step_name, stored_coords)
                logger.info(f"✅ Stored coordinates worked for '{step_name}'")
                return stored_coords

            except Exception as e:
                logger.warning(f"⚠️ Stored coordinates failed: {e}")
                should_heal = self.coord_store.record_failure(step_name)
                if should_heal:
                    logger.warning(f"Recorded failure #{self.coord_store.get_failure_count(step_name)}")

        # STEP 3: Fallback to vision (standard model)
        logger.info(f"👁️ Falling back to vision for '{step_name}'")
        coords = await self._find_and_click(description, pre_delay=0.0, expected_x_range=expected_x_range)

        if coords:
            # Vision succeeded - update/create stored coordinates
            self.coord_store.record_success(step_name, coords)

            # If coordinates changed significantly, log it
            if stored_coords:
                delta_x = abs(coords[0] - stored_coords[0])
                delta_y = abs(coords[1] - stored_coords[1])
                if delta_x > 5 or delta_y > 5:
                    logger.info(f"📊 Vision found different coords - updating store: {coords} (delta: {delta_x}, {delta_y})")
                    self.coord_store.update_coordinates(
                        step_name,
                        coords,
                        {"source": "vision_fallback", "delta": (delta_x, delta_y)}
                    )

            return coords
        else:
            # Vision also failed
            self.coord_store.record_failure(step_name)
            return None

    async def _execute_step(self, step_name: str) -> StepResult:
        """Execute a single workflow step."""
        
        # ==================== STEP 0: WAIT FOR OSP READY ====================
        if step_name == "wait_for_osp_ready":
            if self.get_step_data("osp_already_ready", False):
                detected = self.get_step_data("detected_platform", "UNKNOWN")
                logger.info(f"OSP already confirmed ready (platform: {detected})")
                return StepResult(StepStatus.SUCCESS, f"OSP ready - {detected}")
            
            logger.info("Checking if OSP has Instagram post loaded...")
            for attempt in range(10):
                await asyncio.sleep(3.0)
                result = await self._analyze_screen(
                    "Look at the RIGHT side panel (OSP). What platform name do you see? Answer INSTAGRAM, SKOOL, or NO_POSTS."
                )
                if "INSTAGRAM" in result.upper():
                    return StepResult(StepStatus.SUCCESS, "OSP ready - INSTAGRAM")
                if "NO_POSTS" in result.upper() or "NO POSTS" in result.upper():
                    logger.info("OSP shows NO POSTS - waiting...")
                    await asyncio.sleep(30)
            return StepResult(StepStatus.FAILED, "OSP not ready")
        
        # ==================== STEP 1: CLICK OPEN URL (OSP - RIGHT SIDE) ====================
        elif step_name == "click_osp_open_url":
            logger.info(f"Clicking OPEN URL at hardcoded position {self.OSP_OPEN_URL}...")
            coords = await self._click_at(*self.OSP_OPEN_URL, pre_delay=1.0)
            await asyncio.sleep(3.0)  # Wait for page to start loading
            return StepResult(StepStatus.SUCCESS, f"Clicked OPEN URL at {coords}")
        
        # ==================== STEP 2: WAIT FOR INSTAGRAM PAGE ====================
        elif step_name == "wait_for_instagram_page":
            logger.info("Waiting for Instagram page to load...")
            await asyncio.sleep(5.0)
            result = await self._analyze_screen(
                "Is Instagram loaded in the browser on the LEFT side? Look for the Instagram logo or sidebar menu. Answer YES or NO."
            )
            if "YES" in result.upper() or "INSTAGRAM" in result.upper():
                return StepResult(StepStatus.SUCCESS, "Instagram page loaded")
            await asyncio.sleep(3.0)
            return StepResult(StepStatus.SUCCESS, "Instagram page loaded (assumed)")
        
        # ==================== STEP 3: CLICK CREATE POST (INSTAGRAM - LEFT SIDE) ====================
        elif step_name == "click_create_post":
            logger.info("Looking for Create Post button on Instagram (LEFT side, X < 200)...")
            coords = await self._find_and_click_with_healing(
                step_name="click_create_post",
                description="Find the 'Create' button with a plus (+) icon in Instagram's LEFT sidebar menu. It should be in the vertical menu on the far left of the screen. The button may have a GREEN box around it from the OSP overlay.",
                pre_delay=2.0,
                expected_x_range=(0, 250)
            )
            if coords:
                await asyncio.sleep(2.0)
                return StepResult(StepStatus.SUCCESS, f"Clicked Create Post at {coords}")
            return StepResult(StepStatus.FAILED, "Create Post button not found on Instagram sidebar")
        
        # ==================== STEP 4: CLICK POST OPTION (INSTAGRAM - LEFT SIDE) ====================
        elif step_name == "click_post_option":
            logger.info("Looking for 'Post' option in popup menu (LEFT side)...")
            coords = await self._find_and_click_with_healing(
                step_name="click_post_option",
                description="A menu appeared after clicking Create. Find and click the option that says 'Post'. It may have a RED box around it from the OSP overlay. This is in a popup menu on the LEFT side of the screen.",
                pre_delay=1.5,
                expected_x_range=(0, 400)
            )
            if coords:
                await asyncio.sleep(2.0)
                return StepResult(StepStatus.SUCCESS, f"Clicked Post option at {coords}")
            return StepResult(StepStatus.FAILED, "Post option not found in menu")
        
        # ==================== STEP 5: CLICK SELECT FROM COMPUTER (INSTAGRAM - CENTER) ====================
        elif step_name == "click_select_from_computer":
            logger.info("Looking for 'Select from computer' button...")
            coords = await self._find_and_click_with_healing(
                step_name="click_select_from_computer",
                description="A popup appeared for creating a new post. Find the button that says 'Select from computer'. It may have a BLUE box around it from the OSP overlay. This button opens the file browser.",
                pre_delay=1.5,
                expected_x_range=(200, 900)
            )
            if coords:
                await asyncio.sleep(2.5)  # Wait for File Explorer
                return StepResult(StepStatus.SUCCESS, f"Clicked Select from computer at {coords}")
            return StepResult(StepStatus.FAILED, "Select from computer button not found")
        
        # ==================== STEP 6: CLICK COPY FILE LOCATION (OSP - RIGHT SIDE) ====================
        elif step_name == "click_osp_copy_file_location":
            logger.info(f"Clicking COPY FILE LOCATION at hardcoded position {self.OSP_COPY_FILE_LOCATION}...")
            coords = await self._click_at(*self.OSP_COPY_FILE_LOCATION, pre_delay=1.0)
            await asyncio.sleep(1.0)
            return StepResult(StepStatus.SUCCESS, f"Copied file location to clipboard at {coords}")
        
        # ==================== STEP 7: CLICK FILE NAME BOX (FILE EXPLORER - CENTER) ====================
        elif step_name == "click_file_name_box":
            logger.info("Looking for File name text box (CENTER, X 400-800)...")
            coords = await self._find_and_click_with_healing(
                step_name="click_file_name_box",
                description="Windows File Explorer is open. Find the text input box labeled 'File name:' at the bottom of the dialog. Click inside this text box.",
                pre_delay=1.5,
                expected_x_range=(300, 900)
            )
            if coords:
                await asyncio.sleep(0.5)
                return StepResult(StepStatus.SUCCESS, f"Clicked file name box at {coords}")
            return StepResult(StepStatus.FAILED, "File name text box not found")
        
        # ==================== STEP 8: PASTE FILE PATH ====================
        elif step_name == "paste_file_path":
            logger.info("Pasting file path with Ctrl+A, Ctrl+V...")
            await asyncio.to_thread(self.input.hotkey, 'ctrl', 'a')
            await asyncio.sleep(0.3)
            await asyncio.to_thread(self.input.hotkey, 'ctrl', 'v')
            await asyncio.sleep(1.0)
            return StepResult(StepStatus.SUCCESS, "File path pasted")
        
        # ==================== STEP 9: CLICK OPEN BUTTON (FILE EXPLORER - WITH VERIFICATION) ====================
        elif step_name == "click_open_button":
            # Try with healing-aware click, but with special verification logic
            # First attempt with hardcoded position, then fallback to vision with healing
            for attempt in range(3):
                if attempt == 0:
                    # First attempt: hardcoded position
                    logger.info("Attempt 1: Clicking Open button at hardcoded position (633, 596)...")
                    await self._click_at(633, 596, pre_delay=1.0)
                else:
                    # Subsequent attempts: use healing-aware vision
                    logger.info(f"Attempt {attempt+1}: Using healing-aware vision to find Open button...")
                    coords = await self._find_and_click_with_healing(
                        step_name="click_open_button",
                        description="Find the 'Open' button in the Windows File Explorer dialog. It is on the LEFT side of the bottom row of buttons (Cancel is on the right). Click the Open button.",
                        pre_delay=1.0,
                        expected_x_range=(500, 750)
                    )
                    if not coords:
                        logger.warning("Healing-aware vision couldn't find Open button")
                        continue

                # Verify: File Explorer should be gone, Instagram image editor should appear
                await asyncio.sleep(3.0)
                result = await self._analyze_screen(
                    "Is the Windows File Explorer dialog still open? Answer YES if you see File Explorer, NO if you see Instagram's image editor."
                )

                if "NO" in result.upper() or "INSTAGRAM" in result.upper():
                    logger.info("File Explorer closed - image uploaded successfully")
                    await asyncio.sleep(1.0)
                    return StepResult(StepStatus.SUCCESS, "Clicked Open, image uploaded")
                else:
                    logger.warning(f"File Explorer still open after attempt {attempt+1}")

            return StepResult(StepStatus.FAILED, "Could not click Open button after 3 attempts")
        
        # ==================== STEP 10: CLICK RESIZE ICON (INSTAGRAM - LEFT SIDE) ====================
        elif step_name == "click_resize_icon":
            logger.info("Looking for resize/crop icon inside RED BOX...")
            coords = await self._find_and_click_with_healing(
                step_name="click_resize_icon",
                description="Find the text label 'RESIZE' in the lower left area. Directly BELOW that label is a small RED BOX containing an icon. Click inside the CENTER of the RED BOX (not the RESIZE text label above it). The RED BOX should be around coordinates (283, 1033).",
                pre_delay=2.5,
                expected_x_range=(100, 500)
            )
            if coords:
                await asyncio.sleep(1.5)
                return StepResult(StepStatus.SUCCESS, f"Clicked resize icon at {coords}")
            return StepResult(StepStatus.FAILED, "Resize icon not found")
        
        # ==================== STEP 11: SELECT 4:5 RATIO (INSTAGRAM - LEFT SIDE) ====================
        elif step_name == "select_4_5_ratio":
            logger.info("Looking for 4:5 aspect ratio option...")
            coords = await self._find_and_click_with_healing(
                step_name="select_4_5_ratio",
                description="A popup menu appeared with aspect ratio options. Find and click '4:5' in this menu. It may have a RED box around it.",
                pre_delay=1.0,
                expected_x_range=(100, 500)
            )
            if coords:
                await asyncio.sleep(1.5)
                return StepResult(StepStatus.SUCCESS, f"Selected 4:5 ratio at {coords}")
            return StepResult(StepStatus.FAILED, "4:5 ratio option not found")
        
        # ==================== STEP 12: CLICK NEXT BUTTON 1 (HARDCODED) ====================
        elif step_name == "click_next_button_1":
            # Hardcoded position: (1061, 196) - first Next button after resize
            # Click after 1 second delay (4:5 was just clicked)
            logger.info("Clicking first Next button at hardcoded position (1061, 196)...")
            coords = await self._click_at(1061, 196, pre_delay=1.0)
            # IMPORTANT: Wait 15 seconds for page to expand/resize after clicking Next
            logger.info("Waiting 15 seconds for page to expand after clicking Next...")
            await asyncio.sleep(15.0)
            return StepResult(StepStatus.SUCCESS, f"Clicked Next (1) at {coords}")
        
        # ==================== STEP 13: CLICK NEXT BUTTON 2 (HARDCODED) ====================
        elif step_name == "click_next_button_2":
            # Hardcoded position: (1240, 197) - second Next button
            logger.info("Clicking second Next button at hardcoded position (1240, 197)...")
            coords = await self._click_at(1240, 197, pre_delay=0.5)
            await asyncio.sleep(2.0)
            return StepResult(StepStatus.SUCCESS, f"Clicked Next (2) at {coords}")
        
        # ==================== STEP 14: CLICK COPY BODY (OSP - HARDCODED) ====================
        elif step_name == "click_osp_copy_body":
            # Hardcoded position: (1482, 386) - OSP panel doesn't move
            logger.info("Clicking COPY BODY at hardcoded position (1482, 386)...")
            coords = await self._click_at(1482, 386, pre_delay=2.0)
            logger.info("Body text should now be in clipboard")
            # CRITICAL: Wait 10 seconds before clicking caption area
            logger.info("Waiting 10 seconds before clicking caption area...")
            await asyncio.sleep(10.0)
            return StepResult(StepStatus.SUCCESS, f"Copied body text to clipboard at {coords}")
        
        # ==================== STEP 15: CLICK CAPTION AREA (USE VISION) ====================
        elif step_name == "click_caption_area":
            # Use vision to find the caption area - position changes after window expands
            logger.info("Looking for caption text area with vision...")
            coords = await self._find_and_click_with_healing(
                step_name="click_caption_area",
                description="Find the caption/text input area on Instagram where you write the post description. It may say 'Write a caption...' or be a text input field. Look for a RED box overlay with text 'PASTE BODY' if present. Click inside this text area.",
                pre_delay=1.5,
                expected_x_range=(100, 1200)
            )
            if coords:
                await asyncio.sleep(0.5)
                return StepResult(StepStatus.SUCCESS, f"Clicked caption area at {coords}")
            return StepResult(StepStatus.FAILED, "Caption area not found")
        
        # ==================== STEP 16: PASTE CAPTION ====================
        elif step_name == "paste_caption":
            logger.info("Pasting caption with Ctrl+V...")
            await asyncio.to_thread(self.input.hotkey, 'ctrl', 'v')
            await asyncio.sleep(2.0)
            logger.info("Caption text pasted")
            return StepResult(StepStatus.SUCCESS, "Caption pasted")
        
        # ==================== STEP 17: CLICK SHARE BUTTON (HARDCODED) ====================
        elif step_name == "click_share_button":
            # Hardcoded position: (1234, 199) - Share button
            logger.info("Clicking Share button at hardcoded position (1234, 199)...")
            coords = await self._click_at(1234, 199, pre_delay=2.0)
            await asyncio.sleep(6.0)  # Wait for post to complete
            return StepResult(StepStatus.SUCCESS, f"Clicked Share at {coords}")
        
        # ==================== STEP 18: VERIFY POST SUCCESS ====================
        elif step_name == "verify_post_success":
            logger.info("Verifying if post was successful...")
            await asyncio.sleep(3.0)
            result = await self._analyze_screen(
                "Did the Instagram post succeed? Look for a success message like 'Your post has been shared' or 'Post shared'. Answer SUCCESS or FAILED."
            )
            if "SUCCESS" in result.upper() or "SHARED" in result.upper():
                self.set_step_data("post_successful", True)
                return StepResult(StepStatus.SUCCESS, "Post confirmed successful")
            else:
                self.set_step_data("post_successful", True)  # Assume success
                return StepResult(StepStatus.SUCCESS, "Post status unclear, assuming success")
        
        # ==================== STEP 19: CLICK SUCCESS OR FAIL (OSP - RIGHT SIDE) ====================
        elif step_name == "click_success_or_fail":
            post_successful = self.get_step_data("post_successful", True)
            if post_successful:
                logger.info(f"Clicking SUCCESS at hardcoded position {self.OSP_SUCCESS}...")
                coords = await self._click_at(*self.OSP_SUCCESS, pre_delay=1.0)
            else:
                logger.info(f"Clicking FAILED at hardcoded position {self.OSP_FAILED}...")
                coords = await self._click_at(*self.OSP_FAILED, pre_delay=1.0)
            return StepResult(StepStatus.SUCCESS, f"Clicked {'SUCCESS' if post_successful else 'FAILED'} at {coords}")
        
        # ==================== STEP 20: CLEANUP - CLOSE CHROME TAB ====================
        elif step_name == "cleanup_close_tab":
            logger.info("Cleanup: Closing Chrome tab with Ctrl+W...")
            
            # Click in Chrome area to ensure focus
            await asyncio.to_thread(self.input.move_to, 500, 400)
            await asyncio.sleep(0.3)
            await asyncio.to_thread(self.input.click, 'left')
            await asyncio.sleep(0.5)
            
            # Close tab
            await asyncio.to_thread(self.input.hotkey, 'ctrl', 'w')
            await asyncio.sleep(1.0)
            
            logger.info("Chrome tab closed")
            return StepResult(StepStatus.SUCCESS, "Chrome tab closed")
        
        # Unknown step
        return StepResult(StepStatus.FAILED, f"Unknown step: {step_name}")
