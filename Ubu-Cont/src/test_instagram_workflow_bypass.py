"""
Test Instagram Workflow - Offline test for Instagram OSP posting workflow

This script tests the Instagram workflow with a mock post to verify
the 15-step color-coded OSP system works correctly.
"""

import sys
import os
import asyncio
import logging

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TestInstagramWorkflow")


async def main():
    """Main test function."""
    logger.info("=" * 60)
    logger.info("Starting Instagram Workflow Test (OSP Color Boxes)")
    logger.info("=" * 60)

    # Import required components
    try:
        from src.subsystems.vnc_capture import VNCCapture
        from src.subsystems.vision_engine import VisionEngine
        from src.subsystems.input_injector import InputInjector
        from src.workflows.instagram_workflow import InstagramWorkflow
        from src.fetcher import PendingPost

        logger.info("✓ Imports successful")
    except ImportError as e:
        logger.error(f"✗ Import failed: {e}")
        return False

    # Initialize subsystems
    try:
        logger.info("Initializing subsystems...")

        # VNC Capture
        vnc = VNCCapture()
        await vnc.connect()
        logger.info("✓ VNC connected")

        # Vision Engine (Qwen2.5-VL)
        vision = VisionEngine()
        logger.info("✓ Vision engine initialized")

        # Input Injector (HID)
        input_injector = InputInjector()
        await input_injector.connect()
        logger.info("✓ Input injector connected")

    except Exception as e:
        logger.error(f"✗ Subsystem initialization failed: {e}")
        return False

    # Create workflow instance
    try:
        workflow = InstagramWorkflow(vnc, vision, input_injector)
        logger.info("✓ Instagram workflow created")
    except Exception as e:
        logger.error(f"✗ Workflow creation failed: {e}")
        return False

    # Create mock post data
    mock_post = PendingPost(
        id="INSTAGRAM_TEST_001",
        platform="instagram",
        url="https://www.instagram.com/ultraskool",
        title="Test Post Title",
        body="This is a test post from the automated Instagram workflow!\n\nTesting the OSP color-coded system with:\n🟢 GREEN boxes for primary actions\n🔴 RED boxes for selections\n🔵 BLUE boxes for navigation\n\n#automation #test #instagram",
        image_path="C:\\PostQueue\\pending\\INSTAGRAM_TEST_001\\media_1.jpg",
        send_email=False
    )

    logger.info("")
    logger.info("Mock Post Details:")
    logger.info(f"  ID: {mock_post.id}")
    logger.info(f"  Platform: {mock_post.platform}")
    logger.info(f"  URL: {mock_post.url}")
    logger.info(f"  Title: {mock_post.title}")
    logger.info(f"  Body: {mock_post.body[:80]}...")
    logger.info(f"  Image: {mock_post.image_path}")
    logger.info("")

    # Execute workflow
    logger.info("=" * 60)
    logger.info("Executing Instagram Workflow...")
    logger.info("=" * 60)

    try:
        result = await workflow.execute(mock_post)

        logger.info("")
        logger.info("=" * 60)
        logger.info("WORKFLOW RESULT")
        logger.info("=" * 60)
        logger.info(f"Success: {result.success}")
        logger.info(f"Steps Completed: {result.steps_completed}/{result.total_steps}")
        logger.info(f"Duration: {result.duration_seconds:.2f}s")

        if result.success:
            logger.info("✓ TEST PASSED: Workflow completed successfully!")
            logger.info("All 15 OSP color-coded steps executed correctly")
        else:
            logger.error("✗ TEST FAILED: Workflow did not complete")
            if result.error_message:
                logger.error(f"Error: {result.error_message}")
            if result.error_step:
                logger.error(f"Failed at step: {result.error_step}")

        logger.info("=" * 60)

        return result.success

    except Exception as e:
        logger.error("")
        logger.error("=" * 60)
        logger.error("TEST CRASHED")
        logger.error("=" * 60)
        logger.exception(f"Exception: {e}")
        return False

    finally:
        # Cleanup
        try:
            await input_injector.disconnect()
            await vnc.disconnect()
            logger.info("✓ Cleanup complete")
        except:
            pass


if __name__ == "__main__":
    logger.info("")
    logger.info("╔════════════════════════════════════════════════════════════╗")
    logger.info("║    INSTAGRAM WORKFLOW TEST - OSP COLOR CODED SYSTEM        ║")
    logger.info("╚════════════════════════════════════════════════════════════╝")
    logger.info("")
    logger.info("This test validates the 15-step Instagram posting workflow:")
    logger.info("")
    logger.info("  1. Click GREEN box (New Post +)")
    logger.info("  2. Click RED box (Post type)")
    logger.info("  3. Click BLUE box (Select from computer)")
    logger.info("  4. Click RIGHT button (COPY FILE LOCATION)")
    logger.info("  5. Paste file path in File name box")
    logger.info("  6. Click Open button")
    logger.info("  7. Click RED box (Resize)")
    logger.info("  8. Click RED box (4:5 ratio)")
    logger.info("  9. Click BLUE box (Next 1)")
    logger.info(" 10. Click BLUE box (Next 2)")
    logger.info(" 11. Click RIGHT button (COPY BODY)")
    logger.info(" 12. Paste body in caption area")
    logger.info(" 13. Click BLUE box (Share)")
    logger.info(" 14. Verify 'SUCCESSFUL POST'")
    logger.info(" 15. Click SUCCESS or FAIL button")
    logger.info("")
    logger.info("─" * 60)
    logger.info("")

    # Run async main
    success = asyncio.run(main())

    logger.info("")
    if success:
        logger.info("🎉 All tests passed!")
        sys.exit(0)
    else:
        logger.info("❌ Tests failed!")
        sys.exit(1)
