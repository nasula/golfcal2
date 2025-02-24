"""Type stubs for configuration types."""

from typing import Dict, Any, Optional, TypedDict, List, Union
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

class WeatherApiConfig(TypedDict):
    """Weather API configuration."""
    met: str
    openmeteo: str

class ApiKeysConfig(TypedDict):
    """API keys configuration."""
    weather: WeatherApiConfig

class LoggingConfig(TypedDict):
    """Logging configuration."""
    dev_level: str
    verbose_level: str
    default_level: str
    file: Optional[str]
    max_size: int
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

class AppConfig:
    """Application configuration."""
    users: Dict[str, UserConfig]
    clubs: Dict[str, ClubConfig]
    global_config: GlobalConfig
    api_keys: ApiKeysConfig
    timezone: str
    ics_dir: str
    ics_file_path: Optional[str]
    config_dir: str
    log_level: str
    log_file: Optional[str]

    def __init__(self, users: Dict[str, UserConfig], clubs: Dict[str, ClubConfig], global_config: GlobalConfig, api_keys: ApiKeysConfig) -> None: ...

    def get(self, key: str, default: Any = None) -> Any: ...

    def get_user_config(self, username: str) -> Optional[UserConfig]: ...

    def get_ics_path(self, user_name: str) -> Optional[str]: ... 