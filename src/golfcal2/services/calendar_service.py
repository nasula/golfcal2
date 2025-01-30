"""
Calendar service for golf calendar application.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set, cast, NoReturn, Type, TypeVar, Protocol, runtime_checkable
from typing_extensions import Never
from zoneinfo import ZoneInfo
from pathlib import Path
import requests
from icalendar import Event, Calendar  # type: ignore
from types import TracebackType

from golfcal2.models.golf_club import GolfClubFactory
from golfcal2.models.reservation import Reservation
from golfcal2.models.user import User, Membership
from golfcal2.utils.logging_utils import EnhancedLoggerMixin
from golfcal2.config.settings import AppConfig
from golfcal2.services.auth_service import AuthService
from golfcal2.services.mixins import CalendarHandlerMixin
from golfcal2.services.weather_service import WeatherService
from golfcal2.services.external_event_service import ExternalEventService
from golfcal2.services.calendar.builders import (
    CalendarBuilder,
    ReservationEventBuilder,
    ExternalEventBuilder
)
from golfcal2.exceptions import (
    APIError,
    APITimeoutError,
    APIRateLimitError,
    APIResponseError,
    CalendarError,
    CalendarWriteError,
    CalendarEventError,
    ErrorCode,
    handle_errors
)
from golfcal2.config.error_aggregator import aggregate_error

T = TypeVar('T')

@runtime_checkable
class ConfigProtocol(Protocol):
    """Protocol for configuration objects."""
    ics_dir: str
    clubs: Dict[str, Any]
    timezone: str
    global_config: Dict[str, Any]

def raise_error(msg: str = "") -> Never:
    """Helper function to raise an error and satisfy the Never type."""
    raise CalendarError(msg, ErrorCode.SERVICE_ERROR)

class CalendarService(EnhancedLoggerMixin, CalendarHandlerMixin):
    """Service for managing calendar operations."""
    
    def __init__(
        self,
        config: ConfigProtocol,
        weather_service: Optional[WeatherService] = None,
        dev_mode: bool = False
    ):
        """Initialize service."""
        super().__init__()
        self.config = config
        self.dev_mode = dev_mode
        self.local_tz = ZoneInfo(config.timezone)
        self.seen_uids: Set[str] = set()
        
        # Initialize services
        with handle_errors(
            CalendarError,
            "calendar",
            "initialize services",
            lambda: raise_error("Failed to initialize calendar service")
        ):
            # Use provided weather service or create new one
            self.weather_service = weather_service or WeatherService(
                config=self.config.__dict__
            )
            
            # Initialize external event service
            self.external_event_service = ExternalEventService(
                weather_service=self.weather_service,
                config=config
            )
            
            # Initialize builders with proper typing
            self.calendar_builder = CalendarBuilder(local_tz=self.local_tz)
            self.reservation_builder = ReservationEventBuilder(
                weather_service=self.weather_service,
                config=config
            )
            self.external_builder = ExternalEventBuilder(
                weather_service=self.weather_service,
                config=config
            )
            
            # Setup ICS directory
            self.ics_dir = Path(str(config.ics_dir))
            self.ics_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Using ICS directory: {self.ics_dir}")

    def check_config(self) -> bool:
        """Check if the service configuration is valid.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check if ICS directory exists or can be created
            if os.path.isabs(str(self.config.ics_dir)):
                ics_dir = Path(str(self.config.ics_dir))
            else:
                # Use workspace directory as base for relative paths
                workspace_dir = Path(__file__).parent.parent
                ics_dir = workspace_dir / str(self.config.ics_dir)
                
            if not ics_dir.exists():
                try:
                    ics_dir.mkdir(parents=True, exist_ok=True)
                    self.info(f"Created ICS directory: {ics_dir}")
                except Exception as e:
                    self.error(f"Failed to create ICS directory {ics_dir}: {str(e)}")
                    return False
            
            # Check if ICS directory is writable
            if not os.access(ics_dir, os.W_OK):
                self.error(f"ICS directory {ics_dir} is not writable")
                return False
            
            # All checks passed
            self.info("Calendar configuration is valid")
            return True
            
        except Exception as e:
            self.error(f"Error checking configuration: {str(e)}")
            return False

    def process_user_reservations(self, user: User, reservations: List[Reservation]) -> None:
        """Process reservations for a user."""
        try:
            # Create base calendar
            calendar = self.build_base_calendar(user.name, self.local_tz)
            self.seen_uids.clear()  # Reset seen UIDs for each user
            
            # Process reservations with error handling
            with handle_errors(
                CalendarError,
                "calendar",
                f"process reservations for user {user.name}",
                lambda: raise_error("Failed to process reservations")
            ):
                # Add reservations
                for reservation in reservations:
                    self._process_reservation(reservation, calendar, user.name)
                
                # Add external events
                self._process_external_events(calendar, user.name)
                
                # Write calendar to file
                file_path = self._get_calendar_path(user.name)
                self._write_calendar(calendar, file_path, user.name)
                
                self.logger.info(
                    f"Calendar created for user {user.name} with "
                    f"{len(reservations)} reservations and "
                    f"{len(self.external_event_service.get_events())} external events"
                )
                
        except Exception as e:
            error = CalendarError(
                f"Failed to process reservations: {str(e)}",
                ErrorCode.SERVICE_ERROR,
                {
                    "user": user.name,
                    "reservation_count": len(reservations),
                    "operation": "process_user_reservations"
                }
            )
            aggregate_error(str(error), "calendar", str(e.__traceback__))
            raise error

    def _process_reservation(self, reservation: Reservation, calendar: Calendar, user_name: str) -> None:
        """Process a single reservation."""
        # Skip if we've already seen this event
        if reservation.uid in self.seen_uids:
            self.debug(f"Skipping duplicate reservation with UID: {reservation.uid}")
            return
        
        with handle_errors(
            CalendarEventError,
            "calendar",
            f"process reservation {reservation.uid}",
            lambda: raise_error("Failed to process reservation")
        ):
            # Get club configuration
            club_config = cast(Dict[str, Any], self.config.clubs).get(reservation.membership.club) or \
                         cast(Dict[str, Any], self.config.clubs).get(reservation.club.name)
            if not club_config:
                self.warning(f"No club config found for {reservation.membership.club} or {reservation.club.name}")
                club_config = {}
            
            # Create event
            event = self.reservation_builder.build(reservation, club_config)
            if event:
                self._add_event_to_calendar(event, calendar)
                self.seen_uids.add(reservation.uid)
                self.debug(f"Added reservation event: {event.get('summary')}")

    def _process_external_events(self, calendar: Calendar, user_name: str) -> None:
        """Process external events."""
        with handle_errors(
            CalendarEventError,
            "calendar",
            f"process external events for user {user_name}",
            lambda: raise_error("Failed to process external events")
        ):
            # Process events first
            external_events = self.external_event_service.process_events(user_name, dev_mode=self.dev_mode)
            
            # Now get the processed events
            for event in external_events:
                self._add_event_to_calendar(event, calendar)
                self.debug(f"Added external event: {event.get('summary')}")

    def _write_calendar(self, calendar: Calendar, file_path: Path, user_name: str) -> None:
        """Write calendar to file."""
        with handle_errors(
            CalendarWriteError,
            "calendar",
            f"write calendar for user {user_name}",
            lambda: raise_error("Failed to write calendar")
        ):
            self.calendar_builder.write_calendar(calendar, file_path, self.dev_mode)

    def _get_calendar_path(self, user_name: str) -> Path:
        """Get calendar file path for user."""
        file_name = f"{user_name}.ics"
        return self.ics_dir / file_name

    def _make_api_request(self, *args: Any, **kwargs: Any) -> Never:
        """Make an API request with error handling."""
        with handle_errors(
            CalendarError,
            "calendar",
            "make api request",
            lambda: raise_error("API request failed")
        ):
            raise NotImplementedError("_make_api_request not implemented")

    def _process_calendar(self, calendar: Any, *args: Any, **kwargs: Any) -> Never:
        """Process calendar with error handling."""
        with handle_errors(
            CalendarError,
            "calendar",
            "process calendar",
            lambda: raise_error("Calendar processing failed")
        ):
            raise NotImplementedError("_process_calendar not implemented")

    def _handle_event(self, event: Any, *args: Any, **kwargs: Any) -> Never:
        """Handle event with error handling."""
        with handle_errors(
            CalendarError,
            "calendar",
            "handle event",
            lambda: raise_error("Event handling failed")
        ):
            raise NotImplementedError("_handle_event not implemented")

    def raise_error(self, msg: str = "") -> NoReturn:
        """Raise a calendar error."""
        raise CalendarError(msg)

    def _get_club_address(self, club_id: str) -> str:
        """
        Get club address from configuration.
        
        Args:
            club_id: Club ID
            
        Returns:
            Club address
        """
        if club_id in self.config.clubs:
            return self.config.clubs[club_id].get('address') or ''
        return ''

    def add_reservation_to_calendar(self, calendar: Calendar, reservation: Reservation) -> None:
        """Add a reservation to the calendar."""
        with handle_errors(
            CalendarEventError,
            "calendar",
            f"add reservation {reservation.uid}",
            lambda: raise_error("Failed to add reservation")
        ):
            # Get club configuration
            club_config = cast(Dict[str, Any], self.config.clubs).get(reservation.membership.club) or \
                         cast(Dict[str, Any], self.config.clubs).get(reservation.club.name)
            if not club_config:
                self.warning(f"No club config found for {reservation.membership.club} or {reservation.club.name}")
                club_config = {}
            
            # Create event
            event = self.reservation_builder.build(reservation, club_config)
            if event:
                self._add_event_to_calendar(event, calendar)
                self.seen_uids.add(reservation.uid)
                self.debug(f"Added reservation event: {event.get('summary')}")

    def _add_event_to_calendar(self, event: Event, calendar: Calendar) -> None:
        """Add an event to the calendar."""
        # Check for duplicate UIDs
        uid = event.get('uid')
        if uid and uid in self.seen_uids:
            self.debug(f"Skipping duplicate event with UID: {uid}")
            return
        
        calendar.add_component(event)
        if uid:
            self.seen_uids.add(uid)