"""Configuration models for the application."""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from zoneinfo import ZoneInfo
import json

@dataclass
class UserConfig:
    """User configuration."""
    name: str
    duration: Dict[str, int]
    timezone: Optional[str] = None  # User-specific timezone override
    memberships: List[Dict[str, Any]] = None
    notifications: Dict[str, Any] = None

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "UserConfig":
        """Create UserConfig from dictionary."""
        return cls(
            name=name,
            duration=data.get("duration", {"hours": 3, "minutes": 0}),
            timezone=data.get("timezone"),  # Optional timezone override
            memberships=data.get("memberships", []),
            notifications=data.get("notifications", {})
        )

    def validate_timezone(self) -> None:
        """Validate timezone if specified."""
        if self.timezone:
            try:
                ZoneInfo(self.timezone)
            except Exception as e:
                raise ValueError(f"Invalid timezone {self.timezone}: {str(e)}")

@dataclass
class AppConfig:
    """Application configuration."""
    users: Dict[str, UserConfig]
    clubs: Dict[str, Dict[str, Any]]
    default_timezone: str = "Europe/Helsinki"  # Default application timezone
    ics_dir: str = "ics"
    log_level: str = "INFO"
    log_file: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create AppConfig from dictionary."""
        # Parse users
        users = {}
        for name, user_data in data.get("users", {}).items():
            users[name] = UserConfig.from_dict(name, user_data)

        # Create config
        config = cls(
            users=users,
            clubs=data.get("clubs", {}),
            default_timezone=data.get("timezone", "Europe/Helsinki"),
            ics_dir=data.get("ics_dir", "ics"),
            log_level=data.get("log_level", "INFO"),
            log_file=data.get("log_file")
        )

        # Validate configuration
        config.validate()
        return config

    def validate(self) -> None:
        """Validate configuration."""
        # Validate default timezone
        try:
            ZoneInfo(self.default_timezone)
        except Exception as e:
            raise ValueError(f"Invalid default timezone {self.default_timezone}: {str(e)}")

        # Validate user timezones
        for user in self.users.values():
            user.validate_timezone()

    @property
    def timezone(self) -> str:
        """Get application timezone."""
        return self.default_timezone

    def get_user_timezone(self, user_name: str) -> str:
        """Get timezone for user, falling back to default if not specified."""
        user = self.users.get(user_name)
        if user and user.timezone:
            return user.timezone
        return self.default_timezone