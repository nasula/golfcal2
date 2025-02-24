"""Environment variable handling for configuration."""

import os
from typing import Any
from typing import TypeVar

from golfcal2.config.types import GlobalConfig
from golfcal2.config.types import LoggingConfig
from golfcal2.config.types import WeatherApiConfig


T = TypeVar('T')

class EnvConfig:
    """Environment variable configuration."""

    # Mapping of environment variables to configuration paths
    ENV_MAPPING = {
        'GOLFCAL_TIMEZONE': ('timezone',),
        'GOLFCAL_CONFIG_DIR': ('directories', 'config'),
        'GOLFCAL_ICS_DIR': ('directories', 'ics'),
        'GOLFCAL_LOG_LEVEL': ('logging', 'default_level'),
        'GOLFCAL_LOG_FILE': ('logging', 'file'),
        'GOLFCAL_AEMET_API_KEY': ('api_keys', 'weather', 'aemet'),
        'GOLFCAL_OPENWEATHER_API_KEY': ('api_keys', 'weather', 'openweather'),
    }

    @staticmethod
    def get_env_value(env_var: str, default: Any | None = None) -> Any | None:
        """Get value from environment variable with default."""
        return os.getenv(env_var, default)

    @staticmethod
    def _set_nested_value(config: dict[str, Any], path: tuple, value: Any) -> None:
        """Set value in nested dictionary using path tuple."""
        current = config
        for part in path[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[path[-1]] = value

    @classmethod
    def update_config_from_env(cls, config: dict[str, Any]) -> None:
        """Update configuration dictionary with environment variables.
        
        Args:
            config: Configuration dictionary to update
        """
        for env_var, path in cls.ENV_MAPPING.items():
            value = cls.get_env_value(env_var)
            if value is not None:
                cls._set_nested_value(config, path, value)

    @classmethod
    def get_weather_api_config(cls) -> WeatherApiConfig:
        """Get weather API configuration from environment."""
        return {
            'aemet': cls.get_env_value('GOLFCAL_AEMET_API_KEY', ''),
            'openweather': cls.get_env_value('GOLFCAL_OPENWEATHER_API_KEY', '')
        }

    @classmethod
    def get_logging_config(cls) -> LoggingConfig:
        """Get logging configuration from environment."""
        return {
            'dev_level': cls.get_env_value('GOLFCAL_DEV_LOG_LEVEL', 'DEBUG'),
            'verbose_level': cls.get_env_value('GOLFCAL_VERBOSE_LOG_LEVEL', 'INFO'),
            'default_level': cls.get_env_value('GOLFCAL_LOG_LEVEL', 'WARNING'),
            'file': cls.get_env_value('GOLFCAL_LOG_FILE'),
            'max_size': int(cls.get_env_value('GOLFCAL_LOG_MAX_SIZE', '10')),
            'backup_count': int(cls.get_env_value('GOLFCAL_LOG_BACKUP_COUNT', '5'))
        }

    @classmethod
    def get_global_config(cls) -> GlobalConfig:
        """Get global configuration from environment."""
        return {
            'timezone': cls.get_env_value('GOLFCAL_TIMEZONE', 'Europe/Helsinki'),
            'directories': {
                'config': cls.get_env_value('GOLFCAL_CONFIG_DIR', 'config'),
                'ics': cls.get_env_value('GOLFCAL_ICS_DIR', 'ics')
            },
            'ics_files': {},  # ICS files are loaded from config file
            'api_keys': {
                'weather': cls.get_weather_api_config()
            },
            'logging': cls.get_logging_config()
        } 