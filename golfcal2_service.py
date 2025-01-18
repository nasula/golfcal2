#!/usr/bin/env python3

import time
import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, Set, Optional
from dataclasses import dataclass, field

from golfcal2.cli import process_command
from golfcal2.config.settings import load_config
from golfcal2.utils.logging_utils import get_logger
from golfcal2.config.logging import setup_logging
from golfcal2.config.error_aggregator import init_error_aggregator, ErrorAggregationConfig
from golfcal2.services import WeatherManager, CalendarService, ExternalEventService

@dataclass
class EventState:
    """Track the state of an event's processing."""
    start_time: datetime
    thirty_min_processed: bool = False
    fifteen_min_processed: bool = False

class ServiceState:
    """Track the state of the calendar service."""
    def __init__(self):
        self.processed_events: Dict[str, EventState] = {}  # uid -> EventState
        self.calendar_mtimes: Dict[str, float] = {}  # path -> mtime
        self.next_event: Optional[datetime] = None
        self.next_event_uid: Optional[str] = None
        
    def needs_processing(self, event_uid: str, event_time: datetime, current_time: datetime) -> bool:
        """Check if an event needs processing at current_time."""
        if event_time < current_time:
            return False
            
        state = self.processed_events.get(event_uid)
        if not state:
            return True
            
        # Check if we need to process 30 or 15 minute marks
        time_to_event = event_time - current_time
        if time_to_event <= timedelta(minutes=30) and not state.thirty_min_processed:
            return True
        if time_to_event <= timedelta(minutes=15) and not state.fifteen_min_processed:
            return True
            
        return False
        
    def mark_processed(self, event_uid: str, event_time: datetime, current_time: datetime):
        """Mark appropriate processing flags for an event."""
        state = self.processed_events.get(event_uid)
        if not state:
            state = EventState(event_time)
            self.processed_events[event_uid] = state
            
        time_to_event = event_time - current_time
        if time_to_event <= timedelta(minutes=30):
            state.thirty_min_processed = True
        if time_to_event <= timedelta(minutes=15):
            state.fifteen_min_processed = True
            
    def cleanup_old_events(self, current_time: datetime):
        """Remove state for past events."""
        old_uids = [
            uid for uid, state in self.processed_events.items()
            if state.start_time < current_time
        ]
        for uid in old_uids:
            del self.processed_events[uid]

def create_args():
    """Create args object to match CLI interface."""
    args = argparse.Namespace()
    args.dev = False
    args.verbose = False
    args.log_file = str(Path('logs/service.log'))  # Service-specific log file
    args.command = 'process'  # Always use process command
    args.dry_run = False  # Add required CLI args
    args.user = None  # Add required CLI args
    return args

def get_next_event_time(calendar_service: CalendarService, service_state: ServiceState) -> tuple[Optional[datetime], Optional[str]]:
    """Get the time of the next upcoming event across all users."""
    next_event_time = None
    next_event_uid = None
    calendar_changed = False
    
    try:
        # Get all users from config
        users = calendar_service.config.users.values()
        
        # Check each user's calendar for upcoming events
        for user in users:
            calendar_path = calendar_service._get_calendar_path(user.name)
            if not calendar_path.exists():
                continue
                
            # Check if calendar has been modified
            current_mtime = calendar_path.stat().st_mtime
            last_mtime = service_state.calendar_mtimes.get(str(calendar_path))
            if last_mtime and current_mtime <= last_mtime:
                continue
                
            calendar_changed = True
            service_state.calendar_mtimes[str(calendar_path)] = current_mtime
            
            # Read and parse calendar
            with open(calendar_path, 'rb') as f:
                cal = calendar_service.calendar_builder.parse_calendar(f.read())
                for component in cal.walk('VEVENT'):
                    event_start = component.get('dtstart').dt
                    if isinstance(event_start, datetime):
                        # Convert to local timezone if needed
                        if event_start.tzinfo is None:
                            event_start = event_start.replace(tzinfo=calendar_service.utc_tz)
                        event_start = event_start.astimezone(calendar_service.local_tz)
                        
                        # Check if event is in the future and needs processing
                        now = datetime.now(calendar_service.local_tz)
                        event_uid = str(component.get('uid'))
                        if event_start > now and service_state.needs_processing(event_uid, event_start, now):
                            if next_event_time is None or event_start < next_event_time:
                                next_event_time = event_start
                                next_event_uid = event_uid
                                
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error getting next event time: {e}", exc_info=True)
    
    # Only update state if calendars changed or we found a new next event
    if calendar_changed or next_event_time != service_state.next_event:
        service_state.next_event = next_event_time
        service_state.next_event_uid = next_event_uid
        
    return next_event_time, next_event_uid

def get_next_processing_time(now: datetime, next_event: datetime = None) -> datetime:
    """Calculate the next processing time based on current time and next event."""
    # Always process at the start of each hour
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    
    if next_event is None:
        return next_hour
    
    # Check if we need to process 30 or 15 minutes before the event
    thirty_mins_before = next_event - timedelta(minutes=30)
    fifteen_mins_before = next_event - timedelta(minutes=15)
    
    # Find the earliest time that's still in the future
    processing_times = [
        time for time in [next_hour, thirty_mins_before, fifteen_mins_before]
        if time > now
    ]
    
    return min(processing_times) if processing_times else next_hour

def main():
    """Main service entry point."""
    try:
        # Load configuration
        config = load_config()
        
        # Set up logging with service-specific file
        args = create_args()
        setup_logging(config, dev_mode=args.dev, verbose=args.verbose, log_file=args.log_file)
        logger = get_logger(__name__)
        
        # Initialize error aggregator
        error_config = ErrorAggregationConfig(
            enabled=True,
            report_interval=config.get('ERROR_REPORT_INTERVAL', 3600),
            error_threshold=config.get('ERROR_THRESHOLD', 5),
            time_threshold=config.get('ERROR_TIME_THRESHOLD', 300),
            categorize_by=['service', 'message']  # Categorize errors by service and message
        )
        init_error_aggregator(error_config)
        
        logger.info("Starting GolfCal2 service")
        
        # Initialize services and state
        calendar_service = CalendarService(config, dev_mode=args.dev)
        service_state = ServiceState()
        
        while True:
            try:
                logger.info("Starting calendar processing")
                process_command(args, logger, config, is_dev=False)
                logger.info("Calendar processing completed successfully")
                
                # Mark current event as processed if applicable
                now = datetime.now(ZoneInfo(config.timezone))
                if service_state.next_event_uid:
                    service_state.mark_processed(
                        service_state.next_event_uid,
                        service_state.next_event,
                        now
                    )
                
                # Cleanup old event states
                service_state.cleanup_old_events(now)
                
            except Exception as e:
                logger.error(f"Error in calendar processing: {e}", exc_info=True)
            
            # Get current time and next event time
            now = datetime.now(ZoneInfo(config.timezone))
            next_event, next_event_uid = get_next_event_time(calendar_service, service_state)
            
            # Calculate time until next processing
            next_process = get_next_processing_time(now, next_event)
            sleep_seconds = (next_process - now).total_seconds()
            
            if next_event:
                logger.info(
                    f"Next event at {next_event.strftime('%Y-%m-%d %H:%M:%S %Z')}, "
                    f"next processing at {next_process.strftime('%Y-%m-%d %H:%M:%S %Z')}"
                )
            else:
                logger.info(f"No upcoming events, next processing at {next_process.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            logger.info(f"Sleeping for {sleep_seconds:.0f} seconds")
            time.sleep(sleep_seconds)
            
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.error(f"Fatal error in service: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    main() 