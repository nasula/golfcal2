"""Logging filters and utilities."""

import logging
import random
import time
import uuid
from contextvars import ContextVar
from functools import wraps
from typing import Any


# Context variable for correlation ID
correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')

class SamplingFilter(logging.Filter):
    """Filter to sample logs at a given rate."""

    def __init__(self, sample_rate: float = 0.1):
        """Initialize filter.
        
        Args:
            sample_rate: Fraction of logs to keep (0.0 to 1.0)
        """
        super().__init__()
        self.sample_rate = sample_rate

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record based on sampling rate."""
        return random.random() < self.sample_rate

class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive data in logs."""

    def __init__(self, sensitive_fields: set[str] | None = None):
        """Initialize filter.
        
        Args:
            sensitive_fields: Set of field names to mask
        """
        super().__init__()
        self.sensitive_fields = sensitive_fields or {
            'password', 'token', 'api_key', 'secret',
            'credit_card', 'ssn', 'auth', 'cookie'
        }

    def _mask_sensitive_data(self, obj: Any) -> Any:
        """Recursively mask sensitive data in object."""
        if isinstance(obj, dict):
            return {
                k: '***MASKED***' if k.lower() in self.sensitive_fields else self._mask_sensitive_data(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [self._mask_sensitive_data(item) for item in obj]
        return obj

    def filter(self, record: logging.LogRecord) -> bool:
        """Mask sensitive data in log record."""
        if hasattr(record, 'extra_fields'):
            record.extra_fields = self._mask_sensitive_data(record.extra_fields)
        return True

def with_correlation_id(func):
    """Decorator to add correlation ID to logs."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Generate new correlation ID if not present
        if not correlation_id.get():
            correlation_id.set(str(uuid.uuid4()))
        return func(*args, **kwargs)
    return wrapper

def log_performance(logger: logging.Logger, operation: str):
    """Decorator to log operation performance.
    
    Args:
        logger: Logger instance to use
        operation: Name of operation being timed
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = (time.perf_counter() - start_time) * 1000  # Convert to milliseconds
                logger.info_with_fields(
                    f"Completed {operation}",
                    {
                        'operation': operation,
                        'duration_ms': duration,
                        'status': 'success',
                        'correlation_id': correlation_id.get()
                    }
                )
                return result
            except Exception as e:
                duration = (time.perf_counter() - start_time) * 1000
                logger.error_with_fields(
                    f"Failed {operation}",
                    {
                        'operation': operation,
                        'duration_ms': duration,
                        'status': 'error',
                        'error_type': type(e).__name__,
                        'correlation_id': correlation_id.get()
                    },
                    exc_info=True
                )
                raise
        return wrapper
    return decorator

class CorrelationFilter(logging.Filter):
    """Filter to add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to log record."""
        if not hasattr(record, 'extra_fields'):
            record.extra_fields = {}
        record.extra_fields['correlation_id'] = correlation_id.get()
        return True 