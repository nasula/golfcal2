"""
Configuration management for golf calendar application.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

@dataclass
class AppConfig:
    """Application configuration."""
    users: Dict[str, Any]
    clubs: Dict[str, Any]
    timezone: str = "Europe/Helsinki"
    ics_dir: str = "ics"
    config_dir: str = "config"
    log_level: str = "INFO"
    log_file: Optional[str] = None

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with default."""
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        """Support dictionary-style access."""
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator."""
        return hasattr(self, key)

def load_config(config_dir: Optional[str] = None) -> AppConfig:
    """
    Load configuration from JSON files.
    
    Args:
        config_dir: Optional path to configuration directory
        
    Returns:
        AppConfig object
        
    Raises:
        FileNotFoundError: If configuration files are not found
        json.JSONDecodeError: If configuration files are invalid JSON
    """
    # Get configuration directory
    if config_dir is None:
        # First try environment variable
        config_dir = os.getenv("GOLFCAL_CONFIG_DIR")
        if not config_dir:
            # Then use the current directory (golfcal/config)
            config_dir = os.path.dirname(os.path.abspath(__file__))
    
    config_path = Path(config_dir)
    print(f"Loading configuration from {config_path}")
    
    # Load users configuration
    users_file = config_path / "users.json"
    if not users_file.exists():
        raise FileNotFoundError(f"Users configuration file not found: {users_file}")
    
    with open(users_file, "r", encoding="utf-8") as f:
        users = json.load(f)
    
    # Load clubs configuration
    clubs_file = config_path / "clubs.json"
    if not clubs_file.exists():
        raise FileNotFoundError(f"Clubs configuration file not found: {clubs_file}")
    
    print(f"Loading clubs from {clubs_file}")
    with open(clubs_file, "r", encoding="utf-8") as f:
        clubs = json.load(f)
        print(f"Loaded clubs: {list(clubs.keys())}")
        for club_name, club_config in clubs.items():
            print(f"Club {club_name} config: {club_config}")
    
    # Create configuration object with environment variables
    return AppConfig(
        users=users,
        clubs=clubs,
        timezone=os.getenv("GOLFCAL_TIMEZONE", "Europe/Helsinki"),
        ics_dir=os.getenv("GOLFCAL_ICS_DIR", "ics"),
        config_dir=str(config_path),
        log_level=os.getenv("GOLFCAL_LOG_LEVEL", "INFO"),
        log_file=os.getenv("GOLFCAL_LOG_FILE")
    )

def validate_config(config: AppConfig) -> bool:
    """
    Validate configuration.
    
    Args:
        config: AppConfig object to validate
        
    Returns:
        True if configuration is valid, False otherwise
    """
    try:
        # Check required directories
        Path(config.ics_dir).mkdir(parents=True, exist_ok=True)
        Path(config.config_dir).mkdir(parents=True, exist_ok=True)
        
        # Validate users configuration
        for user_name, user_config in config.users.items():
            if not isinstance(user_config, dict):
                raise ValueError(f"Invalid user configuration for {user_name}")
            
            if "memberships" not in user_config:
                raise ValueError(f"No memberships found for user {user_name}")
            
            for membership in user_config["memberships"]:
                if "club" not in membership:
                    raise ValueError(f"No club specified in membership for user {user_name}")
                
                if membership["club"] not in config.clubs:
                    raise ValueError(f"Unknown club {membership['club']} in membership for user {user_name}")
                
                if "duration" not in membership:
                    raise ValueError(f"No duration specified in membership for user {user_name}")
                
                if "auth_details" not in membership:
                    raise ValueError(f"No authentication details specified in membership for user {user_name}")
        
        # Validate clubs configuration
        for club_name, club_config in config.clubs.items():
            if not isinstance(club_config, dict):
                raise ValueError(f"Invalid club configuration for {club_name}")
            
            # Different required fields based on club type
            if club_config.get('type') == 'wisegolf0':
                required_fields = ["type", "clubId", "ajaxUrl", "restUrl", "auth_type", "crm"]
            elif club_config.get('type') == 'wisegolf':
                required_fields = ["type", "url", "auth_type", "crm"]
            elif club_config.get('type') == 'teetime':
                required_fields = ["type", "url", "auth_type", "crm"]
            elif club_config.get('type') == 'nexgolf':
                required_fields = ["type", "url", "auth_type", "crm"]
            else:
                required_fields = ["type", "auth_type"]
            
            for field in required_fields:
                if field not in club_config:
                    raise ValueError(f"Missing required field '{field}' in club configuration for {club_name}")
            
            # Validate coordinates if present
            if 'coordinates' in club_config:
                coords = club_config['coordinates']
                if not isinstance(coords, dict) or 'lat' not in coords or 'lon' not in coords:
                    raise ValueError(f"Invalid coordinates format for {club_name}")
        
        return True
    
    except Exception as e:
        print(f"Configuration validation failed: {e}")
        return False 