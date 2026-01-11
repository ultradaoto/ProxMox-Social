#!/usr/bin/env python3
"""
Ubuntu Brain Agent - Main Entry Point

Uses the WORKING VisionController and InputController approach
from test_osp_click.py that successfully finds and clicks buttons.
"""

import asyncio
import signal
import sys
import os
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.orchestrator import BrainOrchestrator
from src.utils.logger import setup_logging, get_logger

logger = get_logger(__name__)


class UbuntuBrain:
    """Main brain controller."""
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config_path = config_path
        self.orchestrator = None
        self.running = False
        self._shutdown_count = 0
    
    async def start(self):
        """Start the brain."""
        logger.info("=" * 60)
        logger.info("UBUNTU BRAIN AGENT STARTING")
        logger.info("Using WORKING VisionController + InputController")
        logger.info("=" * 60)
        
        self.running = True
        
        # Initialize orchestrator
        self.orchestrator = BrainOrchestrator(self.config_path)
        await self.orchestrator.initialize()
        
        logger.info("Brain initialized successfully")
        logger.info("Beginning main loop...")
        
        # Main loop
        await self.orchestrator.run_forever()
    
    async def stop(self):
        """Stop the brain gracefully."""
        logger.info("Stopping Ubuntu Brain...")
        self.running = False
        
        if self.orchestrator:
            await self.orchestrator.shutdown()
        
        logger.info("Ubuntu Brain stopped")
    
    def handle_signal(self, signum, frame):
        """Handle shutdown signals - force exit on second signal."""
        self._shutdown_count += 1
        
        if self._shutdown_count >= 2:
            logger.info(f"Force exit (signal {signum} received {self._shutdown_count} times)")
            os._exit(0)
        
        logger.info(f"Received signal {signum}, initiating shutdown... (send again to force)")
        self.running = False
        
        # Cancel all running tasks
        for task in asyncio.all_tasks():
            task.cancel()


async def main():
    """Main entry point."""
    setup_logging()
    
    brain = UbuntuBrain()
    
    # Setup signal handlers (Unix only)
    if sys.platform != 'win32':
        signal.signal(signal.SIGINT, brain.handle_signal)
        signal.signal(signal.SIGTERM, brain.handle_signal)
    
    try:
        await brain.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except asyncio.CancelledError:
        logger.info("Tasks cancelled, shutting down")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
    finally:
        await brain.stop()


if __name__ == "__main__":
    asyncio.run(main())
