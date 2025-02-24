"""Rate limiter implementation for API calls."""

import time
from collections import deque


class RateLimiter:
    """Rate limiter for API calls.
    
    Implements a sliding window rate limiter that tracks API calls and ensures
    the number of calls doesn't exceed the specified limit within the time window.
    """
    
    def __init__(self, max_calls: int, time_window: int):
        """Initialize rate limiter.
        
        Args:
            max_calls: Maximum number of calls allowed in the time window
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: deque[float] = deque()
    
    def add_call(self) -> None:
        """Record a new API call."""
        now = time.time()
        self.calls.append(now)
        
        # Remove calls outside the time window
        while self.calls and now - self.calls[0] > self.time_window:
            self.calls.popleft()
    
    def get_sleep_time(self) -> float:
        """Get the time to sleep before next call is allowed.
        
        Returns:
            Number of seconds to sleep. 0 if call can be made immediately.
        """
        if not self.calls:
            return 0
            
        now = time.time()
        
        # Remove calls outside the time window
        while self.calls and now - self.calls[0] > self.time_window:
            self.calls.popleft()
        
        # If we haven't hit the limit, no need to wait
        if len(self.calls) < self.max_calls:
            return 0
        
        # Calculate time until oldest call expires
        return self.calls[0] + self.time_window - now 