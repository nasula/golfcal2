"""Configuration settings for golf calendar application."""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.config.validation import validate_config, ConfigValidationError
from golfcal2.config.types import (
    AppConfig, GlobalConfig, UserConfig, ClubConfig,
    WeatherApiConfig, ApiKeysConfig, LoggingConfig
)
from golfcal2.config.logging import setup_logging
from golfcal2.config.env import EnvConfig
from golfcal2.config.utils import deep_merge, resolve_path, validate_api_key, get_config_paths

def _get_config_path(config_dir: Optional[str] = None) -> Path:
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
        with open(config_file, "r", encoding="utf-8") as f:
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

def _load_users_config(config_path: Path) -> Dict[str, UserConfig]:
    """Load users configuration from JSON file."""
    users_file = config_path / "users.json"
    if not users_file.exists():
        raise FileNotFoundError(f"Users configuration file not found: {users_file}")
    
    with open(users_file, "r", encoding="utf-8") as f:
        return json.load(f)

def _load_clubs_config(config_path: Path) -> Dict[str, ClubConfig]:
    """Load clubs configuration from JSON file."""
    clubs_file = config_path / "clubs.json"
    if not clubs_file.exists():
        raise FileNotFoundError(f"Clubs configuration file not found: {clubs_file}")
    
    with open(clubs_file, "r", encoding="utf-8") as f:
        return json.load(f)

def load_config(config_dir: Optional[str] = None, dev_mode: bool = False, verbose: bool = False) -> AppConfig:
    """Load configuration from JSON and YAML files.
    
    Args:
        config_dir: Optional path to configuration directory
        dev_mode: Whether to run in development mode
        verbose: Whether to enable verbose logging
        
    Returns:
        AppConfig object
        
    Raises:
        ConfigValidationError: If configuration is invalid
        FileNotFoundError: If required configuration files are not found
        json.JSONDecodeError: If configuration files contain invalid JSON
    """
    try:
        # Get configuration directory
        config_path = _get_config_path(config_dir)
        
        # Load configurations
        global_config = _load_global_config(config_path)
        users = _load_users_config(config_path)
        clubs = _load_clubs_config(config_path)
        
        # Create configuration object
        config = AppConfig(
            users=users,
            clubs=clubs,
            global_config=global_config,
            timezone=os.getenv("GOLFCAL_TIMEZONE", global_config.get('timezone', "Europe/Helsinki")),
            ics_dir=os.getenv("GOLFCAL_ICS_DIR", global_config.get('directories', {}).get('ics', "ics")),
            ics_file_path=os.getenv("GOLFCAL_ICS_FILE_PATH"),
            config_dir=str(config_path),
            log_level=os.getenv("GOLFCAL_LOG_LEVEL", global_config.get('logging', {}).get('level', "WARNING")),
            log_file=os.getenv("GOLFCAL_LOG_FILE", global_config.get('logging', {}).get('file'))
        )

        # Validate configuration
        validate_config(config)
        
        # Set up logging based on mode
        setup_logging(config, dev_mode=dev_mode, verbose=verbose)

        return config
        
    except (FileNotFoundError, json.JSONDecodeError, ConfigValidationError):
        raise
    except Exception as e:
        raise ConfigValidationError(
            f"Unexpected error during configuration loading: {str(e)}",
            {"error_type": type(e).__name__}
        ) from e 