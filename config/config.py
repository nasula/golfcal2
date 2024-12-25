from dataclasses import dataclass
from typing import Dict, Any, Optional
import json
from pathlib import Path

@dataclass
class GolfClubConfig:
    """Configuration for a golf club."""
    name: str
    type: str
    url: str
    variant: Optional[str] = None
    product: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GolfClubConfig':
        return cls(
            name=data['name'],
            type=data['type'],
            url=data['url'],
            variant=data.get('variant'),
            product=data.get('product')
        )

@dataclass
class UserConfig:
    """Configuration for a user."""
    name: str
    email: str
    phone: Optional[str] = None
    clubs: Optional[Dict[str, str]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserConfig':
        return cls(
            name=data['name'],
            email=data['email'],
            phone=data.get('phone'),
            clubs=data.get('clubs', {})
        )

@dataclass
class AppConfig:
    """Main application configuration."""
    clubs: Dict[str, GolfClubConfig]
    users: Dict[str, UserConfig]
    timezone: str
    ics_output_dir: Path
    log_level: str = "ERROR"
    request_timeout: int = 20
    retry_count: int = 3
    retry_delay: int = 5

    @classmethod
    def from_file(cls, config_path: str) -> 'AppConfig':
        """Load configuration from a JSON file."""
        with open(config_path, 'r') as f:
            data = json.load(f)

        return cls(
            clubs={
                name: GolfClubConfig.from_dict(club_data)
                for name, club_data in data['clubs'].items()
            },
            users={
                name: UserConfig.from_dict(user_data)
                for name, user_data in data['users'].items()
            },
            timezone=data['timezone'],
            ics_output_dir=Path(data['ics_output_dir']),
            log_level=data.get('log_level', "ERROR"),
            request_timeout=data.get('request_timeout', 20),
            retry_count=data.get('retry_count', 3),
            retry_delay=data.get('retry_delay', 5)
        )

    def validate(self) -> None:
        """Validate the configuration."""
        if not self.ics_output_dir.exists():
            raise ValueError(f"ICS output directory does not exist: {self.ics_output_dir}")

        for club in self.clubs.values():
            if club.type not in ['wisegolf0', 'nexgolf']:
                raise ValueError(f"Invalid club type for {club.name}: {club.type}")

        for user in self.users.values():
            if not user.email:
                raise ValueError(f"Email is required for user {user.name}")
            for club_name in (user.clubs or {}).keys():
                if club_name not in self.clubs:
                    raise ValueError(f"Unknown club {club_name} for user {user.name}")

    def get_club_config(self, club_name: str) -> GolfClubConfig:
        """Get configuration for a specific club."""
        if club_name not in self.clubs:
            raise ValueError(f"Unknown club: {club_name}")
        return self.clubs[club_name]

    def get_user_config(self, user_name: str) -> UserConfig:
        """Get configuration for a specific user."""
        if user_name not in self.users:
            raise ValueError(f"Unknown user: {user_name}")
        return self.users[user_name] 