"""Type stubs for configuration types."""

from typing import Any
from typing import TypedDict

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
    file: str | None
    max_size: int
    backup_count: int

class GlobalConfig(TypedDict):
    """Global configuration structure."""
    timezone: str
    directories: dict[str, str]
    ics_files: dict[str, str]
    api_keys: ApiKeysConfig
    logging: LoggingConfig

class AuthDetails(TypedDict):
    """Authentication details."""
    type: str
    auth_type: str
    token: str | None
    cookie_name: str | None
    cookie_value: str | None

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
    timezone: str | None
    duration: Duration | None
    memberships: list[Membership]
    ics_file_path: str | None

class Coordinates(TypedDict):
    """Golf club coordinates."""
    lat: float
    lon: float

class ClubConfig(TypedDict):
    """Golf club configuration."""
    name: str
    type: str
    url: str | None
    clubId: str | None
    ajaxUrl: str | None
    restUrl: str | None
    auth_type: str
    crm: str
    timezone: str | None
    variant: str | None
    address: str | None
    coordinates: Coordinates | None

class AppConfig:
    """Application configuration."""
    users: dict[str, UserConfig]
    clubs: dict[str, ClubConfig]
    global_config: GlobalConfig
    api_keys: ApiKeysConfig
    timezone: str
    ics_dir: str
    ics_file_path: str | None
    config_dir: str
    log_level: str
    log_file: str | None

    def __init__(self, users: dict[str, UserConfig], clubs: dict[str, ClubConfig], global_config: GlobalConfig, api_keys: ApiKeysConfig) -> None: ...

    def get(self, key: str, default: Any = None) -> Any: ...

    def get_user_config(self, username: str) -> UserConfig | None: ...

    def get_ics_path(self, user_name: str) -> str | None: ... 