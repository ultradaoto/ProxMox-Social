#!/usr/bin/env python3
"""
Ubuntu Brain Agent - Main Entry Point

This is the BRAIN that orchestrates all social media posting.
It runs continuously, polling for posts and executing workflows.
"""

import asyncio
import signal
import sys
import os
from pathlib import Path

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
    
    async def start(self):
        """Start the brain."""
        logger.info("=" * 60)
        logger.info("UBUNTU BRAIN AGENT STARTING")
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
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.running = False


async def main():
    """Main entry point."""
    # Setup logging
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
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
    finally:
        await brain.stop()


if __name__ == "__main__":
    asyncio.run(main())
