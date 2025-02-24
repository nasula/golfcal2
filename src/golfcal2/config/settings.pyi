"""Type stubs for configuration settings."""

from typing import Optional, Dict, Any
from pathlib import Path
from zoneinfo import ZoneInfo

from golfcal2.config.types import AppConfig, GlobalConfig, UserConfig, ClubConfig

class ConfigurationManager:
    """Centralized configuration management with caching."""
    
    _instance: Optional['ConfigurationManager']
    _initialized: bool
    _config: Optional[AppConfig]
    _config_path: Optional[Path]
    _timezone_cache: Dict[str, ZoneInfo]
    
    def __new__(cls) -> 'ConfigurationManager': ...
    
    def __init__(self) -> None: ...
    
    @property
    def config(self) -> AppConfig: ...
    
    def get_timezone(self, tz_name: str) -> ZoneInfo: ...
    
    def load_config(self, config_dir: Optional[str] = None, dev_mode: bool = False, verbose: bool = False) -> AppConfig: ...
    
    def reload_config(self) -> AppConfig: ... 