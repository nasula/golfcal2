"""Custom logging handlers."""

import logging
import traceback
from typing import Optional

from golfcal2.config.error_aggregator import aggregate_error

class AggregatingErrorHandler(logging.Handler):
    """Logging handler that aggregates errors."""
    
    def __init__(self):
        super().__init__()
        # Only handle ERROR and CRITICAL
        self.addFilter(lambda record: record.levelno >= logging.ERROR)
    
    def emit(self, record: logging.LogRecord) -> None:
        """Process log record.
        
        Args:
            record: Log record to process
        """
        try:
            # Extract service name from logger hierarchy
            service = record.name.split('.')[2] if len(record.name.split('.')) > 2 else 'unknown'
            
            # Get stack trace if available
            stack_trace: Optional[str] = None
            if record.exc_info:
                stack_trace = ''.join(traceback.format_exception(*record.exc_info))
            
            # Aggregate the error
            aggregate_error(record.getMessage(), service, stack_trace)
            
        except Exception:
            self.handleError(record) 