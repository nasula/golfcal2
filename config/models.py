"""Configuration models for golf calendar application."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator

class Coordinates(BaseModel):
    """Geographic coordinates."""
    
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)

class AuthDetails(BaseModel):
    """Authentication details for golf club APIs."""
    
    type: str = Field(..., pattern="^(wisegolf|wisegolf0|nexgolf|teetime)$")
    auth_type: str = Field(..., pattern="^(token_appauth|cookie|query)$")
    url: str
    token: Optional[str] = None
    cookie_value: Optional[str] = None
    appauth: Optional[str] = None
    cookie_name: Optional[str] = None
    
    @field_validator("type")
    def validate_type(cls, v: str) -> str:
        """Validate club type is supported."""
        valid_types = {"wisegolf", "wisegolf0", "nexgolf", "teetime"}
        if v not in valid_types:
            raise ValueError(f"Invalid club type: {v}. Must be one of {valid_types}")
        return v
    
    @field_validator("auth_type")
    def validate_auth_type(cls, v: str) -> str:
        """Validate auth type is supported."""
        valid_types = {"token_appauth", "cookie", "query"}
        if v not in valid_types:
            raise ValueError(f"Invalid auth type: {v}. Must be one of {valid_types}")
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert auth details to dictionary.
        
        Returns:
            Dictionary containing auth details
        """
        return {
            'type': self.type,
            'auth_type': self.auth_type,
            'url': self.url,
            'token': self.token,
            'cookie_value': self.cookie_value,
            'appauth': self.appauth,
            'cookie_name': self.cookie_name
        }

class ClubConfig(BaseModel):
    """Golf club configuration."""
    
    name: str
    type: str = Field(..., pattern="^(wisegolf|wisegolf0|nexgolf|teetime)$")
    url: str
    variant: Optional[str] = None
    product: Optional[str] = None
    address: str
    coordinates: Optional[Coordinates] = None
    auth_details: AuthDetails
    duration_minutes: int = 240
    
    @field_validator("type")
    def validate_type(cls, v: str) -> str:
        """Validate club type is supported."""
        valid_types = {"wisegolf", "wisegolf0", "nexgolf", "teetime"}
        if v not in valid_types:
            raise ValueError(f"Invalid club type: {v}. Must be one of {valid_types}")
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert club configuration to dictionary.
        
        Returns:
            Dictionary containing club configuration
        """
        return {
            'name': self.name,
            'type': self.type,
            'url': self.url,
            'variant': self.variant,
            'product': self.product,
            'address': self.address,
            'coordinates': self.coordinates.dict() if self.coordinates else None,
            'auth_details': self.auth_details.to_dict(),
            'duration_minutes': self.duration_minutes
        }

class Membership(BaseModel):
    """User's club membership details."""
    
    club_name: str
    auth_details: Dict[str, str]
    duration: Dict[str, int] = {"hours": 4}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert membership to dictionary.
        
        Returns:
            Dictionary containing membership details
        """
        return {
            'club': self.club_name,
            'auth_details': self.auth_details,
            'duration': self.duration
        }

class UserConfig(BaseModel):
    """User configuration."""
    
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    handicap: float = 54.0
    memberships: List[Membership]
    
    @field_validator("handicap")
    def validate_handicap(cls, v: float) -> float:
        """Validate handicap is within valid range."""
        if not 0 <= v <= 54:
            raise ValueError("Handicap must be between 0 and 54")
        return v

class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(..., pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    file: Optional[Path] = None
    max_bytes: int = Field(default=1024*1024, ge=0)  # 1MB
    backup_count: int = Field(default=3, ge=0)
    
    @field_validator("level")
    def validate_level(cls, v: str) -> str:
        """Validate logging level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v not in valid_levels:
            raise ValueError(f"Invalid logging level: {v}. Must be one of {valid_levels}")
        return v

class WeatherConfig(BaseModel):
    """Weather service configuration."""
    api_key: str
    base_url: str = "https://api.openweathermap.org/data/2.5"
    cache_duration: timedelta = timedelta(hours=1)
    api_rate_limit_calls: int = Field(default=10, ge=1)
    api_rate_limit_period: int = Field(default=60, ge=1)

class AppConfig(BaseModel):
    """Application configuration."""
    timezone: str
    ics_dir: Path
    users: List[UserConfig]
    clubs: Dict[str, ClubConfig]
    logging: LoggingConfig
    weather: WeatherConfig
    
    @field_validator("timezone")
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone is available."""
        try:
            ZoneInfo(v)
            return v
        except Exception as e:
            raise ValueError(f"Invalid timezone: {v}. {str(e)}")
            
    @field_validator("ics_dir")
    def validate_ics_dir(cls, v: Path) -> Path:
        """Create ICS directory if it doesn't exist."""
        v.mkdir(parents=True, exist_ok=True)
        return v