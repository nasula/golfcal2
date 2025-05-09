"""Application initialization."""


from flask import Flask
from flask_cors import CORS

from .config import Config
from .config.settings import ConfigurationManager
from .services.calendar_service import CalendarService
from .services.weather_service import WeatherService
from .utils.logging_utils import setup_logging

# Global service cache
_weather_service_cache: WeatherService | None = None
_calendar_service_cache: CalendarService | None = None

def create_app(config_file: str | None = None, dev_mode: bool = False, verbose: bool = False) -> Flask:
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
    def get_weather_service() -> WeatherService:
        global _weather_service_cache
        if not _weather_service_cache:
            _weather_service_cache = WeatherService(
                config=config.global_config.__dict__ if hasattr(config.global_config, '__dict__') else dict(config.global_config)
            )
        return _weather_service_cache
    
    def get_calendar_service() -> CalendarService:
        global _calendar_service_cache
        if not _calendar_service_cache:
            _calendar_service_cache = CalendarService(
                config=config,
                weather_service=get_weather_service()
            )
        return _calendar_service_cache
    
    # Add service getters to app context
    app.get_weather_service = get_weather_service
    app.get_calendar_service = get_calendar_service
    
    return app 