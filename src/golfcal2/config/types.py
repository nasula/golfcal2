"""Configuration type definitions."""

import os
from dataclasses import dataclass, field
from pathlib import Path
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
class WeatherConfig:
    """Weather service configuration."""
    met: str
    openmeteo: str

@dataclass
class APIKeys:
    """API key configuration."""
    weather: WeatherConfig

@dataclass
class GlobalConfig:
    """Global configuration."""
    api_keys: APIKeys
    timezone: str = "Europe/Oslo"
    utc_timezone: str = "UTC"
    log_level: str = "INFO"
    log_file: str = "golfcal2.log"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_date_format: str = "%Y-%m-%d %H:%M:%S"
    log_max_bytes: int = 10485760  # 10MB
    log_backup_count: int = 5
    log_to_console: bool = True
    log_to_file: bool = True
    log_to_syslog: bool = False
    log_syslog_address: str = "/dev/log"
    log_syslog_facility: str = "local0"
    log_syslog_format: str = "%(name)s: %(levelname)s %(message)s"
    log_syslog_level: str = "INFO"
    log_syslog_tag: str = "golfcal2"
    log_syslog_enabled: bool = False
    log_syslog_host: str = "localhost"
    log_syslog_port: int = 514
    log_syslog_socket: str = "UDP"
    log_syslog_tls: bool = False
    log_syslog_tls_verify: bool = True
    log_syslog_tls_ca_cert: str = ""
    log_syslog_tls_cert: str = ""
    log_syslog_tls_key: str = ""
    log_syslog_tls_password: str = ""
    log_syslog_tls_keyfile: str = ""
    log_syslog_tls_certfile: str = ""
    log_syslog_tls_ca_certs: str = ""
    log_syslog_tls_ciphers: str = ""
    log_syslog_tls_version: str = ""
    log_syslog_tls_verify_mode: str = ""
    log_syslog_tls_verify_flags: str = ""
    log_syslog_tls_verify_depth: int = 0
    log_syslog_tls_verify_callback: str = ""
    log_syslog_tls_verify_hostname: bool = True
    log_syslog_tls_verify_cert: bool = True
    log_syslog_tls_verify_key: bool = True
    log_syslog_tls_verify_chain: bool = True
    log_syslog_tls_verify_dates: bool = True
    log_syslog_tls_verify_hostname_callback: str = ""
    log_syslog_tls_verify_cert_callback: str = ""
    log_syslog_tls_verify_key_callback: str = ""
    log_syslog_tls_verify_chain_callback: str = ""
    log_syslog_tls_verify_dates_callback: str = ""

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
            self.api_keys = self.global_config.get('api_keys', {'weather': {'met': '', 'openmeteo': ''}})

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return getattr(self, key, default)

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
        
        # Check both global and user configs for the path
        user_path: Optional[str] = None
        
        # Check global config first
        if self.global_config and 'ics_files' in self.global_config:
            user_path = self.global_config['ics_files'].get(user_name)
        
        # If not found, check user config
        if not user_path and user_name in self.users:
            user_config = self.users[user_name]
            user_path = user_config.get('ics_file_path')
        
        # Process the path if found
        if user_path is None or not isinstance(user_path, str):
            return None
            
        if not os.path.isabs(user_path):
            return str(workspace_dir / user_path)
            
        return user_path 