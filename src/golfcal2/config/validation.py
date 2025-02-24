"""Configuration validation utilities."""

import os
from pathlib import Path
from typing import Any

from golfcal2.config.types import AppConfig


class ConfigValidationError(Exception):
    """Configuration validation error."""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}

def validate_directories(config: AppConfig) -> None:
    """Validate and create required directories."""
    workspace_dir = Path(config.config_dir).parent

    # Validate and create ICS directory
    if not os.path.isabs(config.ics_dir):
        config.ics_dir = str(workspace_dir / config.ics_dir)
    Path(config.ics_dir).mkdir(parents=True, exist_ok=True)

    # Validate and create config directory
    if not os.path.isabs(config.config_dir):
        config.config_dir = str(workspace_dir / config.config_dir)
    Path(config.config_dir).mkdir(parents=True, exist_ok=True)

    # Validate and create logs directory if log file is configured
    if config.log_file:
        log_dir = os.path.dirname(config.log_file)
        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)

def validate_user_config(user_name: str, user_config: dict[str, Any], clubs: dict[str, Any]) -> None:
    """Validate user configuration."""
    if not isinstance(user_config, dict):
        raise ConfigValidationError(
            f"Invalid user configuration for {user_name}",
            {"user": user_name, "config_type": type(user_config).__name__}
        )

    if "memberships" not in user_config:
        raise ConfigValidationError(
            f"No memberships found for user {user_name}",
            {"user": user_name}
        )

    for membership in user_config["memberships"]:
        # Validate club reference
        if "club" not in membership:
            raise ConfigValidationError(
                f"No club specified in membership for user {user_name}",
                {"user": user_name, "membership": membership}
            )

        if membership["club"] not in clubs:
            raise ConfigValidationError(
                f"Unknown club {membership['club']} in membership for user {user_name}",
                {"user": user_name, "club": membership["club"]}
            )

        # Validate required membership fields
        required_fields = ["duration", "auth_details"]
        missing_fields = [field for field in required_fields if field not in membership]
        if missing_fields:
            raise ConfigValidationError(
                f"Missing required fields in membership for user {user_name}",
                {
                    "user": user_name,
                    "club": membership["club"],
                    "missing_fields": missing_fields
                }
            )

def validate_club_config(club_name: str, club_config: dict[str, Any]) -> None:
    """Validate club configuration."""
    if not isinstance(club_config, dict):
        raise ConfigValidationError(
            f"Invalid club configuration for {club_name}",
            {"club": club_name, "config_type": type(club_config).__name__}
        )

    # Determine required fields based on club type
    club_type = club_config.get('type')
    if club_type == 'wisegolf0':
        required_fields = ["type", "clubId", "ajaxUrl", "restUrl", "auth_type", "crm"]
    elif club_type in ['wisegolf', 'teetime', 'nexgolf']:
        required_fields = ["type", "url", "auth_type", "crm"]
    else:
        required_fields = ["type", "auth_type"]

    # Check required fields
    missing_fields = [field for field in required_fields if field not in club_config]
    if missing_fields:
        raise ConfigValidationError(
            f"Missing required fields in club configuration for {club_name}",
            {
                "club": club_name,
                "type": club_type,
                "missing_fields": missing_fields
            }
        )

    # Validate coordinates if present
    if 'coordinates' in club_config:
        coords = club_config['coordinates']
        if not isinstance(coords, dict) or 'lat' not in coords or 'lon' not in coords:
            raise ConfigValidationError(
                f"Invalid coordinates format for {club_name}",
                {
                    "club": club_name,
                    "coordinates": coords
                }
            )

def validate_config(config: AppConfig) -> None:
    """
    Validate configuration.
    
    Args:
        config: AppConfig object to validate
        
    Raises:
        ConfigValidationError: If configuration is invalid
    """
    try:
        # Validate and create directories
        validate_directories(config)

        # Validate users configuration
        for user_name, user_config in config.users.items():
            validate_user_config(user_name, user_config, config.clubs)

        # Validate clubs configuration
        for club_name, club_config in config.clubs.items():
            validate_club_config(club_name, club_config)

    except ConfigValidationError:
        raise
    except Exception as e:
        raise ConfigValidationError(
            f"Unexpected error during configuration validation: {e!s}",
            {"error_type": type(e).__name__}
        ) from e 