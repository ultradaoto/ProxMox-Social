"""
Profile Generator

Generates personal profile YAML from analyzed recordings.
Combines multiple sessions for robust profile generation.
"""

from dataclasses import asdict
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime
import json
import logging

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .analyzer import ProfileAnalyzer, MouseProfile, KeyboardProfile
from .mouse_recorder import MouseRecorder
from .keyboard_recorder import KeyboardRecorder

logger = logging.getLogger(__name__)


class ProfileGenerator:
    """
    Generates personal profile YAML from analysis.

    Features:
        - Combines multiple recording sessions
        - Weights by session quality
        - Validates profile completeness
        - Exports to YAML or JSON
    """

    def __init__(self, analyzer: Optional[ProfileAnalyzer] = None):
        """
        Initialize profile generator.

        Args:
            analyzer: ProfileAnalyzer instance, or creates new one
        """
        self.analyzer = analyzer or ProfileAnalyzer()

    def generate_profile(
        self,
        mouse_sessions: List[str],
        keyboard_sessions: List[str],
        output_path: str,
        user_name: str = "default",
        weights: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Generate complete personal profile.

        Args:
            mouse_sessions: List of paths to mouse recording JSONL files
            keyboard_sessions: List of paths to keyboard recording JSONL files
            output_path: Where to save the profile YAML
            user_name: Name identifier for the profile
            weights: Optional session weights (path -> weight)

        Returns:
            Path to generated profile
        """
        logger.info(f"Generating profile from {len(mouse_sessions)} mouse sessions, "
                   f"{len(keyboard_sessions)} keyboard sessions")

        # Load all events
        all_mouse_events = []
        all_keyboard_events = []

        for path in mouse_sessions:
            try:
                events = self._load_jsonl(path)
                weight = weights.get(path, 1.0) if weights else 1.0
                # Apply weight by repeating events (simple weighting)
                for _ in range(int(weight)):
                    all_mouse_events.extend(events)
                logger.debug(f"Loaded {len(events)} mouse events from {path}")
            except Exception as e:
                logger.warning(f"Could not load {path}: {e}")

        for path in keyboard_sessions:
            try:
                events = self._load_jsonl(path)
                weight = weights.get(path, 1.0) if weights else 1.0
                for _ in range(int(weight)):
                    all_keyboard_events.extend(events)
                logger.debug(f"Loaded {len(events)} keyboard events from {path}")
            except Exception as e:
                logger.warning(f"Could not load {path}: {e}")

        # Analyze
        mouse_profile = self.analyzer.analyze_mouse_session(all_mouse_events)
        keyboard_profile = self.analyzer.analyze_keyboard_session(all_keyboard_events)

        # Build profile dict
        profile = self._build_profile_dict(
            mouse_profile,
            keyboard_profile,
            user_name,
            len(all_mouse_events),
            len(all_keyboard_events)
        )

        # Validate
        validation = self._validate_profile(profile)
        profile['metadata']['validation'] = validation

        # Save
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if HAS_YAML and output_path.suffix in ['.yaml', '.yml']:
            with open(output_path, 'w') as f:
                yaml.dump(profile, f, default_flow_style=False, sort_keys=False)
        else:
            # Fall back to JSON
            if output_path.suffix not in ['.json']:
                output_path = output_path.with_suffix('.json')
            with open(output_path, 'w') as f:
                json.dump(profile, f, indent=2)

        logger.info(f"Profile saved to {output_path}")
        logger.info(f"Validation: {validation['completeness']:.0%} complete, "
                   f"{validation['warnings']} warnings")

        return str(output_path)

    def generate_from_session_dir(
        self,
        session_dir: str,
        output_path: str,
        user_name: str = "default"
    ) -> str:
        """
        Generate profile from a session directory.

        Args:
            session_dir: Path to session directory
            output_path: Where to save the profile
            user_name: Profile name

        Returns:
            Path to generated profile
        """
        session_dir = Path(session_dir)

        mouse_file = session_dir / "mouse_events.jsonl"
        keyboard_file = session_dir / "keyboard_events.jsonl"

        mouse_sessions = [str(mouse_file)] if mouse_file.exists() else []
        keyboard_sessions = [str(keyboard_file)] if keyboard_file.exists() else []

        return self.generate_profile(
            mouse_sessions,
            keyboard_sessions,
            output_path,
            user_name
        )

    def generate_from_multiple_sessions(
        self,
        session_dirs: List[str],
        output_path: str,
        user_name: str = "default"
    ) -> str:
        """
        Generate profile from multiple session directories.

        Args:
            session_dirs: List of session directory paths
            output_path: Where to save the profile
            user_name: Profile name

        Returns:
            Path to generated profile
        """
        mouse_sessions = []
        keyboard_sessions = []

        for session_dir in session_dirs:
            session_dir = Path(session_dir)
            mouse_file = session_dir / "mouse_events.jsonl"
            keyboard_file = session_dir / "keyboard_events.jsonl"

            if mouse_file.exists():
                mouse_sessions.append(str(mouse_file))
            if keyboard_file.exists():
                keyboard_sessions.append(str(keyboard_file))

        return self.generate_profile(
            mouse_sessions,
            keyboard_sessions,
            output_path,
            user_name
        )

    def _build_profile_dict(
        self,
        mouse_profile: MouseProfile,
        keyboard_profile: KeyboardProfile,
        user_name: str,
        mouse_samples: int,
        keyboard_samples: int
    ) -> Dict[str, Any]:
        """Build the complete profile dictionary."""
        return {
            'metadata': {
                'profile_name': user_name,
                'generated_at': datetime.now().isoformat(),
                'version': '1.0',
                'mouse_samples': mouse_samples,
                'keyboard_samples': keyboard_samples
            },

            'mouse': {
                'fitts_law': {
                    'a': round(mouse_profile.fitts_a, 2),
                    'b': round(mouse_profile.fitts_b, 2),
                    'r_squared': round(mouse_profile.fitts_r2, 3),
                    'description': 'T = a + b * log2(D/W + 1), T in ms'
                },
                'velocity': {
                    'mean_pixels_per_sec': round(mouse_profile.avg_velocity, 1),
                    'std': round(mouse_profile.velocity_std, 1)
                },
                'trajectory': {
                    'curvature_mean': round(mouse_profile.curvature_mean, 3),
                    'curvature_std': round(mouse_profile.curvature_std, 3),
                    'overshoot_rate': round(mouse_profile.overshoot_rate, 3),
                    'overshoot_distance_mean': round(mouse_profile.overshoot_distance_mean, 1)
                },
                'jitter': {
                    'amplitude_pixels': round(mouse_profile.jitter_amplitude, 2),
                    'frequency_hz': round(mouse_profile.jitter_frequency, 1)
                },
                'clicks': {
                    'duration_mean_ms': round(mouse_profile.click_duration_mean, 1),
                    'duration_std_ms': round(mouse_profile.click_duration_std, 1),
                    'double_click_interval_mean_ms': round(mouse_profile.double_click_interval_mean, 1),
                    'double_click_interval_std_ms': round(mouse_profile.double_click_interval_std, 1)
                },
                'acceleration_profile': [round(v, 3) for v in mouse_profile.acceleration_profile]
            },

            'keyboard': {
                'speed': {
                    'wpm_mean': round(keyboard_profile.wpm_mean, 1),
                    'wpm_std': round(keyboard_profile.wpm_std, 1)
                },
                'timing': {
                    'inter_key_interval_mean_ms': round(keyboard_profile.iki_mean, 1),
                    'inter_key_interval_std_ms': round(keyboard_profile.iki_std, 1),
                    'hold_duration_mean_ms': round(keyboard_profile.hold_duration_mean, 1),
                    'hold_duration_std_ms': round(keyboard_profile.hold_duration_std, 1),
                    'distribution': keyboard_profile.iki_distribution
                },
                'errors': {
                    'rate_per_100_keys': round(keyboard_profile.error_rate, 2),
                    'correction_delay_ms': round(keyboard_profile.correction_delay_mean, 1),
                    'error_types': keyboard_profile.common_errors
                },
                'pauses': {
                    'word_pause_mean_ms': round(keyboard_profile.word_pause_mean, 1),
                    'sentence_pause_mean_ms': round(keyboard_profile.sentence_pause_mean, 1),
                    'think_pause_threshold_ms': round(keyboard_profile.think_pause_threshold, 1)
                },
                'digraph_timing': {
                    k: {'mean_ms': round(v[0], 1), 'std_ms': round(v[1], 1)}
                    for k, v in list(keyboard_profile.digraph_timing.items())[:50]
                }
            },

            'interaction': {
                'think_time': {
                    'min_ms': 200,
                    'max_ms': 3000,
                    'mean_ms': 800,
                    'distribution': 'lognormal'
                },
                'read_time': {
                    'chars_per_second': 25,
                    'min_pause_ms': 500
                },
                'action_cooldown': {
                    'click_to_move_ms': 100,
                    'type_to_click_ms': 200,
                    'scroll_to_click_ms': 150
                }
            },

            'advanced': {
                'fatigue_simulation': {
                    'enabled': True,
                    'degradation_rate': 0.02,  # 2% per hour
                    'affects': ['velocity', 'accuracy', 'iki']
                },
                'circadian_variation': {
                    'enabled': False,
                    'peak_hours': [10, 11, 14, 15, 16],
                    'variation_percent': 10
                }
            }
        }

    def _validate_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate profile completeness and reasonableness.

        Returns validation results.
        """
        warnings = []
        completeness = 1.0

        # Check mouse profile
        mouse = profile.get('mouse', {})
        if not mouse:
            warnings.append("No mouse profile data")
            completeness -= 0.3
        else:
            fitts = mouse.get('fitts_law', {})
            if fitts.get('r_squared', 0) < 0.5:
                warnings.append(f"Low Fitts's Law fit: R²={fitts.get('r_squared')}")

            velocity = mouse.get('velocity', {})
            if velocity.get('mean_pixels_per_sec', 0) < 100:
                warnings.append("Very low average velocity")
            if velocity.get('mean_pixels_per_sec', 0) > 5000:
                warnings.append("Very high average velocity - may be noisy data")

        # Check keyboard profile
        keyboard = profile.get('keyboard', {})
        if not keyboard:
            warnings.append("No keyboard profile data")
            completeness -= 0.3
        else:
            speed = keyboard.get('speed', {})
            if speed.get('wpm_mean', 0) < 10:
                warnings.append("Very low WPM - limited typing data")
            if speed.get('wpm_mean', 0) > 150:
                warnings.append("Very high WPM - may be unrealistic")

            digraphs = keyboard.get('digraph_timing', {})
            if len(digraphs) < 10:
                warnings.append(f"Only {len(digraphs)} digraphs captured - more data recommended")
                completeness -= 0.1

        # Check sample counts
        metadata = profile.get('metadata', {})
        if metadata.get('mouse_samples', 0) < 1000:
            warnings.append("Low mouse sample count - more recording recommended")
            completeness -= 0.1
        if metadata.get('keyboard_samples', 0) < 500:
            warnings.append("Low keyboard sample count - more recording recommended")
            completeness -= 0.1

        return {
            'completeness': max(0, completeness),
            'warnings': len(warnings),
            'warning_messages': warnings,
            'validated_at': datetime.now().isoformat()
        }

    def _load_jsonl(self, path: str) -> List[Dict[str, Any]]:
        """Load events from JSONL file."""
        events = []
        with open(path) as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events

    def merge_profiles(
        self,
        profile_paths: List[str],
        output_path: str,
        weights: Optional[List[float]] = None
    ) -> str:
        """
        Merge multiple profiles into one.

        Args:
            profile_paths: Paths to profile files
            output_path: Where to save merged profile
            weights: Weights for each profile (default: equal)

        Returns:
            Path to merged profile
        """
        if weights is None:
            weights = [1.0] * len(profile_paths)

        profiles = []
        for path in profile_paths:
            with open(path) as f:
                if path.endswith('.yaml') or path.endswith('.yml'):
                    if HAS_YAML:
                        profiles.append(yaml.safe_load(f))
                    else:
                        raise ImportError("PyYAML required for YAML files")
                else:
                    profiles.append(json.load(f))

        # Weighted merge of numeric values
        merged = self._weighted_merge(profiles, weights)

        # Save
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if HAS_YAML and output_path.suffix in ['.yaml', '.yml']:
            with open(output_path, 'w') as f:
                yaml.dump(merged, f, default_flow_style=False, sort_keys=False)
        else:
            with open(output_path, 'w') as f:
                json.dump(merged, f, indent=2)

        return str(output_path)

    def _weighted_merge(
        self,
        profiles: List[Dict],
        weights: List[float]
    ) -> Dict[str, Any]:
        """Merge profiles with weighted averaging."""
        if not profiles:
            return {}

        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]

        # Start with first profile structure
        merged = json.loads(json.dumps(profiles[0]))  # Deep copy

        # Merge numeric values
        self._merge_dict(merged, profiles, normalized_weights)

        # Update metadata
        merged['metadata']['generated_at'] = datetime.now().isoformat()
        merged['metadata']['merged_from'] = len(profiles)
        merged['metadata']['mouse_samples'] = sum(
            p.get('metadata', {}).get('mouse_samples', 0) for p in profiles
        )
        merged['metadata']['keyboard_samples'] = sum(
            p.get('metadata', {}).get('keyboard_samples', 0) for p in profiles
        )

        return merged

    def _merge_dict(
        self,
        target: Dict,
        sources: List[Dict],
        weights: List[float]
    ) -> None:
        """Recursively merge dictionaries with weighted averaging."""
        for key, value in target.items():
            if isinstance(value, dict):
                source_dicts = [s.get(key, {}) for s in sources]
                self._merge_dict(value, source_dicts, weights)
            elif isinstance(value, (int, float)):
                values = [s.get(key, value) for s in sources]
                target[key] = sum(v * w for v, w in zip(values, weights))
            elif isinstance(value, list) and all(isinstance(x, (int, float)) for x in value):
                # Merge numeric lists (like acceleration_profile)
                merged_list = []
                for i in range(len(value)):
                    vals = [s.get(key, value)[i] if i < len(s.get(key, value)) else value[i]
                           for s in sources]
                    merged_list.append(sum(v * w for v, w in zip(vals, weights)))
                target[key] = merged_list
