#!/usr/bin/env python3
"""
Test Full Skool Workflow (with SUCCESS click)

Runs through ALL workflow steps including clicking SUCCESS at the end.
"""

import sys
import os
import asyncio
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vision_controller import VisionController
from src.input_controller import InputController
from src.subsystems.vnc_capture import VNCCapture
from src.workflows.skool_workflow import SkoolWorkflow
from src.workflows.async_base_workflow import StepResult, StepStatus
from src.fetcher import PendingPost, Platform

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FullWorkflowTest")


# All steps including SUCCESS click
STEPS_TO_RUN = [
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
    "click_success_or_fail",  # Now included - will click SUCCESS and remove post from OSP
]


async def run_workflow_steps():
    """Run all workflow steps including SUCCESS click."""
    logger.info("=" * 70)
    logger.info("SKOOL WORKFLOW TEST (FULL - with SUCCESS click)")
    logger.info("=" * 70)
    
    # Initialize controllers
    logger.info("Initializing VisionController...")
    vision = VisionController()
    
    logger.info("Initializing InputController...")
    input_ctrl = InputController()
    input_ctrl.connect()
    
    # VNC capture
    vnc = VNCCapture()
    
    # Create workflow
    workflow = SkoolWorkflow(
        vnc=vnc,
        vision=vision,
        input_injector=input_ctrl
    )
    
    # Create a test post
    test_post = PendingPost(
        id="test-full-001",
        platform=Platform.SKOOL,
        url="https://www.skool.com/test-community",
        title="Test Post from Ubuntu Brain",
        body="This is a test post created by the Ubuntu Brain Agent workflow test.",
        image_path=None,
        image_base64=None,
        send_email=False
    )
    
    workflow.current_post = test_post
    
    logger.info(f"Running {len(STEPS_TO_RUN)} steps (including SUCCESS click)")
    logger.info("=" * 70)
    
    completed = 0
    failed_step = None
    failed_message = None
    
    for i, step_name in enumerate(STEPS_TO_RUN):
        logger.info(f"\n>>> Step {i+1}/{len(STEPS_TO_RUN)}: {step_name}")
        
        try:
            result = await asyncio.wait_for(
                workflow._execute_step(step_name),
                timeout=60
            )
            
            if result.status == StepStatus.SUCCESS:
                logger.info(f"    SUCCESS: {result.message}")
                completed += 1
            elif result.status == StepStatus.SKIPPED:
                logger.info(f"    SKIPPED: {result.message}")
                completed += 1
            else:
                logger.error(f"    FAILED: {result.message}")
                failed_step = step_name
                failed_message = result.message
                break
                
        except asyncio.TimeoutError:
            logger.error(f"    TIMEOUT after 60s")
            failed_step = step_name
            failed_message = "Step timed out"
            break
        except Exception as e:
            logger.error(f"    ERROR: {e}")
            failed_step = step_name
            failed_message = str(e)
            break
        
        # Brief pause between steps
        await asyncio.sleep(0.5)
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("WORKFLOW RESULT")
    logger.info("=" * 70)
    logger.info(f"Steps Completed: {completed}/{len(STEPS_TO_RUN)}")
    
    if failed_step:
        logger.error(f"Failed at: {failed_step}")
        logger.error(f"Reason: {failed_message}")
        return False
    else:
        logger.info("All steps completed successfully!")
        logger.info("SUCCESS button was clicked - post removed from OSP")
        return True


if __name__ == "__main__":
    try:
        success = asyncio.run(run_workflow_steps())
        print("\n" + "=" * 70)
        if success:
            print("WORKFLOW COMPLETED SUCCESSFULLY!")
            print("SUCCESS button was clicked - post removed from OSP")
        else:
            print("WORKFLOW FAILED - Check logs above for details")
        print("=" * 70)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
