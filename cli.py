"""
Command line interface for golf calendar application.
"""

import sys
import logging
import argparse
from typing import Optional
from zoneinfo import ZoneInfo
import os
from pathlib import Path

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
    
    # Get command
    get_parser = subparsers.add_parser(
        'get',
        help='Get various types of data (weather, etc.)'
    )
    get_subparsers = get_parser.add_subparsers(
        dest='get_type',
        help='Type of data to get'
    )
    
    # Weather subcommand
    weather_parser = get_subparsers.add_parser(
        'weather',
        help='Get weather data for a specific location'
    )
    weather_parser.add_argument(
        '--lat',
        type=float,
        required=True,
        help='Latitude of the location (e.g., 37.0 for Algarve)'
    )
    weather_parser.add_argument(
        '--lon',
        type=float,
        required=True,
        help='Longitude of the location (e.g., -8.0 for Algarve)'
    )
    weather_parser.add_argument(
        '--service',
        choices=['met', 'portuguese', 'iberian'],
        help='Weather service to use (met=MET.no for Nordic countries, portuguese=IPMA for Portugal, iberian=AEMET for Spain)'
    )
    weather_parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format: human-readable text or machine-readable JSON (default: text)'
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
                except sqlite3.Error as e:
                    logger.error(f"Database error while clearing weather cache: {e}")
                    return 1
                except Exception as e:
                    logger.error(f"Failed to clear weather cache: {e}")
                    return 1
            
            # List cache contents
            try:
                entries = cache.list_entries()
                if not entries:
                    logger.info("Weather cache is empty")
                    return 0
                
                if args.format == 'json':
                    print(json.dumps(entries, indent=2, default=str))
                else:
                    print("\nWeather Cache Contents")
                    print("=" * 60)
                    for entry in entries:
                        print(f"\nService: {entry['service']}")
                        print(f"Location: {entry['location']}")
                        print(f"Start Time: {entry['start_time']}")
                        print(f"End Time: {entry['end_time']}")
                        print(f"Expires: {entry['expires']}")
                        print("-" * 60)
                return 0
                
            except sqlite3.Error as e:
                logger.error(f"Database error while listing weather cache: {e}")
                return 1
            except Exception as e:
                logger.error(f"Failed to list weather cache: {e}")
                return 1

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
    """Check configuration and system health."""
    try:
        # Get list of users to check
        users = [args.user] if args.user else config.users.keys()
        if not users:
            logger.error("No users configured")
            return 1
            
        success = True
        
        # Basic configuration checks
        logger.info("Checking basic configuration")
        
        # Check directory permissions
        dirs_to_check = [
            ('ICS', config.get('ics_dir', 'ics')),
            ('Logs', config.get('logs_dir', 'logs')),
            ('Config', config.get('config_dir', 'config'))
        ]
        
        for dir_name, dir_path in dirs_to_check:
            try:
                if os.path.isabs(dir_path):
                    path = Path(dir_path)
                else:
                    workspace_dir = Path(__file__).parent.parent
                    path = workspace_dir / dir_path
                    
                if not path.exists():
                    try:
                        path.mkdir(parents=True, exist_ok=True)
                        logger.info(f"Created {dir_name} directory: {path}")
                    except Exception as e:
                        logger.error(f"Failed to create {dir_name} directory {path}: {str(e)}")
                        success = False
                        continue
                
                # Check if directory is writable
                if not os.access(path, os.W_OK):
                    logger.error(f"{dir_name} directory {path} is not writable")
                    success = False
            except Exception as e:
                logger.error(f"Error checking {dir_name} directory: {str(e)}")
                success = False
        
        # Check weather cache
        try:
            cache = WeatherResponseCache(os.path.join(config.get('data_dir', 'data'), 'weather_cache.db'))
            if not cache.check_health():
                logger.error("Weather cache health check failed")
                success = False
        except Exception as e:
            logger.error(f"Failed to check weather cache: {str(e)}")
            success = False
        
        # Check user configurations
        for username in users:
            try:
                logger.info(f"Checking configuration for user {username}")
                user_config = config.users.get(username)
                
                if not user_config:
                    logger.error(f"No configuration found for user {username}")
                    success = False
                    continue
                
                # Check required user fields
                required_fields = ['memberships']
                for field in required_fields:
                    if field not in user_config:
                        logger.error(f"Missing required field '{field}' in user config for {username}")
                        success = False
                
                # Check club memberships
                for membership in user_config.get('memberships', []):
                    if 'club' not in membership:
                        logger.error(f"Missing 'club' in membership config for user {username}")
                        success = False
                        continue
                        
                    if 'auth_details' not in membership:
                        logger.error(f"Missing 'auth_details' in membership config for club {membership['club']} for user {username}")
                        success = False
                
                # Initialize services for basic checks
                reservation_service = ReservationService(username, config)
                calendar_service = CalendarService(config)
                
                if not reservation_service.check_config():
                    logger.error(f"Reservation service configuration check failed for user {username}")
                    success = False
                
                if not calendar_service.check_config():
                    logger.error(f"Calendar service configuration check failed for user {username}")
                    success = False
                
                # Perform comprehensive API checks if requested
                if args.full:
                    logger.info(f"Performing full configuration check for user {username}")
                    
                    # Check weather services
                    weather_manager = WeatherManager(ZoneInfo(config.timezone), ZoneInfo('UTC'), config)
                    for service_name, service in weather_manager.services.items():
                        try:
                            service.check_availability()
                            logger.info(f"Weather service {service_name} is available")
                        except Exception as e:
                            logger.error(f"Weather service {service_name} check failed: {str(e)}")
                            success = False
                    
                    # Check club APIs
                    for membership in user_config.get('memberships', []):
                        club_name = membership.get('club')
                        if not club_name:
                            continue
                            
                        try:
                            club = reservation_service.get_club(club_name)
                            if club:
                                club.check_availability()
                                logger.info(f"Club API for {club_name} is available")
                            else:
                                logger.error(f"Club {club_name} not found in configuration")
                                success = False
                        except Exception as e:
                            logger.error(f"Club API check failed for {club_name}: {str(e)}")
                            success = False
                    
                    # Check external calendar services if configured
                    if calendar_service.external_event_service:
                        try:
                            calendar_service.external_event_service.check_availability()
                            logger.info("External calendar services are available")
                        except Exception as e:
                            logger.error(f"External calendar services check failed: {str(e)}")
                            success = False
                
            except Exception as e:
                logger.error(f"Failed to check configuration for user {username}: {e}", exc_info=True)
                success = False
                continue
        
        if success:
            logger.info("All configuration checks passed successfully")
        else:
            logger.error("One or more configuration checks failed")
            
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

def get_command(args: argparse.Namespace, logger: logging.Logger, config: AppConfig) -> int:
    """Get various types of data."""
    try:
        if not args.get_type:
            logger.error("Please specify what to get: 'weather'")
            return 1
            
        if args.get_type == 'weather':
            logger.info(f"Getting weather data for location ({args.lat}, {args.lon})")
            
            # Initialize weather manager
            weather_manager = WeatherManager(ZoneInfo(config.timezone), ZoneInfo('UTC'), config)
            
            # Get weather data for the next 24 hours
            from datetime import datetime, timedelta
            now = datetime.now(ZoneInfo(config.timezone))
            end = now + timedelta(hours=24)
            
            try:
                response = weather_manager.get_weather(args.lat, args.lon, now, end)
                if not response or not response.data:
                    logger.error("No weather data found")
                    return 1
                
                if args.format == 'json':
                    import json
                    print(json.dumps({
                        'data': [w.to_dict() for w in response.data],
                        'expires': response.expires.isoformat() if response.expires else None
                    }, indent=2, default=str))
                else:
                    print("\nWeather Forecast")
                    print("---------------")
                    for w in response.data:
                        print(f"\nTime: {w.elaboration_time}")
                        print(f"Temperature: {w.temperature}°C")
                        print(f"Precipitation: {w.precipitation} mm")
                        print(f"Wind: {w.wind_speed} m/s from {w.wind_direction}°")
                        if w.precipitation_probability is not None:
                            print(f"Precipitation probability: {w.precipitation_probability}%")
                        if w.thunder_probability is not None:
                            print(f"Thunder probability: {w.thunder_probability}%")
                        if w.symbol:
                            print(f"Summary: {w.symbol}")
                    
                    if response.expires:
                        print(f"\nExpires: {response.expires}")
                
                return 0

            except Exception as e:
                logger.error(f"Failed to get weather data: {str(e)}")
                return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to get data: {str(e)}")
        return 1

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
        elif args.command == 'get':
            return get_command(args, logger, config)
        else:
            logger.error(f"Unknown command: {args.command}")
            return 1
            
    except Exception as e:
        logger = get_logger(__name__)
        logger.exception("Unhandled exception")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 