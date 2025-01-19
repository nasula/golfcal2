"""
Calendar service for golf calendar application.
"""

import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from icalendar import Calendar, Event
from dateutil.tz import UTC

from golfcal2.utils.logging_utils import EnhancedLoggerMixin
from golfcal2.config.settings import AppConfig
from golfcal2.models.reservation import Reservation
from golfcal2.models.user import User
from golfcal2.services.weather_service import WeatherManager
from golfcal2.services.external_event_service import ExternalEventService
from golfcal2.services.calendar.builders import (
    CalendarBuilder,
    ReservationEventBuilder,
    ExternalEventBuilder
)
from golfcal2.models.mixins import CalendarHandlerMixin
from golfcal2.exceptions import (
    CalendarError,
    CalendarWriteError,
    CalendarEventError,
    ErrorCode,
    handle_errors
)
from golfcal2.config.error_aggregator import aggregate_error

class CalendarService(EnhancedLoggerMixin, CalendarHandlerMixin):
    """Service for handling calendar operations."""
    
    def __init__(self, config: AppConfig, weather_service: Optional[WeatherManager] = None, dev_mode: bool = False):
        """Initialize calendar service.
        
        Args:
            config: Application configuration
            weather_service: Optional pre-initialized weather service
            dev_mode: Whether to run in development mode
        """
        super().__init__()
        self.config = config
        self.dev_mode = dev_mode
        
        # Initialize timezone settings - use cached objects if available
        self.utc_tz = getattr(config, 'utc_tz', UTC)
        self.local_tz = getattr(config, 'local_tz', config.timezone)
        
        # Initialize seen UIDs set
        self.seen_uids = set()
        
        with handle_errors(CalendarError, "calendar", "initialize services"):
            # Use provided weather service or create new one
            self.weather_service = weather_service or WeatherManager(self.local_tz, self.utc_tz, self.config)
            
            # Initialize builders with shared dependencies
            self.calendar_builder = CalendarBuilder(self.local_tz)
            
            # Share weather service instance across builders
            builders_config = {
                'weather_service': self.weather_service,
                'config': self.config
            }
            self.external_event_service = ExternalEventService(**builders_config)
            self.reservation_builder = ReservationEventBuilder(**builders_config)
            self.external_builder = ExternalEventBuilder(**builders_config)
            
            # Set up ICS directory
            try:
                if os.path.isabs(self.config.ics_dir):
                    self.ics_dir = Path(self.config.ics_dir)
                else:
                    # Use workspace directory as base for relative paths
                    workspace_dir = Path(__file__).parent.parent
                    self.ics_dir = workspace_dir / self.config.ics_dir
                
                # Create output directory if it doesn't exist
                self.ics_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Using ICS directory: {self.ics_dir}")
            except Exception as e:
                error = CalendarError(
                    f"Failed to initialize calendar directory: {str(e)}",
                    ErrorCode.CONFIG_INVALID,
                    {"ics_dir": str(self.config.ics_dir)}
                )
                aggregate_error(str(error), "calendar", e.__traceback__)
                raise error

    def check_config(self) -> bool:
        """Check if the service configuration is valid.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check if ICS directory exists or can be created
            if os.path.isabs(self.config.ics_dir):
                ics_dir = Path(self.config.ics_dir)
            else:
                # Use workspace directory as base for relative paths
                workspace_dir = Path(__file__).parent.parent
                ics_dir = workspace_dir / self.config.ics_dir
                
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
                lambda: None
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
            aggregate_error(str(error), "calendar", e.__traceback__)
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
            lambda: None
        ):
            # Get club configuration
            club_config = self.config.clubs.get(reservation.membership.club) or self.config.clubs.get(reservation.club.name)
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
            lambda: None
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
            lambda: None
        ):
            self.calendar_builder.write_calendar(calendar, file_path, self.dev_mode)

    def _get_calendar_path(self, user_name: str) -> Path:
        """Get calendar file path for user."""
        file_name = f"{user_name}.ics"
        return self.ics_dir / file_name