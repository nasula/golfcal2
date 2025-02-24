"""Type stubs for configuration settings."""

from pathlib import Path
from zoneinfo import ZoneInfo

from golfcal2.config.types import AppConfig

class ConfigurationManager:
    """Centralized configuration management with caching."""
    
    _instance: ConfigurationManager | None
    _initialized: bool
    _config: AppConfig | None
    _config_path: Path | None
    _timezone_cache: dict[str, ZoneInfo]
    
    def __new__(cls) -> ConfigurationManager: ...
    
    def __init__(self) -> None: ...
    
    @property
    def config(self) -> AppConfig: ...
    
    def get_timezone(self, tz_name: str) -> ZoneInfo: ...
    
    def load_config(self, config_dir: str | None = None, dev_mode: bool = False, verbose: bool = False) -> AppConfig: ...
    
    def reload_config(self) -> AppConfig: ... 