"""
Command line interface for golf calendar application.
"""

import sys
import logging
import argparse
from typing import Optional

from golfcal2.config.settings import load_config, AppConfig
from golfcal2.utils.logging_utils import get_logger
from golfcal2.config.logging import setup_logging
from golfcal2.services.calendar_service import CalendarService
from golfcal2.services.reservation_service import ReservationService
from golfcal2.models.user import User
from golfcal2.config.error_aggregator import init_error_aggregator, ErrorAggregationConfig

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(description='Golf calendar application')
    
    # Global options
    parser.add_argument('-u', '--user', required=True, help='User name')
    parser.add_argument('--dev', action='store_true', help='Run in development mode')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--log-file', help='Log file path')
    
    # Commands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process golf calendar')
    process_parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    process_parser.add_argument('--force', action='store_true', help='Force processing')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List golf courses or reservations')
    list_subparsers = list_parser.add_subparsers(dest='list_type', help='What to list')
    
    # Courses subcommand
    courses_parser = list_subparsers.add_parser('courses', help='List golf courses')
    courses_parser.add_argument('--all', action='store_true', help='List all courses')
    
    # Weather cache subcommand
    weather_cache_parser = list_subparsers.add_parser('weather-cache', help='List weather cache contents')
    weather_cache_parser.add_argument('--service', choices=['met', 'portuguese', 'iberian'], help='Filter by weather service')
    weather_cache_parser.add_argument('--location', help='Filter by location (lat,lon)')
    weather_cache_parser.add_argument('--date', help='Filter by date (YYYY-MM-DD)')
    weather_cache_parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')
    weather_cache_parser.add_argument('--clear', action='store_true', help='Clear the weather cache')
    
    # Reservations subcommand
    reservations_parser = list_subparsers.add_parser('reservations', help='List reservations')
    reservations_parser.add_argument('--active', action='store_true', help='Show only active reservations')
    reservations_parser.add_argument('--upcoming', action='store_true', help='Show only upcoming reservations')
    reservations_parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')
    reservations_parser.add_argument('--days', type=int, default=1, help='Number of days to look ahead/behind')
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check configuration')
    check_parser.add_argument('--full', action='store_true', help='Full check')
    
    return parser

def process_command(args: argparse.Namespace, logger: logging.Logger, config: AppConfig, is_dev: bool = False) -> int:
    """Process golf calendar."""
    try:
        logger.info(f"Processing calendar for user {args.user}")
        
        if args.dry_run:
            logger.info("Dry run mode - no changes will be made")
        
        reservation_service = ReservationService(args.user, config)
        calendar_service = CalendarService(config, dev_mode=is_dev)
        
        # Get reservations
        calendar, reservations = reservation_service.process_user(args.user, config.users[args.user])
        if not reservations:
            logger.info("No reservations found")
            return 0
        
        logger.info(f"Found {len(reservations)} reservations")
        
        # Process reservations
        if not args.dry_run:
            user = User.from_config(args.user, config.users[args.user])
            calendar_service.process_user_reservations(user, reservations)
            logger.info("Calendar processed successfully")
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to process calendar: {e}", exc_info=True)
        return 1

def list_command(args: argparse.Namespace, logger: logging.Logger, config: AppConfig) -> int:
    """List golf courses or reservations."""
    try:
        if not args.list_type:
            logger.error("Please specify what to list: 'courses', 'reservations', or 'weather-cache'")
            return 1
            
        if args.list_type == 'weather-cache':
            logger.info("Listing weather cache contents")
            from golfcal2.services.weather_database import WeatherDatabase
            from golfcal2.services.weather_schemas import MET_SCHEMA, PORTUGUESE_SCHEMA, IBERIAN_SCHEMA
            import json
            from datetime import datetime, timedelta
            import sqlite3
            
            # Initialize databases based on service filter
            dbs = []
            if not args.service or args.service == 'met':
                dbs.append(('met', WeatherDatabase('met_weather', MET_SCHEMA)))
            if not args.service or args.service == 'portuguese':
                dbs.append(('portuguese', WeatherDatabase('portuguese_weather', PORTUGUESE_SCHEMA)))
            if not args.service or args.service == 'iberian':
                dbs.append(('iberian', WeatherDatabase('iberian_weather', IBERIAN_SCHEMA)))
            
            # Handle clear command
            if args.clear:
                for service_name, db in dbs:
                    try:
                        with sqlite3.connect(db.db_file) as conn:
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM weather")
                            conn.commit()
                            logger.info(f"Cleared weather cache for {service_name} service")
                    except Exception as e:
                        logger.warning(f"Failed to clear {service_name} weather cache: {str(e)}")
                return 0
            
            all_data = {}
            for service_name, db in dbs:
                try:
                    # Get all locations from the database
                    conn = sqlite3.connect(db.db_file)
                    cursor = conn.cursor()
                    
                    # Build the WHERE clause based on filters
                    where_clauses = ["1=1"]  # Always true condition as base
                    params = []
                    
                    if args.location:
                        where_clauses.append("location = ?")
                        params.append(args.location)
                    
                    if args.date:
                        try:
                            date = datetime.strptime(args.date, '%Y-%m-%d')
                            where_clauses.append("(time LIKE ? OR time LIKE ?)")
                            # Match both formats: with and without T and timezone
                            params.extend([
                                f"{date.strftime('%Y-%m-%d')}T%",
                                f"{date.strftime('%Y-%m-%d')} %"
                            ])
                        except ValueError:
                            logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
                            return 1
                    
                    # Query to get distinct locations and their time ranges
                    query = f"""
                        SELECT DISTINCT location, 
                               MIN(substr(time, 1, 19)) || '+00:00' as start_time,
                               MAX(substr(time, 1, 19)) || '+00:00' as end_time
                        FROM weather
                        WHERE {' AND '.join(where_clauses)}
                        GROUP BY location
                    """
                    
                    cursor.execute(query, params)
                    locations = cursor.fetchall()
                    
                    service_data = {}
                    for location, start_time, end_time in locations:
                        try:
                            # Parse ISO format times
                            start = datetime.fromisoformat(start_time)
                            end = datetime.fromisoformat(end_time)
                            
                            # Generate time points
                            times = []
                            current = start
                            while current <= end:
                                times.append(current.isoformat())  # Store in ISO format
                                current += timedelta(hours=1)
                            
                            # Get weather data for this location and time range
                            data = db.get_weather_data(
                                location=location,
                                times=times,
                                data_type='daily',
                                fields=[
                                    'air_temperature',
                                    'precipitation_amount',
                                    'wind_speed',
                                    'wind_from_direction',
                                    'probability_of_precipitation',
                                    'probability_of_thunder',
                                    'summary_code'
                                ]
                            )
                            
                            if data:
                                service_data[location] = data
                        except ValueError as e:
                            logger.warning(f"Failed to parse time for location {location}: {e}")
                            continue
                    
                    conn.close()
                    
                    if service_data:
                        all_data[service_name] = service_data
                        
                except Exception as e:
                    logger.warning(f"Failed to get data from {service_name} database: {str(e)}")
                    continue
            
            if not all_data:
                logger.info("No weather cache data found")
                return 0
            
            if args.format == 'json':
                print(json.dumps(all_data, indent=2))
            else:
                for service_name, locations in all_data.items():
                    print(f"\nWeather Cache - {service_name.upper()} Service")
                    print("=" * 60)
                    
                    for location, data in locations.items():
                        print(f"\nLocation: {location}")
                        print("-" * 40)
                        
                        for time_str, values in sorted(data.items()):
                            print(f"\nTime: {time_str}")
                            print("  " + "-" * 38)
                            for key, value in values.items():
                                if value is not None:  # Only print non-None values
                                    print(f"  {key}: {value}")
                    print()
            
            return 0
            
        elif args.list_type == 'courses':
            logger.info(f"Listing courses for user {args.user}")
            reservation_service = ReservationService(args.user, config)
            courses = reservation_service.list_courses(include_all=args.all)
            
            if not courses:
                logger.info("No courses found")
                return 0
                
            for course in courses:
                print(f"- {course}")
                
        elif args.list_type == 'reservations':
            logger.info(f"Listing reservations for user {args.user}")
            
            # Initialize reservation service
            reservation_service = ReservationService(args.user, config)
            
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
            external_events = calendar_service.external_event_service.process_events(args.user, dev_mode=args.dev)
            
            if not reservations and not external_events:
                logger.info("No reservations or events found")
                return 0
            
            if args.format == 'json':
                import json
                # Convert reservations to JSON-serializable format
                data = {
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
                print(json.dumps(data, indent=2))
            else:
                # Print regular reservations
                if reservations:
                    print("\nReservations:")
                    print("=" * 60)
                    for reservation in reservations:
                        # Format time in local timezone
                        start_time = reservation.start_time.strftime('%Y-%m-%d %H:%M')
                        end_time = reservation.end_time.strftime('%H:%M')
                        
                        # Get club and variant info
                        club_name = reservation.club.name
                        variant = reservation.club.variant if hasattr(reservation.club, 'variant') else None
                        variant_str = f" - {variant}" if variant else ""
                        
                        # Print header with time and club info
                        print(f"{start_time} - {end_time}: {club_name}{variant_str}")
                        
                        # Print players with handicaps
                        if reservation.players:
                            print("Players:")
                            for player in reservation.players:
                                if player.handicap > 0:
                                    print(f"  - {player.name} (HCP: {player.handicap})")
                                else:
                                    print(f"  - {player.name}")
                            print(f"Total HCP: {reservation.total_handicap}")
                        else:
                            print("No player information available")
                        
                        print("-" * 60)
                
                # Print external events
                if external_events:
                    if reservations:  # Add extra newline if we printed reservations
                        print()
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
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to list {args.list_type}: {e}", exc_info=True)
        return 1

def check_command(args: argparse.Namespace, logger: logging.Logger, config: AppConfig) -> int:
    """Check configuration."""
    try:
        logger.info(f"Checking configuration for user {args.user}")
        
        if args.full:
            logger.info("Performing full configuration check")
            # TODO: Implement full check
        
        # Basic check
        reservation_service = ReservationService(args.user, config)
        calendar_service = CalendarService(config)
        
        if reservation_service.check_config() and calendar_service.check_config():
            logger.info("Configuration check passed")
            return 0
        else:
            logger.error("Configuration check failed")
            return 1
        
    except Exception as e:
        logger.error(f"Failed to check configuration: {e}", exc_info=True)
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
        
        # Execute command
        if args.command == 'process':
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