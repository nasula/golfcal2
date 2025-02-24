"""Metrics collection and reporting for golfcal2."""

import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Any


@dataclass
class TimerStats:
    """Statistics for timed operations."""
    count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    times: list[float] = field(default_factory=list)

    def add(self, duration: float) -> None:
        """Add a new duration measurement."""
        self.count += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.times.append(duration)
        
        # Keep only last 1000 measurements to avoid memory growth
        if len(self.times) > 1000:
            self.times = self.times[-1000:]

    def get_stats(self) -> dict[str, float]:
        """Get statistical summary."""
        if not self.times:
            return {
                "count": 0,
                "total": 0.0,
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "median": 0.0
            }
            
        return {
            "count": self.count,
            "total": self.total_time,
            "avg": self.total_time / self.count,
            "min": self.min_time,
            "max": self.max_time,
            "median": statistics.median(self.times)
        }

class Metrics:
    """Central metrics collection."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(Metrics, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not getattr(self, '_initialized', False):
            self._timers: dict[str, TimerStats] = defaultdict(TimerStats)
            self._counters: dict[str, int] = defaultdict(int)
            self._gauges: dict[str, float] = {}
            self._start_time = datetime.now()
            self._lock = threading.Lock()
            self._initialized = True
    
    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter.
        
        Args:
            name: Counter name
            value: Value to increment by
        """
        with self._lock:
            self._counters[name] += value
    
    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge value.
        
        Args:
            name: Gauge name
            value: Current value
        """
        with self._lock:
            self._gauges[name] = value
    
    def record_time(self, name: str, duration: float) -> None:
        """Record a timing measurement.
        
        Args:
            name: Timer name
            duration: Duration in seconds
        """
        with self._lock:
            self._timers[name].add(duration)
    
    def get_metrics(self) -> dict[str, Any]:
        """Get all metrics.
        
        Returns:
            Dictionary of all metrics
        """
        with self._lock:
            uptime = datetime.now() - self._start_time
            
            return {
                "uptime_seconds": uptime.total_seconds(),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "timers": {
                    name: stats.get_stats()
                    for name, stats in self._timers.items()
                }
            }

class Timer:
    """Context manager for timing operations."""
    
    def __init__(self, name: str):
        """Initialize timer.
        
        Args:
            name: Name of the operation being timed
        """
        self.name = name
        self.start_time: float | None = None
        self.metrics = Metrics()
    
    def __enter__(self) -> 'Timer':
        """Start timing."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop timing and record duration."""
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.metrics.record_time(self.name, duration)
            
def track_time(name: str):
    """Decorator for timing function calls.
    
    Args:
        name: Name of the operation being timed
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with Timer(name):
                return func(*args, **kwargs)
        return wrapper
    return decorator 