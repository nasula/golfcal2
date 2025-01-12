"""
Command line interface for golf calendar application.
"""

import sys
import logging
import argparse
from typing import Optional
from zoneinfo import ZoneInfo

from golfcal2.config.settings import load_config, AppConfig
from golfcal2.utils.logging_utils import get_logger
from golfcal2.config.logging import setup_logging
from golfcal2.services.calendar_service import CalendarService
from golfcal2.services.reservation_service import ReservationService
from golfcal2.models.user import User
from golfcal2.config.error_aggregator import init_error_aggregator, ErrorAggregationConfig
from golfcal2.services.external_event_service import ExternalEventService
from golfcal2.services.weather_service import WeatherManager
from golfcal2.services.weather_database import WeatherResponseCache

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description='Golf calendar application for managing golf reservations and related weather data'
    )
    
    # Global options
    parser.add_argument(
        '-u', '--user',
        help='Process specific user only (default: process all configured users)'
    )
    parser.add_argument(
        '--dev',
        action='store_true',
        help='Run in development mode with additional debug output and test data'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging output'
    )
    parser.add_argument(
        '--log-file',
        help='Path to write log output (default: logs to stdout)'
    )
    
    # Commands
    subparsers = parser.add_subparsers(
        dest='command',
        help='Command to execute'
    )
    
    # Process command
    process_parser = subparsers.add_parser(
        'process',
        help='Process golf calendar by fetching reservations and updating calendar files'
    )
    process_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making any actual changes'
    )
    process_parser.add_argument(
        '--force',
        action='store_true',
        help='Force processing even if no changes are detected'
    )
    
    # List command
    list_parser = subparsers.add_parser(
        'list',
        help='List various types of information (courses, reservations, weather cache)'
    )
    list_subparsers = list_parser.add_subparsers(
        dest='list_type',
        help='Type of information to list'
    )
    
    # Courses subcommand
    courses_parser = list_subparsers.add_parser(
        'courses',
        help='List available golf courses'
    )
    courses_parser.add_argument(
        '--all',
        action='store_true',
        help='List all configured courses (default: only list courses for current user)'
    )
    
    # Weather cache subcommand
    weather_cache_parser = list_subparsers.add_parser(
        'weather-cache',
        help='List or manage weather cache contents from different weather services'
    )
    weather_cache_parser.add_argument(
        '--service',
        choices=['met', 'portuguese', 'iberian'],
        help='Filter by weather service (met=MET.no for Nordic countries, portuguese=IPMA for Portugal, iberian=AEMET for Spain)'
    )
    weather_cache_parser.add_argument(
        '--location',
        help='Filter by location coordinates (format: lat,lon, e.g., 60.1699,24.9384 for Helsinki)'
    )
    weather_cache_parser.add_argument(
        '--date',
        help='Filter by date in YYYY-MM-DD format (e.g., 2025-01-11). Shows data for the entire day'
    )
    weather_cache_parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format: human-readable text or machine-readable JSON (default: text)'
    )
    weather_cache_parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear the weather cache. If --service is specified, only clears that service\'s cache. Use with caution'
    )
    
    # Reservations subcommand
    reservations_parser = list_subparsers.add_parser(
        'reservations',
        help='List golf reservations with various filtering options'
    )
    reservations_parser.add_argument(
        '--active',
        action='store_true',
        help='Show only currently active reservations (ongoing at the time of listing)'
    )
    reservations_parser.add_argument(
        '--upcoming',
        action='store_true',
        help='Show only upcoming reservations (future dates)'
    )
    reservations_parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format: human-readable text or machine-readable JSON (default: text)'
    )
    reservations_parser.add_argument(
        '--days',
        type=int,
        default=1,
        help='Number of days to look ahead/behind (default: 1). Affects both past and future reservations'
    )
    
    # Check command
    check_parser = subparsers.add_parser(
        'check',
        help='Check application configuration and connectivity'
    )
    check_parser.add_argument(
        '--full',
        action='store_true',
        help='Perform a comprehensive check including API connectivity tests and cache validation'
    )
    
    return parser

def process_command(args: argparse.Namespace, logger: logging.Logger, config: AppConfig, is_dev: bool = False) -> int:
    """Process golf calendar."""
    try:
        # Get list of users to process
        users = [args.user] if args.user else config.users.keys()
        if not users:
            logger.error("No users configured")
            return 1
            
        if args.dry_run:
            logger.info("Dry run mode - no changes will be made")
        
        success = True
        for username in users:
            try:
                logger.info(f"Processing calendar for user {username}")
                
                reservation_service = ReservationService(username, config)
                calendar_service = CalendarService(config, dev_mode=is_dev)
                
                # Get reservations
                calendar, reservations = reservation_service.process_user(username, config.users[username])
                if not reservations:
                    logger.info(f"No reservations found for user {username}")
                else:
                    logger.info(f"Found {len(reservations)} reservations for user {username}")
                
                # Process calendar regardless of reservations
                if not args.dry_run:
                    user = User.from_config(username, config.users[username])
                    calendar_service.process_user_reservations(user, reservations)
                    logger.info(f"Calendar processed successfully for user {username}")
                
            except Exception as e:
                logger.error(f"Failed to process calendar for user {username}: {e}", exc_info=True)
                success = False
                continue
        
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"Failed to process calendars: {e}", exc_info=True)
        return 1

def list_command(args: argparse.Namespace, logger: logging.Logger, config: AppConfig) -> int:
    """List golf courses or reservations."""
    try:
        if not args.list_type:
            logger.error("Please specify what to list: 'courses', 'reservations', or 'weather-cache'")
            return 1
            
        # Initialize weather manager if needed for reservations
        weather_manager = None
        if args.list_type == 'reservations':
            weather_manager = WeatherManager(ZoneInfo(config.timezone), ZoneInfo('UTC'), config)
        
        if args.list_type == 'weather-cache':
            logger.info("Listing weather cache contents")
            import json
            from datetime import datetime, timedelta
            import sqlite3
            
            # Initialize cache
            cache = WeatherResponseCache('weather_cache.db')
            
            # Handle clear command
            if args.clear:
                try:
                    deleted = cache.cleanup_expired()
                    logger.info(f"Removed {deleted} expired weather cache entries")
                    return 0
                except Exception as e:
                    logger.error(f"Failed to clear weather cache: {e}")
                    return 1
            
            # TODO: Implement listing of cache contents
            logger.warning("Listing cache contents not yet implemented")
            return 0

        elif args.list_type == 'courses':
            # Get list of users to process
            users = [args.user] if args.user else config.users.keys()
            if not users:
                logger.error("No users configured")
                return 1
                
            success = True
            for username in users:
                try:
                    logger.info(f"Listing courses for user {username}")
                    reservation_service = ReservationService(username, config)
                    courses = reservation_service.list_courses(include_all=args.all)
                    
                    if not courses:
                        logger.info(f"No courses found for user {username}")
                        continue
                        
                    if len(users) > 1:
                        print(f"\nCourses for {username}:")
                        print("-" * 40)
                    
                    for course in courses:
                        print(f"- {course}")
                        
                except Exception as e:
                    logger.error(f"Failed to list courses for user {username}: {e}", exc_info=True)
                    success = False
                    continue
                    
            return 0 if success else 1
                
        elif args.list_type == 'reservations':
            # Get list of users to process
            users = [args.user] if args.user else config.users.keys()
            if not users:
                logger.error("No users configured")
                return 1
                
            success = True
            for username in users:
                try:
                    logger.info(f"Listing reservations for user {username}")
                    
                    # Initialize reservation service
                    reservation_service = ReservationService(username, config)
                    
                    # Get regular reservations
                    reservations = reservation_service.list_reservations(
                        active_only=args.active,
                        upcoming_only=args.upcoming,
                        days=args.days
                    )
                    
                    # Initialize error aggregator before getting external events
                    from golfcal2.config.error_aggregator import init_error_aggregator
                    from golfcal2.config.logging_config import load_logging_config
                    logging_config = load_logging_config()
                    init_error_aggregator(logging_config.error_aggregation)
                    
                    # Get external events
                    calendar_service = CalendarService(config, dev_mode=args.dev)
                    external_events = calendar_service.external_event_service.process_events(username, dev_mode=args.dev)
                    
                    if not reservations and not external_events:
                        logger.info(f"No reservations or events found for user {username}")
                        continue
                    
                    if args.format == 'json':
                        import json
                        # Convert reservations to JSON-serializable format
                        data = {
                            username: {
                                "reservations": [r.to_dict() for r in reservations],
                                "external_events": [
                                    {
                                        "summary": event.get("summary", "Unknown Event"),
                                        "start": event.get("dtstart").dt.isoformat() if event.get("dtstart") else None,
                                        "end": event.get("dtend").dt.isoformat() if event.get("dtend") else None,
                                        "location": event.get("location", ""),
                                        "description": event.get("description", "")
                                    }
                                    for event in external_events
                                ]
                            }
                        }
                        print(json.dumps(data, indent=2))
                    else:
                        if len(users) > 1:
                            print(f"\nReservations for {username}:")
                            print("=" * 60)
                        
                        # Print regular reservations
                        if reservations:
                            if len(users) == 1:
                                print("\nReservations:")
                                print("=" * 60)
                            for reservation in reservations:
                                # Get weather data for the reservation
                                weather_data = None
                                try:
                                    if reservation.club and reservation.club.club_details and 'coordinates' in reservation.club.club_details:
                                        weather_response = weather_manager.get_weather(
                                            lat=reservation.club.club_details['coordinates']['lat'],
                                            lon=reservation.club.club_details['coordinates']['lon'],
                                            start_time=reservation.start_time,
                                            end_time=reservation.end_time,
                                            club=reservation.club.name
                                        )
                                        if weather_response:
                                            weather_data = weather_response.data
                                except Exception as e:
                                    logger.warning(f"Failed to get weather data for reservation: {e}")

                                # Format times
                                start_str = reservation.start_time.strftime('%Y-%m-%d %H:%M')
                                end_str = reservation.end_time.strftime('%H:%M')
                                
                                # Print reservation details
                                print(f"{start_str} - {end_str}: {reservation.club.name}")
                                if reservation.club.address:
                                    print(f"Location: {reservation.club.address}")
                                
                                # Print players
                                players_str = ", ".join([f"{p.name} (HCP: {p.handicap})" for p in reservation.players])
                                print(f"Players: {players_str}")
                                
                                # Print weather if available
                                if weather_data:
                                    weather_str = reservation._format_weather_data(weather_data)
                                    print(f"Weather: {weather_str}")
                                
                                print("-" * 60)
                        
                        # Print external events
                        if external_events:
                            if reservations:  # Add extra newline if we printed reservations
                                print()
                            if len(users) == 1:
                                print("External Events:")
                                print("=" * 60)
                            for event in external_events:
                                start = event.get("dtstart").dt
                                end = event.get("dtend").dt if event.get("dtend") else None
                                
                                # Format times
                                start_str = start.strftime('%Y-%m-%d %H:%M')
                                end_str = end.strftime('%H:%M') if end else "?"
                                
                                # Print event details
                                print(f"{start_str} - {end_str}: {event.get('summary', 'Unknown Event')}")
                                if event.get("location"):
                                    print(f"Location: {event.get('location')}")
                                if event.get("description"):
                                    print(f"Details: {event.get('description')}")
                                print("-" * 60)
                                
                except Exception as e:
                    logger.error(f"Failed to list reservations for user {username}: {e}", exc_info=True)
                    success = False
                    continue
                    
            return 0 if success else 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to list {args.list_type}: {e}", exc_info=True)
        return 1

def check_command(args: argparse.Namespace, logger: logging.Logger, config: AppConfig) -> int:
    """Check configuration."""
    try:
        # Get list of users to check
        users = [args.user] if args.user else config.users.keys()
        if not users:
            logger.error("No users configured")
            return 1
            
        success = True
        for username in users:
            try:
                logger.info(f"Checking configuration for user {username}")
                
                if args.full:
                    logger.info("Performing full configuration check")
                    # TODO: Implement full check
                
                # Basic check
                reservation_service = ReservationService(username, config)
                calendar_service = CalendarService(config)
                
                if reservation_service.check_config() and calendar_service.check_config():
                    logger.info(f"Configuration check passed for user {username}")
                else:
                    logger.error(f"Configuration check failed for user {username}")
                    success = False
                    
            except Exception as e:
                logger.error(f"Failed to check configuration for user {username}: {e}", exc_info=True)
                success = False
                continue
                
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"Failed to check configuration: {e}", exc_info=True)
        return 1

def cleanup_weather_cache(args):
    """Clean up expired weather cache entries."""
    try:
        cache = WeatherResponseCache('weather_cache.db')
        deleted = cache.cleanup_expired()
        print(f"Removed {deleted} expired weather cache entries")
    except Exception as e:
        print(f"Error cleaning up weather cache: {e}", file=sys.stderr)
        return 1
    return 0

def main() -> int:
    """Main entry point."""
    try:
        # Parse arguments
        parser = create_parser()
        args = parser.parse_args()
        
        # Load configuration
        config = load_config()
        
        # Set up logging
        setup_logging(config, dev_mode=args.dev, verbose=args.verbose, log_file=args.log_file)
        logger = get_logger(__name__)
        
        # Initialize error aggregator
        error_config = ErrorAggregationConfig(
            enabled=True,
            report_interval=config.get('ERROR_REPORT_INTERVAL', 3600),
            error_threshold=config.get('ERROR_THRESHOLD', 5),
            time_threshold=config.get('ERROR_TIME_THRESHOLD', 300),  # 5 minutes
            categorize_by=['service', 'error_type']  # Categorize errors by service and type
        )
        init_error_aggregator(error_config)
        
        # Initialize services
        weather_manager = WeatherManager(ZoneInfo(config.timezone), ZoneInfo('UTC'), config)
        calendar_service = CalendarService(config)
        external_event_service = ExternalEventService(weather_manager, config)
        
        # Execute command
        if not args.command:
            parser.print_help()
            return 1
        elif args.command == 'process':
            return process_command(args, logger, config, args.dev)
        elif args.command == 'list':
            return list_command(args, logger, config)
        elif args.command == 'check':
            return check_command(args, logger, config)
        else:
            logger.error(f"Unknown command: {args.command}")
            return 1
            
    except Exception as e:
        logger = get_logger(__name__)
        logger.exception("Unhandled exception")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 