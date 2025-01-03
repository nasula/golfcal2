"""
Reservation service for golf calendar application.
"""

import os
import pytz
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
from zoneinfo import ZoneInfo
import requests
from icalendar import Event, Calendar

from golfcal2.models.golf_club import GolfClubFactory
from golfcal2.models.reservation import Reservation
from golfcal2.models.user import User, Membership
from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.config.settings import AppConfig
from golfcal2.services.auth_service import AuthService
from golfcal2.services.weather_service import WeatherManager
from golfcal2.models.mixins import ReservationHandlerMixin, CalendarHandlerMixin
from golfcal2.exceptions import (
    APIError,
    APITimeoutError,
    APIRateLimitError,
    APIResponseError,
    ErrorCode,
    handle_errors
)
from golfcal2.config.error_aggregator import aggregate_error

class ReservationService(LoggerMixin, ReservationHandlerMixin, CalendarHandlerMixin):
    """Service for handling reservations."""
    
    def __init__(self, config: AppConfig, user_name: str):
        """Initialize service."""
        super().__init__()
        self.config = config
        self.user_name = user_name
        
        with handle_errors(APIError, "reservation", "initialize services"):
            # Initialize timezone settings
            self.utc_tz = pytz.UTC
            self.local_tz = pytz.timezone('Europe/Helsinki')  # Finland timezone
            
            # Initialize services
            self.auth_service = AuthService()
            self.weather_service = WeatherManager(self.local_tz, self.utc_tz)
    
    def _make_api_request(self, method: str, url: str, headers: Dict[str, str] = None, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make an API request with error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL to make request to
            headers: Request headers
            data: Request data
            
        Returns:
            Response data as dictionary
        """
        with handle_errors(APIError, "reservation", f"make {method} request to {url}"):
            try:
                response = requests.request(method, url, headers=headers, json=data, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                error = APITimeoutError(
                    f"Request timed out: {method} {url}",
                    {"method": method, "url": url}
                )
                aggregate_error(str(error), "reservation", error.__traceback__)
                raise error
            except requests.exceptions.TooManyRedirects:
                error = APIError(
                    f"Too many redirects: {method} {url}",
                    ErrorCode.REQUEST_FAILED,
                    {"method": method, "url": url}
                )
                aggregate_error(str(error), "reservation", error.__traceback__)
                raise error
            except requests.exceptions.RequestException as e:
                error = APIResponseError(
                    f"Request failed: {str(e)}",
                    response=getattr(e, 'response', None)
                )
                aggregate_error(str(error), "reservation", e.__traceback__)
                raise error

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
            lambda: (Calendar(), [])  # Fallback to empty calendar and reservations
        ):
            self.logger.debug(f"Processing reservations for user {user_name}")
            self.logger.debug(f"User config: {user_config}")
            
            user = User.from_config(user_name, user_config)
            self.logger.debug(f"Created user with {len(user.memberships)} memberships")
            all_reservations = []
            
            # Create calendar
            cal = self.build_base_calendar(user_name, self.local_tz)
            
            # Calculate cutoff time (24 hours ago)
            now = datetime.now(self.local_tz)
            cutoff_time = now - timedelta(hours=24)
            self.logger.debug(f"Using cutoff time: {cutoff_time}")
            
            for membership in user.memberships:
                with handle_errors(
                    APIError,
                    "reservation",
                    f"process membership {membership.club} for user {user_name}",
                    lambda: None
                ):
                    self.logger.debug(f"Processing membership {membership.club} for user {user_name}")
                    self.logger.debug(f"Membership details: {membership.__dict__}")
                    
                    if membership.club not in self.config.clubs:
                        error = APIError(
                            f"Club {membership.club} not found in configuration",
                            ErrorCode.CONFIG_MISSING,
                            {"club": membership.club, "user": user_name}
                        )
                        aggregate_error(str(error), "reservation", None)
                        continue

                    club_details = self.config.clubs[membership.club]
                    self.logger.debug(f"Club details from config: {club_details}")
                    
                    club = GolfClubFactory.create_club(club_details, membership, self.auth_service)
                    if not club:
                        error = APIError(
                            f"Unsupported club type: {club_details['type']}",
                            ErrorCode.CONFIG_INVALID,
                            {"club_type": club_details['type'], "club": membership.club}
                        )
                        aggregate_error(str(error), "reservation", None)
                        continue
                    
                    self.logger.debug(f"Created club instance of type: {type(club).__name__}")
                    self.logger.debug(f"Fetching reservations from {club.name}")
                    
                    raw_reservations = club.fetch_reservations(membership)
                    self.logger.debug(f"Found {len(raw_reservations)} raw reservations for {club.name}")
                    
                    for raw_reservation in raw_reservations:
                        with handle_errors(
                            APIError,
                            "reservation",
                            f"process reservation for {club.name}",
                            lambda: None
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
            self.logger.debug(f"Returning {len(all_reservations)} reservations for user {user_name}")
            
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
        self.logger.debug(f"Processing WiseGolf reservation: {raw_reservation}")
        start_time = datetime.strptime(raw_reservation['dateTimeStart'], '%Y-%m-%d %H:%M:%S')
        start_time = start_time.replace(tzinfo=self.local_tz)
        
        # Skip if older than cutoff
        if start_time < cutoff_time:
            self.logger.debug(f"Skipping old WiseGolf reservation: {start_time}")
            return
        
        reservation = Reservation.from_wisegolf(raw_reservation, club, user, membership)
        if self._should_include_reservation(reservation, past_days, self.local_tz):
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
        self.logger.debug(f"Processing WiseGolf0 reservation: {raw_reservation}")
        start_time = datetime.strptime(raw_reservation['dateTimeStart'], '%Y-%m-%d %H:%M:%S')
        start_time = start_time.replace(tzinfo=self.local_tz)
        
        # Skip if older than cutoff
        if start_time < cutoff_time:
            self.logger.debug(f"Skipping old WiseGolf0 reservation: {start_time}")
            return
        
        reservation = Reservation.from_wisegolf0(raw_reservation, club, user, membership)
        if self._should_include_reservation(reservation, past_days, self.local_tz):
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
        self.logger.debug(f"Processing NexGolf reservation: {raw_reservation}")
        reservation = Reservation.from_nexgolf(raw_reservation, club, user, membership)
        
        # Skip if older than cutoff
        if reservation.start_time < cutoff_time:
            self.logger.debug(f"Skipping old NexGolf reservation: {reservation.start_time}")
            return
        
        if self._should_include_reservation(reservation, past_days, self.local_tz):
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
        self.logger.debug(f"Processing TeeTime reservation: {raw_reservation}")
        reservation = Reservation.from_teetime(raw_reservation, club, user, membership)
        
        # Skip if older than cutoff
        if reservation.start_time < cutoff_time:
            self.logger.debug(f"Skipping old TeeTime reservation: {reservation.start_time}")
            return
        
        if self._should_include_reservation(reservation, past_days, self.local_tz):
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
            lambda: []  # Fallback to empty list
        ):
            all_reservations = []
            now = datetime.now(self.local_tz)
            
            for user_name, user_config in self.config.users.items():
                _, reservations = self.process_user(user_name, user_config, days)
                
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
            lambda: []  # Fallback to empty list
        ):
            overlaps = []
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

    def _add_reservation_to_calendar(self, reservation: Reservation, cal: Calendar) -> None:
        """
        Add a reservation to the calendar.
        
        Args:
            reservation: Reservation to add
            cal: Calendar to add to
        """
        event = Event()
        event.add('summary', f"Golf {reservation.membership.clubAbbreviation}")
        event.add('dtstart', reservation.start_time)
        event.add('dtend', reservation.end_time)
        event.add('location', self._get_club_address(reservation.membership.club))
        
        # Create unique event ID
        resource_id = reservation.raw_data.get('resourceId', '0')
        if not resource_id and 'resources' in reservation.raw_data:
            resources = reservation.raw_data.get('resources', [{}])
            if resources:
                resource_id = resources[0].get('resourceId', '0')
        
        event_uid = f"{reservation.membership.clubAbbreviation}_{reservation.start_time.strftime('%Y%m%d%H%M')}_{resource_id}_{self.user_name}"
        event.add('uid', event_uid)
        
        # Add description
        event.add('description', reservation.get_event_description())
        
        # Add weather if not wisegolf0
        if reservation.membership.club not in self.config.clubs or self.config.clubs[reservation.membership.club].get('crm') != 'wisegolf0':
            self._add_weather_to_event(event, reservation.membership.clubAbbreviation, reservation.start_time, self.weather_service)
        
        self._add_event_to_calendar(event, cal)

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

    