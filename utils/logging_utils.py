"""
Logging utilities for golf calendar application.
"""

import os
import logging
from typing import Optional
from pathlib import Path

def setup_logging(
    level: str = 'INFO',
    log_file: Optional[str] = None,
    dev_mode: bool = False,
    verbose: bool = False,
    component_levels: Optional[dict] = None
) -> None:
    """Set up logging configuration.
    
    Args:
        level: Base logging level (default: INFO)
        log_file: Optional log file path
        dev_mode: Whether to run in development mode
        verbose: Whether to enable verbose logging
        component_levels: Optional dict of component-specific log levels
            Example: {
                'golfcal2.api': 'DEBUG',
                'golfcal2.api.nex_golf': 'DEBUG',
                'golfcal2.services.weather': 'DEBUG'
            }
    """
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if verbose else level)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_formatter = logging.Formatter('%(levelname)s - %(message)s')
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(simple_formatter)
    console_handler.setLevel(logging.DEBUG if verbose else level)
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(detailed_formatter)
        file_handler.setLevel(logging.DEBUG if verbose else level)
        root_logger.addHandler(file_handler)
    
    # Set component-specific levels
    if component_levels:
        for component, level in component_levels.items():
            logging.getLogger(component).setLevel(level)
    
    # Set default component levels for better debugging
    if verbose or dev_mode:
        # API logging
        logging.getLogger('golfcal2.api').setLevel(logging.DEBUG)
        logging.getLogger('golfcal2.api.wise_golf').setLevel(logging.DEBUG)
        logging.getLogger('golfcal2.api.nex_golf').setLevel(logging.DEBUG)
        logging.getLogger('golfcal2.api.teetime').setLevel(logging.DEBUG)
        
        # Service logging
        logging.getLogger('golfcal2.services.weather').setLevel(logging.DEBUG)
        logging.getLogger('golfcal2.services.reservation').setLevel(logging.DEBUG)
        logging.getLogger('golfcal2.services.calendar').setLevel(logging.DEBUG)
        
        # Model logging
        logging.getLogger('golfcal2.models').setLevel(logging.DEBUG)
    
    # Suppress some noisy loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """Get logger for module.
    
    Args:
        name: Module name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

class LoggerMixin:
    """Mixin class to add logging capability to any class."""
    
    @property
    def logger(self) -> logging.Logger:
        """Get a logger instance for this class."""
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        return self._logger