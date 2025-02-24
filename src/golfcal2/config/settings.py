"""Configuration settings for golf calendar application."""

import json
import os
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from golfcal2.config.env import EnvConfig
from golfcal2.config.types import AppConfig
from golfcal2.config.types import ClubConfig
from golfcal2.config.types import GlobalConfig
from golfcal2.config.types import UserConfig
from golfcal2.config.utils import deep_merge
from golfcal2.config.utils import resolve_path
from golfcal2.config.utils import validate_api_key


class ConfigurationManager:
    """Centralized configuration management with caching."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._config: AppConfig | None = None
        self._config_path: Path | None = None
        self._initialized = True
        self._timezone_cache = {}
    
    @property
    def config(self) -> AppConfig:
        """Get the current configuration, loading it if necessary."""
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config() first.")
        return self._config
    
    @lru_cache(maxsize=32)
    def get_timezone(self, tz_name: str) -> ZoneInfo:
        """Get cached timezone instance."""
        return ZoneInfo(tz_name)
    
    def load_config(self, config_dir: str | None = None, dev_mode: bool = False, verbose: bool = False) -> AppConfig:
        """Load configuration with caching."""
        if self._config is not None:
            return self._config
            
        self._config_path = _get_config_path(config_dir)
        
        # Load configurations
        global_config = _load_global_config(self._config_path)
        users_config = _load_users_config(self._config_path)
        clubs_config = _load_clubs_config(self._config_path)
        
        # Create AppConfig instance
        self._config = AppConfig(
            global_config=global_config,
            users=users_config,
            clubs=clubs_config,
            api_keys=global_config.get('api_keys', {'weather': {'aemet': '', 'openweather': ''}}),
            timezone=global_config.get('timezone', 'UTC'),
            ics_dir=global_config.get('ics_dir', 'ics'),
            config_dir=str(self._config_path),
            log_level=global_config.get('log_level', 'WARNING'),
            log_file=global_config.get('log_file')
        )
        
        return self._config
    
    def reload_config(self) -> AppConfig:
        """Force reload configuration."""
        self._config = None
        return self.load_config()

def _get_config_path(config_dir: str | None = None) -> Path:
    """Get configuration directory path."""
    return resolve_path(
        config_dir or os.getenv("GOLFCAL_CONFIG_DIR", os.path.dirname(os.path.abspath(__file__)))
    )

def _load_global_config(config_path: Path) -> GlobalConfig:
    """Load global configuration from YAML file and environment."""
    # Get base configuration from environment
    global_config = EnvConfig.get_global_config()
    
    # Load from file if exists
    config_file = config_path / "config.yaml"
    if config_file.exists():
        with open(config_file, encoding="utf-8") as f:
            loaded_config = yaml.safe_load(f)
            # Deep merge loaded config with environment config
            global_config = deep_merge(global_config, loaded_config)
            
            # Convert relative paths to absolute
            workspace_dir = config_path.parent
            if 'ics_files' in global_config:
                for user, path in global_config['ics_files'].items():
                    if not os.path.isabs(path):
                        global_config['ics_files'][user] = str(workspace_dir / path)
    
    # Validate API keys
    weather_config = global_config['api_keys']['weather']
    validate_api_key(weather_config['aemet'], 'aemet')
    validate_api_key(weather_config['openweather'], 'openweather')
    
    return global_config

def _load_users_config(config_path: Path) -> dict[str, UserConfig]:
    """Load users configuration from JSON file."""
    users_file = config_path / "users.json"
    if not users_file.exists():
        raise FileNotFoundError(f"Users configuration file not found: {users_file}")
    
    with open(users_file, encoding="utf-8") as f:
        return json.load(f)

def _load_clubs_config(config_path: Path) -> dict[str, ClubConfig]:
    """Load clubs configuration from JSON file."""
    clubs_file = config_path / "clubs.json"
    if not clubs_file.exists():
        raise FileNotFoundError(f"Clubs configuration file not found: {clubs_file}")
    
    with open(clubs_file, encoding="utf-8") as f:
        return json.load(f)

def load_config(config_dir: str | None = None, dev_mode: bool = False, verbose: bool = False) -> AppConfig:
    """Load configuration using the ConfigurationManager."""
    config_manager = ConfigurationManager()
    return config_manager.load_config(config_dir, dev_mode, verbose) 