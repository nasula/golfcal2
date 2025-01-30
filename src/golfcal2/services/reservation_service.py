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
from golfcal2.services.weather_service import WeatherManager
from golfcal2.services.weather_formatter import WeatherFormatter
from golfcal2.services.reservation_factory import ReservationFactory
from golfcal2.utils.api_handler import APIResponseValidator

# Lazy load weather service
_weather_manager: Optional[WeatherManager] = None

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
    """Service for handling reservations."""
    
    def __init__(self, username: str, config: AppConfig):
        """Initialize reservation service.
        
        Args:
            username: Name of the user to process
            config: Application configuration
        """
        # Initialize logger first
        EnhancedLoggerMixin.__init__(self)
        # Then initialize calendar handler with config
        CalendarHandlerMixin.__init__(self, config)
        
        # Validate config
        if not isinstance(config, AppConfig):
            raise ValueError("Config must be an instance of AppConfig")
        
        # Store username and config
        self.username = username
        self.config: AppConfigProtocol = config  # type: ignore
        self.dev_mode = config.global_config.get('dev_mode', False)
        
        # Get user configuration
        if not hasattr(config, 'users'):
            raise ValueError("Config missing 'users' attribute")
        
        self.user_config = self.config.users.get(username)
        if not self.user_config:
            raise ValueError(f"No configuration found for user {username}")
        
        # Initialize timezone settings
        if not hasattr(config, 'global_config'):
            raise ValueError("Config missing 'global_config' attribute")
            
        self.timezone = ZoneInfo(config.global_config.get('timezone', 'UTC'))
        self.utc_tz = ZoneInfo('UTC')
        
        # Initialize services
        self._weather_service = WeatherManager(self.timezone, self.utc_tz, dict(config.global_config))
        self.auth_service = AuthService(self.user_config.get('auth_details', {}))
        
        # Set logging context
        self.set_log_context(user=username)
        
        # Initialize event builder
        from golfcal2.services.calendar.builders.event_builder import ReservationEventBuilder
        self.event_builder = ReservationEventBuilder(self.weather_service, config)
    
    @property
    def weather_service(self) -> WeatherManager:
        """Get the weather service."""
        return self._weather_service

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

    def process_user(
        self,
        user_name: str,
        user_config: Dict[str, Any],
        past_days: int = 1
    ) -> Tuple[Calendar, List[Reservation]]:
        """Process a user's reservations."""
        try:
            self.debug(f"Processing reservations for user: {user_name}")
            
            # Create calendar
            cal = Calendar()
            all_reservations: List[Reservation] = []
            
            # Create user object
            user = User(
                name=user_name,
                email=user_config.get('email'),
                phone=user_config.get('phone'),
                memberships=[
                    Membership(
                        club=m['club'],
                        clubAbbreviation=self.config.clubs[m['club']].get('clubAbbreviation'),
                        duration=m.get('duration', self.config.global_config['default_durations']['regular']),
                        auth_details=m.get('auth_details', {})
                    )
                    for m in user_config.get('memberships', [])
                ]
            )
            
            # Calculate cutoff time
            cutoff_time = datetime.now(self.timezone) - timedelta(days=past_days)
            
            # Process each membership
            for membership in user.memberships:
                try:
                    self.debug(f"Processing club: {membership.club}")
                    
                    if membership.club not in self.config.clubs:
                        error = APIError(
                            f"Club {membership.club} not found in configuration",
                            ErrorCode.CONFIG_MISSING,
                            {"club": membership.club, "user": user_name}
                        )
                        aggregate_error(str(error), "reservation", None)
                        continue

                    club_details = self.config.clubs[membership.club]
                    club = GolfClubFactory.create_club(club_details, membership, self.auth_service, self.config)
                    if not club:
                        error = APIError(
                            f"Unsupported club type: {club_details['type']}",
                            ErrorCode.CONFIG_INVALID,
                            {"club_type": club_details['type'], "club": membership.club}
                        )
                        aggregate_error(str(error), "reservation", None)
                        continue
                    
                    raw_reservations = club.fetch_reservations(membership)
                    self.debug(f"Found {len(raw_reservations)} reservations for {club.name}")
                    
                    for raw_reservation in raw_reservations:
                        try:
                            processor = ReservationFactory.get_processor(club_details['type'])
                            reservation = processor.create_reservation(
                                raw_reservation,
                                user,
                                club,
                                membership
                            )
                            
                            # Add weather data if available
                            if reservation.start_time and reservation.location:
                                try:
                                    weather_data = self.weather_service.get_weather(
                                        start_time=reservation.start_time,
                                        end_time=reservation.end_time,
                                        lat=club_details.get('coordinates', {}).get('lat'),
                                        lon=club_details.get('coordinates', {}).get('lon')
                                    )
                                    if weather_data:
                                        reservation.weather_summary = WeatherFormatter.format_forecast(
                                            weather_data,
                                            start_time=reservation.start_time,
                                            end_time=reservation.end_time
                                        )
                                except Exception as e:
                                    self.error(f"Error getting weather data: {e}")
                            
                            # Add to calendar and list if within time range
                            if (
                                reservation.start_time
                                and reservation.start_time >= cutoff_time - timedelta(days=past_days)
                            ):
                                self._add_reservation_to_calendar(reservation, cal)
                                all_reservations.append(reservation)
                                
                        except Exception as e:
                            self.error(f"Error processing reservation: {str(e)}")
                            aggregate_error(str(e), "reservation", None)
                            continue
                            
                except Exception as e:
                    self.error(f"Error processing membership {membership.club}: {str(e)}")
                    aggregate_error(str(e), "reservation", None)
                    continue
            
            self.debug(f"Processed {len(all_reservations)} total reservations for {user_name}")
            return cal, all_reservations
            
        except APIError as e:
            self.error(f"API Error processing {user_name}: {str(e)}")
            aggregate_error(
                f"Reservation error for {user_name}",
                "reservation",
                str(e)
            )
            raise
        except Exception as e:
            self.error(f"Unexpected error processing {user_name}: {str(e)}")
            aggregate_error(
                f"Unexpected error for {user_name}",
                "reservation",
                str(e)
            )
            raise

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
            all_reservations: List[Reservation] = []
            now = datetime.now(self.timezone)
            
            if self.username not in self.config.users:
                self.warning(f"User {self.username} not found in configuration")
                return []
            
            self.debug(f"Processing user {self.username}")
            user_config = self.config.users[self.username]
            self.debug("User config retrieved")
            
            try:
                self.debug("Calling process_user")
                _, reservations = self.process_user(self.username, user_config, days)
                self.debug(f"Got {len(reservations)} reservations from process_user")
            except Exception as e:
                self.error(f"Error in process_user: {e}")
                raise
            
            for idx, reservation in enumerate(reservations):
                self.debug(f"Processing reservation {idx + 1}/{len(reservations)}")
                try:
                    if active_only:
                        self.debug("Checking if reservation is active")
                        if not self._is_active(reservation, now):
                            self.debug("Reservation is not active, skipping")
                            continue
                    
                    if upcoming_only:
                        self.debug("Checking if reservation is upcoming")
                        if not self._is_upcoming(reservation, now, days):
                            self.debug("Reservation is not upcoming, skipping")
                            continue
                    
                    self.debug("Adding reservation to list")
                    all_reservations.append(reservation)
                except Exception as e:
                    self.error(f"Error processing reservation {idx + 1}: {e}")
                    self.error(f"Reservation data: {reservation.__dict__}")
                    raise
            
            self.debug(f"Found {len(all_reservations)} matching reservations")
            sorted_reservations = sorted(all_reservations, key=lambda r: r.start_time)
            self.debug("=== Finished list_reservations ===")
            return sorted_reservations
    
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

    def clear_weather_cache(self) -> None:
        """Clear all cached weather responses."""
        self.weather_service.clear_cache()
    
    def list_weather_cache(self) -> List[Dict[str, Any]]:
        """List all cached weather responses."""
        return self.weather_service.list_cache()
    
    def cleanup_weather_cache(self) -> int:
        """Clean up expired weather cache entries."""
        return self.weather_service.cleanup_cache()

    