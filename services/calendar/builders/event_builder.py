"""
Event builder classes for calendar events.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List
from zoneinfo import ZoneInfo

from icalendar import Event, vText, vDatetime

from golfcal2.models.reservation import Reservation
from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.services.weather_service import WeatherService

class EventBuilder(ABC, LoggerMixin):
    """Base class for event builders."""
    
    def __init__(self, weather_service: WeatherService):
        """Initialize event builder."""
        super().__init__()
        self.weather_service = weather_service
        self.local_tz = ZoneInfo('Europe/Helsinki')
    
    @abstractmethod
    def build(self, *args, **kwargs) -> Optional[Event]:
        """Build an event."""
        pass
    
    def _get_weather(self, coordinates: Dict[str, float], start_time: datetime, duration_minutes: int, club_name: str) -> Optional[str]:
        """Get weather data if available."""
        try:
            return self.weather_service.get_weather(
                club=club_name,
                teetime=start_time,
                coordinates=coordinates,
                duration_minutes=duration_minutes
            )
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
            event.add('dtstart', vDatetime(start))
            event.add('dtend', vDatetime(end))
            event.add('dtstamp', vDatetime(datetime.now(self.local_tz)))
            
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
                    f"EXT_{event_data['name']}"
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
        
        return f"EXT_{event_data['name']}_{date_str}_{time_str}_{location_id}_{person_name}"
    
    def _get_location(self, event_data: Dict[str, Any]) -> str:
        """Format location string from event data."""
        location = event_data['location']
        if 'address' in event_data:
            location = f"{location}, {event_data['address']}"
        return location 