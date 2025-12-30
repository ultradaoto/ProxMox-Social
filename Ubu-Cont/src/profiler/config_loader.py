"""
Configuration Loader

Loads and validates profiler configuration from YAML files.
"""

from typing import Optional, Dict, Any
from pathlib import Path
import os
import logging

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    'user': {
        'id': 'default',
        'display_name': 'Default User',
        'profile_path': 'profiles/default.yaml'
    },
    'recording': {
        'session_dir': 'recordings/sessions',
        'calibration_dir': 'recordings/calibrations',
        'profile_dir': 'profiles',
        'mouse': {
            'sample_rate_hz': 1000,
            'min_velocity_threshold': 0.1,
            'segment_gap_threshold': 0.1,
            'overshoot_threshold': 5,
            'jitter_window_ms': 50
        },
        'keyboard': {
            'record_key_content': True,
            'anonymize_passwords': True,
            'digraph_max_gap_ms': 2000,
            'session_idle_timeout': 5.0
        },
        'auto_save': {
            'enabled': True,
            'interval_seconds': 30,
            'backup_on_crash': True
        }
    },
    'vnc': {
        'host': '192.168.100.10',
        'port': 5900,
        'password': None,
        'display': {
            'window_title': 'VNC Passthrough - Recording',
            'default_size': [1920, 1080],
            'target_fps': 60,
            'show_recording_indicator': True
        }
    },
    'hid': {
        'host': '192.168.100.1',
        'mouse_port': 8888,
        'keyboard_port': 8889,
        'connection_timeout': 5.0,
        'retry_attempts': 3
    },
    'analysis': {
        'fitts_law': {
            'min_distance': 10,
            'max_distance': 2000,
            'min_target_width': 5,
            'default_target_width': 50
        },
        'velocity': {
            'smoothing_window': 5,
            'acceleration_threshold': 100
        },
        'keyboard': {
            'min_iki_ms': 10,
            'max_iki_ms': 5000,
            'wpm_calculation_window': 60
        },
        'quality': {
            'min_duration_seconds': 60,
            'min_mouse_events': 100,
            'min_keyboard_events': 50,
            'ideal_event_density': 50
        }
    },
    'profile': {
        'selection': {
            'min_quality_score': 5.0,
            'max_sessions': 20,
            'prefer_recent': True,
            'recent_weight_decay': 0.95
        },
        'statistics': {
            'confidence_level': 0.95,
            'outlier_threshold': 3.0,
            'distribution_types': ['normal', 'lognormal', 'gamma']
        },
        'validation': {
            'require_fitts_data': True,
            'require_digraph_data': True,
            'min_completeness_score': 0.7
        }
    },
    'replay': {
        'timing': {
            'base_delay_ms': 1,
            'jitter_enabled': True,
            'jitter_max_percent': 10
        },
        'movement': {
            'use_bezier_curves': True,
            'bezier_control_points': 2,
            'overshoot_simulation': True,
            'overshoot_probability': 0.15
        },
        'keyboard': {
            'typo_injection': True,
            'typo_base_rate': 0.02,
            'correct_typos': True,
            'fatigue_simulation': True,
            'fatigue_rate': 0.001
        }
    },
    'calibration': {
        'fitts_test': {
            'num_trials': 50,
            'target_sizes': [20, 40, 60, 80, 100],
            'distances': [100, 200, 400, 600, 800],
            'randomize': True
        },
        'typing_test': {
            'passages': [
                'The quick brown fox jumps over the lazy dog.',
                'Pack my box with five dozen liquor jugs.',
                'How vexingly quick daft zebras jump!'
            ],
            'duration_seconds': 120,
            'include_numbers': True,
            'include_punctuation': True
        },
        'scroll_test': {
            'duration_seconds': 60,
            'directions': ['up', 'down'],
            'scroll_types': ['smooth', 'discrete']
        }
    },
    'ai': {
        'enabled': True,
        'provider': 'openrouter',
        'openrouter': {
            'api_key_env': 'OPENROUTER_API_KEY',
            'base_url': 'https://openrouter.ai/api/v1',
            'models': {
                'text': 'qwen/qwen-2.5-coder-32b-instruct',
                'vision': 'qwen/qwen-2-vl-72b-instruct'
            },
            'parameters': {
                'temperature': 0.7,
                'max_tokens': 4096,
                'top_p': 0.9
            }
        }
    },
    'logging': {
        'level': 'INFO',
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file': {
            'enabled': True,
            'path': 'logs/profiler.log',
            'max_size_mb': 10,
            'backup_count': 5
        },
        'console': {
            'enabled': True,
            'colored': True
        }
    }
}


class ProfilerConfig:
    """
    Configuration manager for the profiler system.

    Handles loading, merging, and accessing configuration values.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to YAML config file. If None, uses defaults.
        """
        self._config = DEFAULT_CONFIG.copy()
        self._config_path = config_path

        if config_path:
            self.load(config_path)

        # Apply environment variable overrides
        self._apply_env_overrides()

    def load(self, config_path: str) -> bool:
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to YAML config file

        Returns:
            True if loaded successfully
        """
        if not HAS_YAML:
            logger.warning("PyYAML not installed, using default config")
            return False

        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Config file not found: {config_path}")
            return False

        try:
            with open(path, 'r') as f:
                loaded = yaml.safe_load(f)

            if loaded:
                self._config = self._deep_merge(self._config, loaded)
                logger.info(f"Loaded config from: {config_path}")
                return True

        except Exception as e:
            logger.error(f"Failed to load config: {e}")

        return False

    def save(self, config_path: Optional[str] = None) -> bool:
        """
        Save current configuration to YAML file.

        Args:
            config_path: Path to save to. Uses loaded path if None.

        Returns:
            True if saved successfully
        """
        if not HAS_YAML:
            logger.error("PyYAML not installed, cannot save config")
            return False

        path = Path(config_path or self._config_path)
        if not path:
            logger.error("No config path specified")
            return False

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Saved config to: {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.

        Args:
            key: Dot-separated key path (e.g., 'recording.mouse.sample_rate_hz')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value by dot-notation key.

        Args:
            key: Dot-separated key path
            value: Value to set
        """
        keys = key.split('.')
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def __getitem__(self, key: str) -> Any:
        """Get config value using bracket notation."""
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Set config value using bracket notation."""
        self.set(key, value)

    @property
    def user_id(self) -> str:
        """Get user ID."""
        return self.get('user.id', 'default')

    @property
    def session_dir(self) -> str:
        """Get session directory."""
        return self.get('recording.session_dir', 'recordings/sessions')

    @property
    def profile_dir(self) -> str:
        """Get profile directory."""
        return self.get('recording.profile_dir', 'profiles')

    @property
    def vnc_host(self) -> str:
        """Get VNC host."""
        return self.get('vnc.host', '192.168.100.10')

    @property
    def vnc_port(self) -> int:
        """Get VNC port."""
        return self.get('vnc.port', 5900)

    @property
    def hid_host(self) -> str:
        """Get HID controller host."""
        return self.get('hid.host', '192.168.100.1')

    @property
    def mouse_sample_rate(self) -> int:
        """Get mouse sample rate."""
        return self.get('recording.mouse.sample_rate_hz', 1000)

    @property
    def ai_enabled(self) -> bool:
        """Check if AI integration is enabled."""
        return self.get('ai.enabled', True)

    @property
    def openrouter_api_key(self) -> Optional[str]:
        """Get OpenRouter API key from environment."""
        env_var = self.get('ai.openrouter.api_key_env', 'OPENROUTER_API_KEY')
        return os.environ.get(env_var)

    @property
    def text_model(self) -> str:
        """Get text model name."""
        return self.get('ai.openrouter.models.text', 'qwen/qwen-2.5-coder-32b-instruct')

    @property
    def vision_model(self) -> str:
        """Get vision model name."""
        return self.get('ai.openrouter.models.vision', 'qwen/qwen-2-vl-72b-instruct')

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """
        Deep merge two dictionaries.

        Args:
            base: Base dictionary
            override: Dictionary with override values

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        # VNC password from environment
        vnc_password = os.environ.get('VNC_PASSWORD')
        if vnc_password:
            self.set('vnc.password', vnc_password)

        # HID host override
        hid_host = os.environ.get('HID_HOST')
        if hid_host:
            self.set('hid.host', hid_host)

        # VNC host override
        vnc_host = os.environ.get('VNC_HOST')
        if vnc_host:
            self.set('vnc.host', vnc_host)

        # User ID override
        user_id = os.environ.get('PROFILER_USER_ID')
        if user_id:
            self.set('user.id', user_id)

    def to_dict(self) -> Dict[str, Any]:
        """Get full configuration as dictionary."""
        return self._config.copy()

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate configuration.

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check required paths exist or can be created
        session_dir = Path(self.session_dir)
        if not session_dir.exists():
            try:
                session_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create session directory: {e}")

        # Check network settings
        if not self.vnc_host:
            issues.append("VNC host not configured")
        if not self.hid_host:
            issues.append("HID host not configured")

        # Check AI settings if enabled
        if self.ai_enabled:
            if not self.openrouter_api_key:
                issues.append("OpenRouter API key not set (check OPENROUTER_API_KEY env)")

        # Validate numeric ranges
        sample_rate = self.mouse_sample_rate
        if sample_rate < 1 or sample_rate > 10000:
            issues.append(f"Invalid mouse sample rate: {sample_rate}")

        return len(issues) == 0, issues


# Global configuration instance
_config: Optional[ProfilerConfig] = None


def get_config() -> ProfilerConfig:
    """
    Get global configuration instance.

    Returns:
        ProfilerConfig instance
    """
    global _config

    if _config is None:
        # Try to find config file
        config_paths = [
            'config/profiler_config.yaml',
            'profiler_config.yaml',
            Path.home() / '.config' / 'profiler' / 'config.yaml',
        ]

        for path in config_paths:
            if Path(path).exists():
                _config = ProfilerConfig(str(path))
                break
        else:
            _config = ProfilerConfig()

    return _config


def set_config(config: ProfilerConfig) -> None:
    """
    Set global configuration instance.

    Args:
        config: ProfilerConfig instance
    """
    global _config
    _config = config


def load_config(config_path: str) -> ProfilerConfig:
    """
    Load and set configuration from file.

    Args:
        config_path: Path to config file

    Returns:
        ProfilerConfig instance
    """
    global _config
    _config = ProfilerConfig(config_path)
    return _config
