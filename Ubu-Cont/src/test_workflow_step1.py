#!/usr/bin/env python3
"""
Test Workflow Step 1 - Click OPEN URL

This tests that the SkoolWorkflow can successfully find and click
the OPEN URL button using the same working approach as test_osp_click.py.
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WorkflowTest")


async def test_step1():
    """Test just step 1 (click OPEN URL) of the Skool workflow."""
    logger.info("=" * 60)
    logger.info("Testing SkoolWorkflow Step 1: click_osp_open_url")
    logger.info("=" * 60)
    
    # Initialize controllers (same as test_osp_click.py)
    logger.info("Initializing VisionController...")
    vision = VisionController()
    
    logger.info("Initializing InputController...")
    input_ctrl = InputController()
    input_ctrl.connect()
    
    # Create a dummy VNC capture (workflow needs it but we use VisionController's capture)
    vnc = VNCCapture()
    
    # Create workflow
    workflow = SkoolWorkflow(
        vnc=vnc,
        vision=vision,
        input_injector=input_ctrl
    )
    
    # Create a fake post for testing
    fake_post = PendingPost(
        id="test-001",
        platform=Platform.SKOOL,
        url="https://www.skool.com/test",
        title="Test Post Title",
        body="Test post body content",
        image_path=None,
        image_base64=None,
        send_email=False
    )
    
    workflow.current_post = fake_post
    
    # Execute just step 1
    logger.info("Executing step 1: click_osp_open_url")
    result = await workflow._execute_step("click_osp_open_url")
    
    logger.info(f"Result: {result.status.name} - {result.message}")
    
    if result.status == StepStatus.SUCCESS:
        logger.info("SUCCESS! Step 1 completed successfully.")
        return True
    else:
        logger.error(f"FAILED: {result.message}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_step1())
    sys.exit(0 if success else 1)
