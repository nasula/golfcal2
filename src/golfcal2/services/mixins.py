"""Mixins for service classes."""

from datetime import datetime
from typing import Optional, Any, Dict, Union, Set
from zoneinfo import ZoneInfo
from icalendar import Event, Calendar, vText

# Since icalendar doesn't have type stubs, we need to import it this way
import icalendar  # type: ignore[import]
from golfcal2.utils.logging_utils import LoggerMixin

class CalendarHandlerMixin:
    """Mixin for handling calendar operations."""
    
    def __init__(self, config: Optional[Any] = None) -> None:
        """Initialize the mixin.
        
        Args:
            config: Optional configuration object
        """
        self.seen_uids: Set[str] = set()
        self._config: Optional[Any] = config
    
    @property
    def config(self) -> Optional[Any]:
        """Get config, either from instance or parent."""
        if hasattr(self, '_config') and self._config is not None:
            return self._config
        return getattr(super(), 'config', None)
    
    @config.setter
    def config(self, value: Any) -> None:
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
        club: str,
        start_time: datetime,
        weather_service: Any
    ) -> None:
        """Add weather information to event description."""
        try:
            # Get club coordinates from config
            club_config = self.config.clubs.get(club)
            if not club_config or 'coordinates' not in club_config:
                if hasattr(self, 'logger'):
                    self.logger.warning(f"No coordinates found for club {club}")
                return
            
            # Get end time from event
            end_time = event.get('dtend').dt
            if not end_time:
                if hasattr(self, 'logger'):
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
                if hasattr(self, 'logger'):
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