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
import json

from golfcal2.config.settings import ConfigurationManager
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

def process_command(args: argparse.Namespace, logger: logging.Logger, config_manager: ConfigurationManager, is_dev: bool = False) -> int:
    """Process golf calendar."""
    try:
        # Get the AppConfig instance
        config = config_manager.config
        
        # Get username from args or config
        username = args.user or config.get('default_user')
        if not username:
            logger.error("No username specified and no default user configured")
            return 1
            
        # Initialize services
        reservation_service = ReservationService(username, config)
        
        if args.command == 'list':
            if args.list_type == 'weather-cache':
                # Handle weather cache listing
                entries = reservation_service.list_weather_cache()
                
                if args.clear:
                    reservation_service.clear_weather_cache()
                    print("Weather cache cleared successfully")
                    return 0
                
                if not entries:
                    print("Weather cache is empty")
                    return 0
                
                if args.format == 'json':
                    print(json.dumps(entries, indent=2))
                else:
                    print("\nWeather Cache Contents")
                    print("=" * 60)
                    for entry in entries:
                        print(f"Service: {entry['service']}")
                        print(f"Location: {entry['location']}")
                        print(f"Forecast Period: {entry['forecast_period']}")
                        print(f"Expires: {entry['expires']}")
                        print(f"Created: {entry['created']}")
                        print("-" * 60)
                return 0
        
        # Get list of users to process
        users = [args.user] if args.user else list(config.users.keys())
        if not users:
            logger.error("No users configured")
            return 1
            
        if getattr(args, 'dry_run', False):
            logger.info("Dry run mode - no changes will be made")
        
        success = True
        for username in users:
            try:
                # Different log message based on command
                if getattr(args, 'list_type', None) == 'reservations':
                    logger.info(f"Listing reservations for user {username}")
                else:
                    logger.info(f"Processing calendar for user {username}")
                
                # Get the User object using from_config
                user_config = config.users.get(username)
                if not user_config:
                    logger.warning(f"User {username} not found in configuration")
                    continue
                
                # Convert user_config to dict for User.from_config
                user = User.from_config(username, dict(user_config))
                reservation_service = ReservationService(username, config)
                calendar_service = CalendarService(config)
                
                # Get reservations
                calendar, reservations = reservation_service.process_user(username, dict(user_config))
                if not reservations:
                    logger.info(f"No reservations found for user {username}")
                else:
                    logger.info(f"Found {len(reservations)} reservations for user {username}")
                
                # If listing reservations, print them out
                if getattr(args, 'list_type', None) == 'reservations':
                    # Get external events too
                    external_events = calendar_service.external_event_service.process_events(username, dev_mode=args.dev)
                    
                    # Add external events to calendar
                    for event in external_events:
                        calendar.add_component(event)
                    
                    if args.format == 'json':
                        # Convert all events to JSON-serializable format
                        data = {
                            username: {
                                "events": [event.format_for_display() for event in reservations + external_events]
                            }
                        }
                        print(json.dumps(data, indent=2))
                    else:
                        if len(users) > 1:
                            print(f"\nEvents for {username}:")
                            print("=" * 60)
                        else:
                            print("\nEvents:")
                            print("=" * 60)
                        
                        # Print all events in chronological order
                        for event in sorted(calendar.walk('vevent'), key=lambda x: x['dtstart'].dt):
                            # Get event details
                            start_time = event['dtstart'].dt
                            end_time = event['dtend'].dt
                            name = event['summary']
                            location = event.get('location', '')
                            description = event.get('description', '')
                            
                            # Format times
                            start_str = start_time.strftime('%Y-%m-%d %H:%M')
                            end_str = end_time.strftime('%H:%M')
                            
                            # Print event details
                            print(f"{start_str} - {end_str}: {name}")
                            if location:
                                print(f"Location: {location}")
                            
                            # Extract and print weather data if present
                            if description and 'Weather:' in description:
                                weather_part = description.split('Weather:', 1)[1].strip()
                                print("\nWeather:")
                                print(weather_part)
                            print("-" * 60)
                # Otherwise process calendar as usual
                elif not getattr(args, 'dry_run', False):
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

def list_command(args: argparse.Namespace, logger: logging.Logger, config_manager: ConfigurationManager) -> int:
    """List reservations for users."""
    # Just call process_command with list_type set
    return process_command(args, logger, config_manager)

def check_command(args: argparse.Namespace, logger: logging.Logger, config_manager: ConfigurationManager) -> int:
    """Check configuration and system health."""
    try:
        # Get the AppConfig instance
        config = config_manager.config
        
        # Get list of users to check
        users = [args.user] if args.user else list(config.users.keys())
        if not users:
            logger.error("No users configured")
            return 1
            
        success = True
        
        # Basic configuration checks
        logger.info("Checking basic configuration")
        
        # Check directory permissions
        dirs_to_check = [
            ('ICS', config.ics_dir),
            ('Logs', config.get('logs_dir', 'logs')),
            ('Config', config.config_dir)
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
            if not cache.clear():  # Use clear() instead of check_health()
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
                    weather_manager = WeatherManager(
                        ZoneInfo(config.timezone),
                        ZoneInfo('UTC'),
                        dict(config.global_config)  # Convert AppConfig to dict
                    )
                    for service_name, service in weather_manager.services.items():
                        try:
                            if not service.is_healthy():  # Use is_healthy() instead of check_health()
                                logger.error(f"Weather service {service_name} is not available")
                                success = False
                            else:
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
                            club = reservation_service.get_club(club_name)  # Use get_club() instead of get_club_instance()
                            if club:
                                if not club.is_healthy():  # Use is_healthy() instead of check_health()
                                    logger.error(f"Club API for {club_name} is not available")
                                    success = False
                                else:
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
                            if not calendar_service.external_event_service.is_healthy():  # Use is_healthy() instead of check_health()
                                logger.error("External calendar services are not available")
                                success = False
                            else:
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

def get_command(args: argparse.Namespace, logger: logging.Logger, config_manager: ConfigurationManager) -> int:
    """Get various types of data."""
    try:
        if not args.get_type:
            logger.error("Please specify what to get: 'weather'")
            return 1
            
        # Get the AppConfig instance
        config = config_manager.config
            
        if args.get_type == 'weather':
            logger.info(f"Getting weather data for location ({args.lat}, {args.lon})")
            
            # Initialize weather manager
            weather_manager = WeatherManager(
                ZoneInfo(config.timezone),
                ZoneInfo('UTC'),
                dict(config.global_config)  # Convert AppConfig to dict
            )
            
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
                    print(json.dumps({
                        'data': [w.to_dict() for w in response.data],
                        'expires': response.expires.isoformat() if response.expires else None
                    }, indent=2, default=str))
                else:
                    print("\nWeather Forecast")
                    print("---------------")
                    for w in response.data:
                        print(f"\nTime: {w.time}")
                        print(f"Temperature: {w.temperature}°C")
                        print(f"Precipitation: {w.precipitation} mm")
                        print(f"Wind: {w.wind_speed} m/s from {w.wind_direction}°")
                        if w.precipitation_probability is not None:
                            print(f"Precipitation probability: {w.precipitation_probability}%")
                        if w.thunder_probability is not None:
                            print(f"Thunder probability: {w.thunder_probability}%")
                        if w.weather_code:
                            print(f"Summary: {w.weather_code}")
                    
                    if response.expires:
                        print(f"\nExpires: {response.expires}")
                
                return 0

            except Exception as e:
                logger.error(f"Failed to get weather data: {str(e)}")
                return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to get data: {e}", exc_info=True)
        return 1

def main() -> int:
    """Main entry point for CLI."""
    try:
        # Parse arguments
        parser = create_parser()
        args = parser.parse_args()
        
        # Initialize configuration
        config_manager = ConfigurationManager()
        config = config_manager.load_config(dev_mode=args.dev, verbose=args.verbose)
        
        # Set up logging
        setup_logging(config, dev_mode=args.dev, verbose=args.verbose, log_file=args.log_file)
        logger = get_logger(__name__)
        
        # Initialize error aggregator
        error_config = ErrorAggregationConfig(
            enabled=True,
            report_interval=int(str(config.global_config.get('ERROR_REPORT_INTERVAL', 3600))),
            error_threshold=int(str(config.global_config.get('ERROR_THRESHOLD', 5))),
            time_threshold=int(str(config.global_config.get('ERROR_TIME_THRESHOLD', 300))),  # 5 minutes
            categorize_by=['service', 'error_type']  # Categorize errors by service and type
        )
        init_error_aggregator(error_config)
        
        # Initialize services
        weather_manager = WeatherManager(
            ZoneInfo(config.timezone),
            ZoneInfo('UTC'),
            dict(config.global_config)  # Convert AppConfig to dict
        )
        
        # Execute command
        if not args.command:
            parser.print_help()
            return 1
        elif args.command == 'process':
            return process_command(args, logger, config_manager, args.dev)
        elif args.command == 'list':
            return list_command(args, logger, config_manager)
        elif args.command == 'check':
            return check_command(args, logger, config_manager)
        elif args.command == 'get':
            return get_command(args, logger, config_manager)
        else:
            logger.error(f"Unknown command: {args.command}")
            return 1
            
    except Exception as e:
        logger = get_logger(__name__)
        logger.exception("Unhandled exception")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 