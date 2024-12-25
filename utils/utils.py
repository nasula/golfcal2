# utils.py

import os
import logging
from datetime import datetime
from typing import List, Tuple, Dict, Any
from icalendar import Calendar
from config_data import club_coordinates, config, special_street_addresses
import requests

logger = logging.getLogger(__name__)

def filter_wisegolf_past_future_reservations(reservations: List[Dict[str, any]], now: datetime) -> Tuple[List[Dict[str, any]], List[Dict[str, any]]]:
    """
    Filter out past and future reservations based on the current time.
    Returns a tuple of (past_events, future_events).
    """
    reservations_with_datetime = [
        (reservation, datetime.strptime(reservation['dateTimeStart'], '%Y-%m-%d %H:%M:%S')) for reservation in reservations
    ]
    past_events = [reservation for reservation, start_datetime in reservations_with_datetime if start_datetime < now]
    future_events = [reservation for reservation, start_datetime in reservations_with_datetime if start_datetime >= now]
    return past_events, future_events

def write_calendar_file(cal: Calendar, person_name: str, config: Dict[str, Any]) -> None:
    """Write calendar to file."""
    try:
        # Create ics directory if it doesn't exist
        ics_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ics')
        os.makedirs(ics_dir, exist_ok=True)

        # Write calendar to file
        file_path = os.path.join(ics_dir, f"{person_name}.ics")
        with open(file_path, 'wb') as f:
            f.write(cal.to_ical())
        logger.info(f"Created calendar file for {person_name}: {file_path}")

    except Exception as e:
        logger.error(f"Failed to write calendar file for {person_name}: {e}")
        raise

def get_club_address(club_id: str) -> str:
    """Get the club address from configuration."""
    try:
        club_data = config.get('clubs', {}).get(club_id, {})
        if not club_data:
            logger.warning(f"No club data found for ID: {club_id}")
            return "Address not available"

        address = club_data.get('address', '')
        if not address:
            logger.warning(f"No address found for club ID: {club_id}")
            return "Address not available"

        return address

    except Exception as e:
        logger.error(f"Error getting club address: {e}")
        return "Address not available"

def get_club_abbreviation(club_id: str) -> str:
    """Get the club abbreviation from configuration."""
    try:
        if club_id in club_coordinates:
            return club_coordinates[club_id].get('abbreviation', club_id)
        return club_id
    except Exception as e:
        logger.error(f"Error getting club abbreviation: {e}")
        return club_id

def make_api_request(
    method: str, url: str, headers: Dict[str, str] = None, 
    data: Dict[str, any] = None, params: Dict[str, str] = None,
    timeout: Tuple[int, int] = (7, 20)
) -> Dict[str, any]:
    """
    Make an API request with error handling.
    """
    try:
        response = requests.request(method, url, headers=headers, json=data, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error for request to {url}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during API request to {url}: {e}")
    return {}

