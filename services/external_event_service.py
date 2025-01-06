"""
Service for handling external golf events.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from zoneinfo import ZoneInfo
import yaml
import os
from pathlib import Path

from icalendar import Event
from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.services.weather_service import WeatherService
from golfcal2.services.calendar.builders import ExternalEventBuilder

class ExternalEventService(LoggerMixin):
    """Service for handling external golf events."""
    
    def __init__(self, weather_service: WeatherService):
        """Initialize service."""
        self.weather_service = weather_service
        self.seen_uids: Set[str] = set()  # Track seen UIDs for deduplication
        self.default_timezone = ZoneInfo('Europe/Helsinki')  # Default timezone if not specified
        self.event_builder = ExternalEventBuilder(weather_service)
        
        # Get config directory path relative to this file
        self.config_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'config'
    
    def load_events(self, dev_mode: bool = False) -> List[Dict[str, Any]]:
        """Load external events from YAML file."""
        try:
            # Load regular events
            events = []
            events_file = self.config_dir / 'external_events.yaml'
            
            if events_file.exists():
                with open(events_file, 'r', encoding='utf-8') as file:
                    self.logger.info(f"Loading external events from {events_file}")
                    data = yaml.safe_load(file)
                    events.extend(data.get('events', []))
            
            # Load test events in dev mode
            if dev_mode:
                test_file = self.config_dir / 'test_events.yaml'
                if test_file.exists():
                    with open(test_file, 'r', encoding='utf-8') as file:
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

    def process_events(self, person_name: str, dev_mode: bool = False) -> List[Event]:
        """Process external events for a person."""
        events = []
        
        # Calculate cutoff time (24 hours ago) with timezone
        now = datetime.now(self.default_timezone)
        cutoff_time = now - timedelta(hours=24)
        self.logger.debug(f"Using cutoff time: {cutoff_time}")
        
        for event_data in self.load_events(dev_mode):
            # Handle repeating events
            if 'repeat' in event_data:
                events.extend(self._process_recurring_event(event_data, person_name, cutoff_time))
            else:
                # Single event
                event = self._create_event(event_data, person_name, cutoff_time)
                if event:
                    events.append(event)
        return events

    def _process_recurring_event(
        self,
        event_data: Dict[str, Any],
        person_name: str,
        cutoff_time: datetime
    ) -> List[Event]:
        """Process a recurring event and return all instances."""
        events = []
        # Get event timezone
        event_timezone = ZoneInfo(event_data.get('timezone', 'Europe/Helsinki'))
        
        # Parse dates with timezone
        start_date = datetime.fromisoformat(event_data['start']).replace(tzinfo=event_timezone)
        end_date = datetime.fromisoformat(event_data['repeat']['until']).replace(tzinfo=event_timezone)
        current_date = start_date
        
        while current_date <= end_date:
            # Skip if older than 24 hours
            if current_date < cutoff_time:
                self.logger.debug(f"Skipping old recurring event: {current_date}")
                # Move to next occurrence
                if event_data['repeat']['frequency'] == 'weekly':
                    current_date += timedelta(days=7)
                elif event_data['repeat']['frequency'] == 'monthly':
                    # Move to same day next month
                    if current_date.month == 12:
                        current_date = current_date.replace(year=current_date.year + 1, month=1)
                    else:
                        current_date = current_date.replace(month=current_date.month + 1)
                continue
            
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
            event = self._create_event(instance_data, person_name, cutoff_time)
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
        event_data: Dict[str, Any],
        person_name: str,
        cutoff_time: datetime
    ) -> Optional[Event]:
        """Create an event from external event data."""
        try:
            # Get event timezone
            event_timezone = ZoneInfo(event_data.get('timezone', 'Europe/Helsinki'))
            
            # Parse start and end times
            if 'start_time' in event_data and 'end_time' in event_data:
                # Handle dynamic dates
                start = self._parse_dynamic_time(event_data['start_time'], event_timezone)
                end = self._parse_dynamic_time(event_data['end_time'], event_timezone)
            else:
                # Handle fixed dates - use fromisoformat for better timezone handling
                try:
                    # First try parsing with fromisoformat in case we have timezone info
                    start = datetime.fromisoformat(event_data['start'])
                    end = datetime.fromisoformat(event_data['end'])
                    
                    # Only set timezone if it's not already set
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=event_timezone)
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=event_timezone)
                except ValueError as e:
                    self.logger.error(f"Failed to parse event dates: {e}")
                    return None
            
            # Skip if older than 24 hours
            if start < cutoff_time:
                self.logger.debug(f"Skipping old external event: {start}")
                return None
            
            # Create event using builder
            event = self.event_builder.build(event_data, person_name, start, end)
            
            # Skip if we've already seen this event
            if event and event.get('uid') in self.seen_uids:
                self.logger.debug(f"Skipping duplicate external event with UID: {event.get('uid')}")
                return None
            
            if event:
                self.seen_uids.add(event.get('uid'))
            
            return event
            
        except Exception as e:
            self.logger.error(f"Failed to create external event: {e}")
            return None

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