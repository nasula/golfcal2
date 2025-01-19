"""Timezone utilities for the application."""

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo, available_timezones
import pytz

class TimezoneManager:
    """Manages timezone operations throughout the application."""
    
    def __init__(self, local_timezone: str = "Europe/Helsinki"):
        """Initialize timezone manager.
        
        Args:
            local_timezone: The local timezone to use. Defaults to Europe/Helsinki.
            
        Raises:
            ValueError: If the timezone is invalid
        """
        self.set_timezone(local_timezone)
    
    def set_timezone(self, timezone: str) -> None:
        """Set the local timezone.
        
        Args:
            timezone: IANA timezone name
            
        Raises:
            ValueError: If the timezone is invalid
        """
        try:
            self.local_tz = ZoneInfo(timezone)
            self.utc_tz = ZoneInfo("UTC")
        except Exception as e:
            raise ValueError(f"Invalid timezone {timezone}: {str(e)}")
    
    def localize_datetime(self, dt: datetime) -> datetime:
        """Convert naive datetime to local timezone-aware datetime."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self.local_tz)
        return dt.astimezone(self.local_tz)
    
    def to_utc(self, dt: datetime) -> datetime:
        """Convert datetime to UTC."""
        if dt.tzinfo is None:
            dt = self.localize_datetime(dt)
        return dt.astimezone(self.utc_tz)
    
    def to_local(self, dt: datetime) -> datetime:
        """Convert datetime to local timezone."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.utc_tz)
        return dt.astimezone(self.local_tz)
    
    def now(self) -> datetime:
        """Get current time in local timezone."""
        return datetime.now(self.local_tz)
    
    def utc_now(self) -> datetime:
        """Get current time in UTC."""
        return datetime.now(self.utc_tz)
    
    @property
    def timezone_name(self) -> str:
        """Get the name of the local timezone."""
        return str(self.local_tz)
    
    @staticmethod
    def list_available_timezones() -> list[str]:
        """Get list of available IANA timezone names."""
        return sorted(available_timezones())
    
    @staticmethod
    def is_valid_timezone(timezone: str) -> bool:
        """Check if a timezone name is valid.
        
        Args:
            timezone: IANA timezone name to check
            
        Returns:
            True if timezone is valid, False otherwise
        """
        try:
            ZoneInfo(timezone)
            return True
        except Exception:
            return False 