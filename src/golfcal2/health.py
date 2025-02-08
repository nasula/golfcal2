"""Health check functionality for golfcal2."""

import os
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime
import logging

from golfcal2.config.settings import ConfigurationManager
from golfcal2.utils.logging_utils import get_logger

logger = get_logger(__name__)

def check_directory_access(path: Path) -> Tuple[bool, str]:
    """Check if directory exists and is accessible.
    
    Args:
        path: Directory path to check
        
    Returns:
        Tuple of (success, message)
    """
    try:
        if not path.exists():
            return False, f"Directory does not exist: {path}"
        
        # Check read access
        if not os.access(path, os.R_OK):
            return False, f"Directory not readable: {path}"
            
        # Check write access
        if not os.access(path, os.W_OK):
            return False, f"Directory not writable: {path}"
            
        return True, f"Directory accessible: {path}"
        
    except Exception as e:
        return False, f"Error checking directory {path}: {str(e)}"

def check_config_access() -> Tuple[bool, str]:
    """Check if configuration is accessible.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        config_manager = ConfigurationManager()
        config = config_manager.config
        return True, "Configuration accessible"
    except Exception as e:
        return False, f"Configuration error: {str(e)}"

def check_logging() -> Tuple[bool, str]:
    """Check if logging is working.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        test_logger = logging.getLogger("healthcheck")
        test_logger.debug("Health check test log message")
        return True, "Logging system operational"
    except Exception as e:
        return False, f"Logging error: {str(e)}"

def get_health_status() -> Dict[str, Any]:
    """Get complete health status of the application.
    
    Returns:
        Dictionary containing health status information
    """
    status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": [],
        "version": "0.1.0"  # TODO: Get from package metadata
    }
    
    # List of checks to perform
    checks: List[Tuple[str, Tuple[bool, str]]] = []
    
    # Check configuration
    checks.append(("config", check_config_access()))
    
    # Get required directories from config
    try:
        config = ConfigurationManager().config
        ics_dir = Path(config.ics_dir)
        log_dir = Path(config.global_config.get('directories', {}).get('logs', 'logs'))
        
        # Check directory access
        checks.append(("ics_directory", check_directory_access(ics_dir)))
        checks.append(("log_directory", check_directory_access(log_dir)))
        
    except Exception as e:
        checks.append(("config_dirs", (False, f"Error getting directories: {str(e)}")))
    
    # Check logging
    checks.append(("logging", check_logging()))
    
    # Process check results
    all_healthy = True
    for name, (success, message) in checks:
        status["checks"].append({
            "name": name,
            "status": "healthy" if success else "unhealthy",
            "message": message
        })
        if not success:
            all_healthy = False
    
    if not all_healthy:
        status["status"] = "unhealthy"
    
    return status 