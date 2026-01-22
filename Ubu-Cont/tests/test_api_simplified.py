import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.fetcher import Fetcher, PendingPost, Platform
from src.reporter import Reporter, PostStatus

@pytest.mark.asyncio
async def test_pending_post_parsing():
    api_data = {
        "id": "test-uuid",
        "platform": "instagram_ultra",
        "platform_url": "https://instagram.com/test",
        "caption": "Test caption",
        "media": [
            {"id": "media-1", "type": "image"}
        ],
        "email_members": True
    }
    
    post = PendingPost.from_api_response(api_data)
    
    assert post.id == "test-uuid"
    assert post.platform == Platform.INSTAGRAM
    assert post.url == "https://instagram.com/test"
    assert post.body == "Test caption"
    assert post.send_email is True
    # We still parse media for awareness, just don't download it
    assert len(post.media) == 1

@pytest.mark.asyncio
async def test_reporter_failure_no_retry():
    # Verify that fail reports don't include retry field (spec v2.0)
    reporter = Reporter("https://test.api", api_key="test-key")
    reporter.session = MagicMock()
    
    mock_response = AsyncMock()
    mock_response.status = 200
    reporter.session.post.return_value.__aenter__.return_value = mock_response
    
    await reporter.report_failure("test-id", "Error message", step="test-step")
    
    args, kwargs = reporter.session.post.call_args
    assert "retry" not in kwargs["json"]
    assert kwargs["json"]["id"] == "test-id"
    assert "[Step: test-step]" in kwargs["json"]["error"]

@pytest.mark.asyncio
async def test_fetcher_polling():
    fetcher = Fetcher("https://test.api", api_key="test-key")
    fetcher.session = MagicMock()
    
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text.return_value = json.dumps([{"id": "test-1", "platform": "skool"}])
    fetcher.session.get.return_value.__aenter__.return_value = mock_response
    
    post = await fetcher.get_next_pending_post()
    assert post.id == "test-1"
    assert post.platform == Platform.SKOOL

if __name__ == "__main__":
    import sys
    import pytest
    pytest.main([__file__])
