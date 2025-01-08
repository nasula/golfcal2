"""Tests for the rate limiter implementation."""

import time
import pytest
from golfcal2.utils.rate_limiter import RateLimiter


def test_rate_limiter_init():
    """Test RateLimiter initialization."""
    limiter = RateLimiter(max_calls=10, time_window=60)
    assert limiter.max_calls == 10
    assert limiter.time_window == 60
    assert len(limiter.calls) == 0


def test_add_call():
    """Test adding calls to the rate limiter."""
    limiter = RateLimiter(max_calls=2, time_window=1)
    
    # Add first call
    limiter.add_call()
    assert len(limiter.calls) == 1
    
    # Add second call
    limiter.add_call()
    assert len(limiter.calls) == 2


def test_get_sleep_time_under_limit():
    """Test sleep time when under the rate limit."""
    limiter = RateLimiter(max_calls=2, time_window=1)
    
    # No calls yet
    assert limiter.get_sleep_time() == 0
    
    # One call
    limiter.add_call()
    assert limiter.get_sleep_time() == 0


def test_get_sleep_time_at_limit():
    """Test sleep time when at the rate limit."""
    limiter = RateLimiter(max_calls=2, time_window=1)
    
    # Add calls up to limit
    limiter.add_call()
    limiter.add_call()
    
    # Should need to wait
    sleep_time = limiter.get_sleep_time()
    assert sleep_time > 0
    assert sleep_time <= 1  # Should not need to wait more than time_window


def test_window_expiry():
    """Test that calls expire after the time window."""
    limiter = RateLimiter(max_calls=2, time_window=0.1)  # 100ms window
    
    # Add calls
    limiter.add_call()
    limiter.add_call()
    
    # Wait for window to expire
    time.sleep(0.2)  # 200ms
    
    # Should be able to make new calls
    assert limiter.get_sleep_time() == 0
    assert len(limiter.calls) == 0  # Old calls should be cleared


def test_sliding_window():
    """Test the sliding window behavior."""
    limiter = RateLimiter(max_calls=2, time_window=0.2)  # 200ms window
    
    # Add first call
    limiter.add_call()
    time.sleep(0.1)  # 100ms
    
    # Add second call
    limiter.add_call()
    
    # Should need to wait ~100ms
    sleep_time = limiter.get_sleep_time()
    assert 0 < sleep_time <= 0.1


def test_high_volume():
    """Test rate limiter under high volume."""
    limiter = RateLimiter(max_calls=100, time_window=1)
    
    # Add many calls quickly
    for _ in range(50):
        limiter.add_call()
    
    # Should still be under limit
    assert limiter.get_sleep_time() == 0
    
    # Add more calls to reach limit
    for _ in range(50):
        limiter.add_call()
    
    # Should now need to wait
    assert limiter.get_sleep_time() > 0 