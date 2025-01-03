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

def create_app(config_file=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)
    
    # Load configuration
    app.config.from_object(Config)
    if config_file:
        app.config.from_pyfile(config_file)
    
    # Set up logging
    setup_logging(app.config.get('LOG_LEVEL', 'INFO'))
    
    # Initialize services
    local_tz = ZoneInfo('Europe/Helsinki')
    utc_tz = ZoneInfo('UTC')
    
    app.weather_manager = WeatherManager(local_tz, utc_tz)
    app.calendar_service = CalendarService(app.weather_manager, local_tz, utc_tz)
    
    # Register routes
    from .routes import register_routes
    register_routes(app)
    
    return app 