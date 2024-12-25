"""
Configuration utilities for golf calendar application.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

from golfcal.utils.logging_utils import get_logger

logger = get_logger(__name__)

def load_config() -> Dict[str, Any]:
    """
    Load configuration from JSON files.
    
    Returns:
        Dictionary containing configuration data
    """
    config_dir = os.getenv('GOLFCAL_CONFIG_DIR', 'config')
    logger.debug(f"Using config directory: {config_dir}")
    
    # Load clubs configuration
    clubs_file = Path(config_dir) / "clubs.json"
    try:
        with open(clubs_file, 'r') as f:
            clubs = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load clubs configuration: {e}")
        raise
    
    # Load users configuration
    users_file = Path(config_dir) / "users.json"
    try:
        with open(users_file, 'r') as f:
            users = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load users configuration: {e}")
        raise
    
    # Combine configurations
    config = {
        'clubs': clubs,
        'people': users
    }
    
    return config 