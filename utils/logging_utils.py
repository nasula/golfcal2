"""
Logging utilities for golf calendar application.

This module provides utilities for setting up and managing logging across the application.
It includes:
- Centralized logging configuration with console and file output
- Automatic log rotation with compression for file logs
- Component-specific log level management
- A mixin class for adding logging capabilities to other classes
"""

import gzip
import logging
import logging.handlers
import os
from typing import Optional

# Constants for log rotation
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5  # Keep 5 backup files

class CompressedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """A rotating file handler that automatically compresses rotated log files.
    
    This handler extends RotatingFileHandler to automatically compress rotated log files
    using gzip compression. When a log file reaches its size limit:
    1. The current file is closed
    2. The file is compressed using gzip
    3. The compressed file is renamed with a .gz extension
    4. The original file is removed
    5. A new log file is started
    
    The handler maintains a fixed number of backup files (BACKUP_COUNT), and old
    backups are automatically removed when this limit is reached.
    """
    
    def rotation_filename(self, default_name: str) -> str:
        """Get the filename for a rotated log file.
        
        Args:
            default_name: The default filename that would be used by RotatingFileHandler
            
        Returns:
            The filename with .gz extension appended
        """
        return default_name + ".gz"
    
    def rotate(self, source: str, dest: str) -> None:
        """Rotate the current log file by compressing it.
        
        Args:
            source: Path to the current log file
            dest: Path where the compressed file should be saved
            
        The source file is compressed using gzip and saved to the destination path,
        then the original source file is removed.
        """
        if os.path.exists(source):
            with open(source, 'rb') as f_in:
                with gzip.open(dest, 'wb') as f_out:
                    f_out.writelines(f_in)
            os.remove(source)

def setup_logging(level: str = 'INFO', log_file: Optional[str] = None) -> None:
    """Setup application-wide logging configuration.
    
    This function configures logging for the entire application, setting up both
    console and file-based logging with appropriate formatting and log levels.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) for the root logger
              and handlers. Defaults to 'INFO'.
        log_file: Optional path to a log file. If provided, logs will be written to
                 this file in addition to console output. The file will be automatically
                 rotated when it reaches 10MB, keeping 5 compressed backup files (.gz).
                 
    The function:
    1. Sets up console logging with timestamp, logger name, and log level
    2. If a log file is specified, sets up compressed rotating file logging
    3. Configures specific log levels for different application components
    4. Forces override of any existing logging configuration
    
    Component-specific log levels:
    - urllib3: WARNING (reduce noise from HTTP client)
    - golfcal.models: INFO
    - golfcal.api: INFO
    - golfcal.services.weather_service: DEBUG (detailed weather service logs)
    - golfcal.services.reservation_service: INFO
    - golfcal.services.calendar_service: INFO
    """
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    handlers.append(console_handler)
    
    # File handler if log file specified
    if log_file:
        file_handler = CompressedRotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True  # Override any existing handlers
    )
    
    # Set specific log levels for different components
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('golfcal.models').setLevel(logging.INFO)
    logging.getLogger('golfcal.api').setLevel(logging.INFO)
    logging.getLogger('golfcal.services.weather_service').setLevel(logging.DEBUG)  # Keep weather service detailed
    logging.getLogger('golfcal.services.reservation_service').setLevel(logging.INFO)
    logging.getLogger('golfcal.services.calendar_service').setLevel(logging.INFO)

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name.
    
    Args:
        name: The name for the logger, typically __name__ for the current module
        
    Returns:
        A Logger instance configured according to the application's logging setup
        
    This is a convenience function that should be used to get logger instances
    throughout the application to ensure consistent logging behavior.
    """
    return logging.getLogger(name)

class LoggerMixin:
    """Mixin class to add logging capability to any class.
    
    This mixin adds a 'logger' property to the class that provides a properly
    configured logger instance. The logger name is automatically set based on
    the class's module and name.
    
    Example:
        class MyClass(LoggerMixin):
            def my_method(self):
                self.logger.debug("Debug message")
                self.logger.info("Info message")
    
    The logger is lazily instantiated when first accessed and cached for
    subsequent uses. Each instance gets its own logger with appropriate
    naming based on the class hierarchy.
    """
    
    @property
    def logger(self) -> logging.Logger:
        """Get a logger instance for this class.
        
        Returns:
            A Logger instance configured with the class's module and name
            
        The logger is created on first access and cached. It includes a console
        handler with DEBUG level and uses the standard application log format.
        """
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
            self._logger.setLevel(logging.DEBUG)
            
            if not self._logger.handlers:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.DEBUG)
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                console_handler.setFormatter(formatter)
                self._logger.addHandler(console_handler)
        
        return self._logger