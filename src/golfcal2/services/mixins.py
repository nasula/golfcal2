"""Mixins for service classes."""

from datetime import datetime
from typing import Optional, Any
from zoneinfo import ZoneInfo
from icalendar import Event, Calendar, vText

import icalendar  # type: ignore
from golfcal2.utils.logging_utils import LoggerMixin

class CalendarHandlerMixin:
    """Mixin for handling calendar operations."""
    
    def __init__(self, config=None):
        """Initialize calendar handler."""
        super().__init__()
        self.seen_uids = set()
        self._config = config
    
    @property
    def logger(self):
        """Get logger for this mixin."""
        if not hasattr(self, '_calendar_logger'):
            self._calendar_logger = LoggerMixin().logger
        return self._calendar_logger
    
    @property
    def config(self):
        """Get config, either from instance or parent."""
        if hasattr(self, '_config') and self._config is not None:
            return self._config
        return getattr(super(), 'config', None)
    
    @config.setter
    def config(self, value):
        """Set config value."""
        self._config = value
    
    def _add_event_to_calendar(
        self,
        event: Event,
        calendar: Calendar
    ) -> None:
        """
        Add an event to the calendar, ensuring no duplicates.
        
        Args:
            event: Event to add
            calendar: Calendar to add to
        """
        uid = event.get('uid')
        if uid and uid in self.seen_uids:
            self.logger.debug(f"Skipping duplicate event with UID: {uid}")
            return
            
        if uid:
            self.seen_uids.add(uid)
        calendar.add_component(event)
        self.logger.debug(f"Added event to calendar: {event.decoded('summary')}")
    
    def _add_weather_to_event(
        self,
        event: Event,
        club: str,
        start_time: datetime,
        weather_service: Any
    ) -> None:
        """Add weather information to event description."""
        try:
            # Get club coordinates from config
            club_config = self.config.clubs.get(club)
            if not club_config or 'coordinates' not in club_config:
                self.logger.warning(f"No coordinates found for club {club}")
                return
            
            # Get end time from event
            end_time = event.get('dtend').dt
            if not end_time:
                self.logger.warning(f"No end time found for event {event.get('uid')}")
                return
            
            # Get weather data - pass all required parameters including service_name
            weather_data = weather_service.get_weather(
                lat=club_config['coordinates']['lat'],
                lon=club_config['coordinates']['lon'],
                start_time=start_time,
                end_time=end_time,
                service_name='met'  # Use met service by default
            )
            
            if not weather_data:
                self.logger.warning(f"No weather data found for club {club}")
                return
            
            # Update event description with weather data
            description = event.get('description', '')
            if description:
                description = description + "\n\nWeather:\n"
            else:
                description = "Weather:\n"
            
            # Format weather data
            for forecast in weather_data:
                description += (
                    f"{forecast.time.strftime('%H:%M')} - "
                    f"{forecast.temperature}°C, "
                    f"{forecast.wind_speed}m/s"
                )
                if forecast.precipitation_probability is not None:
                    description += f", {forecast.precipitation_probability}% rain"
                description += "\n"
            
            event['description'] = description
            
        except Exception as e:
            self.logger.error(f"Failed to add weather to event: {e}")
            return
    
    def build_base_calendar(
        self,
        user_name: str,
        local_tz: ZoneInfo
    ) -> Calendar:
        """
        Create base calendar with metadata.
        
        Args:
            user_name: Name of the user
            local_tz: Local timezone
            
        Returns:
            Base calendar with metadata
        """
        calendar = Calendar()
        calendar.add('prodid', vText('-//Golf Calendar//EN'))
        calendar.add('version', vText('2.0'))
        calendar.add('calscale', vText('GREGORIAN'))
        calendar.add('method', vText('PUBLISH'))
        calendar.add('x-wr-calname', vText(f'Golf Reservations - {user_name}'))
        calendar.add('x-wr-timezone', vText(str(local_tz)))
        return calendar 