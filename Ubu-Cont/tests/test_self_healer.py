"""
Unit tests for SelfHealer module.

Tests healing API calls (mocked), coordinate validation, and healing history tracking.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
from PIL import Image
from src.subsystems.self_healer import SelfHealer, HealingResult


class TestSelfHealer:
    """Test suite for SelfHealer."""

    @pytest.fixture
    def mock_vnc(self):
        """Create mock VNC capture."""
        vnc = Mock()
        # Create a dummy PIL image
        vnc.capture_frame = Mock(return_value=Image.new('RGB', (1600, 1200), color='white'))
        return vnc

    @pytest.fixture
    def mock_vision(self):
        """Create mock vision controller."""
        vision = Mock()
        # Default: vision finds element at (500, 600)
        vision.find_element = Mock(return_value=(500, 600))
        return vision

    @pytest.fixture
    def temp_screenshot_dir(self, tmp_path):
        """Create temporary screenshot directory."""
        screenshot_dir = tmp_path / "healing_screenshots"
        screenshot_dir.mkdir()
        return str(screenshot_dir)

    @pytest.fixture
    def healer(self, mock_vnc, mock_vision, temp_screenshot_dir):
        """Create SelfHealer instance with mocks."""
        return SelfHealer(
            vnc_capture=mock_vnc,
            vision_controller=mock_vision,
            healing_model="qwen/test-model",
            screenshot_dir=temp_screenshot_dir
        )

    @pytest.mark.asyncio
    async def test_successful_healing(self, healer, mock_vision):
        """Test successful healing operation."""
        result = await healer.heal_coordinates(
            step_name="test_button",
            element_description="Find the test button",
            expected_x_range=(400, 600),
            current_coords=(495, 595)
        )

        assert result.success
        assert result.new_coordinates == (500, 600)
        assert result.delta == (5, 5)
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_healing_with_no_current_coords(self, healer):
        """Test healing when no previous coordinates exist."""
        result = await healer.heal_coordinates(
            step_name="new_button",
            element_description="Find the new button",
            expected_x_range=(400, 600),
            current_coords=None
        )

        assert result.success
        assert result.new_coordinates == (500, 600)
        assert result.delta is None  # No previous coords

    @pytest.mark.asyncio
    async def test_healing_vision_failure(self, healer, mock_vision):
        """Test healing when vision API fails to find element."""
        mock_vision.find_element = Mock(return_value=None)

        result = await healer.heal_coordinates(
            step_name="missing_button",
            element_description="Find the missing button",
            expected_x_range=(400, 600),
            current_coords=(500, 600)
        )

        assert not result.success
        assert result.new_coordinates is None
        assert result.confidence == 0.0
        assert "did not find element" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_healing_screenshot_failure(self, healer, mock_vnc):
        """Test healing when screenshot capture fails."""
        mock_vnc.capture_frame = Mock(return_value=None)

        result = await healer.heal_coordinates(
            step_name="test_button",
            element_description="Find button",
            expected_x_range=(400, 600),
            current_coords=(500, 600)
        )

        assert not result.success
        assert "screenshot" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_coordinate_validation_out_of_x_range(self, healer, mock_vision):
        """Test that coordinates outside expected X range are rejected."""
        # Vision returns coords outside expected range
        mock_vision.find_element = Mock(return_value=(800, 600))

        result = await healer.heal_coordinates(
            step_name="test_button",
            element_description="Find button",
            expected_x_range=(400, 600),  # 800 is outside this range
            current_coords=(500, 600)
        )

        assert not result.success
        assert "validation" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_coordinate_validation_out_of_screen_bounds(self, healer, mock_vision):
        """Test that coordinates outside screen bounds are rejected."""
        # Vision returns coords outside screen (1600x1200)
        mock_vision.find_element = Mock(return_value=(2000, 600))

        result = await healer.heal_coordinates(
            step_name="test_button",
            element_description="Find button",
            expected_x_range=None,
            current_coords=(500, 600)
        )

        assert not result.success
        assert "validation" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_coordinate_validation_large_delta(self, healer, mock_vision):
        """Test that coordinates with large delta are rejected."""
        # Vision returns coords very far from current (>200px)
        mock_vision.find_element = Mock(return_value=(800, 900))

        result = await healer.heal_coordinates(
            step_name="test_button",
            element_description="Find button",
            expected_x_range=None,
            current_coords=(500, 600)  # Delta: 300x, 300y
        )

        assert not result.success
        assert "validation" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_screenshot_saved(self, healer, temp_screenshot_dir):
        """Test that healing screenshot is saved."""
        result = await healer.heal_coordinates(
            step_name="test_button",
            element_description="Find button",
            expected_x_range=(400, 600),
            current_coords=(495, 595)
        )

        # Check screenshot was saved
        screenshot_files = list(Path(temp_screenshot_dir).glob("healing_test_button_*.png"))
        assert len(screenshot_files) == 1
        assert result.screenshot_path is not None

    def test_validate_coordinates_within_bounds(self, healer):
        """Test coordinate validation - valid coordinates."""
        assert healer._validate_coordinates(
            new_coords=(500, 600),
            old_coords=(495, 595),
            expected_x_range=(400, 600)
        )

    def test_validate_coordinates_outside_x_range(self, healer):
        """Test coordinate validation - outside X range."""
        assert not healer._validate_coordinates(
            new_coords=(700, 600),
            old_coords=(500, 600),
            expected_x_range=(400, 600)
        )

    def test_validate_coordinates_outside_screen(self, healer):
        """Test coordinate validation - outside screen bounds."""
        assert not healer._validate_coordinates(
            new_coords=(1700, 600),
            old_coords=None,
            expected_x_range=None
        )

    def test_validate_coordinates_large_delta(self, healer):
        """Test coordinate validation - delta too large."""
        assert not healer._validate_coordinates(
            new_coords=(800, 900),
            old_coords=(500, 600),
            expected_x_range=None
        )

    def test_validate_coordinates_acceptable_delta(self, healer):
        """Test coordinate validation - acceptable delta."""
        assert healer._validate_coordinates(
            new_coords=(550, 650),
            old_coords=(500, 600),
            expected_x_range=None
        )

    @pytest.mark.asyncio
    async def test_healing_exception_handling(self, healer, mock_vision):
        """Test that exceptions during healing are handled gracefully."""
        mock_vision.find_element = Mock(side_effect=Exception("API error"))

        result = await healer.heal_coordinates(
            step_name="test_button",
            element_description="Find button",
            expected_x_range=(400, 600),
            current_coords=(500, 600)
        )

        assert not result.success
        assert "API error" in result.error_message

    @pytest.mark.asyncio
    async def test_healing_result_dataclass(self):
        """Test HealingResult dataclass structure."""
        result = HealingResult(
            success=True,
            new_coordinates=(100, 200),
            confidence=0.95,
            delta=(5, 10),
            error_message=None,
            screenshot_path="/tmp/screenshot.png"
        )

        assert result.success
        assert result.new_coordinates == (100, 200)
        assert result.confidence == 0.95
        assert result.delta == (5, 10)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
