"""
Configuration Management

Handles loading and validation of configuration from YAML files.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import yaml


@dataclass
class VNCConfig:
    """VNC connection configuration."""
    host: str = '192.168.100.100'
    port: int = 5900
    password: str = ''
    timeout: float = 10.0


@dataclass
class HIDConfig:
    """HID controller connection configuration."""
    host: str = '192.168.100.1'
    mouse_port: int = 8888
    keyboard_port: int = 8889
    timeout: float = 5.0


@dataclass
class MouseConfig:
    """Human-like mouse behavior configuration."""
    min_duration_ms: float = 100.0
    max_duration_ms: float = 800.0
    overshoot_probability: float = 0.15
    jitter_pixels: int = 3
    fitts_law_a: float = 50.0  # Fitts's Law intercept
    fitts_law_b: float = 150.0  # Fitts's Law slope


@dataclass
class KeyboardConfig:
    """Human-like keyboard behavior configuration."""
    base_wpm: int = 45
    wpm_variance: int = 10
    typo_rate: float = 0.02
    correction_delay_ms: float = 200.0
    burst_words: list = field(default_factory=lambda: ['the', 'and', 'is', 'to', 'in'])


@dataclass
class TimingConfig:
    """Timing behavior configuration."""
    min_think_time_ms: float = 300.0
    max_think_time_ms: float = 2000.0
    double_click_interval_ms: float = 100.0
    scroll_pause_ms: float = 50.0
    action_cooldown_ms: float = 100.0


@dataclass
class VisionConfig:
    """Vision AI configuration."""
    omniparser_model: str = 'models/omniparser_v2.pt'
    confidence_threshold: float = 0.7
    use_ollama: bool = True
    ollama_host: str = 'http://localhost:11434'
    ollama_model: str = 'qwen2.5-vl:7b'
    ocr_lang: str = 'en'


@dataclass
class AgentConfig:
    """Agent behavior configuration."""
    capture_fps: int = 30
    max_actions_per_minute: int = 60
    screenshot_interval: int = 10
    log_level: str = 'INFO'


@dataclass
class Config:
    """Main configuration container."""
    vnc: VNCConfig = field(default_factory=VNCConfig)
    hid: HIDConfig = field(default_factory=HIDConfig)
    mouse: MouseConfig = field(default_factory=MouseConfig)
    keyboard: KeyboardConfig = field(default_factory=KeyboardConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """Create Config from dictionary."""
        return cls(
            vnc=VNCConfig(**data.get('vnc', {})),
            hid=HIDConfig(**data.get('hid', {})),
            mouse=MouseConfig(**data.get('mouse', {})),
            keyboard=KeyboardConfig(**data.get('keyboard', {})),
            timing=TimingConfig(**data.get('timing', {})),
            vision=VisionConfig(**data.get('vision', {})),
            agent=AgentConfig(**data.get('agent', {})),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert Config to dictionary."""
        return {
            'vnc': self.vnc.__dict__,
            'hid': self.hid.__dict__,
            'mouse': self.mouse.__dict__,
            'keyboard': self.keyboard.__dict__,
            'timing': self.timing.__dict__,
            'vision': self.vision.__dict__,
            'agent': self.agent.__dict__,
        }


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, uses default locations.

    Returns:
        Config object with loaded settings.
    """
    # Default config paths
    if config_path is None:
        possible_paths = [
            Path('config/config.yaml'),
            Path('../config/config.yaml'),
            Path.home() / '.config' / 'ai-controller' / 'config.yaml',
            Path('/etc/ai-controller/config.yaml'),
        ]
        for path in possible_paths:
            if path.exists():
                config_path = str(path)
                break

    if config_path and Path(config_path).exists():
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
            return Config.from_dict(data or {})

    # Return default config
    return Config()


def save_config(config: Config, config_path: str) -> None:
    """
    Save configuration to YAML file.

    Args:
        config: Config object to save.
        config_path: Path to save the config file.
    """
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, 'w') as f:
        yaml.dump(config.to_dict(), f, default_flow_style=False, sort_keys=False)
