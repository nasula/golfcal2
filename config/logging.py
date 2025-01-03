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
                JsonFormatter(include_timestamp=service_config.file.include_timestamp),
                service_config.file.max_size_mb * 1024 * 1024,
                service_config.file.backup_count
            )
            
            # Add service-specific filters
            if service_config.sensitive_fields:
                file_handler.addFilter(SensitiveDataFilter(set(service_config.sensitive_fields)))
            if service_config.sampling and effective_level == logging.DEBUG:
                file_handler.addFilter(SamplingFilter(service_config.sampling.debug_rate))
            
            logger.addHandler(file_handler)
    
    return logger

def setup_logging(config: AppConfig, dev_mode: bool = False, verbose: bool = False) -> None:
    """Set up logging based on configuration and mode.
    
    Args:
        config: Application configuration
        dev_mode: Whether to run in development mode (shows INFO logs)
        verbose: Whether to enable verbose mode (shows DEBUG logs)
    """
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
    numeric_level = getattr(logging, level.upper(), logging.WARNING)

    # Register custom logger class
    logging.setLoggerClass(StructuredLogger)

    # Create formatters
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_formatter = JsonFormatter(include_timestamp=logging_config.file.include_timestamp)

    # Create handlers
    handlers: List[logging.Handler] = []
    
    # Create and configure console handler if enabled
    if logging_config.console.enabled:
        console_handler = get_console_handler(console_formatter)
        console_handler.setLevel(numeric_level)  # Set handler level explicitly
        # Add sensitive data filter to console handler
        if logging_config.sensitive_data.enabled:
            console_handler.addFilter(SensitiveDataFilter(set(logging_config.sensitive_data.global_fields)))
        handlers.append(console_handler)

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
        
        # Add sampling filter only for debug logs in verbose mode
        if numeric_level == logging.DEBUG and logging_config.sampling:
            file_handler.addFilter(SamplingFilter(logging_config.sampling.debug_rate))
        
        handlers.append(file_handler)

    # Add error aggregation handler if enabled
    if logging_config.error_aggregation.enabled:
        from golfcal2.config.logging_handlers import AggregatingErrorHandler
        error_handler = AggregatingErrorHandler()
        handlers.append(error_handler)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Add correlation ID filter if enabled
    if logging_config.correlation.enabled:
        root_logger.addFilter(CorrelationFilter())
    
    # Remove existing handlers and add new ones
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    for handler in handlers:
        root_logger.addHandler(handler)

    # Configure library logging
    if not dev_mode:
        for lib, level in logging_config.libraries.items():
            logging.getLogger(lib).setLevel(getattr(logging, level.upper())) 