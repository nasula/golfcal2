"""Mixins for service classes."""

from datetime import datetime
from typing import Optional, Any, Dict, Union, Set, cast
from zoneinfo import ZoneInfo
from icalendar import Event, Calendar, vText  # type: ignore[import]

# Since icalendar doesn't have type stubs, we need to import it this way
import icalendar  # type: ignore[import]
from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.config.settings import AppConfig
from golfcal2.services.weather_service import WeatherManager
from golfcal2.models.reservation import Reservation

class CalendarHandlerMixin:
    """Mixin for handling calendar operations."""
    
    def __init__(self, config: AppConfig) -> None:
        """Initialize calendar handler."""
        if not isinstance(config, AppConfig):
            raise ValueError("Config must be an instance of AppConfig")
            
        self.config = config
        
        # Initialize timezone settings
        self.timezone = ZoneInfo(config.global_config.get('timezone', 'UTC'))
        self.utc_tz = ZoneInfo('UTC')
        
        self.seen_uids: Set[str] = set()
    
    @property
    def config(self) -> AppConfig:
        """Get config, either from instance or parent."""
        return self._config
    
    @config.setter
    def config(self, value: AppConfig) -> None:
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
            if hasattr(self, 'logger'):
                self.logger.debug(f"Skipping duplicate event with UID: {uid}")
            return
            
        if uid:
            self.seen_uids.add(uid)
        calendar.add_component(event)
        if hasattr(self, 'logger'):
            self.logger.debug(f"Added event to calendar: {event.decoded('summary')}")
    
    def _add_weather_to_event(
        self,
        event: Event,
        club_id: str,
        start_time: datetime,
        weather_service: Optional[WeatherManager] = None
    ) -> None:
        """Add weather information to event."""
        if not self.config or not hasattr(self.config, 'clubs'):
            return
            
        club_config = self.config.clubs.get(club_id)
        if not club_config or 'coordinates' not in club_config:
            return
            
        if weather_service is None:
            return
            
        try:
            # Get end time from event
            end_time = event.get('dtend').dt
            if not end_time:
                if hasattr(self, 'logger'):
                    self.logger.warning(f"No end time found for event {event.get('uid')}")
                return
            
            coords = club_config['coordinates']
            if not coords or 'lat' not in coords or 'lon' not in coords:
                return
                
            # Get weather data
            weather_data = weather_service.get_weather(
                lat=coords['lat'],
                lon=coords['lon'],
                start_time=start_time,
                end_time=end_time
            )
            
            if not weather_data:
                if hasattr(self, 'logger'):
                    self.logger.warning(f"No weather data found for club {club_id}")
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
            if hasattr(self, 'logger'):
                self.logger.error(f"Failed to add weather to event: {e}")
            return
    
    def build_base_calendar(self, name: str, timezone: ZoneInfo) -> Calendar:
        """Build a base calendar with common properties."""
        calendar = Calendar()
        calendar.add('prodid', vText('-//Golf Calendar//EN'))
        calendar.add('version', vText('2.0'))
        calendar.add('calscale', vText('GREGORIAN'))
        calendar.add('method', vText('PUBLISH'))
        calendar.add('x-wr-calname', vText(name))
        calendar.add('x-wr-timezone', vText(str(timezone)))
        return calendar

    def add_event_to_calendar(self, calendar: Calendar, event: Dict[str, Any]) -> None:
        """Add an event to the calendar."""
        calendar_event = Event()
        for key, value in event.items():
            calendar_event.add(key, value)
        calendar.add_component(calendar_event)

    def format_datetime(self, dt: datetime) -> str:
        """Format datetime for calendar."""
        return dt.strftime('%Y%m%dT%H%M%SZ') 