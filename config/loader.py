"""Configuration loader for golf calendar application."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from .models import (
    AppConfig,
    UserConfig,
    ClubConfig,
    LoggingConfig,
    WeatherConfig,
    AuthDetails,
    Coordinates
)

logger = logging.getLogger(__name__)

class ConfigurationError(Exception):
    """Configuration error."""
    pass

def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Dictionary containing JSON data
        
    Raises:
        ConfigurationError: If file cannot be loaded
    """
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise ConfigurationError(f"Failed to load {file_path}: {e}")

def get_config_dir() -> Path:
    """Get configuration directory.
    
    Returns:
        Path to configuration directory
        
    Raises:
        ConfigurationError: If directory cannot be found
    """
    # Try environment variable first
    config_dir = os.environ.get("GOLFCAL_CONFIG_DIR")
    if config_dir:
        path = Path(config_dir)
        if path.is_dir():
            return path
        raise ConfigurationError(f"Configuration directory not found: {config_dir}")
    
    # Try default locations
    candidates = [
        Path.cwd() / "config",
        Path.home() / ".config" / "golfcal",
        Path("/etc/golfcal")
    ]
    
    for path in candidates:
        if path.is_dir():
            return path
    
    raise ConfigurationError(
        f"Configuration directory not found in: {', '.join(str(p) for p in candidates)}"
    )

def ensure_directories_exist(settings: Dict[str, Any]) -> None:
    """Ensure required directories exist.
    
    Args:
        settings: Settings dictionary
    """
    # Create ICS directory
    ics_dir = Path(settings.get("ics_dir", "calendars"))
    ics_dir.mkdir(parents=True, exist_ok=True)
    
    # Create logs directory
    if "logging" in settings and "file" in settings["logging"]:
        log_file = Path(settings["logging"]["file"])
        log_file.parent.mkdir(parents=True, exist_ok=True)

def load_config() -> AppConfig:
    """Load application configuration.
    
    Returns:
        Application configuration
        
    Raises:
        ConfigurationError: If configuration cannot be loaded
    """
    try:
        # Get configuration directory
        config_dir = get_config_dir()
        logger.debug(f"Using configuration directory: {config_dir}")
        
        # Load configuration files
        settings = load_json_file(config_dir / "settings.json")
        users_data = load_json_file(config_dir / "users.json")
        clubs_data = load_json_file(config_dir / "clubs.json")
        
        # Ensure required directories exist
        ensure_directories_exist(settings)
        
        # Convert users dictionary to list
        users = [
            UserConfig(**user_data)
            for user_data in users_data.values()
        ]
        
        # Convert clubs dictionary to dictionary of ClubConfig
        clubs = {
            name: ClubConfig(**club_data)
            for name, club_data in clubs_data.items()
        }
        
        # Create configuration dictionary
        config_dict = {
            **settings,
            "users": users,
            "clubs": clubs
        }
        
        # Create and validate configuration
        return AppConfig(**config_dict)
        
    except Exception as e:
        raise ConfigurationError(f"Invalid configuration: {e}")