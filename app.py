"""Application initialization."""

import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any

from flask import Flask
from flask_cors import CORS

from .config import Config
from .config.settings import ConfigurationManager
from .services.calendar_service import CalendarService
from .services.weather_service import WeatherManager
from .utils.logging_utils import setup_logging
from .config.error_aggregator import init_error_aggregator, ErrorAggregationConfig

# Global service cache
_weather_manager_cache: Optional[WeatherManager] = None
_calendar_service_cache: Optional[CalendarService] = None

def create_app(config_file: Optional[str] = None, dev_mode: bool = False, verbose: bool = False) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)
    
    # Get configuration from manager
    config_manager = ConfigurationManager()
    config = config_manager.load_config(config_file, dev_mode=dev_mode, verbose=verbose)
    app.config.from_object(Config)
    
    # Set up logging with proper flags
    setup_logging(config, dev_mode=dev_mode, verbose=verbose)
    
    # Initialize services with cached configuration
    def get_weather_manager():
        global _weather_manager_cache
        if not _weather_manager_cache:
            _weather_manager_cache = WeatherManager(
                config_manager.get_timezone(config.global_config['timezone']),
                config_manager.get_timezone('UTC'),
                config.global_config
            )
        return _weather_manager_cache
    
    def get_calendar_service():
        global _calendar_service_cache
        if not _calendar_service_cache:
            _calendar_service_cache = CalendarService(
                config.global_config,
                get_weather_manager()
            )
        return _calendar_service_cache
    
    # Add service getters to app context
    app.get_weather_manager = get_weather_manager
    app.get_calendar_service = get_calendar_service
    
    return app 