"""
Service for handling external golf events.
"""

import os
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from icalendar import Event

from golfcal2.config.types import AppConfig
from golfcal2.services.calendar.builders import ExternalEventBuilder
from golfcal2.services.weather_service import WeatherService
from golfcal2.utils.logging_utils import EnhancedLoggerMixin


class ExternalEventService(EnhancedLoggerMixin):
    """Service for handling external golf events."""
    
    def __init__(self, weather_service: WeatherService, config: AppConfig):
        """Initialize service."""
        super().__init__()
        self.weather_service = weather_service
        self.config = config
        
        # Initialize event builder
        self.event_builder = ExternalEventBuilder(weather_service, config)
        
        # Configure logger
        self.set_log_context(service="external_events")
        
        self.seen_uids: set[str] = set()  # Track seen UIDs for deduplication
        # Ensure we're using ZoneInfo for default timezone
        self.default_timezone = ZoneInfo('Europe/Helsinki')  # Default timezone if not specified
        
        # Get config directory path relative to this file
        self.config_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'config'
        
        # Cache for processed events
        self._processed_events: list[Event] = []
        self._last_process_time: datetime | None = None
    
    def get_events(self) -> list[Event]:
        """Get the list of processed events.
        
        Returns:
            List of processed events
        """
        return self._processed_events
    
    def load_events(self, dev_mode: bool = False) -> list[dict[str, Any]]:
        """Load external events from YAML file."""
        try:
            # Load regular events
            events = []
            events_file = self.config_dir / 'external_events.yaml'
            
            if events_file.exists():
                with open(events_file, encoding='utf-8') as file:
                    self.logger.info(f"Loading external events from {events_file}")
                    data = yaml.safe_load(file)
                    events.extend(data.get('events', []))
            
            # Load test events in dev mode
            if dev_mode:
                test_file = self.config_dir / 'test_events.yaml'
                if test_file.exists():
                    with open(test_file, encoding='utf-8') as file:
                        self.logger.info(f"Loading test events from {test_file}")
                        data = yaml.safe_load(file)
                        events.extend(data or [])
            
            self.logger.info(f"Found {len(events)} external events")
            return events
            
        except FileNotFoundError:
            self.logger.warning(f"No external events file found at {events_file}")
            return []
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing external events file: {e}")
            return []

    def process_events(self, user_name: str, dev_mode: bool = False) -> list[Event]:
        """Process external events for a user."""
        try:
            events = []
            for event_data in self.load_events(dev_mode):
                # Skip events that don't include this user
                if 'users' in event_data and user_name not in event_data['users']:
                    continue

                # Process recurring events
                if 'repeat' in event_data:
                    recurring_events = self._process_recurring_event(event_data, user_name)
                    events.extend(recurring_events)
                else:
                    # Process single event
                    event = self._create_event(event_data, user_name)
                    if event:
                        events.append(event)
            
            return events
            
        except Exception as e:
            self.logger.error(f"Failed to process external events: {e!s}")
            return []

    def _process_recurring_event(
        self,
        event_data: dict[str, Any],
        person_name: str
    ) -> list[Event]:
        """Process a recurring event and return all instances."""
        events = []
        # Get event timezone
        event_timezone = ZoneInfo(event_data.get('timezone', 'Europe/Helsinki'))
        
        # Parse dates with timezone
        start_date = datetime.fromisoformat(event_data['start']).replace(tzinfo=event_timezone)
        end_date = datetime.fromisoformat(event_data['repeat']['until']).replace(tzinfo=event_timezone)
        current_date = start_date
        
        while current_date <= end_date:
            # Create event data for this instance
            instance_data = event_data.copy()
            # Keep timezone info by using isoformat
            instance_data['start'] = current_date.isoformat()
            
            # Calculate end time for this instance
            original_duration = (datetime.fromisoformat(event_data['end']).replace(tzinfo=event_timezone) - 
                             datetime.fromisoformat(event_data['start']).replace(tzinfo=event_timezone))
            end_time = current_date + original_duration
            instance_data['end'] = end_time.isoformat()
            
            # Create and add the event
            event = self._create_event(instance_data, person_name)
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

    def _create_event(
        self,
        event_data: dict[str, Any],
        person_name: str
    ) -> Event | None:
        """Create an event from external event data."""
        try:
            # Parse start and end times
            start = self._parse_datetime(event_data['start'])
            end = self._parse_datetime(event_data['end'])

            # Skip past events
            now = datetime.now(start.tzinfo)
            if end < now:
                self.logger.debug(f"Skipping past event: {event_data.get('name', 'Unknown')} (ended at {end})")
                return None

            # Create event using builder
            event = self.event_builder.build(event_data, person_name, start, end)
            if event:
                self.logger.debug(f"Created external event: {event.get('summary')}")
            return event
            
        except Exception as e:
            self.logger.error(f"Failed to create external event: {e!s}")
            return None

    def _parse_datetime(self, datetime_str: str) -> datetime:
        """Parse datetime string to datetime object."""
        dt = datetime.fromisoformat(datetime_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.default_timezone)
        return dt

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
            self.logger.error(f"Failed to parse dynamic time '{time_str}': {e}", exc_info=True)
            raise ValueError(f"Invalid time format: {time_str}") 