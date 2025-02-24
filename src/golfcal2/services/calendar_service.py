"""
Calendar service for golf calendar application.
"""

import os
import traceback
from pathlib import Path
from typing import Any
from typing import NoReturn
from typing import Protocol
from typing import TypeVar
from typing import cast
from typing import runtime_checkable
from zoneinfo import ZoneInfo

from icalendar import Calendar
from icalendar import Event

from golfcal2.config.error_aggregator import aggregate_error
from golfcal2.config.types import AppConfig
from golfcal2.error_codes import ErrorCode
from golfcal2.exceptions import CalendarError
from golfcal2.exceptions import CalendarEventError
from golfcal2.exceptions import CalendarWriteError
from golfcal2.exceptions import handle_errors
from golfcal2.models.reservation import Reservation
from golfcal2.models.user import User
from golfcal2.services.calendar.builders import CalendarBuilder
from golfcal2.services.calendar.builders import ExternalEventBuilder
from golfcal2.services.calendar.builders import ReservationEventBuilder
from golfcal2.services.external_event_service import ExternalEventService
from golfcal2.services.mixins import CalendarHandlerMixin
from golfcal2.services.weather_service import WeatherService
from golfcal2.utils.logging_utils import EnhancedLoggerMixin


T = TypeVar('T')

@runtime_checkable
class ConfigProtocol(Protocol):
    """Protocol for configuration objects."""
    ics_dir: str
    clubs: dict[str, Any]
    timezone: str
    global_config: dict[str, Any]

def raise_error(msg: str = "") -> NoReturn:
    """Helper function to raise an error and satisfy the NoReturn type."""
    raise CalendarError(msg, ErrorCode.SERVICE_ERROR)

class CalendarService(EnhancedLoggerMixin, CalendarHandlerMixin):
    """Service for managing calendar operations."""
    
    def __init__(
        self,
        config: AppConfig,
        weather_service: WeatherService | None = None,
        dev_mode: bool = False,
        external_event_service: ExternalEventService | None = None
    ):
        """Initialize service."""
        super().__init__()
        self.config: AppConfig = config
        self.dev_mode = dev_mode
        self.local_tz = ZoneInfo(config.timezone)
        self.seen_uids: set[str] = set()
        
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
            
            # Use provided external event service or create new one
            self.external_event_service = external_event_service or ExternalEventService(
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
            
            # Setup ICS directory - ensure absolute path
            ics_dir = str(config.ics_dir)
            if not os.path.isabs(ics_dir):
                # Use workspace directory as base for relative paths
                workspace_dir = Path(__file__).parent.parent.parent.parent
                ics_dir = str(workspace_dir / ics_dir)
            self.ics_dir = Path(ics_dir)
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
                    self.error(f"Failed to create ICS directory {ics_dir}: {e!s}")
                    return False
            
            # Check if ICS directory is writable
            if not os.access(ics_dir, os.W_OK):
                self.error(f"ICS directory {ics_dir} is not writable")
                return False
            
            # All checks passed
            self.info("Calendar configuration is valid")
            return True
            
        except Exception as e:
            self.error(f"Error checking configuration: {e!s}")
            return False

    def process_user_reservations(self, user: User, reservations: list[Reservation]) -> Calendar:
        """Process reservations for a user and return the calendar object."""
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
                
                # Write calendar to file if not in list-only mode
                if not getattr(self, 'list_only', False):
                    file_path = self._get_calendar_path(user.name)
                    self._write_calendar(calendar, file_path, user.name)
                
                # Count events by type
                reservation_count = len(reservations)
                external_count = sum(1 for event in calendar.walk('vevent') 
                                   if event.get('uid') and 'EXT_' in str(event.get('uid')))
                
                self.logger.info(
                    f"Calendar created for user {user.name} with "
                    f"{reservation_count} reservations and "
                    f"{external_count} external events"
                )
                
                return calendar
                
        except Exception as e:
            error = CalendarError(
                f"Failed to process reservations: {e!s}",
                ErrorCode.SERVICE_ERROR,
                {
                    "user": user.name,
                    "reservation_count": len(reservations),
                    "operation": "process_user_reservations"
                }
            )
            # Convert traceback to string
            tb_str = "".join(traceback.format_tb(e.__traceback__)) if e.__traceback__ else None
            aggregate_error(str(error), "calendar", tb_str)
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
            club_config = cast(dict[str, Any], self.config.clubs).get(reservation.membership.club) or \
                         cast(dict[str, Any], self.config.clubs).get(reservation.club.name)
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

    def _make_api_request(self, *args: Any, **kwargs: Any) -> NoReturn:
        """Make an API request with error handling."""
        with handle_errors(
            CalendarError,
            "calendar",
            "make api request",
            lambda: raise_error("API request failed")
        ):
            raise NotImplementedError("_make_api_request not implemented")

    def _process_calendar(self, calendar: Any, *args: Any, **kwargs: Any) -> NoReturn:
        """Process calendar with error handling."""
        with handle_errors(
            CalendarError,
            "calendar",
            "process calendar",
            lambda: raise_error("Calendar processing failed")
        ):
            raise NotImplementedError("_process_calendar not implemented")

    def _handle_event(self, event: Any, *args: Any, **kwargs: Any) -> NoReturn:
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
            club_config = cast(dict[str, Any], self.config.clubs).get(reservation.membership.club) or \
                         cast(dict[str, Any], self.config.clubs).get(reservation.club.name)
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