"""
Unit tests for CoordinateStore module.

Tests coordinate storage, success/failure tracking, and healing trigger logic.
"""

import pytest
import json
import tempfile
from pathlib import Path
from src.subsystems.coordinate_store import CoordinateStore, CoordinateEntry


class TestCoordinateStore:
    """Test suite for CoordinateStore."""

    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary file path for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        # Delete the temp file so we test with non-existent path
        Path(temp_path).unlink(missing_ok=True)
        yield temp_path
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
        Path(temp_path + '.bak').unlink(missing_ok=True)

    @pytest.fixture
    def coord_store(self, temp_store_path):
        """Create a fresh CoordinateStore for each test."""
        return CoordinateStore(storage_path=temp_store_path, platform="test")

    def test_initialization_creates_empty_store(self, coord_store):
        """Test that a new store starts empty."""
        assert not coord_store.exists()
        assert len(coord_store.get_all_steps()) == 0
        stats = coord_store.get_stats()
        assert stats['total_clicks'] == 0

    def test_add_coordinate(self, coord_store):
        """Test adding a new coordinate."""
        coord_store.add_coordinate(
            step_name="test_button",
            coords=(100, 200),
            coord_type="static",
            description="Test button",
            expected_x_range=(50, 150)
        )

        coords = coord_store.get_coordinates("test_button")
        assert coords == (100, 200)
        assert coord_store.exists()  # File should be created

    def test_record_success(self, coord_store):
        """Test recording successful click."""
        # Add initial coordinate
        coord_store.add_coordinate("test_step", (100, 200), "dynamic", "Test")

        # Record success
        coord_store.record_success("test_step", (100, 200))

        stats = coord_store.get_stats()
        assert stats['total_clicks'] == 1
        assert stats['successful_clicks'] == 1
        assert stats['failed_clicks'] == 0

        # Consecutive failures should be reset
        assert coord_store.get_failure_count("test_step") == 0

    def test_record_failure(self, coord_store):
        """Test recording failed click."""
        coord_store.add_coordinate("test_step", (100, 200), "dynamic", "Test")

        # Record failure
        should_heal = coord_store.record_failure("test_step")

        assert not should_heal  # First failure shouldn't trigger healing
        assert coord_store.get_failure_count("test_step") == 1

        stats = coord_store.get_stats()
        assert stats['total_clicks'] == 1
        assert stats['failed_clicks'] == 1

    def test_healing_trigger_after_three_failures(self, coord_store):
        """Test that healing triggers after 3 consecutive failures."""
        coord_store.add_coordinate("test_step", (100, 200), "dynamic", "Test")

        # First failure - no healing
        assert not coord_store.record_failure("test_step")
        assert not coord_store.should_heal("test_step")

        # Second failure - no healing
        assert not coord_store.record_failure("test_step")
        assert not coord_store.should_heal("test_step")

        # Third failure - trigger healing
        assert coord_store.record_failure("test_step")
        assert coord_store.should_heal("test_step")

    def test_success_resets_consecutive_failures(self, coord_store):
        """Test that success resets consecutive failure counter."""
        coord_store.add_coordinate("test_step", (100, 200), "dynamic", "Test")

        # Two failures
        coord_store.record_failure("test_step")
        coord_store.record_failure("test_step")
        assert coord_store.get_failure_count("test_step") == 2

        # Success resets
        coord_store.record_success("test_step", (100, 200))
        assert coord_store.get_failure_count("test_step") == 0

        # New failure starts from 1 again
        coord_store.record_failure("test_step")
        assert coord_store.get_failure_count("test_step") == 1

    def test_update_coordinates(self, coord_store):
        """Test updating coordinates after healing."""
        coord_store.add_coordinate("test_step", (100, 200), "dynamic", "Test")

        # Update coordinates
        coord_store.update_coordinates(
            step_name="test_step",
            new_coords=(105, 205),
            healing_context={
                "trigger": "3_consecutive_failures",
                "confidence": 0.95
            }
        )

        # Check new coordinates
        coords = coord_store.get_coordinates("test_step")
        assert coords == (105, 205)

        # Check stats
        stats = coord_store.get_stats()
        assert stats['healing_events'] == 1

    def test_coordinate_persistence(self, temp_store_path):
        """Test that coordinates persist across store instances."""
        # Create store and add coordinate
        store1 = CoordinateStore(storage_path=temp_store_path, platform="test")
        store1.add_coordinate("test_step", (100, 200), "static", "Test")

        # Create new store instance with same path
        store2 = CoordinateStore(storage_path=temp_store_path, platform="test")

        # Should load existing coordinates
        coords = store2.get_coordinates("test_step")
        assert coords == (100, 200)

    def test_backup_created_on_save(self, temp_store_path):
        """Test that backup file is created when saving."""
        store = CoordinateStore(storage_path=temp_store_path, platform="test")
        store.add_coordinate("test_step", (100, 200), "static", "Test")

        # Modify and save again
        store.record_success("test_step", (100, 200))

        # Backup should exist
        backup_path = Path(temp_store_path + '.bak')
        assert backup_path.exists()

    def test_healing_history_tracking(self, coord_store):
        """Test that healing history is tracked."""
        coord_store.add_coordinate("test_step", (100, 200), "dynamic", "Test")

        # Perform healing update
        coord_store.update_coordinates(
            step_name="test_step",
            new_coords=(105, 205),
            healing_context={
                "trigger": "3_consecutive_failures",
                "confidence": 0.95,
                "vision_model": "qwen-3"
            }
        )

        # Load JSON and check healing history
        with open(coord_store.storage_path, 'r') as f:
            data = json.load(f)

        healing_history = data['coordinates']['test_step']['healing_history']
        assert len(healing_history) == 1
        assert healing_history[0]['trigger'] == "3_consecutive_failures"
        assert healing_history[0]['delta'] == [5, 5]

    def test_get_coordinates_nonexistent_step(self, coord_store):
        """Test getting coordinates for non-existent step."""
        coords = coord_store.get_coordinates("nonexistent")
        assert coords is None

    def test_thread_safety(self, coord_store):
        """Test that store operations are thread-safe (basic test)."""
        import threading

        coord_store.add_coordinate("test_step", (100, 200), "dynamic", "Test")

        def record_success():
            for _ in range(10):
                coord_store.record_success("test_step", (100, 200))

        def record_failure():
            for _ in range(10):
                coord_store.record_failure("test_step")

        # Run concurrent operations
        threads = [
            threading.Thread(target=record_success),
            threading.Thread(target=record_failure)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have processed all clicks
        stats = coord_store.get_stats()
        assert stats['total_clicks'] == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
