#!/usr/bin/env python3
"""
Manual Instagram Workflow Test

Run this to test the Instagram posting workflow step-by-step.
Uses the working VisionController and InputController.

Usage:
    python src/test_instagram_manual.py
    
The OSP on Windows 10 should already have an Instagram post loaded.
"""

import sys
import os
import asyncio
import logging

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TestInstagram")


async def run_test():
    """Run the Instagram workflow test."""
    
    from src.vision_controller import VisionController
    from src.input_controller import InputController
    from src.workflows.instagram_workflow import InstagramWorkflow
    from src.fetcher import PendingPost, Platform
    from src.subsystems.vnc_capture import VNCCapture
    
    logger.info("=" * 60)
    logger.info("INSTAGRAM WORKFLOW TEST")
    logger.info("=" * 60)
    
    # Initialize components
    logger.info("Initializing VNC...")
    vnc = VNCCapture(host='192.168.100.100', port=5900, password='VNC!Pass3')
    await vnc.initialize()
    
    logger.info("Initializing VisionController...")
    vision = VisionController()
    
    logger.info("Initializing InputController...")
    input_ctrl = InputController()
    
    # Check what's on OSP
    logger.info("")
    logger.info("Checking OSP screen...")
    result = vision.analyze_screen(
        "What platform name do you see on the OSP panel on the right? Answer SKOOL, INSTAGRAM, or FACEBOOK."
    )
    logger.info(f"OSP shows: {result}")
    
    if "INSTAGRAM" not in result.upper():
        logger.warning("OSP does not show INSTAGRAM! Make sure Instagram post is loaded.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return False
    
    # Create workflow
    logger.info("")
    logger.info("Creating Instagram workflow...")
    workflow = InstagramWorkflow(vnc=vnc, vision=vision, input_injector=input_ctrl)
    workflow.step_timeout = 120  # 2 minutes per step
    workflow.max_retries = 2
    
    # Mark OSP as ready
    workflow.set_step_data('osp_already_ready', True)
    workflow.set_step_data('detected_platform', 'INSTAGRAM')
    
    # Create test post
    post = PendingPost(
        id='test-instagram-manual',
        platform=Platform.INSTAGRAM,
        url='https://instagram.com',
        title='Test Post',
        body='Test body content',
        image_path=None,
        image_base64=None,
        send_email=False
    )
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("STARTING WORKFLOW")
    logger.info("=" * 60)
    logger.info("")
    
    # Execute
    result = await workflow.execute(post)
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("RESULT")
    logger.info("=" * 60)
    logger.info(f"Success: {result.success}")
    logger.info(f"Steps completed: {result.steps_completed}/{result.total_steps}")
    logger.info(f"Duration: {result.duration_seconds:.1f}s")
    if result.error_message:
        logger.error(f"Error: {result.error_message}")
    if result.error_step:
        logger.error(f"Failed at: {result.error_step}")
    
    return result.success


if __name__ == "__main__":
    print()
    print("=" * 60)
    print("INSTAGRAM WORKFLOW MANUAL TEST")
    print("=" * 60)
    print()
    print("Make sure:")
    print("  1. Windows 10 OSP has an Instagram post loaded")
    print("  2. The brain daemon is NOT running")
    print("  3. VNC stream server is running")
    print()
    
    try:
        success = asyncio.run(run_test())
        print()
        if success:
            print("TEST PASSED!")
            sys.exit(0)
        else:
            print("TEST FAILED!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nTest cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
