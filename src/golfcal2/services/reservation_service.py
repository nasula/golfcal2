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
        """
        Process reservations for user.
        
        Args:
            user_name: Name of user
            user_config: User configuration
            past_days: Number of days to include past reservations
            
        Returns:
            Tuple of (calendar, list of reservations)
        """
        with handle_errors(
            APIError,
            "reservation",
            f"process user {user_name}",
            lambda: raise_error(f"Failed to process user {user_name}")
        ):
            self.debug(f"Processing reservations for user {user_name}")
            self.debug(f"User config: {user_config}")
            
            user = User.from_config(user_name, user_config)
            self.debug(f"Created user with {len(user.memberships)} memberships")
            all_reservations: List[Reservation] = []
            
            # Create calendar
            cal = self.build_base_calendar(user_name, self.timezone)
            
            # Calculate cutoff time (24 hours ago)
            now = datetime.now(self.timezone)
            cutoff_time = now - timedelta(hours=24)
            self.debug(f"Using cutoff time: {cutoff_time}")
            
            for membership in user.memberships:
                with handle_errors(
                    APIError,
                    "reservation",
                    f"process membership {membership.club} for user {user_name}",
                    lambda: raise_error(f"Failed to process membership {membership.club}")
                ):
                    self.debug(f"Processing membership {membership.club} for user {user_name}")
                    self.debug(f"Membership details: {membership.__dict__}")
                    
                    if membership.club not in self.config.clubs:
                        error = APIError(
                            f"Club {membership.club} not found in configuration",
                            ErrorCode.CONFIG_MISSING,
                            {"club": membership.club, "user": user_name}
                        )
                        aggregate_error(str(error), "reservation", None)
                        continue

                    club_details = self.config.clubs[membership.club]
                    self.debug(f"Club details from config: {club_details}")
                    
                    club = GolfClubFactory.create_club(club_details, membership, self.auth_service, self.config)
                    if not club:
                        error = APIError(
                            f"Unsupported club type: {club_details['type']}",
                            ErrorCode.CONFIG_INVALID,
                            {"club_type": club_details['type'], "club": membership.club}
                        )
                        aggregate_error(str(error), "reservation", None)
                        continue
                    
                    self.debug(f"Created club instance of type: {type(club).__name__}")
                    self.debug(f"Fetching reservations from {club.name}")
                    
                    raw_reservations = club.fetch_reservations(membership)  # type: ignore
                    self.debug(f"Found {len(raw_reservations)} raw reservations for {club.name}")
                    
                    for raw_reservation in raw_reservations:
                        with handle_errors(
                            APIError,
                            "reservation",
                            f"process reservation for {club.name}",
                            lambda: raise_error(f"Failed to process reservation for {club.name}")
                        ):
                            if club_details["type"] == "wisegolf":
                                self._process_wisegolf_reservation(
                                    raw_reservation, club, user, membership,
                                    cutoff_time, past_days, cal, all_reservations
                                )
                            elif club_details["type"] == "wisegolf0":
                                self._process_wisegolf0_reservation(
                                    raw_reservation, club, user, membership,
                                    cutoff_time, past_days, cal, all_reservations
                                )
                            elif club_details["type"] == "nexgolf":
                                self._process_nexgolf_reservation(
                                    raw_reservation, club, user, membership,
                                    cutoff_time, past_days, cal, all_reservations
                                )
                            elif club_details["type"] == "teetime":
                                self._process_teetime_reservation(
                                    raw_reservation, club, user, membership,
                                    cutoff_time, past_days, cal, all_reservations
                                )
                            else:
                                error = APIError(
                                    f"Unsupported club type: {club_details['type']}",
                                    ErrorCode.CONFIG_INVALID,
                                    {"club_type": club_details['type'], "club": club.name}
                                )
                                aggregate_error(str(error), "reservation", None)
                                continue
            
            # Sort reservations by start time
            all_reservations.sort(key=lambda r: r.start_time)
            self.debug(f"Returning {len(all_reservations)} reservations for user {user_name}")
            
            # Return both calendar and reservations
            return cal, all_reservations

    def _process_wisegolf_reservation(
        self,
        raw_reservation: Dict[str, Any],
        club: Any,
        user: User,
        membership: Membership,
        cutoff_time: datetime,
        past_days: int,
        cal: Calendar,
        all_reservations: List[Reservation]
    ) -> None:
        """Process a WiseGolf reservation."""
        self.debug(f"Processing WiseGolf reservation: {raw_reservation}")
        start_time = datetime.strptime(raw_reservation['dateTimeStart'], '%Y-%m-%d %H:%M:%S')
        start_time = start_time.replace(tzinfo=self.timezone)
        
        # Skip if older than cutoff
        if start_time < cutoff_time:
            self.debug(f"Skipping old WiseGolf reservation: {start_time}")
            return
        
        reservation = Reservation.from_wisegolf(raw_reservation, club, user, membership)
        if self._should_include_reservation(reservation, past_days, self.timezone):
            all_reservations.append(reservation)
            self._add_reservation_to_calendar(reservation, cal)

    def _process_wisegolf0_reservation(
        self,
        raw_reservation: Dict[str, Any],
        club: Any,
        user: User,
        membership: Membership,
        cutoff_time: datetime,
        past_days: int,
        cal: Calendar,
        all_reservations: List[Reservation]
    ) -> None:
        """Process a WiseGolf0 reservation."""
        self.debug(f"Processing WiseGolf0 reservation: {raw_reservation}")
        start_time = datetime.strptime(raw_reservation['dateTimeStart'], '%Y-%m-%d %H:%M:%S')
        start_time = start_time.replace(tzinfo=self.timezone)
        
        # Skip if older than cutoff
        if start_time < cutoff_time:
            self.debug(f"Skipping old WiseGolf0 reservation: {start_time}")
            return
        
        reservation = Reservation.from_wisegolf0(raw_reservation, club, user, membership)
        if self._should_include_reservation(reservation, past_days, self.timezone):
            all_reservations.append(reservation)
            self._add_reservation_to_calendar(reservation, cal)

    def _process_nexgolf_reservation(
        self,
        raw_reservation: Dict[str, Any],
        club: Any,
        user: User,
        membership: Membership,
        cutoff_time: datetime,
        past_days: int,
        cal: Calendar,
        all_reservations: List[Reservation]
    ) -> None:
        """Process a NexGolf reservation."""
     #   self.debug(f"Processing NexGolf reservation: {raw_reservation}")
        reservation = Reservation.from_nexgolf(raw_reservation, club, user, membership)
        
        # Skip if older than cutoff
        if reservation.start_time < cutoff_time:
            self.debug(f"Skipping old NexGolf reservation: {reservation.start_time}")
            return
        
        if self._should_include_reservation(reservation, past_days, self.timezone):
            all_reservations.append(reservation)
            self._add_reservation_to_calendar(reservation, cal)

    def _process_teetime_reservation(
        self,
        raw_reservation: Dict[str, Any],
        club: Any,
        user: User,
        membership: Membership,
        cutoff_time: datetime,
        past_days: int,
        cal: Calendar,
        all_reservations: List[Reservation]
    ) -> None:
        """Process a TeeTime reservation."""
        self.debug(f"Processing TeeTime reservation: {raw_reservation}")
        # Create reservation directly since from_teetime is not available
        reservation = Reservation(
            raw_data=raw_reservation,
            club=club,
            user=user,
            membership=membership,
            start_time=datetime.fromisoformat(raw_reservation['start_time']).replace(tzinfo=self.timezone),
            end_time=datetime.fromisoformat(raw_reservation['end_time']).replace(tzinfo=self.timezone),
            players=raw_reservation.get('players', [])  # Add players from raw data or empty list if not present
        )
        
        # Skip if older than cutoff
        if reservation.start_time < cutoff_time:
            self.debug(f"Skipping old TeeTime reservation: {reservation.start_time}")
            return
        
        if self._should_include_reservation(reservation, past_days, self.timezone):
            all_reservations.append(reservation)
            self._add_reservation_to_calendar(reservation, cal)

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
            all_reservations: List[Reservation] = []
            now = datetime.now(self.timezone)
            
            if self.username not in self.config.users:
                self.warning(f"User {self.username} not found in configuration")
                return []
            
            user_config = self.config.users[self.username]
            _, reservations = self.process_user(self.username, user_config, days)
            
            for reservation in reservations:
                if active_only and not self._is_active(reservation, now):
                    continue
                
                if upcoming_only and not self._is_upcoming(reservation, now, days):
                    continue
                
                all_reservations.append(reservation)
            
            return sorted(all_reservations, key=lambda r: r.start_time)
    
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

    def _add_reservation_to_calendar(self, reservation: Reservation, cal: Calendar) -> None:
        """Add a reservation to the calendar."""
        try:
            # Get club config
            club_config = self.config.clubs.get(reservation.membership.club, {})
            
            # Use event builder like external events do
            event = self.event_builder.build(reservation, club_config)
            if event:
                self._add_event_to_calendar(event, cal)
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Failed to add reservation to calendar: {e}")
            return

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

    