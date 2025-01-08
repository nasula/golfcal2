"""Application initialization."""

import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask
from flask_cors import CORS

from .config import Config
from .services.calendar_service import CalendarService
from .services.weather_service import WeatherManager
from .utils.logging_utils import setup_logging
from .config.error_aggregator import init_error_aggregator, ErrorAggregationConfig

def create_app(config_file=None, dev_mode=False, verbose=False):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)
    
    # Load configuration
    app.config.from_object(Config)
    if config_file:
        app.config.from_pyfile(config_file)
    
    # Set up logging with proper flags
    setup_logging(app.config, dev_mode=dev_mode, verbose=verbose)
    
    # Initialize error aggregator
    error_config = ErrorAggregationConfig(
        report_interval=app.config.get('ERROR_REPORT_INTERVAL', 3600),
        error_threshold=app.config.get('ERROR_THRESHOLD', 5)
    )
    init_error_aggregator(error_config)
    
    # Initialize timezone from config
    config = load_config()
    local_tz = ZoneInfo(config.global_config.get('timezone', 'UTC'))
    utc_tz = ZoneInfo('UTC')
    
    app.weather_manager = WeatherManager(local_tz, utc_tz, config)
    app.calendar_service = CalendarService(config, dev_mode)
    
    # Register routes
    from .routes import register_routes
    register_routes(app)
    
    return app 