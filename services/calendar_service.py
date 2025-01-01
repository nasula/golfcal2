"""
Calendar service for golf calendar application.
"""

import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from icalendar import Calendar, Event
from dateutil.tz import UTC

from golfcal2.utils.logging_utils import LoggerMixin
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

class CalendarService(LoggerMixin, CalendarHandlerMixin):
    """Service for handling calendar operations."""
    
    def __init__(self, config: AppConfig, dev_mode: bool = False):
        """Initialize calendar service."""
        super().__init__()
        self.config = config
        self.dev_mode = dev_mode
        
        # Initialize timezone settings
        self.utc_tz = UTC
        self.local_tz = config.timezone
        
        # Initialize services
        self.weather_service = WeatherManager(self.local_tz, self.utc_tz)
        self.external_event_service = ExternalEventService(self.weather_service)
        
        # Initialize builders
        self.calendar_builder = CalendarBuilder(self.local_tz)
        self.reservation_builder = ReservationEventBuilder(self.weather_service)
        self.external_builder = ExternalEventBuilder(self.weather_service)
        
        # Set up ICS directory
        if os.path.isabs(self.config.ics_dir):
            self.ics_dir = Path(self.config.ics_dir)
        else:
            # Use workspace directory as base for relative paths
            workspace_dir = Path(__file__).parent.parent
            self.ics_dir = workspace_dir / self.config.ics_dir
        
        # Create output directory if it doesn't exist
        self.ics_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Using ICS directory: {self.ics_dir}")

    def process_user_reservations(self, user: User, reservations: List[Reservation]) -> None:
        """Process reservations for a user."""
        # Create base calendar
        calendar = self.build_base_calendar(user.name, self.local_tz)
        self.seen_uids.clear()  # Reset seen UIDs for each user
        
        # Add reservations
        for reservation in reservations:
            # Skip if we've already seen this event
            if reservation.uid in self.seen_uids:
                self.logger.debug(f"Skipping duplicate reservation with UID: {reservation.uid}")
                continue
            
            # Get club configuration
            club_config = self.config.clubs.get(reservation.membership.club) or self.config.clubs.get(reservation.club.name)
            if not club_config:
                self.logger.warning(f"No club config found for {reservation.membership.club} or {reservation.club.name}")
                club_config = {}
            
            # Create event
            event = self.reservation_builder.build(reservation, club_config)
            if event:
                self._add_event_to_calendar(event, calendar)
                self.seen_uids.add(reservation.uid)
                self.logger.debug(f"Added reservation event: {event.get('summary')}")
        
        # Add external events
        external_events = self.external_event_service.process_events(user.name, dev_mode=self.dev_mode)
        for event in external_events:
            self._add_event_to_calendar(event, calendar)
            self.logger.debug(f"Added external event: {event.get('summary')}")
        
        # Write calendar to file
        file_path = self._get_calendar_path(user.name)
        self.calendar_builder.write_calendar(calendar, file_path, self.dev_mode)
        self.logger.info(f"Calendar created for user {user.name} with {len(reservations)} reservations and {len(external_events)} external events")

    def _get_calendar_path(self, user_name: str) -> Path:
        """Get calendar file path for user."""
        file_name = f"{user_name}.ics"
        return self.ics_dir / file_name