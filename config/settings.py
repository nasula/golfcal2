"""
Configuration settings for golf calendar application.
"""

import os
import json
import yaml
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

from golfcal2.utils.logging_utils import LoggerMixin

@dataclass
class AppConfig:
    """Application configuration."""
    users: Dict[str, Any]
    clubs: Dict[str, Any]
    global_config: Dict[str, Any]
    timezone: str = "Europe/Helsinki"
    ics_dir: str = "ics"
    ics_file_path: Optional[str] = None
    config_dir: str = "config"
    log_level: str = "WARNING"
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

    def get_ics_path(self, user_name: str) -> Optional[str]:
        """Get ICS file path for a user."""
        # First check environment variable
        env_path = os.getenv("GOLFCAL_ICS_FILE_PATH")
        if env_path:
            return env_path
        
        # Get workspace directory
        workspace_dir = Path(__file__).parent.parent
        
        # Then check global config
        if self.global_config and 'ics_files' in self.global_config:
            user_path = self.global_config['ics_files'].get(user_name)
            if user_path:
                # If path is relative, make it relative to workspace
                if not os.path.isabs(user_path):
                    return str(workspace_dir / user_path)
                return user_path
        
        # Finally check user config
        if user_name in self.users:
            user_config = self.users[user_name]
            if 'ics_file_path' in user_config:
                user_path = user_config['ics_file_path']
                # If path is relative, make it relative to workspace
                if not os.path.isabs(user_path):
                    return str(workspace_dir / user_path)
                return user_path
        
        return None

    def setup_logging(self, dev_mode: bool = False, verbose: bool = False) -> None:
        """Set up logging based on configuration and mode."""
        # Get log level based on mode
        if dev_mode:
            level = self.global_config.get('logging', {}).get('dev_level', 'DEBUG')
        elif verbose:
            level = self.global_config.get('logging', {}).get('verbose_level', 'INFO')
        else:
            level = self.global_config.get('logging', {}).get('default_level', 'WARNING')

        # Convert string level to logging constant
        numeric_level = getattr(logging, level.upper(), logging.WARNING)

        # Configure logging
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        if self.log_file:
            logging.basicConfig(
                level=numeric_level,
                format=log_format,
                handlers=[
                    logging.FileHandler(self.log_file),
                    logging.StreamHandler()
                ]
            )
        else:
            logging.basicConfig(
                level=numeric_level,
                format=log_format
            )

        # Only show library logs in debug mode
        if not dev_mode:
            # Suppress logs from libraries unless they're WARNING or higher
            logging.getLogger('urllib3').setLevel(logging.WARNING)
            logging.getLogger('requests').setLevel(logging.WARNING)
            logging.getLogger('icalendar').setLevel(logging.WARNING)

def load_config(config_dir: Optional[str] = None, dev_mode: bool = False, verbose: bool = False) -> AppConfig:
    """
    Load configuration from JSON and YAML files.
    
    Args:
        config_dir: Optional path to configuration directory
        dev_mode: Whether to run in development mode
        verbose: Whether to enable verbose logging
        
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
    workspace_dir = config_path.parent
    
    # Load global configuration
    global_config = {}
    config_file = config_path / "config.yaml"
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            global_config = yaml.safe_load(f)
            
            # Convert relative paths to absolute paths using workspace directory
            if 'ics_files' in global_config:
                for user, path in global_config['ics_files'].items():
                    if not os.path.isabs(path):
                        global_config['ics_files'][user] = str(workspace_dir / path)
    
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
    
    with open(clubs_file, "r", encoding="utf-8") as f:
        clubs = json.load(f)
    
    # Create configuration object with environment variables and global config
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

    # Set up logging based on mode
    config.setup_logging(dev_mode=dev_mode, verbose=verbose)

    return config

def validate_config(config: AppConfig) -> bool:
    """
    Validate configuration.
    
    Args:
        config: AppConfig object to validate
        
    Returns:
        True if configuration is valid, False otherwise
    """
    try:
        # Get workspace directory (where the package is installed)
        workspace_dir = Path(__file__).parent.parent
        
        # Check required directories using workspace as base for relative paths
        if not os.path.isabs(config.ics_dir):
            config.ics_dir = str(workspace_dir / config.ics_dir)
        if not os.path.isabs(config.config_dir):
            config.config_dir = str(workspace_dir / config.config_dir)
            
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