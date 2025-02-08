#!/usr/bin/env python3

import time
import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, Set, Optional, Tuple, List
from dataclasses import dataclass, field
import logging
import sys

from golfcal2.cli import ProcessCommands
from golfcal2.config.settings import ConfigurationManager
from golfcal2.utils.logging_utils import get_logger
from golfcal2.config.logging import setup_logging
from golfcal2.config.error_aggregator import init_error_aggregator, ErrorAggregationConfig
from golfcal2.services import WeatherService, CalendarService, ExternalEventService
from golfcal2.services.calendar.builders.calendar_builder import CalendarBuilder
from golfcal2.models.user import User
from golfcal2.utils.cli_utils import CLIContext, CLIBuilder, add_common_options
from golfcal2.server import HealthCheckServer
from golfcal2.metrics import Metrics, Timer, track_time

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
        self._timezone: Optional[ZoneInfo] = None
        
    @property
    def timezone(self) -> ZoneInfo:
        """Get cached timezone instance."""
        if not self._timezone:
            config_manager = ConfigurationManager()
            self._timezone = config_manager.get_timezone(
                config_manager.config.global_config.get('timezone', 'UTC')
            )
        return self._timezone
        
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
        """Mark an event as processed based on current time."""
        state = self.processed_events.get(event_uid)
        if not state:
            state = EventState(start_time=event_time)
            self.processed_events[event_uid] = state
            
        time_to_event = event_time - current_time
        if time_to_event <= timedelta(minutes=15):
            state.fifteen_min_processed = True
        if time_to_event <= timedelta(minutes=30):
            state.thirty_min_processed = True
            
    def cleanup_old_events(self, current_time: datetime):
        """Remove processed events that are in the past."""
        to_remove = [
            uid for uid, state in self.processed_events.items()
            if state.start_time < current_time
        ]
        for uid in to_remove:
            del self.processed_events[uid]

def create_args() -> argparse.Namespace:
    """Create service arguments."""
    parser = argparse.ArgumentParser(description='GolfCal2 calendar processing service')
    parser.add_argument('--dev', action='store_true', help='Run in development mode')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--log-file', help='Path to log file')
    parser.add_argument('-u', '--user', help='Username to use for operations (default: from config)')
    parser.add_argument('--host', default='localhost', help='Host to bind health check server to')
    parser.add_argument('--port', type=int, default=8080, help='Port for health check server')
    return parser.parse_args()

@track_time("get_next_event_time")
def get_next_event_time(calendar_service: CalendarService, service_state: ServiceState) -> Tuple[Optional[datetime], Optional[str]]:
    """Get the next event time that needs processing."""
    next_event_time = None
    next_event_uid = None
    
    try:
        # Get all upcoming events
        now = datetime.now(service_state.timezone)
        end = now + timedelta(days=7)  # Look ahead 7 days
        
        for user in calendar_service.get_users():
            events = calendar_service.get_user_events(user, now, end)
            for event in events:
                event_time = event.get('start_time')
                event_uid = event.get('uid')
                
                if not event_time or not event_uid:
                    continue
                    
                if service_state.needs_processing(event_uid, event_time, now):
                    if not next_event_time or event_time < next_event_time:
                        next_event_time = event_time
                        next_event_uid = event_uid
    
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error getting next event time: {e}", exc_info=True)
    
    return next_event_time, next_event_uid

def get_next_processing_time(now: datetime, next_event: Optional[datetime] = None) -> datetime:
    """Calculate the next processing time.
    
    The service should process:
    1. At the start of every hour
    2. 30 minutes before an event
    3. 15 minutes before an event
    
    Returns the earliest applicable time.
    """
    # Always calculate next hour processing time
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    
    if not next_event:
        return next_hour
    
    # Calculate event-based processing times
    time_to_event = next_event - now
    
    if time_to_event <= timedelta(minutes=15):
        # Process immediately if within 15 minutes
        return now
    elif time_to_event <= timedelta(minutes=30):
        # Process at 15 minute mark
        process_at_15 = next_event - timedelta(minutes=15)
        return min(next_hour, process_at_15)
    else:
        # Process at 30 minute mark
        process_at_30 = next_event - timedelta(minutes=30)
        return min(next_hour, process_at_30)

def main():
    """Main service entry point."""
    try:
        # Initialize configuration
        config_manager = ConfigurationManager()
        args = create_args()
        
        # Force debug mode for the service
        args.dev = True
        args.verbose = True
        
        config = config_manager.load_config(dev_mode=args.dev, verbose=args.verbose)
        
        # Set up logging with service-specific file and force debug level
        setup_logging(config, dev_mode=True, verbose=True, log_file=args.log_file)
        logger = get_logger(__name__)
        logger.setLevel(logging.DEBUG)  # Ensure main logger is at DEBUG level
        
        # Set root logger to DEBUG
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Set all existing handlers to DEBUG level
        for handler in root_logger.handlers:
            handler.setLevel(logging.DEBUG)
        
        # Initialize error aggregator
        error_config = ErrorAggregationConfig(
            enabled=True,
            report_interval=config.global_config.get('ERROR_REPORT_INTERVAL', 3600),
            error_threshold=config.global_config.get('ERROR_THRESHOLD', 5),
            time_threshold=config.global_config.get('ERROR_TIME_THRESHOLD', 300),
            categorize_by=['service', 'message']
        )
        init_error_aggregator(error_config)
        
        logger.debug("Starting GolfCal2 service in debug mode")
        
        # Initialize metrics
        metrics = Metrics()
        
        # Start health check server
        health_server = HealthCheckServer(args.host, args.port)
        try:
            health_server.start()
        except Exception as e:
            logger.error(f"Failed to start health check server: {e}")
            # Continue even if health check server fails
        
        # Initialize services and state
        weather_service = WeatherService(
            config=config.global_config
        )
        
        # Pass the entire config object instead of just global_config
        calendar_service = CalendarService(
            config=config,
            weather_service=weather_service
        )
        
        service_state = ServiceState()
        
        # Create CLI parser for context
        cli_builder = CLIBuilder("GolfCal2 Service CLI")
        parser = cli_builder.build()
        add_common_options(parser)
        
        try:
            while True:
                try:
                    logger.debug("Starting calendar processing cycle")
                    logger.info("Starting calendar processing")
                    
                    with Timer("calendar_processing"):
                        # Process calendars
                        ctx = CLIContext(args=args, logger=logger, config=config, parser=parser)
                        ProcessCommands.process_calendar(ctx)
                        metrics.increment("calendar_processing_success")
                        logger.info("Calendar processing completed successfully")
                    
                    # Mark current event as processed if applicable
                    now = datetime.now(service_state.timezone)
                    if service_state.next_event_uid:
                        service_state.mark_processed(
                            service_state.next_event_uid,
                            service_state.next_event,
                            now
                        )
                        metrics.increment("events_processed")
                    
                    # Cleanup old event states
                    service_state.cleanup_old_events(now)
                    
                except Exception as e:
                    logger.error(f"Error in calendar processing: {e}", exc_info=True)
                    metrics.increment("calendar_processing_errors")
                
                # Get current time and next event time
                now = datetime.now(service_state.timezone)
                next_event, next_event_uid = get_next_event_time(calendar_service, service_state)
                
                # Update service state and metrics
                service_state.next_event = next_event
                service_state.next_event_uid = next_event_uid
                if next_event:
                    time_to_next = (next_event - now).total_seconds()
                    metrics.set_gauge("seconds_to_next_event", time_to_next)
                
                # Calculate time until next processing
                next_process = get_next_processing_time(now, next_event)
                sleep_seconds = (next_process - now).total_seconds()
                metrics.set_gauge("seconds_to_next_processing", sleep_seconds)
                
                if sleep_seconds > 0:
                    logger.debug(f"Next processing scheduled in {sleep_seconds:.0f} seconds")
                    logger.info(f"Sleeping for {sleep_seconds:.0f} seconds until next processing")
                    time.sleep(sleep_seconds)
                    
        finally:
            # Stop health check server
            if health_server:
                try:
                    health_server.stop()
                except Exception as e:
                    logger.error(f"Error stopping health check server: {e}")
            
    except Exception as e:
        logger = get_logger(__name__)
        logger.exception("Fatal error in service")
        metrics.increment("fatal_errors")
        return 1
        
    return 0

if __name__ == '__main__':
    sys.exit(main()) 