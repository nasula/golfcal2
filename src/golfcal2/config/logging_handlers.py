"""Custom logging handlers."""

import logging
import traceback
from typing import Any, Dict, Optional

from golfcal2.config.error_aggregator import aggregate_error
from systemd import journal

class JournaldHandler(logging.Handler):
    """Handler that writes log records to systemd journal."""
    
    def __init__(self, identifier: str = "golfcal2"):
        """Initialize the handler.
        
        Args:
            identifier: Application identifier for journald
        """
        super().__init__()
        self.identifier = identifier
        self.journal = journal.send
    
    def emit(self, record: logging.LogRecord) -> None:
        """Process a log record and send it to the journal.
        
        Args:
            record: Log record to process
        """
        try:
            msg = self.format(record)
            
            # Prepare metadata
            metadata = {
                'PRIORITY': self._map_level_to_priority(record.levelno),
                'SYSLOG_IDENTIFIER': self.identifier,
                'CODE_FILE': record.pathname,
                'CODE_LINE': record.lineno,
                'CODE_FUNC': record.funcName,
            }
            
            # Add exception info if available
            if record.exc_info:
                metadata['EXCEPTION_INFO'] = '\n'.join(traceback.format_exception(*record.exc_info))
            
            # Add structured logging fields if available
            if hasattr(record, 'fields'):
                for key, value in record.fields.items():
                    metadata[f'FIELD_{key.upper()}'] = str(value)
            
            # Send to journal
            self.journal(msg, **metadata)
            
        except Exception:
            self.handleError(record)
    
    @staticmethod
    def _map_level_to_priority(level: int) -> int:
        """Map Python logging levels to syslog priorities.
        
        Args:
            level: Python logging level
            
        Returns:
            Corresponding syslog priority
        """
        return {
            logging.DEBUG: 7,      # DEBUG
            logging.INFO: 6,       # INFO
            logging.WARNING: 4,    # WARNING
            logging.ERROR: 3,      # ERR
            logging.CRITICAL: 2,   # CRIT
        }.get(level, 6)  # Default to INFO

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