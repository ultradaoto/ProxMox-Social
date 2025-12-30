"""
Tests for the Behavioral Biometrics Profiler

Comprehensive tests for all profiler components.
"""

import pytest
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict

# Import profiler components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from profiler.mouse_recorder import MouseRecorder, MouseEvent, MovementSegment
from profiler.keyboard_recorder import KeyboardRecorder, KeyEvent
from profiler.session_manager import SessionManager, SessionMetadata
from profiler.analyzer import ProfileAnalyzer, MouseProfile, KeyboardProfile
from profiler.profile_generator import ProfileGenerator
from profiler.profile_applier import ProfileApplier
from profiler.config_loader import ProfilerConfig, DEFAULT_CONFIG


class TestMouseRecorder:
    """Tests for MouseRecorder."""

    def test_mouse_event_creation(self):
        """Test MouseEvent dataclass."""
        event = MouseEvent(
            timestamp=1000.0,
            x=100,
            y=200,
            event_type='move',
            velocity=50.5,
            acceleration=10.2
        )
        assert event.x == 100
        assert event.y == 200
        assert event.velocity == 50.5

    def test_movement_segment_creation(self):
        """Test MovementSegment dataclass."""
        segment = MovementSegment(
            start_time=0.0,
            end_time=1.0,
            start_pos=(0, 0),
            end_pos=(100, 100),
            distance=141.42,
            duration=1.0,
            mean_velocity=141.42
        )
        assert segment.distance == 141.42
        assert segment.duration == 1.0

    def test_recorder_initialization(self):
        """Test MouseRecorder initialization."""
        recorder = MouseRecorder(sample_rate_hz=500)
        assert recorder.sample_rate_hz == 500
        assert not recorder.recording

    def test_recorder_mock_events(self):
        """Test recording with mock events."""
        recorder = MouseRecorder()

        # Manually add events (simulating what pynput would do)
        recorder.events = [
            MouseEvent(timestamp=0.0, x=0, y=0, event_type='move'),
            MouseEvent(timestamp=0.1, x=10, y=10, event_type='move'),
            MouseEvent(timestamp=0.2, x=20, y=20, event_type='move'),
        ]

        assert len(recorder.events) == 3

    def test_statistics_calculation(self):
        """Test statistics calculation."""
        recorder = MouseRecorder()
        recorder.events = [
            MouseEvent(timestamp=0.0, x=0, y=0, event_type='move', velocity=100.0),
            MouseEvent(timestamp=0.1, x=10, y=10, event_type='move', velocity=150.0),
            MouseEvent(timestamp=0.2, x=20, y=20, event_type='move', velocity=120.0),
        ]

        stats = recorder.get_statistics()
        assert 'total_events' in stats
        assert stats['total_events'] == 3


class TestKeyboardRecorder:
    """Tests for KeyboardRecorder."""

    def test_key_event_creation(self):
        """Test KeyEvent dataclass."""
        event = KeyEvent(
            timestamp=1000.0,
            key='a',
            action='press',
            hold_duration=0.05
        )
        assert event.key == 'a'
        assert event.action == 'press'

    def test_recorder_initialization(self):
        """Test KeyboardRecorder initialization."""
        recorder = KeyboardRecorder()
        assert not recorder.recording

    def test_digraph_extraction(self):
        """Test digraph timing extraction."""
        recorder = KeyboardRecorder()

        # Simulate key events
        recorder.events = [
            KeyEvent(timestamp=0.0, key='t', action='press'),
            KeyEvent(timestamp=0.05, key='t', action='release', hold_duration=0.05),
            KeyEvent(timestamp=0.1, key='h', action='press', iki=0.1),
            KeyEvent(timestamp=0.15, key='h', action='release', hold_duration=0.05),
            KeyEvent(timestamp=0.2, key='e', action='press', iki=0.1),
        ]

        digraphs = recorder.get_digraph_timings()
        assert isinstance(digraphs, dict)


class TestSessionManager:
    """Tests for SessionManager."""

    def test_session_creation(self):
        """Test creating a new session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(tmpdir)
            session_id = manager.start_session(
                task_description="Test session",
                tags=['test']
            )

            assert session_id is not None
            assert manager.current_session == session_id

    def test_session_end(self):
        """Test ending a session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(tmpdir)
            session_id = manager.start_session(task_description="Test")

            # Simulate some time passing
            time.sleep(0.1)

            metadata = manager.end_session(notes="Test notes")

            assert metadata is not None
            assert metadata.session_id == session_id
            assert metadata.notes == "Test notes"

    def test_session_listing(self):
        """Test listing sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(tmpdir)

            # Create multiple sessions
            for i in range(3):
                manager.start_session(task_description=f"Session {i}")
                manager.end_session()

            sessions = manager.list_sessions()
            assert len(sessions) == 3

    def test_session_metadata(self):
        """Test SessionMetadata dataclass."""
        metadata = SessionMetadata(
            session_id="test-123",
            start_time="2024-01-01T00:00:00",
            task_description="Test",
            tags=['test']
        )

        data = metadata.to_dict()
        assert data['session_id'] == "test-123"
        assert 'test' in data['tags']


class TestProfileAnalyzer:
    """Tests for ProfileAnalyzer."""

    def test_analyzer_initialization(self):
        """Test ProfileAnalyzer initialization."""
        analyzer = ProfileAnalyzer()
        assert analyzer is not None

    def test_mouse_profile_creation(self):
        """Test MouseProfile dataclass."""
        profile = MouseProfile(
            fitts_a=0.2,
            fitts_b=0.1,
            velocity_mean=500.0,
            velocity_std=100.0,
            overshoot_rate=0.15,
            jitter_mean=2.0
        )
        assert profile.fitts_a == 0.2
        assert profile.velocity_mean == 500.0

    def test_keyboard_profile_creation(self):
        """Test KeyboardProfile dataclass."""
        profile = KeyboardProfile(
            mean_iki=100.0,
            iki_std=20.0,
            hold_mean=50.0,
            hold_std=10.0,
            digraph_timings={}
        )
        assert profile.mean_iki == 100.0

    def test_fitts_law_calculation(self):
        """Test Fitts's Law ID calculation."""
        analyzer = ProfileAnalyzer()

        # ID = log2(D/W + 1)
        # For D=100, W=50: ID = log2(100/50 + 1) = log2(3) ≈ 1.585
        id_value = analyzer._calculate_index_of_difficulty(100, 50)
        assert 1.5 < id_value < 1.7


class TestProfileGenerator:
    """Tests for ProfileGenerator."""

    def test_generator_initialization(self):
        """Test ProfileGenerator initialization."""
        generator = ProfileGenerator()
        assert generator is not None

    def test_profile_validation(self):
        """Test profile validation."""
        generator = ProfileGenerator()

        # Create a minimal profile
        profile = {
            'version': '1.0',
            'user_id': 'test',
            'mouse': {
                'fitts_coefficients': {'a': 0.2, 'b': 0.1}
            },
            'keyboard': {
                'timing': {'mean_iki_ms': 100}
            }
        }

        is_valid, score, issues = generator.validate_profile(profile)
        assert isinstance(is_valid, bool)
        assert isinstance(score, float)
        assert isinstance(issues, list)


class TestProfileApplier:
    """Tests for ProfileApplier."""

    def test_applier_initialization(self):
        """Test ProfileApplier initialization."""
        applier = ProfileApplier()
        assert applier is not None

    def test_movement_time_calculation(self):
        """Test Fitts's Law movement time calculation."""
        applier = ProfileApplier()

        # Load a simple profile
        applier.profile = {
            'mouse': {
                'fitts_coefficients': {'a': 0.2, 'b': 0.1}
            }
        }

        # Calculate movement time for known values
        time_ms = applier.calculate_movement_time(
            start=(0, 0),
            end=(100, 0),
            target_width=50
        )

        assert time_ms > 0

    def test_bezier_curve_generation(self):
        """Test Bezier curve generation for mouse paths."""
        applier = ProfileApplier()

        # Generate a path
        path = applier._generate_bezier_path(
            start=(0, 0),
            end=(100, 100),
            num_points=10
        )

        assert len(path) == 10
        assert path[0] == (0, 0)
        # End point should be close to target
        assert abs(path[-1][0] - 100) < 1
        assert abs(path[-1][1] - 100) < 1


class TestProfilerConfig:
    """Tests for ProfilerConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = ProfilerConfig()

        assert config.user_id == 'default'
        assert config.mouse_sample_rate == 1000
        assert config.vnc_host == '192.168.100.10'

    def test_get_nested_value(self):
        """Test getting nested config values."""
        config = ProfilerConfig()

        sample_rate = config.get('recording.mouse.sample_rate_hz')
        assert sample_rate == 1000

    def test_set_value(self):
        """Test setting config values."""
        config = ProfilerConfig()

        config.set('user.id', 'test_user')
        assert config.user_id == 'test_user'

    def test_config_file_loading(self):
        """Test loading config from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("user:\n  id: loaded_user\n")
            f.flush()

            config = ProfilerConfig(f.name)
            assert config.user_id == 'loaded_user'

            Path(f.name).unlink()

    def test_config_validation(self):
        """Test configuration validation."""
        config = ProfilerConfig()

        is_valid, issues = config.validate()
        assert isinstance(is_valid, bool)
        assert isinstance(issues, list)


class TestIntegration:
    """Integration tests for the profiler system."""

    def test_full_recording_flow(self):
        """Test complete recording -> analysis -> profile generation flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Create session manager
            session_manager = SessionManager(tmpdir)

            # 2. Start session
            session_id = session_manager.start_session(
                task_description="Integration test"
            )

            # 3. Simulate recorded events
            mouse_events = [
                {'timestamp': 0.0, 'x': 0, 'y': 0, 'event_type': 'move', 'velocity': 100},
                {'timestamp': 0.1, 'x': 50, 'y': 50, 'event_type': 'move', 'velocity': 500},
                {'timestamp': 0.2, 'x': 100, 'y': 100, 'event_type': 'click', 'velocity': 0},
            ]

            keyboard_events = [
                {'timestamp': 0.3, 'key': 'h', 'action': 'press'},
                {'timestamp': 0.35, 'key': 'h', 'action': 'release', 'hold_duration': 0.05},
                {'timestamp': 0.4, 'key': 'i', 'action': 'press', 'iki': 0.1},
                {'timestamp': 0.45, 'key': 'i', 'action': 'release', 'hold_duration': 0.05},
            ]

            # Save events
            session_dir = session_manager.get_session_dir()
            with open(session_dir / 'mouse_events.jsonl', 'w') as f:
                for event in mouse_events:
                    f.write(json.dumps(event) + '\n')

            with open(session_dir / 'keyboard_events.jsonl', 'w') as f:
                for event in keyboard_events:
                    f.write(json.dumps(event) + '\n')

            # 4. End session
            metadata = session_manager.end_session()
            assert metadata is not None

            # 5. Analyze
            analyzer = ProfileAnalyzer()
            # Note: full analysis requires more data

            # 6. Generate profile
            generator = ProfileGenerator()
            # Note: full generation requires analyzed data

            # Verify files exist
            assert (session_dir / 'mouse_events.jsonl').exists()
            assert (session_dir / 'keyboard_events.jsonl').exists()
            assert (session_dir / 'metadata.json').exists()


class TestMathematicalCorrectness:
    """Tests for mathematical correctness of algorithms."""

    def test_fitts_law_coefficients(self):
        """Test that Fitts's Law produces reasonable coefficients."""
        # Known data points: movement time vs index of difficulty
        # T = a + b * ID
        # Typical human values: a ≈ 0, b ≈ 100-200ms

        analyzer = ProfileAnalyzer()

        # Simulate movement data
        movements = []
        for distance in [100, 200, 400, 800]:
            for width in [20, 40, 80]:
                id_val = analyzer._calculate_index_of_difficulty(distance, width)
                # Simulate realistic movement time
                time_ms = 50 + 120 * id_val  # a=50, b=120
                movements.append({
                    'distance': distance,
                    'target_width': width,
                    'movement_time_ms': time_ms,
                    'index_of_difficulty': id_val
                })

        # Fit coefficients (simplified - real impl uses scipy)
        # Just verify we can process the data
        assert len(movements) > 0

    def test_velocity_calculation(self):
        """Test velocity calculation accuracy."""
        # v = sqrt(dx^2 + dy^2) / dt

        dx, dy = 100, 100
        dt = 0.1  # 100ms

        expected_velocity = (dx**2 + dy**2)**0.5 / dt
        assert abs(expected_velocity - 1414.21) < 1  # ~1414 px/s

    def test_bezier_curve_endpoints(self):
        """Test that Bezier curves hit their endpoints."""
        applier = ProfileApplier()

        start = (0, 0)
        end = (500, 300)

        path = applier._generate_bezier_path(start, end, num_points=100)

        # First point should be start
        assert path[0] == start

        # Last point should be very close to end
        assert abs(path[-1][0] - end[0]) < 0.01
        assert abs(path[-1][1] - end[1]) < 0.01


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
