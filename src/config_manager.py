"""Configuration management for the widget"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Fixed per-user location so the config doesn't depend on the launch directory
DEFAULT_CONFIG_PATH = Path.home() / ".sportify" / "config.json"


class ConfigManager:
    """Manages user configuration and settings"""

    DEFAULT_CONFIG = {
        "sport": "world_cup",
        "refresh_interval": 60,
        "favorite_team": "",
        "show_standings": True,
        "window_width": 540,
        "window_height": 600,
        "opacity": 0.95,
        "always_on_top": True
    }

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = Path(config_path)
        self.config = self.load()

    def load(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                # Merge with defaults to handle missing keys
                return {**self.DEFAULT_CONFIG, **config}
            except Exception as e:
                logger.warning("Failed to load config: %s", e)
                return self.DEFAULT_CONFIG.copy()

        self.save(self.DEFAULT_CONFIG)
        return self.DEFAULT_CONFIG.copy()

    def save(self, config: Dict[str, Any] = None):
        """Save configuration to file"""
        if config is None:
            config = self.config

        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save config: %s", e)

    def get(self, key: str, default=None):
        """Get a configuration value"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """Set a configuration value and save"""
        self.config[key] = value
        self.save()
