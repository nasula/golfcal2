"""
Logging utilities for golf calendar application.
"""

import os
import json
import uuid
import logging
import traceback
from typing import Optional, Any, Dict
from pathlib import Path
from functools import wraps
from datetime import datetime

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

class EnhancedLoggerMixin:
    """Enhanced mixin class to add advanced logging capabilities to any class."""
    
    def __init__(self):
        """Initialize logger with correlation ID."""
        super().__init__()
        self._correlation_id = None
        self._log_context = {}
    
    @property
    def logger(self) -> logging.Logger:
        """Get a logger instance for this class."""
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        return self._logger
    
    def set_correlation_id(self, correlation_id: Optional[str] = None) -> None:
        """Set correlation ID for request tracking."""
        self._correlation_id = correlation_id or str(uuid.uuid4())
    
    def set_log_context(self, **kwargs) -> None:
        """Set additional context for logging."""
        self._log_context.update(kwargs)
    
    def clear_log_context(self) -> None:
        """Clear the logging context."""
        self._log_context.clear()
    
    def _format_log_message(self, message: str, **kwargs) -> tuple:
        """Format log message with context."""
        context = {
            'timestamp': datetime.utcnow().isoformat(),
            'correlation_id': self._correlation_id,
            **self._log_context,
            **kwargs
        }
        
        # Remove None values
        context = {k: v for k, v in context.items() if v is not None}
        
        if kwargs:
            try:
                # Try to format complex objects as JSON
                context_str = json.dumps(context, default=str)
                return f"{message} | Context: {context_str}", context
            except Exception:
                return message, context
        return message, context
    
    def debug(self, message: str, **kwargs) -> None:
        """Enhanced debug logging with context."""
        if self.logger.isEnabledFor(logging.DEBUG):
            msg, _ = self._format_log_message(message, **kwargs)
            self.logger.debug(msg)
    
    def info(self, message: str, **kwargs) -> None:
        """Enhanced info logging with context."""
        msg, _ = self._format_log_message(message, **kwargs)
        self.logger.info(msg)
    
    def warning(self, message: str, **kwargs) -> None:
        """Enhanced warning logging with context."""
        msg, _ = self._format_log_message(message, **kwargs)
        self.logger.warning(msg)
    
    def error(self, message: str, exc_info: Optional[Exception] = None, **kwargs) -> None:
        """Enhanced error logging with exception details."""
        if exc_info:
            kwargs['error_type'] = type(exc_info).__name__
            kwargs['error_message'] = str(exc_info)
            kwargs['stack_trace'] = traceback.format_exc()
        
        msg, _ = self._format_log_message(message, **kwargs)
        self.logger.error(msg, exc_info=bool(exc_info))
    
    def critical(self, message: str, exc_info: Optional[Exception] = None, **kwargs) -> None:
        """Enhanced critical logging with exception details."""
        if exc_info:
            kwargs['error_type'] = type(exc_info).__name__
            kwargs['error_message'] = str(exc_info)
            kwargs['stack_trace'] = traceback.format_exc()
        
        msg, _ = self._format_log_message(message, **kwargs)
        self.logger.critical(msg, exc_info=bool(exc_info))

def log_execution(level: str = 'DEBUG', include_args: bool = False):
    """Decorator to log function execution with timing."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not isinstance(self, EnhancedLoggerMixin):
                return func(self, *args, **kwargs)
            
            start_time = datetime.utcnow()
            log_level = getattr(logging, level.upper())
            
            # Log function entry
            log_context = {}
            if include_args:
                log_context.update({
                    'args': args,
                    'kwargs': {k: v for k, v in kwargs.items() if not k.startswith('_')}
                })
            
            try:
                result = func(self, *args, **kwargs)
                end_time = datetime.utcnow()
                duration_ms = (end_time - start_time).total_seconds() * 1000
                
                # Log successful execution
                getattr(self, level.lower())(
                    f"Completed {func.__name__}",
                    duration_ms=duration_ms,
                    status="success",
                    **log_context
                )
                return result
            
            except Exception as e:
                end_time = datetime.utcnow()
                duration_ms = (end_time - start_time).total_seconds() * 1000
                
                # Log error with full context
                self.error(
                    f"Failed {func.__name__}",
                    exc_info=e,
                    duration_ms=duration_ms,
                    status="error",
                    **log_context
                )
                raise
        
        return wrapper
    return decorator

# Legacy mixin for backward compatibility
class LoggerMixin(EnhancedLoggerMixin):
    """Legacy mixin class for backward compatibility."""
    pass