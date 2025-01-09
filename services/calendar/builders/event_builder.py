"""Event builder classes for calendar events."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo

from icalendar import Event, vText, vDatetime

from golfcal2.models.reservation import Reservation
from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.services.weather_service import WeatherService
from golfcal2.config.settings import AppConfig
from golfcal2.services.weather_service import WeatherManager

class EventBuilder(ABC, LoggerMixin):
    """Base class for event builders."""
    
    def __init__(self, weather_service: WeatherManager, config: AppConfig):
        """Initialize builder."""
        super().__init__()
        self.weather_service = weather_service
        self.config = config
        
        # Get timezone from config
        self.local_tz = ZoneInfo(config.global_config.get('timezone', 'UTC'))
        self.utc_tz = ZoneInfo('UTC')
        
        # Configure logger
        self.set_log_context(service="event_builder")
    
    @abstractmethod
    def build(self, *args, **kwargs) -> Optional[Event]:
        """Build an event."""
        pass
    
    def _get_weather(self, coordinates: Dict[str, float], start_time: datetime, duration_minutes: int, club_name: str) -> Optional[str]:
        """Get weather data if available.
        
        Args:
            coordinates: Latitude and longitude
            start_time: Event start time (in local timezone)
            duration_minutes: Event duration in minutes
            club_name: Name of the club/venue
            
        Returns:
            Formatted weather string or None if weather data not available
        """
        try:
            # Ensure start time has timezone
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=self.local_tz)
            
            # Keep times in local timezone for weather service
            end_time = start_time + timedelta(minutes=duration_minutes)
            
            weather_data = self.weather_service.get_weather(
                lat=coordinates['lat'],
                lon=coordinates['lon'],
                start_time=start_time,
                end_time=end_time,
                club=club_name
            )
            
            if weather_data:
                # Create a simple reservation just for formatting
                from golfcal2.models.reservation import Reservation
                
                temp_reservation = Reservation(
                    club=None,  # Not needed for weather formatting
                    user=None,  # Not needed for weather formatting
                    membership=None,  # Not needed for weather formatting
                    start_time=start_time,
                    end_time=start_time + timedelta(minutes=duration_minutes),
                    players=[],
                    raw_data={}
                )
                
                # Handle both WeatherResponse objects and direct lists of forecasts
                forecasts = weather_data.data if hasattr(weather_data, 'data') else weather_data
                
                # Convert forecast times back to local timezone only if they are WeatherData objects
                if forecasts and isinstance(forecasts, list) and all(hasattr(f, 'elaboration_time') for f in forecasts):
                    for forecast in forecasts:
                        if forecast.elaboration_time.tzinfo is None:
                            forecast.elaboration_time = forecast.elaboration_time.replace(tzinfo=ZoneInfo('UTC'))
                        forecast.elaboration_time = forecast.elaboration_time.astimezone(self.local_tz)
                
                return temp_reservation._format_weather_data(forecasts)
            return None
        except Exception as e:
            self.logger.error(f"Failed to get weather data: {e}")
            return None

class ReservationEventBuilder(EventBuilder):
    """Event builder for golf reservations."""
    
    def build(self, reservation: Reservation, club_config: Dict[str, Any]) -> Optional[Event]:
        """Build an event from a reservation."""
        try:
            # Create base event
            event = Event()
            event.add('summary', reservation.get_event_summary())
            event.add('dtstart', vDatetime(reservation.start_time))
            event.add('dtend', vDatetime(reservation.end_time))
            event.add('dtstamp', vDatetime(datetime.now(self.local_tz)))
            event.add('uid', vText(reservation.uid))
            
            # Add location
            location = club_config.get('location', reservation.get_event_location())
            if location:
                event.add('location', vText(location))
            
            # Get weather data if coordinates available
            weather_data = None
            if 'coordinates' in club_config:
                duration_minutes = club_config.get('duration_minutes', 240)
                weather_data = self._get_weather(
                    club_config['coordinates'],
                    reservation.start_time,
                    duration_minutes,
                    reservation.membership.clubAbbreviation
                )
            
            # Add description with player details and weather
            event.add('description', vText(reservation.get_event_description(weather_data)))
            
            return event
            
        except Exception as e:
            self.logger.error(f"Failed to build reservation event: {e}")
            return None

class ExternalEventBuilder(EventBuilder):
    """Event builder for external golf events."""
    
    def build(self, event_data: Dict[str, Any], person_name: str, start: datetime, end: datetime) -> Optional[Event]:
        """Build an event from external event data."""
        try:
            # Check if person is included
            if 'users' in event_data and person_name not in event_data['users']:
                return None
            
            # Create base event
            event = Event()
            event.add('summary', f"Golf: {event_data['name']}")
            
            # Use the original timezone from start time
            event_timezone = start.tzinfo
            self.debug(f"Using timezone {event_timezone} from start time")
            
            # Add times with original timezone
            event.add('dtstart', vDatetime(start))
            event.add('dtend', vDatetime(end))
            event.add('dtstamp', vDatetime(datetime.now(ZoneInfo('UTC'))), parameters={'VALUE': ['DATE-TIME']})
            
            # Generate and add UID
            uid = self._generate_unique_id(event_data, start, person_name)
            event.add('uid', vText(uid))
            
            # Add location if available
            if 'location' in event_data:
                event.add('location', vText(self._get_location(event_data)))
            
            # Build description
            description = f"External golf event at {event_data['location']}"
            
            # Add weather if coordinates available
            if 'coordinates' in event_data:
                duration_minutes = int((end - start).total_seconds() / 60)
                weather_data = self._get_weather(
                    event_data['coordinates'],
                    start,
                    duration_minutes,
                    event_data['name']  # Use event name directly instead of EXT_ prefix
                )
                if weather_data:
                    description += f"\n\nWeather:\n{weather_data}"
            
            event.add('description', vText(description))
            return event
            
        except Exception as e:
            self.logger.error(f"Failed to build external event: {e}")
            return None
    
    def _generate_unique_id(self, event_data: Dict[str, Any], start: datetime, person_name: str) -> str:
        """Generate a unique ID for an external event."""
        date_str = start.strftime('%Y%m%d')
        time_str = start.strftime('%H%M')
        
        if 'coordinates' in event_data:
            location_id = f"{event_data['coordinates']['lat']}_{event_data['coordinates']['lon']}"
        else:
            location_id = event_data['location'][:8].replace(' ', '_')
        
        # Use consistent format with other events
        return f"{event_data['name'].replace(' ', '_')}_{date_str}_{time_str}_{location_id.split('.')[0]}_{person_name}"
    
    def _get_location(self, event_data: Dict[str, Any]) -> str:
        """Format location string from event data."""
        location = event_data['location']
        if 'address' in event_data:
            location = f"{location}, {event_data['address']}"
        return location 