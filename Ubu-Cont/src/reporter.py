"""
Reporter Module - Reports workflow results to the API.

This module handles all communication back to the Social Dashboard API
to report success, failure, and status updates.
"""

import asyncio
import aiohttp
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

from src.utils.logger import get_logger

logger = get_logger(__name__)


class PostStatus(Enum):
    """Post status values."""
    PENDING = "pending"
    PROCESSING = "processing"
    POSTING = "posting"
    SUCCESS = "success"
    FAILED = "failed"


class Reporter:
    """Reports workflow results to the API."""
    
    def __init__(self, api_base_url: str, timeout: int = 10, api_key: str = ""):
        """
        Initialize reporter.
        
        Args:
            api_base_url: Base URL for Social Dashboard API
            timeout: Request timeout in seconds
            api_key: Optional API key for authentication
        """
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self):
        """Initialize HTTP session."""
        headers = {}
        if self.api_key:
            headers['X-API-Key'] = self.api_key
        
        self.session = aiohttp.ClientSession(
            timeout=self.timeout,
            headers=headers
        )
        logger.info("Reporter initialized")
    
    async def shutdown(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def report_status(
        self,
        post_id: str,
        status: PostStatus,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Report status update for a post.
        
        Args:
            post_id: Post ID
            status: New status
            details: Optional additional details
            
        Returns:
            True if report was accepted
        """
        endpoint_map = {
            PostStatus.PROCESSING: "processing",
            PostStatus.POSTING: "posting",
            PostStatus.SUCCESS: "complete",
            PostStatus.FAILED: "failed"
        }
        
        endpoint = endpoint_map.get(status)
        if not endpoint:
            logger.error(f"Unknown status: {status}")
            return False
        
        payload = {
            "status": status.value,
            "timestamp": datetime.now().isoformat(),
            "processor": "ubuntu-brain"
        }
        
        if details:
            payload.update(details)
        
        try:
            async with self.session.post(
                f"{self.api_base_url}/queue/gui/{endpoint}",
                json=payload
            ) as response:
                
                success = response.status == 200
                if success:
                    logger.info(f"Reported {status.value} for post {post_id}")
                else:
                    logger.warning(f"Report failed: {response.status}")
                return success
                
        except Exception as e:
            logger.error(f"Failed to report status: {e}")
            return False
    
    async def report_success(
        self,
        post_id: str,
        email_sent: bool = False,
        post_url: Optional[str] = None
    ) -> bool:
        """
        Report successful post.

        Per GUI-QUEUE-API.md, the payload should be:
        {
            "id": "uuid",
            "platform_post_id": "optional_platform_id"
        }

        Args:
            post_id: Post ID
            email_sent: Whether email was toggled
            post_url: URL of the created post (if available)

        Returns:
            True if report was accepted
        """
        payload = {
            "id": post_id,
            "platform_post_id": post_url  # Optional - URL of created post
        }

        try:
            async with self.session.post(
                f"{self.api_base_url}/queue/gui/complete",
                json=payload
            ) as response:
                success = response.status == 200
                if success:
                    logger.info(f"✓ Reported SUCCESS for post {post_id}")
                else:
                    error_text = await response.text()
                    logger.warning(f"Report success failed: {response.status} - {error_text}")
                return success

        except Exception as e:
            logger.error(f"Failed to report success: {e}")
            return False
    
    async def report_failure(
        self,
        post_id: str,
        error_message: str,
        step: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        retry: bool = True
    ) -> bool:
        """
        Report failed post.

        Per GUI-QUEUE-API.md, the payload should be:
        {
            "id": "uuid",
            "error": "error_message",
            "screenshot": "base64_optional",
            "retry": true
        }

        Args:
            post_id: Post ID
            error_message: Description of what failed
            step: Which step failed (appended to error message)
            screenshot_path: Path to debug screenshot (converted to base64)
            retry: Whether to retry this post

        Returns:
            True if report was accepted
        """
        # Build error message with step if provided
        full_error = error_message
        if step:
            full_error = f"[Step: {step}] {error_message}"

        payload = {
            "id": post_id,
            "error": full_error,
            "retry": retry
        }

        # TODO: Convert screenshot_path to base64 if provided
        if screenshot_path:
            # For now, just note that screenshot is available
            payload["screenshot"] = None  # Convert to base64 in future

        try:
            async with self.session.post(
                f"{self.api_base_url}/queue/gui/failed",
                json=payload
            ) as response:
                success = response.status == 200
                if success:
                    logger.info(f"✗ Reported FAILURE for post {post_id}: {full_error}")
                else:
                    error_text = await response.text()
                    logger.warning(f"Report failure failed: {response.status} - {error_text}")
                return success

        except Exception as e:
            logger.error(f"Failed to report failure: {e}")
            return False
    
    async def report_processing(self, post_id: str) -> bool:
        """Mark post as being processed."""
        return await self.report_status(post_id, PostStatus.PROCESSING)
    
    async def report_posting(self, post_id: str) -> bool:
        """Mark post as in the posting phase."""
        return await self.report_status(post_id, PostStatus.POSTING)
