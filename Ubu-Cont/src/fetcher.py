"""
Fetcher Module - Polls API for pending posts.

This module is responsible for:
1. Polling the Social Dashboard API
2. Retrieving pending posts
3. Parsing post data into workflow-ready format
"""

import asyncio
import aiohttp
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from src.utils.logger import get_logger

logger = get_logger(__name__)


class Platform(Enum):
    """Supported social media platforms."""
    SKOOL = "skool"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    TWITTER = "twitter"  # Future support
    LINKEDIN = "linkedin"  # Future support


@dataclass
class PendingPost:
    """Represents a post to be made."""
    id: str
    platform: Platform
    url: str                          # Platform URL to open
    title: str                        # Post title
    body: str                         # Post body/content
    image_path: Optional[str]         # Path to image on Windows
    image_base64: Optional[str]       # Base64 image data
    send_email: bool                  # Whether to toggle email send
    hashtags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_api_response(cls, data: dict) -> "PendingPost":
        """Create PendingPost from API response."""
        platform_str = data.get("platform", "skool").lower()
        try:
            platform = Platform(platform_str)
        except ValueError:
            logger.warning(f"Unknown platform '{platform_str}', defaulting to skool")
            platform = Platform.SKOOL
        
        return cls(
            id=data.get("id", ""),
            platform=platform,
            url=data.get("url", ""),
            title=data.get("title", ""),
            body=data.get("body", ""),
            image_path=data.get("image_path"),
            image_base64=data.get("image_base64"),
            send_email=data.get("send_email", False),
            hashtags=data.get("hashtags", []),
            metadata=data.get("metadata", {})
        )


class Fetcher:
    """Fetches pending posts from the Social Dashboard API."""
    
    def __init__(self, api_base_url: str, timeout: int = 10, api_key: str = ""):
        """
        Initialize fetcher.
        
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
        logger.info(f"Fetcher initialized with API: {self.api_base_url}")
    
    async def shutdown(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_next_pending_post(self) -> Optional[PendingPost]:
        """
        Fetch the next pending post from the API.
        
        Returns:
            PendingPost if one is available, None otherwise
        """
        try:
            async with self.session.get(
                f"{self.api_base_url}/queue/gui/pending"
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    if data and len(data) > 0:
                        post = PendingPost.from_api_response(data[0])
                        logger.info(f"Found pending post: {post.id} for {post.platform.value}")
                        return post
                    
                elif response.status != 404:
                    logger.warning(f"API returned status {response.status}")
                    
        except aiohttp.ClientError as e:
            logger.error(f"API connection error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error fetching post: {e}")
        
        return None
    
    async def get_all_pending_posts(self) -> List[PendingPost]:
        """
        Fetch all pending posts from the API.
        
        Returns:
            List of PendingPost objects
        """
        try:
            async with self.session.get(
                f"{self.api_base_url}/queue/gui/pending"
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    return [PendingPost.from_api_response(p) for p in data]
                    
        except Exception as e:
            logger.exception(f"Error fetching all posts: {e}")
        
        return []
    
    async def mark_post_in_progress(self, post_id: str) -> bool:
        """
        Mark a post as being processed.
        
        Args:
            post_id: Post ID to mark
            
        Returns:
            True if successful
        """
        try:
            async with self.session.post(
                f"{self.api_base_url}/queue/gui/{post_id}/processing",
                json={"status": "processing"}
            ) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Error marking post in progress: {e}")
            return False
    
    async def check_api_health(self) -> bool:
        """
        Check if API is reachable.
        
        Returns:
            True if API is healthy
        """
        try:
            async with self.session.get(
                f"{self.api_base_url}/health"
            ) as response:
                return response.status == 200
        except:
            return False
