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
    SamplingFilter, SensitiveDataFilter, CorrelationFilter
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
        # Base log data
        data = {
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage()
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

def setup_logging(config: AppConfig, dev_mode: bool = False, verbose: bool = False) -> None:
    """Set up logging based on configuration and mode.
    
    Args:
        config: Application configuration
        dev_mode: Whether to run in development mode
        verbose: Whether to enable verbose logging
    """
    # Get log level based on mode
    logging_config = config.global_config.get('logging', {})
    if dev_mode:
        level = logging_config.get('dev_level', 'DEBUG')
    elif verbose:
        level = logging_config.get('verbose_level', 'INFO')
    else:
        level = logging_config.get('default_level', 'WARNING')

    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.WARNING)

    # Register custom logger class
    logging.setLoggerClass(StructuredLogger)

    # Create formatters
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_formatter = JsonFormatter()

    # Create handlers
    handlers: List[logging.Handler] = []
    
    # Create and configure console handler
    console_handler = get_console_handler(console_formatter)
    # Add sensitive data filter to console handler
    console_handler.addFilter(SensitiveDataFilter())
    handlers.append(console_handler)

    # Add file handler if configured
    log_file = config.log_file or logging_config.get('file')
    if log_file:
        max_size = logging_config.get('max_size', 10) * 1024 * 1024  # Convert MB to bytes
        backup_count = logging_config.get('backup_count', 5)
        file_handler = get_file_handler(log_file, file_formatter, max_size, backup_count)
        
        # Add filters to file handler
        file_handler.addFilter(SensitiveDataFilter())
        # Only sample DEBUG logs
        if numeric_level == logging.DEBUG:
            sample_rate = logging_config.get('debug_sample_rate', 0.1)
            file_handler.addFilter(SamplingFilter(sample_rate))
        
        handlers.append(file_handler)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Add correlation ID filter to root logger
    root_logger.addFilter(CorrelationFilter())
    
    # Remove existing handlers and add new ones
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    for handler in handlers:
        root_logger.addHandler(handler)

    # Configure library logging
    if not dev_mode:
        # Suppress logs from libraries unless they're WARNING or higher
        for lib in ['urllib3', 'requests', 'icalendar']:
            logging.getLogger(lib).setLevel(logging.WARNING) 