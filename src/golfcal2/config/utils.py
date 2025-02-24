"""Configuration utility functions."""

import os
from copy import deepcopy
from pathlib import Path
from typing import Any
from typing import TypeVar


T = TypeVar('T', bound=dict[str, Any])

def deep_merge(base: T, override: T) -> T:
    """Deep merge two dictionaries.
    
    Args:
        base: Base dictionary
        override: Dictionary to override base values
        
    Returns:
        Merged dictionary
    """
    result = deepcopy(base)
    
    for key, value in override.items():
        if (
            key in result and
            isinstance(result[key], dict) and
            isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    
    return result

def resolve_path(
    path: str | Path,
    base_dir: str | Path | None = None,
    create: bool = False
) -> Path:
    """Resolve path relative to base directory.
    
    Args:
        path: Path to resolve
        base_dir: Base directory for relative paths
        create: Whether to create the directory
        
    Returns:
        Resolved Path object
    """
    if isinstance(path, str):
        path = Path(path)
    
    # Convert to absolute path if relative and base_dir provided
    if not path.is_absolute() and base_dir is not None:
        if isinstance(base_dir, str):
            base_dir = Path(base_dir)
        path = base_dir / path
    
    # Create directory if requested
    if create:
        path.mkdir(parents=True, exist_ok=True)
    
    return path

def validate_api_key(key: str | None, service: str) -> None:
    """Validate API key format.
    
    Args:
        key: API key to validate
        service: Service name for error messages
        
    Raises:
        ValueError: If key is invalid
    """
    if not key:
        return
    
    if service == 'aemet':
        if not key.strip():
            raise ValueError(f"Invalid {service} API key: empty key")
        if len(key) < 32:
            raise ValueError(f"Invalid {service} API key: too short")
    elif service == 'openweather':
        if not key.strip():
            raise ValueError(f"Invalid {service} API key: empty key")
        if len(key) != 32:
            raise ValueError(f"Invalid {service} API key: wrong length")
    else:
        raise ValueError(f"Unknown service: {service}")

def get_config_paths(config_dir: str | Path | None = None) -> dict[str, Path]:
    """Get configuration file paths.
    
    Args:
        config_dir: Base configuration directory
        
    Returns:
        Dictionary of configuration file paths
    """
    if config_dir is None:
        config_dir = os.getenv("GOLFCAL_CONFIG_DIR", os.path.dirname(os.path.abspath(__file__)))
    
    base_path = Path(config_dir)
    
    return {
        'config': base_path / 'config.yaml',
        'users': base_path / 'users.json',
        'clubs': base_path / 'clubs.json'
    } 