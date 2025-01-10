"""Pytest configuration and shared fixtures."""

import pytest
import tempfile
import os
from pathlib import Path

@pytest.fixture(scope="session")
def test_data_dir():
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)

@pytest.fixture(scope="session")
def test_config():
    """Test configuration data."""
    return {
        "weather": {
            "cache_dir": "test_cache",
            "cache_duration": 3600,  # 1 hour
            "api_key": "test_key"
        },
        "clubs": {
            "Test Club": {
                "type": "test_crm",
                "name": "Test Golf Club",
                "url": "http://localhost:8000",
                "coordinates": {
                    "lat": 60.2,
                    "lon": 24.9
                }
            }
        }
    }

@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch, test_data_dir):
    """Setup test environment variables and paths."""
    # Set up test environment
    monkeypatch.setenv("GOLFCAL_ENV", "test")
    monkeypatch.setenv("GOLFCAL_CONFIG_DIR", str(test_data_dir))
    
    # Create necessary directories
    cache_dir = test_data_dir / "cache"
    cache_dir.mkdir(exist_ok=True)
    
    yield
    
    # Cleanup (if needed)
    if cache_dir.exists():
        for file in cache_dir.glob("*"):
            file.unlink()
        cache_dir.rmdir() 