"""Mixins for service classes."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

# Since icalendar doesn't have type stubs, we need to import it this way
from icalendar import (
    Calendar,  # type: ignore[import]
    Event,  # type: ignore[import]
    vText,  # type: ignore[import]
)

from golfcal2.config.settings import AppConfig
from golfcal2.models.reservation import Reservation
from golfcal2.services.weather_service import WeatherService
from golfcal2.services.weather_types import WeatherData


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
        
        self.seen_uids: set[str] = set()
    
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
    
    def _get_weather_for_reservation(
        self,
        reservation: Reservation,
        weather_service: WeatherService | None = None
    ) -> list[WeatherData] | None:
        """Get weather data for a reservation."""
        if not self.config or not hasattr(self.config, 'clubs'):
            return None
            
        club_config = self.config.clubs.get(reservation.membership.club)
        if not club_config or 'coordinates' not in club_config:
            return None
            
        if weather_service is None:
            return None
            
        try:
            coords = club_config['coordinates']
            if not coords or 'lat' not in coords or 'lon' not in coords:
                return None
                
            # Get weather data using the reservation's times
            weather_response = weather_service.get_weather(
                lat=coords['lat'],
                lon=coords['lon'],
                start_time=reservation.start_time,
                end_time=reservation.end_time
            )
            
            if not weather_response:
                if hasattr(self, 'logger'):
                    self.logger.warning(f"No weather data found for club {reservation.membership.club}")
                return None
            
            return weather_response.data
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Failed to get weather data: {e}")
            return None

    def _add_weather_to_event(
        self,
        event: Event,
        club_id: str,
        start_time: datetime,
        weather_service: WeatherService | None = None,
        existing_reservation: Reservation | None = None
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
            
            # Use existing reservation if provided, otherwise create a temporary one
            reservation = existing_reservation
            if reservation is None:
                # Create a temporary Reservation object for weather handling
                from golfcal2.models.golf_club import ExternalGolfClub
                from golfcal2.models.reservation import Reservation
                from golfcal2.models.user import Membership, User
                
                # Create minimal club object with coordinates
                club = ExternalGolfClub(
                    name=club_config.get('name', 'Golf Club'),
                    url="",
                    coordinates=club_config['coordinates'],
                    timezone=start_time.tzinfo.key if hasattr(start_time.tzinfo, 'key') else 'UTC',
                    address=club_config.get('address', '')
                )
                
                # Create minimal user and membership objects
                membership = Membership(
                    club=club.name,
                    club_abbreviation="EXT",  # External event marker
                    duration={"hours": 0, "minutes": 0},  # Duration will be calculated from event times
                    auth_details={}  # External events don't need auth details
                )
                user = User(
                    name="",
                    email="",
                    handicap=0,
                    memberships=[membership]
                )
                
                # Create temporary reservation for weather handling
                reservation = Reservation(
                    club=club,
                    user=user,
                    membership=membership,
                    start_time=start_time,
                    end_time=end_time,
                    players=[],
                    raw_data={}
                )
            
            # Get weather data using shared function
            weather_data = self._get_weather_for_reservation(reservation, weather_service)
            if not weather_data:
                return
            
            # Update event description with weather data
            description = event.get('description', '')
            if description:
                description = description + "\n\nWeather:\n"
            else:
                description = "Weather:\n"
            
            # Use get_event_description like WiseGolf0 events do
            weather_description = reservation.get_event_description(weather_data)
            if "\nWeather:\n" in weather_description:
                description = weather_description
            else:
                description += weather_description
            
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

    def add_event_to_calendar(self, calendar: Calendar, event: dict[str, Any]) -> None:
        """Add an event to the calendar."""
        calendar_event = Event()
        for key, value in event.items():
            calendar_event.add(key, value)
        calendar.add_component(calendar_event)

    def format_datetime(self, dt: datetime) -> str:
        """Format datetime for calendar."""
        return dt.strftime('%Y%m%dT%H%M%SZ') 