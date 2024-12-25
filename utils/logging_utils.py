"""
Logging utilities for golf calendar application.
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
    """A rotating file handler that automatically compresses rotated log files."""
    
    def rotation_filename(self, default_name: str) -> str:
        return default_name + ".gz"
    
    def rotate(self, source: str, dest: str) -> None:
        if os.path.exists(source):
            with open(source, 'rb') as f_in:
                with gzip.open(dest, 'wb') as f_out:
                    f_out.writelines(f_in)
            os.remove(source)

def setup_logging(level: str = 'WARNING', log_file: Optional[str] = None, dev_mode: bool = False, verbose: bool = False) -> None:
    """Setup application-wide logging configuration.
    
    Args:
        level: Default log level. Defaults to 'WARNING'.
        log_file: Optional path to a log file.
        dev_mode: If True, sets level to DEBUG
        verbose: If True and not dev_mode, sets level to INFO
    """
    # Determine effective log level
    if dev_mode:
        effective_level = 'DEBUG'
    elif verbose:
        effective_level = 'INFO'
    else:
        effective_level = level
    
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(effective_level)
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
        file_handler.setLevel(effective_level)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s,%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=effective_level,
        handlers=handlers,
        force=True  # Override any existing handlers
    )
    
    # Set specific log levels for different components
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('golfcal2').setLevel(effective_level)

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(name)

class LoggerMixin:
    """Mixin class to add logging capability to any class."""
    
    @property
    def logger(self) -> logging.Logger:
        """Get a logger instance for this class."""
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        return self._logger