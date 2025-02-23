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
from golfcal2.services.reservation_service import ReservationService
from golfcal2.models.user import User
from golfcal2.utils.cli_utils import CLIContext, CLIBuilder, add_common_options
from golfcal2.server import HealthCheckServer
from golfcal2.metrics import Metrics, Timer, track_time
from golfcal2.config.logging import load_logging_config

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
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode - no changes will be made')
    parser.add_argument('--list-only', action='store_true', help='Only list events, do not write calendar')
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
        
        # Process each user's reservations
        for user_name, user_config in calendar_service.config.users.items():
            try:
                # Create user object
                user = User.from_config(user_name, dict(user_config))
                
                # Create reservation service for this user
                reservation_service = ReservationService(user_name, calendar_service.config)
                
                # Get reservations for next 7 days
                reservations = reservation_service.list_reservations(days=7)
                
                # Convert reservations to events
                for reservation in reservations:
                    event_time = reservation.start_time
                    event_uid = reservation.uid
                    
                    if not event_time or not event_uid:
                        continue
                        
                    if service_state.needs_processing(event_uid, event_time, now):
                        if not next_event_time or event_time < next_event_time:
                            next_event_time = event_time
                            next_event_uid = event_uid
                            
            except Exception as e:
                logger = get_logger(__name__)
                logger.error(f"Error processing user {user_name}: {e}", exc_info=True)
                continue
    
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
        # Initialize metrics first
        metrics = Metrics()

        # Initialize configuration
        config_manager = ConfigurationManager()
        args = create_args()
        
        config = config_manager.load_config(dev_mode=args.dev, verbose=args.verbose)
        
        # Set up logging with proper configuration
        logging_config = load_logging_config()
        logging_config.default_level = "INFO"  # Set default level to INFO
        
        # Set up logging with the full configuration
        setup_logging(
            config,
            dev_mode=args.dev,
            verbose=args.verbose,
            log_file=None,  # Don't use file logging
            logging_config=logging_config  # Use the logging config we set up earlier
        )
        
        logger = get_logger(__name__)
        
        # Initialize error aggregator with configuration from logging_config
        error_config = ErrorAggregationConfig(
            enabled=logging_config.error_aggregation.enabled,
            report_interval=logging_config.error_aggregation.report_interval,
            error_threshold=logging_config.error_aggregation.error_threshold,
            time_threshold=logging_config.error_aggregation.time_threshold,
            categorize_by=logging_config.error_aggregation.categorize_by
        )
        init_error_aggregator(error_config)
        
        logger.info("Starting GolfCal2 service")
        
        # Start health check server
        health_server = HealthCheckServer(args.host, args.port)
        try:
            health_server.start()
        except Exception as e:
            logger.error(f"Failed to start health check server: {e}")
            # Continue even if health check server fails
        
        # Initialize services and state
        weather_service = WeatherService(
            config=config
        )
        
        calendar_service = CalendarService(
            config=config,
            weather_service=weather_service
        )
        
        external_event_service = ExternalEventService(
            weather_service=weather_service,
            config=config
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
                        # Process calendars for all configured users
                        for user_name, user_config in config.users.items():
                            try:
                                logger.info(f"Processing calendar for user {user_name}")
                                args.user = user_name  # Set current user
                                ctx = CLIContext(args=args, logger=logger, config=config, parser=parser)
                                logger.info("Processing external events")
                                external_events = external_event_service.process_events(user_name, dev_mode=args.dev)
                                logger.info(f"Found {len(external_events)} external events")
                                
                                # Create calendar service with external events
                                calendar_service = CalendarService(
                                    config=config,
                                    weather_service=weather_service,
                                    dev_mode=args.dev,
                                    external_event_service=external_event_service  # Pass the service directly
                                )
                                
                                user = User.from_config(user_name, dict(user_config))
                                reservation_service = ReservationService(user_name, config)
                                reservations = reservation_service.list_reservations()
                                
                                # Process calendar with both reservations and external events
                                calendar = calendar_service.process_user_reservations(user, reservations)
                                
                                metrics.increment("calendar_processing_success")
                                logger.info(f"Calendar processing completed successfully for user {user_name}")
                            except Exception as e:
                                logger.error(f"Error processing calendar for user {user_name}: {e}", exc_info=True)
                                metrics.increment("calendar_processing_errors")
                                continue
                    
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