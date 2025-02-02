"""
Reservation service for golf calendar application.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple, Set, NoReturn, cast, Protocol, runtime_checkable
from typing_extensions import Never
from zoneinfo import ZoneInfo
import requests
from icalendar import Event, Calendar, vText, vDatetime  # type: ignore
import yaml

from golfcal2.models.golf_club import GolfClubFactory, GolfClub, AppConfigProtocol as GolfClubConfigProtocol
from golfcal2.models.reservation import Reservation
from golfcal2.models.user import User, Membership
from golfcal2.utils.logging_utils import EnhancedLoggerMixin
from golfcal2.config.settings import AppConfig
from golfcal2.services.auth_service import AuthService
from golfcal2.models.mixins import ReservationHandlerMixin
from golfcal2.services.mixins import CalendarHandlerMixin
from golfcal2.exceptions import (
    APIError,
    APITimeoutError,
    APIRateLimitError,
    APIResponseError,
    ErrorCode,
    handle_errors
)
from golfcal2.config.error_aggregator import aggregate_error
from golfcal2.services.weather_service import WeatherService
from golfcal2.services.weather_formatter import WeatherFormatter
from golfcal2.services.reservation_factory import ReservationFactory, ReservationContext
from golfcal2.services.met_weather_strategy import MetWeatherStrategy
from golfcal2.services.open_meteo_strategy import OpenMeteoStrategy
from golfcal2.utils.api_handler import APIResponseValidator

# Lazy load weather service
_weather_service: Optional[WeatherService] = None

@runtime_checkable
class AppConfigProtocol(GolfClubConfigProtocol, Protocol):
    """Protocol for application configuration."""
    users: Dict[str, Any]
    clubs: Dict[str, Any]
    global_config: Dict[str, Any]
    api_keys: Dict[str, str]

def raise_error(msg: str = "") -> Never:
    """Helper function to raise an error and satisfy the Never type."""
    raise APIError(msg)

class ReservationService(EnhancedLoggerMixin, ReservationHandlerMixin, CalendarHandlerMixin):
    """Service for managing golf reservations."""
    
    def __init__(self, username: str, config: AppConfig):
        """Initialize service."""
        super().__init__()
        self.username = username
        self.config = config
        
        # Get user configuration
        if username not in config.users:
            raise APIError(f"User {username} not found in configuration")
        self.user_config = config.users[username]
        
        # Initialize timezone
        self.timezone = ZoneInfo(config.timezone)
        
        # Create user object
        self.user = User(
            name=username,
            email=self.user_config.get('email', ''),
            handicap=self.user_config.get('handicap', 0),
            memberships=[
                Membership(
                    club=membership['club'],
                    clubAbbreviation=membership.get('clubAbbreviation', membership['club']),
                    duration=membership.get('duration', {'hours': 4}),
                    auth_details=membership.get('auth_details', {})
                )
                for membership in self.user_config.get('memberships', [])
            ]
        )
        
        # Initialize services
        self.auth_service = AuthService(self.user_config.get('auth_details', {}))
        self.weather_service = WeatherService(
            config=config
        )
        
        # Set logging context
        self.set_log_context(user=username)
    
    def _init_weather_service(self) -> None:
        """Initialize weather service with strategies."""
        self.weather_service.register_strategy('met', MetWeatherStrategy)
        self.weather_service.register_strategy('openmeteo', OpenMeteoStrategy)
    
    def process_user(
        self,
        user_name: str,
        user_config: Dict[str, Any],
        past_days: int = 1
    ) -> List[Reservation]:
        """Process user's reservations."""
        try:
            # Create user object
            user = User(
                name=user_name,
                email=user_config.get('email', ''),
                handicap=user_config.get('handicap', 0),
                memberships=[
                    Membership(
                        club=membership['club'],
                        clubAbbreviation=membership.get('clubAbbreviation', membership['club']),
                        duration=membership.get('duration', {'hours': 4}),
                        auth_details=membership.get('auth_details', {})
                    )
                    for membership in user_config.get('memberships', [])
                ]
            )
            
            reservations: List[Reservation] = []
            # Use start of current day as cutoff
            now = datetime.now(ZoneInfo(self.config.get('timezone', 'UTC')))
            cutoff_time = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=past_days)
            
            # Process each membership
            for membership in user.memberships:
                try:
                    # Get club configuration
                    club_details = self.config.clubs[membership.club]
                    club = GolfClubFactory.create_club(
                        club_details,
                        membership,
                        self.auth_service,
                        self.config
                    )
                    if not club:
                        self.error(f"Failed to create club for {membership.club}")
                        continue
                    
                    # Create reservation context
                    context = ReservationContext(
                        club=club,
                        user=user,
                        membership=membership
                    )
                    
                    # Fetch and process reservations
                    raw_reservations = club.fetch_reservations(membership)
                    for raw_reservation in raw_reservations:
                        try:
                            # Create reservation using factory
                            reservation = ReservationFactory.create_reservation(
                                club_details['type'],
                                raw_reservation,
                                context
                            )
                            
                            # Skip if older than cutoff
                            if reservation.start_time < cutoff_time:
                                self.debug(f"Skipping old reservation: {reservation.start_time}")
                                continue
                            
                            # Add weather data if available
                            if reservation.start_time and club_details.get('coordinates'):
                                coords = club_details['coordinates']
                                weather_data = self.weather_service.get_weather(
                                    lat=coords['lat'],
                                    lon=coords['lon'],
                                    start_time=reservation.start_time,
                                    end_time=reservation.end_time
                                )
                                if weather_data:
                                    reservation.weather_summary = WeatherFormatter.format_forecast(
                                        weather_data,
                                        start_time=reservation.start_time,
                                        end_time=reservation.end_time
                                    )
                            
                            reservations.append(reservation)
                            
                        except Exception as e:
                            self.error(f"Failed to process reservation: {e}", exc_info=True)
                            aggregate_error(str(e), "reservation_service", str(e.__traceback__))
                            continue
                    
                except Exception as e:
                    self.error(f"Failed to process club {membership.club}: {e}", exc_info=True)
                    aggregate_error(str(e), "reservation_service", str(e.__traceback__))
                    continue
            
            return sorted(reservations, key=lambda r: r.start_time)
            
        except Exception as e:
            self.error(f"Failed to process user {user_name}: {e}", exc_info=True)
            aggregate_error(str(e), "reservation_service", str(e.__traceback__))
            return []
    
    def clear_weather_cache(self) -> None:
        """Clear weather cache."""
        self.weather_service.clear_cache()
    
    def list_weather_cache(self) -> List[Dict[str, Any]]:
        """List weather cache entries."""
        return self.weather_service.list_cache()

    def check_config(self) -> bool:
        """Check if the service configuration is valid.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            if not hasattr(self.config, 'users'):
                self.error("Config missing 'users' attribute")
                return False
                
            # Check if user exists in config
            if not self.username in self.config.users:
                self.error(f"User {self.username} not found in configuration")
                return False
                
            # Check if user has any memberships configured
            user_config = self.config.users[self.username]
            if not user_config.get('memberships'):
                self.error(f"No memberships configured for user {self.username}")
                return False
                
            # All checks passed
            self.info(f"Configuration valid for user {self.username}")
            return True
            
        except Exception as e:
            self.error(f"Error checking configuration: {str(e)}")
            return False

    def _make_api_request(self, method: str, url: str, headers: Optional[Dict[str, str]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make an API request with error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL to make request to
            headers: Request headers
            data: Request data
            
        Returns:
            Response data as dictionary
            
        Raises:
            APIError: If request fails
        """
        with handle_errors(
            APIError,
            "reservation",
            f"make {method} request to {url}",
            lambda: raise_error(f"Failed to {method} {url}")
        ):
            try:
                response = requests.request(method, url, headers=headers, json=data, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                raise APITimeoutError(
                    f"Request timed out: {method} {url}",
                    {"method": method, "url": url}
                )
            except requests.exceptions.TooManyRedirects:
                raise APIError(
                    f"Too many redirects: {method} {url}",
                    ErrorCode.REQUEST_FAILED,
                    {"method": method, "url": url}
                )
            except requests.exceptions.RequestException as e:
                raise APIResponseError(
                    f"Request failed: {str(e)}",
                    response=getattr(e, 'response', None)
                )

    def _add_reservation_to_calendar(self, reservation: Reservation, cal: Calendar) -> None:
        """Add a reservation to the calendar."""
        try:
            event = Event()
            
            # Add basic event details
            try:
                event.add('summary', reservation.title)
                event.add('dtstart', vDatetime(reservation.start_time))
                event.add('dtend', vDatetime(reservation.end_time))
                event.add('location', reservation.location or '')
            except Exception as e:
                self.error(f"Error setting basic event details: {e}")
                raise
            
            # Create unique event ID
            try:
                resource_id = '0'
                if isinstance(reservation.raw_data, dict):
                    if 'resourceId' in reservation.raw_data:
                        resource_id = str(reservation.raw_data.get('resourceId', '0'))
                    elif 'resources' in reservation.raw_data:
                        resources = reservation.raw_data.get('resources', [{}])
                        if resources and isinstance(resources[0], dict):
                            resource_id = str(resources[0].get('resourceId', '0'))
                    elif 'id' in reservation.raw_data:
                        resource_id = str(reservation.raw_data.get('id', '0'))
                
                club_abbr = getattr(reservation.membership, 'clubAbbreviation', 'GOLF')
                event_uid = f"{club_abbr}_{reservation.start_time.strftime('%Y%m%d%H%M')}_{resource_id}_{self.username}"
                event.add('uid', event_uid)
            except Exception as e:
                self.error(f"Error creating event UID: {e}")
                raise
            
            # Add description
            try:
                description = reservation.get_event_description()
                if reservation.weather_summary:
                    description += f"\n\nWeather: {reservation.weather_summary}"
                event.add('description', description)
            except Exception as e:
                self.error(f"Error setting description: {e}")
                event.add('description', "Golf Reservation")
            
            cal.add_component(event)
            
        except Exception as e:
            self.error(f"Error adding reservation to calendar: {e}")
            raise

    def list_reservations(
        self,
        active_only: bool = False,
        upcoming_only: bool = False,
        days: int = 1
    ) -> List[Reservation]:
        """
        List reservations with filters.
        
        Args:
            active_only: Only include active reservations
            upcoming_only: Only include upcoming reservations
            days: Number of days to look ahead/behind
            
        Returns:
            List of reservations
        """
        with handle_errors(
            APIError,
            "reservation",
            "list reservations",
            lambda: raise_error("Failed to list reservations")
        ):
            self.debug("=== Starting list_reservations ===")
            
            if self.username not in self.config.users:
                self.warning(f"User {self.username} not found in configuration")
                return []
            
            self.debug(f"Processing user {self.username}")
            user_config = self.config.users[self.username]
            self.debug("User config retrieved")
            
            try:
                self.debug("Calling process_user")
                reservations = self.process_user(self.username, user_config, days)
                self.debug(f"Got {len(reservations)} reservations from process_user")
                
                # Filter reservations based on flags
                now = datetime.now(self.timezone)
                if active_only:
                    reservations = [r for r in reservations if self._is_active(r, now)]
                if upcoming_only:
                    reservations = [r for r in reservations if self._is_upcoming(r, now, days)]
                
                self.debug(f"Found {len(reservations)} matching reservations")
                self.debug("=== Finished list_reservations ===")
                return sorted(reservations, key=lambda r: r.start_time)
                
            except Exception as e:
                self.error(f"Error in process_user: {e}")
                raise
    
    def check_overlaps(self) -> List[Tuple[Reservation, Reservation]]:
        """
        Check for overlapping reservations.
        
        Returns:
            List of overlapping reservation pairs
        """
        with handle_errors(
            APIError,
            "reservation",
            "check overlaps",
            lambda: raise_error("Failed to check overlaps")
        ):
            overlaps: List[Tuple[Reservation, Reservation]] = []
            all_reservations = self.list_reservations()
            
            # Group reservations by user
            user_reservations: Dict[str, List[Reservation]] = {}
            for reservation in all_reservations:
                user_name = reservation.user.name
                if user_name not in user_reservations:
                    user_reservations[user_name] = []
                user_reservations[user_name].append(reservation)
            
            # Check for overlaps within each user's reservations
            for user_name, reservations in user_reservations.items():
                for i, res1 in enumerate(reservations):
                    for res2 in reservations[i+1:]:
                        if self._reservations_overlap(res1, res2):
                            overlaps.append((res1, res2))
            
            return overlaps

    def _reservations_overlap(self, res1: Reservation, res2: Reservation) -> bool:
        """Check if two reservations overlap."""
        return (
            res1.start_time < res2.end_time and
            res2.start_time < res1.end_time
        )

    def _get_club_address(self, club_id: str) -> str:
        """
        Get club address from configuration.
        
        Args:
            club_id: Club ID
            
        Returns:
            Club address
        """
        if club_id in self.config.clubs:
            return self.config.clubs[club_id].get('address', '')
        return ''

    def _get_club_abbreviation(self, club_id: str) -> str:
        """
        Get club abbreviation from configuration.
        
        Args:
            club_id: Club ID
            
        Returns:
            Club abbreviation
        """
        if club_id in self.config.clubs:
            return self.config.clubs[club_id].get('abbreviation', '')
        return ''

    def list_courses(self, include_all: bool = False) -> List[str]:
        """
        List available golf courses.
        
        Args:
            include_all: If True, list all courses in config, otherwise only user's courses
            
        Returns:
            List of course names/IDs
        """
        with handle_errors(
            APIError,
            "reservation",
            "list courses",
            lambda: raise_error("Failed to list courses")
        ):
            if include_all:
                return sorted(self.config.clubs.keys())
            
            # Get user's memberships
            if self.username not in self.config.users:
                self.warning(f"User {self.username} not found in configuration")
                return []
                
            user_config = self.config.users[self.username]
            user = User.from_config(self.username, user_config)
            
            # Get unique clubs from user's memberships
            courses = {membership.club for membership in user.memberships}
            return sorted(courses)

    def cleanup_weather_cache(self) -> int:
        """Clean up expired weather cache entries."""
        return self.weather_service.cleanup_cache()

    def get_test_events(self, days: int = 1) -> List[Reservation]:
        """Get test events from test_events.yaml file.
        
        Args:
            days: Number of days to look ahead/behind
            
        Returns:
            List of test reservations
        """
        try:
            # Load test events from YAML file
            config_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            test_events_path = os.path.join(config_dir, 'config', 'test_events.yaml')
            
            if not os.path.exists(test_events_path):
                self.warning(f"Test events file not found: {test_events_path}")
                return []
            
            with open(test_events_path, 'r') as f:
                test_events = yaml.safe_load(f)
            
            if not test_events:
                return []
            
            # Convert test events to reservations
            reservations = []
            for event in test_events:
                # Skip if event is not for current user
                if self.username not in event.get('users', []):
                    continue
                
                try:
                    reservation = Reservation.from_external_event(event, self.user)
                    # Only include events within the specified time range
                    if reservation.start_time and reservation.end_time:
                        now = datetime.now(self.timezone)
                        cutoff = now - timedelta(days=days)
                        if reservation.start_time >= cutoff:
                            reservations.append(reservation)
                except Exception as e:
                    self.error(f"Failed to create test reservation: {e}")
                    continue
            
            return reservations
            
        except Exception as e:
            self.error(f"Failed to load test events: {e}")
            return []

    def _parse_dynamic_time(self, time_str: str, timezone: ZoneInfo) -> datetime:
        """Parse a dynamic time string like 'tomorrow 10:00' or '3 days 09:30'."""
        try:
            # Split into parts
            parts = time_str.split()
            
            # Get current date in the target timezone
            now = datetime.now(timezone)
            
            # Parse the time part (always the last part)
            time_part = parts[-1]
            hour, minute = map(int, time_part.split(':'))
            
            # Initialize result with today's date and the specified time
            result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Handle date part
            if len(parts) == 2:
                if parts[0] == 'tomorrow':
                    result += timedelta(days=1)
                elif parts[0] == 'today':
                    pass  # Already set to today
                elif parts[0].isdigit():
                    # Format: "N days"
                    days = int(parts[0])
                    result += timedelta(days=days)
                else:
                    raise ValueError(f"Invalid date format: {parts[0]}")
            elif len(parts) == 3:
                if parts[1] == 'days':
                    # Format: "N days HH:MM"
                    try:
                        days = int(parts[0])
                        result += timedelta(days=days)
                    except ValueError:
                        raise ValueError(f"Invalid number of days: {parts[0]}")
                else:
                    raise ValueError(f"Invalid format: expected 'days' but got '{parts[1]}'")
            else:
                raise ValueError(f"Invalid time format: {time_str}")
            
            return result
            
        except Exception as e:
            self.error(f"Failed to parse dynamic time '{time_str}': {e}", exc_info=True)
            raise ValueError(f"Invalid time format: {time_str}")

    