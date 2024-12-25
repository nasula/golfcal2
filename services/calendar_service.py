"""
Calendar service for golf calendar application.
"""

import os
import json
import yaml
import pytz
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from icalendar import Calendar, Event, vText, vDatetime
from dateutil.parser import parse
from dateutil.tz import UTC

from golfcal.utils.logging_utils import LoggerMixin
from golfcal.config.settings import AppConfig
from golfcal.models.reservation import Reservation
from golfcal.models.user import User
from golfcal.services.weather_service import WeatherManager
from golfcal.services.external_event_service import ExternalEventService

class CalendarService(LoggerMixin):
    """Service for handling calendar operations."""
    
    def __init__(self, config: AppConfig, dev_mode: bool = False):
        """Initialize calendar service."""
        super().__init__()
        self.config = config
        self.dev_mode = dev_mode
        
        # Initialize timezone settings
        self.utc_tz = pytz.UTC
        self.local_tz = pytz.timezone('Europe/Helsinki')  # Finland timezone
        
        # Initialize services
        self.weather_service = WeatherManager(self.local_tz, self.utc_tz)
        self.external_event_service = ExternalEventService(self.weather_service)
        self.seen_uids = set()  # Track seen UIDs for deduplication
        
        # Use absolute path for ics directory
        script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        workspace_dir = script_dir.parent.parent
        self.ics_dir = workspace_dir / config.ics_dir
        
        # Create output directory if it doesn't exist
        self.ics_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Using ICS directory: {self.ics_dir}")
    
    def process_user_reservations(self, user: User, reservations: List[Reservation]) -> None:
        """Process reservations for a user."""
        calendar = self._create_base_calendar(user)
        self.seen_uids.clear()  # Reset seen UIDs for each user
        
        # Add reservations
        for reservation in reservations:
            # Generate UID first
            uid = self._generate_unique_id(reservation)
            
            # Skip if we've already seen this event
            if uid in self.seen_uids:
                self.logger.debug(f"Skipping duplicate reservation with UID: {uid}")
                continue
            
            # Create event with the UID
            reservation.uid = uid
            event = self._create_event(reservation)
            if event:
                calendar.add_component(event)
                self.seen_uids.add(uid)
                self.logger.debug(f"Added reservation event: {event.get('summary')}")
        
        # Add external events
        external_events = self.external_event_service.process_events(user.name, dev_mode=self.dev_mode)
        for event in external_events:
            calendar.add_component(event)
            self.logger.debug(f"Added external event: {event.get('summary')}")
        
        # Write calendar to file
        self._write_calendar(calendar, user.name)
        self.logger.info(f"Calendar created for user {user.name} with {len(reservations)} reservations and {len(external_events)} external events")
    
    def write_calendar(self, calendar: Calendar, user_name: str) -> None:
        """
        Write calendar to file.
        
        Args:
            calendar: Calendar object to write
            user_name: Name of the user whose calendar is being written
        """
        self._write_calendar(calendar, user_name)
    
    def _create_base_calendar(self, user: User) -> Calendar:
        """Create base calendar with metadata."""
        calendar = Calendar()
        calendar.add("prodid", vText("-//Golf Calendar//EN"))
        calendar.add("version", vText("2.0"))
        calendar.add("calscale", vText("GREGORIAN"))
        calendar.add("method", vText("PUBLISH"))
        calendar.add("x-wr-calname", vText(f"Golf Reservations - {user.name}"))
        calendar.add("x-wr-timezone", vText(str(self.local_tz)))
        return calendar
    
    def _create_event(self, reservation: Reservation) -> Optional[Event]:
        """Create a calendar event from a reservation."""
        try:
            # Get club configuration - try both membership club and club name
            club_config = self.config.clubs.get(reservation.membership.club) or self.config.clubs.get(reservation.club.name)
            self.logger.info(f"Looking up club config for membership club '{reservation.membership.club}' or club name '{reservation.club.name}'")
            self.logger.debug(f"Available clubs in config: {list(self.config.clubs.keys())}")
            
            if not club_config:
                self.logger.warning(f"No club config found for {reservation.membership.club} or {reservation.club.name}")
                club_config = {}
            else:
                self.logger.debug(f"Found club config: {club_config}")
                if 'coordinates' in club_config:
                    self.logger.info(f"Found coordinates in config: {club_config['coordinates']}")
                else:
                    self.logger.warning(f"No coordinates in config, raw config: {club_config}")
            
            self.logger.info(f"Creating event for {reservation.club.name} at {reservation.start_time}")
            
            # Calculate event duration from club config or default to 4 hours
            duration_minutes = club_config.get('duration_minutes', 240)
            
            # Get weather data if applicable
            weather = None
            try:
                # Get coordinates from club config
                coordinates = None
                if 'coordinates' in club_config:
                    coordinates = {
                        'lat': club_config['coordinates']['lat'],
                        'lon': club_config['coordinates']['lon']
                    }
                    self.logger.info(f"Found coordinates for {reservation.club.name}: {coordinates}")
                else:
                    self.logger.warning(f"No coordinates found for {reservation.club.name} in club config: {club_config}")
                
                # Fetch weather if we have coordinates
                if coordinates:
                    self.logger.info(f"Fetching weather for {reservation.club.name} at {reservation.start_time}")
                    weather = self.weather_service.get_weather(
                        club=reservation.membership.clubAbbreviation,
                        teetime=reservation.start_time,
                        coordinates=coordinates,
                        duration_minutes=duration_minutes
                    )
                    if weather:
                        self.logger.info(f"Got weather data: {weather}")
                    else:
                        self.logger.warning(f"No weather data available")
            except Exception as e:
                self.logger.error(f"Failed to get weather: {e}", exc_info=True)
            
            # Create event
            event = Event()
            event.add('summary', reservation.get_event_summary())
            event.add('dtstart', vDatetime(reservation.start_time))
            event.add('dtend', vDatetime(reservation.end_time))
            event.add('dtstamp', vDatetime(datetime.now(self.local_tz)))
            event.add('uid', vText(reservation.uid))
            
            # Add location from club configuration or reservation
            location = club_config.get('location', reservation.get_event_location())
            if location:
                event.add('location', vText(location))
            
            # Add description with player details and weather
            description_parts = [f"Teetime {reservation.start_time.strftime('%Y-%m-%d %H:%M:%S')}"]
            
            # Add player details
            for player in reservation.players:
                player_info = f"{player.name}, {player.club}, HCP: {player.handicap}"
                description_parts.append(player_info)
            
            # Add weather if available
            if weather:
                description_parts.append("\nWeather:")
                description_parts.append(weather)
            
            event.add('description', vText("\n".join(description_parts)))
            
            return event
            
        except Exception as e:
            self.logger.error(f"Failed to create event: {e}", exc_info=True)
            return None
    
    def _generate_unique_id(self, reservation: Reservation) -> str:
        """
        Generate a unique ID for a reservation event.
        
        The UID format is: {club_name}_{date}_{time}_{resource_id}_{user_name}
        This ensures uniqueness while allowing deduplication of the same reservation.
        """
        # Get resource ID from raw data
        resource_id = reservation.raw_data.get('resourceId', '0')
        if not resource_id and 'resources' in reservation.raw_data:
            # Try to get resource ID from resources array
            resources = reservation.raw_data.get('resources', [{}])
            if resources:
                resource_id = resources[0].get('resourceId', '0')
        
        # Format date and time components
        date_str = reservation.start_time.strftime('%Y%m%d')
        time_str = reservation.start_time.strftime('%H%M')
        
        # Create unique ID that includes all necessary components
        return f"{reservation.club.name}_{date_str}_{time_str}_{resource_id}_{reservation.user.name}"
    
    def _write_calendar(self, calendar: Calendar, user_name: str) -> None:
        """Write calendar to file."""
        suffix = "-dev" if self.dev_mode else ""
        file_name = f"{user_name.replace(' ', '_')}_golf_reservations{suffix}.ics"
        file_path = self.ics_dir / file_name
        
        try:
            # Ensure all events are properly added
            event_count = len(calendar.walk('vevent'))
            self.logger.debug(f"Writing calendar with {event_count} events to {file_path}")
            
            with open(file_path, "wb") as f:
                calendar_data = calendar.to_ical()
                f.write(calendar_data)
                self.logger.debug(f"Wrote {len(calendar_data)} bytes to calendar file")
            
            self.logger.info(f"Created calendar file: {file_path}")
        except IOError as e:
            self.logger.error(f"Failed to write calendar file: {e}")
            raise