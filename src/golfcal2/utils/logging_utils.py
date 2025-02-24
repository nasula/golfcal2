"""
Logging utilities for golf calendar application.
"""

import logging
import traceback
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from inspect import signature
from typing import Any
from typing import TypeVar

from typing_extensions import ParamSpec


T = TypeVar('T')
P = ParamSpec('P')

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)

def log_execution(level: str = 'DEBUG', include_args: bool = False) -> Callable[
    [Callable[P, T]], Callable[P, T]
]:
    """Decorator to log function execution with timing."""
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            logger = logging.getLogger(func.__module__)
            start_time = datetime.now()
            
            # Log function call
            if include_args:
                # Get function signature
                sig = signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                
                # Format arguments
                arg_str = ", ".join(f"{k}={v!r}" for k, v in bound_args.arguments.items())
                logger.log(getattr(logging, level), f"Calling {func.__name__}({arg_str})")
            else:
                logger.log(getattr(logging, level), f"Calling {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                duration = datetime.now() - start_time
                logger.log(getattr(logging, level), 
                    f"{func.__name__} completed in {duration.total_seconds():.3f}s")
                return result
            except Exception as e:
                duration = datetime.now() - start_time
                logger.error(
                    f"{func.__name__} failed after {duration.total_seconds():.3f}s: {e!s}",
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator

class EnhancedLoggerMixin:
    """Mixin class that provides enhanced logging capabilities."""
    
    def __init__(self) -> None:
        """Initialize logger."""
        # Create logger as instance variable
        self._logger = logging.getLogger(self.__class__.__module__)
        self._log_context: dict[str, Any] = {}
    
    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance."""
        return self._logger
    
    def set_log_context(self, **kwargs: Any) -> None:
        """Set context values for all subsequent log messages."""
        self._log_context.update(kwargs)
    
    def clear_log_context(self) -> None:
        """Clear all context values."""
        self._log_context.clear()
    
    def _format_message(self, msg: str, **kwargs: Any) -> str:
        """Format log message with context and additional kwargs."""
        context = {**self._log_context, **kwargs}
        if context:
            context_str = " | ".join(f"{k}={v}" for k, v in context.items())
            return f"{msg} | Context: {context_str}"
        return msg
    
    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log a debug message with context."""
        self.logger.debug(self._format_message(msg, **kwargs))
    
    def info(self, msg: str, **kwargs: Any) -> None:
        """Log an info message with context."""
        self.logger.info(self._format_message(msg, **kwargs))
    
    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log a warning message with context."""
        self.logger.warning(self._format_message(msg, **kwargs))
    
    def error(self, msg: str, exc_info: Any = None, **kwargs: Any) -> None:
        """Log an error message with context and optional exception info."""
        if exc_info:
            if isinstance(exc_info, bool):
                # If exc_info is True, get the current exception info
                import sys
                exc_type, exc_value, exc_traceback = sys.exc_info()
                if exc_traceback:
                    kwargs['traceback'] = "".join(traceback.format_tb(exc_traceback))
                if exc_value:
                    kwargs['error'] = str(exc_value)
            elif isinstance(exc_info, Exception):
                kwargs['error'] = str(exc_info)
                kwargs['traceback'] = "".join(traceback.format_tb(exc_info.__traceback__))
        self.logger.error(self._format_message(msg, **kwargs))
    
    def critical(self, msg: str, exc_info: Any = None, **kwargs: Any) -> None:
        """Log a critical message with context and optional exception info."""
        if exc_info:
            if isinstance(exc_info, bool):
                # If exc_info is True, get the current exception info
                import sys
                exc_type, exc_value, exc_traceback = sys.exc_info()
                if exc_traceback:
                    kwargs['traceback'] = "".join(traceback.format_tb(exc_traceback))
                if exc_value:
                    kwargs['error'] = str(exc_value)
            elif isinstance(exc_info, Exception):
                kwargs['error'] = str(exc_info)
                kwargs['traceback'] = "".join(traceback.format_tb(exc_info.__traceback__))
        self.logger.critical(self._format_message(msg, **kwargs))

# Legacy mixin for backward compatibility
class LoggerMixin(EnhancedLoggerMixin):
    """Legacy mixin class for backward compatibility."""
    pass