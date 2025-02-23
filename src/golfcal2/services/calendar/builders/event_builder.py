"""Event builder classes for calendar events."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Union, cast, Sequence
from zoneinfo import ZoneInfo

from icalendar import Event, vText, vDatetime  # type: ignore[import]

from golfcal2.models.reservation import Reservation
from golfcal2.models.golf_club import ExternalGolfClub
from golfcal2.models.user import User, Membership
from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.services.weather_service import WeatherService
from golfcal2.config.settings import AppConfig
from golfcal2.services.weather_types import (
    WeatherResponse, WeatherData, Location, WeatherCode
)
from golfcal2.services.weather_formatter import WeatherFormatter

class EventBuilder(ABC, LoggerMixin):
    """Base class for event builders."""
    
    def __init__(self, weather_service: WeatherService, config: AppConfig):
        """Initialize builder."""
        super().__init__()
        self.weather_service = weather_service
        self.config = config
        
        # Get timezone from config and ensure it's a ZoneInfo object
        timezone_name = config.global_config.get('timezone', 'UTC')
        self.local_tz = ZoneInfo(timezone_name)
        self.utc_tz = ZoneInfo('UTC')
        
        # Configure logger
        self.set_log_context(service="event_builder")
    
    @abstractmethod
    def build(self, *args, **kwargs) -> Optional[Event]:
        """Build an event."""
        pass
    
    def _get_weather(self, location: Location, start_time: datetime, end_time: datetime) -> Optional[WeatherResponse]:
        try:
            weather_response = self.weather_service.get_weather(
                location.latitude, location.longitude, start_time, end_time
            )
            
            if weather_response is None:
                return None
                
            # Convert forecast times to local timezone
            for forecast in weather_response.data:
                if forecast.time.tzinfo is None:
                    forecast.time = forecast.time.replace(tzinfo=timezone.utc)
                forecast.time = forecast.time.astimezone(self.local_tz)
            
            # Convert elaboration time to local timezone
            if weather_response.elaboration_time.tzinfo is None:
                weather_response.elaboration_time = weather_response.elaboration_time.replace(tzinfo=timezone.utc)
            weather_response.elaboration_time = weather_response.elaboration_time.astimezone(self.local_tz)
            
            return weather_response
            
        except Exception as e:
            self.error("Failed to get weather data", exc_info=e)
            return None

    def _format_weather_data(self, weather_data: Sequence[WeatherData]) -> str:
        """Format weather data for event description."""
        return WeatherFormatter.format_forecast(weather_data)

class ReservationEventBuilder(EventBuilder):
    """Event builder for golf reservations."""
    
    def __init__(self, weather_service: WeatherService, config: AppConfig):
        """Initialize builder."""
        super().__init__(weather_service, config)
    
    def build(self, reservation: Reservation, club_config: Dict[str, Any]) -> Optional[Event]:
        """Build an event from a reservation."""
        try:
            # Create base event
            event = Event()
            event.add('summary', reservation.get_event_summary())
            event.add('dtstart', vDatetime(reservation.start_time))
            event.add('dtend', vDatetime(reservation.end_time))
            event.add('dtstamp', vDatetime(datetime.now(timezone.utc)))
            event.add('uid', vText(reservation.uid))
            
            # Add location
            location = club_config.get('location', reservation.get_event_location())
            if location:
                event.add('location', vText(location))
            
            # Get weather data if coordinates available
            weather_data = None
            if 'coordinates' in club_config:
                duration_minutes = club_config.get('duration_minutes', 240)
                coords = club_config['coordinates']
                location = Location(
                    id=str(coords['lat']) + ',' + str(coords['lon']),
                    name=club_config.get('name', 'Golf Club'),
                    latitude=coords['lat'],
                    longitude=coords['lon']
                )
                weather_response = self._get_weather(
                    location,
                    reservation.start_time,
                    reservation.start_time + timedelta(minutes=duration_minutes)
                )
                if weather_response is not None:
                    weather_data = weather_response.data
            
            # Add description with player details and weather
            event.add('description', vText(reservation.get_event_description(weather_data)))
            
            return event
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Failed to build reservation event: {e}")
            return None

class ExternalEventBuilder(EventBuilder):
    """Event builder for external golf events."""
    
    def build(self, event_data: Dict[str, Any], person_name: str, start: datetime, end: datetime) -> Optional[Event]:
        """Build an event from external event data."""
        try:
            self.logger.debug(f"Building external event for {event_data.get('name', 'Unknown')}")
            
            # Create base event
            event = Event()
            event.add('summary', f"Golf: {event_data['name']}")
            
            # Get proper timezone from event data or config
            timezone_name = event_data.get('timezone', self.config.global_config.get('timezone', 'Europe/Helsinki'))
            event_timezone = ZoneInfo(timezone_name)
            self.debug(f"Using timezone {timezone_name} for event")
            
            # Ensure times are in the correct timezone
            if start.tzinfo is None:
                start = start.replace(tzinfo=event_timezone)
            else:
                start = start.astimezone(event_timezone)
                
            if end.tzinfo is None:
                end = end.replace(tzinfo=event_timezone)
            else:
                end = end.astimezone(event_timezone)
            
            # Add times with timezone
            event.add('dtstart', vDatetime(start), parameters={'TZID': [timezone_name]})
            event.add('dtend', vDatetime(end), parameters={'TZID': [timezone_name]})
            event.add('dtstamp', vDatetime(datetime.now(timezone.utc)), parameters={'VALUE': ['DATE-TIME']})
            
            # Generate and add UID
            uid = self._generate_unique_id(event_data, start, person_name)
            event.add('uid', vText(uid))
            
            # Add location if available
            if 'location' in event_data:
                event.add('location', vText(self._get_location(event_data)))
            
            try:
                self.logger.debug("Creating ExternalGolfClub instance")
                club = ExternalGolfClub(
                    name=event_data['name'],
                    url="",
                    coordinates=event_data.get('coordinates'),
                    timezone=timezone_name,
                    address=event_data.get('address', event_data.get('location', ''))
                )
                
                self.logger.debug("Creating Membership instance")
                membership = Membership(
                    club=club.name,
                    clubAbbreviation="EXT",
                    duration={"hours": 0, "minutes": 0},
                    auth_details={}
                )
                
                self.logger.debug("Creating User instance")
                user = User(
                    name=person_name,
                    email="",
                    handicap=0,
                    memberships=[membership]
                )
                
                self.logger.debug("Creating Reservation instance")
                reservation = Reservation(
                    club=club,
                    user=user,
                    membership=membership,
                    start_time=start,
                    end_time=end,
                    players=[],
                    raw_data=event_data  # Pass the entire event_data as raw_data
                )
            except Exception as e:
                self.logger.error(f"Failed to create event objects: {str(e)}", exc_info=True)
                raise
            
            # Get weather data if coordinates available
            weather_data = None
            if 'coordinates' in event_data:
                try:
                    coords = event_data['coordinates']
                    location = Location(
                        id=str(coords['lat']) + ',' + str(coords['lon']),
                        name=event_data.get('name', 'Golf Event'),
                        latitude=coords['lat'],
                        longitude=coords['lon']
                    )
                    weather_response = self._get_weather(
                        location,
                        start,
                        end
                    )
                    if weather_response is not None:
                        weather_data = weather_response.data
                except Exception as e:
                    self.logger.warning(f"Failed to get weather data: {str(e)}")
                    # Continue without weather data
            
            # Use reservation's description formatting
            event.add('description', vText(reservation.get_event_description(weather_data)))
            return event
            
        except Exception as e:
            self.logger.error(f"Failed to build external event for {event_data.get('name', 'Unknown')}: {str(e)}", exc_info=True)
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