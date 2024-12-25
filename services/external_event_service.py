"""
Service for handling external golf events.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from zoneinfo import ZoneInfo
import yaml
import os

from icalendar import Calendar, Event, vText, vDatetime
from golfcal.utils.logging_utils import LoggerMixin
from golfcal.services.weather_service import WeatherService

# Define timezone constants
UTC_TZ = ZoneInfo('UTC')

class ExternalEventService(LoggerMixin):
    """Service for handling external golf events."""
    
    def __init__(self, weather_service: WeatherService):
        """Initialize service."""
        self.weather_service = weather_service
        self.seen_uids: Set[str] = set()  # Track seen UIDs for deduplication
        self.default_timezone = ZoneInfo('Europe/Helsinki')  # Default timezone if not specified
    
    def load_events(self, dev_mode: bool = False) -> List[Dict[str, Any]]:
        """Load external events from YAML file."""
        try:
            # Load regular events
            path = 'golfcal/config/external_events.yaml'
            events = []
            
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as file:
                    self.logger.info(f"Loading external events from {path}")
                    data = yaml.safe_load(file)
                    events.extend(data.get('events', []))
            
            # Load test events in dev mode
            if dev_mode:
                test_path = 'golfcal/config/test_events.yaml'
                if os.path.exists(test_path):
                    with open(test_path, 'r', encoding='utf-8') as file:
                        self.logger.info(f"Loading test events from {test_path}")
                        data = yaml.safe_load(file)
                        events.extend(data or [])
            
            self.logger.info(f"Found {len(events)} external events")
            return events
            
        except FileNotFoundError:
            self.logger.warning(f"No external events file found at {path}")
            return []
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing external events file: {e}")
            return []

    def process_events(self, person_name: str, dev_mode: bool = False) -> List[Event]:
        """Process external events for a person."""
        events = []
        for event_data in self.load_events(dev_mode):
            # Handle repeating events
            if 'repeat' in event_data:
                events.extend(self._process_recurring_event(event_data, person_name))
            else:
                # Single event
                event = self.create_event(event_data, person_name)
                if event:
                    events.append(event)
        return events

    def _process_recurring_event(self, event_data: Dict[str, Any], person_name: str) -> List[Event]:
        """Process a recurring event and return all instances."""
        events = []
        start_date = datetime.fromisoformat(event_data['start'])
        end_date = datetime.fromisoformat(event_data['repeat']['until'])
        current_date = start_date
        
        while current_date <= end_date:
            # Create event data for this instance
            instance_data = event_data.copy()
            instance_data['start'] = current_date.isoformat()
            
            # Calculate end time for this instance
            original_duration = (datetime.fromisoformat(event_data['end']) - 
                             datetime.fromisoformat(event_data['start']))
            instance_data['end'] = (current_date + original_duration).isoformat()
            
            # Create and add the event
            event = self.create_event(instance_data, person_name)
            if event:
                events.append(event)
            
            # Move to next occurrence
            if event_data['repeat']['frequency'] == 'weekly':
                current_date += timedelta(days=7)
            elif event_data['repeat']['frequency'] == 'monthly':
                # Move to same day next month
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
        
        return events

    def create_event(self, event_data: Dict[str, Any], person_name: str) -> Optional[Event]:
        """Create an event from external event data."""
        try:
            # Check if person is included in event
            if 'users' in event_data and person_name not in event_data['users']:
                return None

            # Get event timezone
            event_timezone = ZoneInfo(event_data.get('timezone', 'Europe/Helsinki'))
            
            # Parse start and end times
            if 'start_time' in event_data and 'end_time' in event_data:
                # Handle dynamic dates
                start = self._parse_dynamic_time(event_data['start_time'], event_timezone)
                end = self._parse_dynamic_time(event_data['end_time'], event_timezone)
            else:
                # Handle fixed dates
                start = datetime.strptime(event_data['start'], '%Y-%m-%dT%H:%M:%S')
                start = start.replace(tzinfo=event_timezone)
                end = datetime.strptime(event_data['end'], '%Y-%m-%dT%H:%M:%S')
                end = end.replace(tzinfo=event_timezone)
            
            duration_minutes = int((end - start).total_seconds() / 60)
            
            # Create event
            event = Event()
            event.add('summary', f"Golf: {event_data['name']}")
            event.add('dtstart', vDatetime(start))
            event.add('dtend', vDatetime(end))
            event.add('dtstamp', vDatetime(datetime.now(event_timezone)))
            
            # Create unique ID using coordinates if available
            uid = self._generate_unique_id(event_data, start, person_name)
            event.add('uid', vText(uid))
            
            # Skip if we've already seen this event
            if uid in self.seen_uids:
                self.logger.debug(f"Skipping duplicate external event with UID: {uid}")
                return None
            self.seen_uids.add(uid)
            
            # Add location if available
            if 'location' in event_data:
                event.add('location', vText(self._get_location(event_data)))
            
            # Add weather if coordinates are provided
            if 'coordinates' in event_data:
                try:
                    weather_data = self.weather_service.get_weather(
                        club=f"EXT_{event_data['name']}",
                        teetime=start,
                        coordinates=event_data['coordinates'],
                        duration_minutes=duration_minutes
                    )
                    # Format weather data
                    if weather_data:
                        event.add('description', vText(f"Weather:\n{weather_data}"))
                    else:
                        event.add('description', vText("No weather forecast available"))
                except Exception as e:
                    self.logger.error(f"Failed to fetch weather for external event: {e}")
                    event.add('description', vText("No weather forecast available"))
            else:
                event.add('description', vText(f"External golf event at {event_data['location']}"))
            
            return event
            
        except Exception as e:
            self.logger.error(f"Failed to create external event: {e}")
            return None
    
    def _generate_unique_id(self, event_data: Dict[str, Any], start: datetime, person_name: str) -> str:
        """
        Generate a unique ID for an external event.
        
        The UID format is: EXT_{name}_{date}_{time}_{location_hash}_{user_name}
        This ensures uniqueness while allowing deduplication of the same event.
        """
        # Format date and time components
        date_str = start.strftime('%Y%m%d')
        time_str = start.strftime('%H%M')
        
        # Create a location hash from coordinates or address
        if 'coordinates' in event_data:
            location_id = f"{event_data['coordinates']['lat']}_{event_data['coordinates']['lon']}"
        else:
            # Use first 8 chars of location as identifier
            location_id = event_data['location'][:8].replace(' ', '_')
        
        # Create unique ID that includes all necessary components
        return f"EXT_{event_data['name']}_{date_str}_{time_str}_{location_id}_{person_name}"
    
    def _get_location(self, event_data: Dict[str, Any]) -> str:
        """Format location string from event data."""
        location = event_data['location']
        if 'address' in event_data:
            location = f"{location}, {event_data['address']}"
        return location 

    def _parse_dynamic_time(self, time_str: str, timezone: ZoneInfo) -> datetime:
        """Parse a dynamic time string like 'tomorrow 10:00' or '3 days 09:30'."""
        try:
            # Split into date and time parts
            parts = time_str.split(' ')
            if len(parts) == 3 and parts[1] == 'days':
                # Format: "N days HH:MM"
                days = int(parts[0])
                time_part = parts[2]
            elif len(parts) == 2:
                # Format: "tomorrow HH:MM" or "today HH:MM"
                date_part = parts[0]
                time_part = parts[1]
            else:
                raise ValueError(f"Invalid time format: {time_str}")
            
            # Parse the time part (HH:MM)
            hour, minute = map(int, time_part.split(':'))
            
            # Get current date in the target timezone
            now = datetime.now(timezone)
            result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Handle relative date specifications
            if 'days' in time_str:
                result += timedelta(days=days)
            elif date_part == 'tomorrow':
                result += timedelta(days=1)
            elif date_part == 'today':
                pass  # Already set to today
            else:
                raise ValueError(f"Invalid date format: {date_part}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to parse dynamic time '{time_str}': {e}")
            raise ValueError(f"Invalid time format: {time_str}") 