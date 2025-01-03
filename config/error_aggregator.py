"""Error aggregation and reporting utilities."""

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import DefaultDict, Dict, List, Optional, Set

from golfcal2.config.logging_config import ErrorAggregationConfig

@dataclass
class ErrorGroup:
    """Group of similar errors."""
    message: str
    count: int = 0
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    services: Set[str] = field(default_factory=set)
    stack_traces: Set[str] = field(default_factory=set)
    
    def update(self, service: str, stack_trace: Optional[str] = None) -> None:
        """Update error group with new occurrence."""
        self.count += 1
        self.last_seen = datetime.now()
        self.services.add(service)
        if stack_trace:
            self.stack_traces.add(stack_trace)

class ErrorAggregator:
    """Aggregates and reports errors across services."""
    
    def __init__(self, config: ErrorAggregationConfig):
        """Initialize error aggregator.
        
        Args:
            config: Error aggregation configuration
        """
        self._errors: DefaultDict[str, ErrorGroup] = defaultdict(ErrorGroup)
        self._lock = threading.Lock()
        self._config = config
        self._last_report = datetime.now()
        
        # Start reporting thread if enabled
        self._stop_flag = threading.Event()
        if config.enabled:
            self._report_thread = threading.Thread(target=self._periodic_report)
            self._report_thread.daemon = True
            self._report_thread.start()
    
    def add_error(
        self,
        message: str,
        service: str,
        stack_trace: Optional[str] = None
    ) -> None:
        """Add error occurrence to aggregator.
        
        Args:
            message: Error message
            service: Service where error occurred
            stack_trace: Optional stack trace
        """
        if not self._config.enabled:
            return
            
        with self._lock:
            if message not in self._errors:
                self._errors[message] = ErrorGroup(message=message)
            self._errors[message].update(service, stack_trace)
            
            # Check if immediate report needed
            error_group = self._errors[message]
            if (
                error_group.count >= self._config.error_threshold or
                (datetime.now() - error_group.first_seen).seconds >= self._config.time_threshold
            ):
                self._report_error_group(message, error_group)
                del self._errors[message]
    
    def _report_error_group(self, message: str, group: ErrorGroup) -> None:
        """Report error group to logging system."""
        logger = logging.getLogger('error_aggregator')
        
        report = (
            f"Error Group Report:\n"
            f"Message: {message}\n"
            f"Count: {group.count}\n"
            f"First seen: {group.first_seen.isoformat()}\n"
            f"Last seen: {group.last_seen.isoformat()}\n"
            f"Services affected: {', '.join(sorted(group.services))}\n"
        )
        
        if group.stack_traces and 'stack_trace' in self._config.categorize_by:
            report += "\nUnique stack traces:\n"
            for trace in sorted(group.stack_traces):
                report += f"{trace}\n"
        
        logger.error(report)
    
    def _periodic_report(self) -> None:
        """Periodically report all accumulated errors."""
        while not self._stop_flag.is_set():
            time.sleep(1)  # Check every second
            
            now = datetime.now()
            if (now - self._last_report).seconds >= self._config.report_interval:
                with self._lock:
                    for message, group in self._errors.items():
                        self._report_error_group(message, group)
                    self._errors.clear()
                    self._last_report = now
    
    def shutdown(self) -> None:
        """Shutdown aggregator and report remaining errors."""
        if not self._config.enabled:
            return
            
        self._stop_flag.set()
        if hasattr(self, '_report_thread'):
            self._report_thread.join()
        
        # Report any remaining errors
        with self._lock:
            for message, group in self._errors.items():
                self._report_error_group(message, group)
            self._errors.clear()

# Global error aggregator instance
_error_aggregator: Optional[ErrorAggregator] = None

def init_error_aggregator(config: ErrorAggregationConfig) -> None:
    """Initialize global error aggregator with configuration.
    
    Args:
        config: Error aggregation configuration
    """
    global _error_aggregator
    _error_aggregator = ErrorAggregator(config)

def get_error_aggregator() -> ErrorAggregator:
    """Get global error aggregator instance.
    
    Returns:
        Global error aggregator instance
        
    Raises:
        RuntimeError: If error aggregator not initialized
    """
    if _error_aggregator is None:
        raise RuntimeError("Error aggregator not initialized. Call init_error_aggregator first.")
    return _error_aggregator

def aggregate_error(
    message: str,
    service: str,
    stack_trace: Optional[str] = None
) -> None:
    """Add error to global aggregator.
    
    Args:
        message: Error message
        service: Service where error occurred
        stack_trace: Optional stack trace
    """
    aggregator = get_error_aggregator()
    aggregator.add_error(message, service, stack_trace) 