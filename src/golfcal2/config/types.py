"""Configuration type definitions."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, TypedDict, List, Union

class WeatherApiConfig(TypedDict):
    """Weather API configuration."""
    aemet: str
    openweather: str

class ApiKeysConfig(TypedDict):
    """API keys configuration."""
    weather: WeatherApiConfig

class LoggingConfig(TypedDict):
    """Logging configuration."""
    dev_level: str
    verbose_level: str
    default_level: str
    file: Optional[str]
    max_size: int  # in MB
    backup_count: int

class GlobalConfig(TypedDict):
    """Global configuration structure."""
    timezone: str
    directories: Dict[str, str]
    ics_files: Dict[str, str]
    api_keys: ApiKeysConfig
    logging: LoggingConfig

class AuthDetails(TypedDict):
    """Authentication details."""
    type: str
    auth_type: str
    token: Optional[str]
    cookie_name: Optional[str]
    cookie_value: Optional[str]

class Duration(TypedDict):
    """Duration configuration."""
    hours: int
    minutes: int

class Membership(TypedDict):
    """Club membership configuration."""
    club: str
    duration: Duration
    auth_details: AuthDetails

class UserConfig(TypedDict):
    """User configuration."""
    timezone: Optional[str]
    duration: Optional[Duration]
    memberships: List[Membership]
    ics_file_path: Optional[str]

class Coordinates(TypedDict):
    """Golf club coordinates."""
    lat: float
    lon: float

class ClubConfig(TypedDict):
    """Golf club configuration."""
    name: str
    type: str
    url: Optional[str]
    clubId: Optional[str]
    ajaxUrl: Optional[str]
    restUrl: Optional[str]
    auth_type: str
    crm: str
    timezone: Optional[str]
    variant: Optional[str]
    address: Optional[str]
    coordinates: Optional[Coordinates]

@dataclass
class AppConfig:
    """Application configuration."""
    users: Dict[str, UserConfig]
    clubs: Dict[str, ClubConfig]
    global_config: GlobalConfig
    api_keys: ApiKeysConfig
    timezone: str = "Europe/Helsinki"
    ics_dir: str = "ics"
    ics_file_path: Optional[str] = None
    config_dir: str = "config"
    log_level: str = "WARNING"
    log_file: Optional[str] = None

    def __post_init__(self):
        """Initialize additional fields from global config."""
        if 'api_keys' not in self.__dict__ or not self.api_keys:
            self.api_keys = self.global_config.get('api_keys', {'weather': {'aemet': '', 'openweather': ''}})

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
        """Get ICS file path for a user.
        
        Args:
            user_name: Name of the user
            
        Returns:
            Path to the ICS file or None if not configured
        """
        # First check environment variable
        env_path = os.getenv("GOLFCAL_ICS_FILE_PATH")
        if env_path:
            return env_path
        
        # Get workspace directory
        workspace_dir = Path(self.config_dir).parent
        
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