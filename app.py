"""Application initialization."""

import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any

from flask import Flask
from flask_cors import CORS

from .config import Config, load_config
from .services.calendar_service import CalendarService
from .services.weather_service import WeatherManager
from .utils.logging_utils import setup_logging
from .config.error_aggregator import init_error_aggregator, ErrorAggregationConfig

# Global cache for configuration and services
_config_cache: Optional[Dict[str, Any]] = None
_weather_manager_cache: Optional[WeatherManager] = None
_calendar_service_cache: Optional[CalendarService] = None

def _get_or_create_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """Get or create configuration with caching."""
    global _config_cache
    if not _config_cache:
        _config_cache = load_config()
        if config_file:
            # Merge additional config if provided
            with open(config_file, 'r') as f:
                additional_config = yaml.safe_load(f)
                _config_cache.update(additional_config)
        
        # Cache timezone objects
        _config_cache['local_tz'] = ZoneInfo(_config_cache.global_config.get('timezone', 'UTC'))
        _config_cache['utc_tz'] = ZoneInfo('UTC')
    return _config_cache

def create_app(config_file: Optional[str] = None, dev_mode: bool = False, verbose: bool = False) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)
    
    # Load configuration with caching
    config = _get_or_create_config(config_file)
    app.config.from_object(Config)
    
    # Set up logging with proper flags
    setup_logging(config, dev_mode=dev_mode, verbose=verbose)
    
    # Initialize error aggregator
    error_config = ErrorAggregationConfig(
        report_interval=app.config.get('ERROR_REPORT_INTERVAL', 3600),
        error_threshold=app.config.get('ERROR_THRESHOLD', 5)
    )
    init_error_aggregator(error_config)
    
    # Initialize services with caching
    global _weather_manager_cache, _calendar_service_cache
    
    if not _weather_manager_cache:
        _weather_manager_cache = WeatherManager(config['local_tz'], config['utc_tz'], config)
    
    if not _calendar_service_cache:
        _calendar_service_cache = CalendarService(
            config=config,
            weather_service=_weather_manager_cache,
            dev_mode=dev_mode
        )
    
    app.weather_manager = _weather_manager_cache
    app.calendar_service = _calendar_service_cache
    
    # Register routes
    from .routes import register_routes
    register_routes(app)
    
    return app 