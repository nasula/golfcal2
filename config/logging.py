"""Logging configuration utilities."""

import os
import sys
import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from golfcal2.config.types import AppConfig
from golfcal2.config.logging_filters import (
    SensitiveDataFilter, CorrelationFilter
)
from golfcal2.config.logging_config import (
    load_logging_config, LoggingConfig, ServiceConfig
)

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(self, include_timestamp: bool = True):
        """Initialize formatter.
        
        Args:
            include_timestamp: Whether to include timestamp in output
        """
        self.include_timestamp = include_timestamp
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON formatted string
        """
        # Check if message is already formatted by EnhancedLoggerMixin
        message = record.getMessage()
        if " | Context: " in message:
            # Message already has context, return as is
            return message
            
        # Base log data
        data = {
            'level': record.levelname,
            'logger': record.name,
            'message': message
        }

        # Add timestamp if requested
        if self.include_timestamp:
            data['timestamp'] = datetime.fromtimestamp(record.created).isoformat()

        # Add exception info if present
        if record.exc_info:
            data['exception'] = self.formatException(record.exc_info)

        # Add extra fields from record
        if hasattr(record, 'extra_fields'):
            data.update(record.extra_fields)

        return json.dumps(data)

class StructuredLogger(logging.Logger):
    """Logger with support for structured logging."""

    def _log_with_fields(
        self,
        level: int,
        msg: str,
        extra_fields: Optional[Dict[str, Any]] = None,
        *args: Any,
        **kwargs: Any
    ) -> None:
        """Log message with extra fields.
        
        Args:
            level: Log level
            msg: Log message
            extra_fields: Additional fields to include in log
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments
        """
        if extra_fields:
            kwargs.setdefault('extra', {})['extra_fields'] = extra_fields
        super().log(level, msg, *args, **kwargs)

    def debug_with_fields(self, msg: str, extra_fields: Optional[Dict[str, Any]] = None, *args: Any, **kwargs: Any) -> None:
        """Log debug message with extra fields."""
        self._log_with_fields(logging.DEBUG, msg, extra_fields, *args, **kwargs)

    def info_with_fields(self, msg: str, extra_fields: Optional[Dict[str, Any]] = None, *args: Any, **kwargs: Any) -> None:
        """Log info message with extra fields."""
        self._log_with_fields(logging.INFO, msg, extra_fields, *args, **kwargs)

    def warning_with_fields(self, msg: str, extra_fields: Optional[Dict[str, Any]] = None, *args: Any, **kwargs: Any) -> None:
        """Log warning message with extra fields."""
        self._log_with_fields(logging.WARNING, msg, extra_fields, *args, **kwargs)

    def error_with_fields(self, msg: str, extra_fields: Optional[Dict[str, Any]] = None, *args: Any, **kwargs: Any) -> None:
        """Log error message with extra fields."""
        self._log_with_fields(logging.ERROR, msg, extra_fields, *args, **kwargs)

    def critical_with_fields(self, msg: str, extra_fields: Optional[Dict[str, Any]] = None, *args: Any, **kwargs: Any) -> None:
        """Log critical message with extra fields."""
        self._log_with_fields(logging.CRITICAL, msg, extra_fields, *args, **kwargs)

class ColoredFormatter(logging.Formatter):
    """Formatter that adds color to console output."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with color.
        
        Args:
            record: Log record to format
            
        Returns:
            Colored string
        """
        # Get the color for this level
        color = self.COLORS.get(record.levelname, self.RESET)
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        
        # Format the message
        msg = record.getMessage()
        
        # Format context data more cleanly
        context = ""
        if hasattr(record, 'extra_fields'):
            # Format each field on its own line with proper indentation
            fields = []
            for key, value in record.extra_fields.items():
                fields.append(f"\n    {key}: {value}")
            if fields:
                context = " |" + "".join(fields)
        
        # Add exception info if present
        if record.exc_info:
            msg = f"{msg}\n{self.formatException(record.exc_info)}"
        
        # Combine all parts with color
        return f"{color}{timestamp} - {record.name} - {record.levelname} - {msg}{context}{self.RESET}"

def get_console_handler(formatter: logging.Formatter) -> logging.StreamHandler:
    """Create console handler.
    
    Args:
        formatter: Formatter to use
        
    Returns:
        Configured console handler
    """
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    return console_handler

def get_file_handler(
    log_file: Union[str, Path],
    formatter: logging.Formatter,
    max_bytes: int,
    backup_count: int
) -> logging.handlers.RotatingFileHandler:
    """Create rotating file handler.
    
    Args:
        log_file: Path to log file
        formatter: Formatter to use
        max_bytes: Maximum file size in bytes
        backup_count: Number of backup files to keep
        
    Returns:
        Configured file handler
    """
    # Create log directory if needed
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    # Create rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setFormatter(formatter)
    return file_handler

def get_service_logger(service_name: str, config: LoggingConfig, global_level: int) -> logging.Logger:
    """Get logger for specific service with appropriate configuration.
    
    Args:
        service_name: Name of the service
        config: Logging configuration
        global_level: Global logging level to respect
        
    Returns:
        Configured logger for service
    """
    logger = logging.getLogger(service_name)
    
    # Get service-specific config
    service_config = config.services.get(service_name)
    if service_config:
        # Set service level but don't go below global level
        service_level = getattr(logging, service_config.level.upper())
        effective_level = max(service_level, global_level)
        logger.setLevel(effective_level)
        
        # Only set propagate to False if we're adding our own handlers
        has_handlers = False
        
        # Add service-specific file handler if configured
        if service_config.file and service_config.file.enabled:
            file_handler = get_file_handler(
                service_config.file.path,
                JsonFormatter(include_timestamp=service_config.file.include_timestamp),
                service_config.file.max_size_mb * 1024 * 1024,
                service_config.file.backup_count
            )
            
            # Add service-specific filters
            if service_config.sensitive_fields:
                file_handler.addFilter(SensitiveDataFilter(set(service_config.sensitive_fields)))
            
            logger.addHandler(file_handler)
            has_handlers = True
        
        # Set propagate based on whether we added handlers
        logger.propagate = not has_handlers
    
    return logger

def setup_logging(config: AppConfig, dev_mode: bool = False, verbose: bool = False) -> None:
    """Set up logging based on configuration and mode.
    
    Args:
        config: Application configuration
        dev_mode: Whether to run in development mode (shows INFO logs)
        verbose: Whether to enable verbose mode (shows DEBUG logs)
    """
    # Debug existing handlers before setup
    root_logger = logging.getLogger()
    print("\nBefore setup - Root logger handlers:")
    for i, h in enumerate(root_logger.handlers, start=1):
        print(f"Handler #{i}: {h.__class__.__name__}, level={logging.getLevelName(h.level)}")
    
    weather_logger = logging.getLogger('weather_service')
    print("\nBefore setup - Weather service logger handlers:")
    for i, h in enumerate(weather_logger.handlers, start=1):
        print(f"Handler #{i}: {h.__class__.__name__}, level={logging.getLevelName(h.level)}")
    print("\n")

    # Load granular logging configuration
    logging_config = load_logging_config()
    
    # Initialize error aggregator
    from golfcal2.config.error_aggregator import init_error_aggregator
    init_error_aggregator(logging_config.error_aggregation)
    
    # Get log level based on mode
    if verbose:  # Explicit request for debug logs
        level = logging_config.verbose_level  # DEBUG
    elif dev_mode:  # Development mode shows INFO
        level = logging_config.dev_level      # INFO
    else:  # Production mode shows WARNING and above
        level = logging_config.default_level  # WARNING

    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.DEBUG)

    # Register custom logger class that inherits from EnhancedLoggerMixin
    from golfcal2.utils.logging_utils import EnhancedLoggerMixin
    
    class EnhancedLogger(logging.Logger, EnhancedLoggerMixin):
        def __init__(self, name, level=logging.NOTSET):
            logging.Logger.__init__(self, name, level)
            EnhancedLoggerMixin.__init__(self)
    
    logging.setLoggerClass(EnhancedLogger)

    # Configure root logger first
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)  # Set root logger level
    
    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Always use ColoredFormatter for console output in development
    console_formatter = ColoredFormatter()
    file_formatter = JsonFormatter(include_timestamp=logging_config.file.include_timestamp)

    # Create and configure console handler if enabled
    if logging_config.console.enabled:
        console_handler = get_console_handler(console_formatter)
        console_handler.setLevel(numeric_level)  # Set handler level explicitly
        # Add sensitive data filter to console handler
        if logging_config.sensitive_data.enabled:
            console_handler.addFilter(SensitiveDataFilter(set(logging_config.sensitive_data.global_fields)))
        root_logger.addHandler(console_handler)

    # Add global file handler if enabled
    if logging_config.file.enabled:
        file_handler = get_file_handler(
            logging_config.file.path,
            file_formatter,
            logging_config.file.max_size_mb * 1024 * 1024,
            logging_config.file.backup_count
        )
        file_handler.setLevel(numeric_level)  # Set handler level explicitly
        
        # Add filters to file handler
        if logging_config.sensitive_data.enabled:
            file_handler.addFilter(SensitiveDataFilter(set(logging_config.sensitive_data.global_fields)))
        
        root_logger.addHandler(file_handler)
    
    # Configure library loggers
    for lib, level in logging_config.libraries.items():
        logging.getLogger(lib).setLevel(getattr(logging, level.upper()))
        
    # Configure service loggers
    for service_name, service_config in logging_config.services.items():
        logger = logging.getLogger(service_name)
        
        # Debug - show handlers before configuration
        print(f"\nBefore configuring {service_name} handlers:")
        for i, h in enumerate(logger.handlers, start=1):
            print(f"Handler #{i}: {h.__class__.__name__}, level={logging.getLevelName(h.level)}")
        
        # In verbose mode, force DEBUG level regardless of config
        if verbose:
            logger.setLevel(logging.DEBUG)
            # Debug call to verify logger level
            if root_logger.isEnabledFor(logging.DEBUG):
                root_logger.debug("Set service logger level to DEBUG", extra={'service': service_name})
        else:
            logger.setLevel(getattr(logging, service_config.level.upper()))
            # Debug call to verify logger level
            if root_logger.isEnabledFor(logging.DEBUG):
                root_logger.debug(f"Set service logger level to {service_config.level}", extra={'service': service_name})
        
        # Ensure propagation to root logger is disabled
        logger.propagate = False
        
        # Add service-specific file handler if enabled
        if hasattr(service_config, 'file') and service_config.file.enabled:
            service_file_handler = get_file_handler(
                service_config.file.path,
                file_formatter,
                service_config.file.max_size_mb * 1024 * 1024,
                service_config.file.backup_count
            )
            
            # In verbose mode, force DEBUG level for handler
            if verbose:
                service_file_handler.setLevel(logging.DEBUG)
                # Debug call to verify handler level
                if root_logger.isEnabledFor(logging.DEBUG):
                    root_logger.debug("Set service file handler to DEBUG", extra={'service': service_name})
            else:
                service_file_handler.setLevel(getattr(logging, service_config.level.upper()))
                # Debug call to verify handler level
                if root_logger.isEnabledFor(logging.DEBUG):
                    root_logger.debug(f"Set service file handler to {service_config.level}", extra={'service': service_name})
            
            # Add filters
            if logging_config.sensitive_data.enabled:
                sensitive_fields = set(logging_config.sensitive_data.global_fields)
                if hasattr(service_config, 'sensitive_fields'):
                    sensitive_fields.update(service_config.sensitive_fields)
                service_file_handler.addFilter(SensitiveDataFilter(sensitive_fields))
            
            logger.addHandler(service_file_handler) 
        
        # Debug - show handlers after configuration
        print(f"\nAfter configuring {service_name} handlers:")
        for i, h in enumerate(logger.handlers, start=1):
            print(f"Handler #{i}: {h.__class__.__name__}, level={logging.getLevelName(h.level)}") 