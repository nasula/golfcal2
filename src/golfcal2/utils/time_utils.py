"""Time-related utility functions."""

from datetime import datetime, timedelta


def round_to_hour(dt: datetime) -> datetime:
    """Round a datetime to the nearest hour.
    
    Args:
        dt: The datetime to round
        
    Returns:
        A new datetime rounded to the nearest hour
    """
    # Get the number of minutes past the hour
    minutes_past = dt.minute
    
    # If more than 30 minutes past, round up
    if minutes_past >= 30:
        return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    
    # Otherwise round down
    return dt.replace(minute=0, second=0, microsecond=0) 