"""Logging configuration utilities."""

import json
import logging
import logging.config
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from golfcal2.config.logging_config import LoggingConfig
from golfcal2.config.logging_filters import SensitiveDataFilter
from golfcal2.config.types import AppConfig


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
        extra_fields: dict[str, Any] | None = None,
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

    def debug_with_fields(self, msg: str, extra_fields: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> None:
        """Log debug message with extra fields."""
        self._log_with_fields(logging.DEBUG, msg, extra_fields, *args, **kwargs)

    def info_with_fields(self, msg: str, extra_fields: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> None:
        """Log info message with extra fields."""
        self._log_with_fields(logging.INFO, msg, extra_fields, *args, **kwargs)

    def warning_with_fields(self, msg: str, extra_fields: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> None:
        """Log warning message with extra fields."""
        self._log_with_fields(logging.WARNING, msg, extra_fields, *args, **kwargs)

    def error_with_fields(self, msg: str, extra_fields: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> None:
        """Log error message with extra fields."""
        self._log_with_fields(logging.ERROR, msg, extra_fields, *args, **kwargs)

    def critical_with_fields(self, msg: str, extra_fields: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> None:
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
    log_file: str | Path,
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
        
        # Add service-specific file handler if configured
        if service_config.file and service_config.file.enabled:
            file_handler = get_file_handler(
                service_config.file.path,
                JsonFormatter(include_timestamp=True),
                service_config.file.max_size_mb * 1024 * 1024,
                service_config.file.backup_count
            )
            # Service file handler always logs at DEBUG level for troubleshooting
            file_handler.setLevel(logging.DEBUG)
            
            # Add service-specific filters
            if service_config.sensitive_fields:
                file_handler.addFilter(SensitiveDataFilter(set(service_config.sensitive_fields)))
            
            logger.addHandler(file_handler)
    
    return logger

def init_error_aggregator(config: dict[str, Any] | None = None) -> None:
    """Initialize error aggregator with given configuration.
    
    Args:
        config: Error aggregation configuration
    """
    # Currently a placeholder - can be implemented later if error aggregation is needed
    pass

def setup_logging(config: AppConfig | None = None, dev_mode: bool = False, verbose: bool = False, log_file: str | None = None) -> None:
    """Set up logging configuration."""
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Create console handler with colored output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(ColoredFormatter())
    root_logger.addHandler(console_handler)
    
    # Try to set up journald logging, but don't fail if not available
    try:
        from golfcal2.config.logging_handlers import JournaldHandler
        journald_handler = JournaldHandler()
        journald_handler.setLevel(logging.INFO)
        root_logger.addHandler(journald_handler)
    except ImportError:
        root_logger.warning("systemd module not available, journald logging disabled")
    
    # Add file handler if log file is specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        root_logger.addHandler(file_handler)
    
    # Set up error aggregator
    init_error_aggregator() 