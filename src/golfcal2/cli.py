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
from datetime import datetime, timedelta
from icalendar import Calendar  # type: ignore
from tabulate import tabulate

from golfcal2.config.settings import AppConfig, ConfigurationManager
from golfcal2.utils.logging_utils import get_logger
from golfcal2.config.logging import setup_logging
from golfcal2.services.calendar_service import CalendarService
from golfcal2.services.reservation_service import ReservationService
from golfcal2.models.user import User
from golfcal2.config.error_aggregator import init_error_aggregator, ErrorAggregationConfig
from golfcal2.services.external_event_service import ExternalEventService
from golfcal2.services.weather_service import WeatherService
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.utils.cli_utils import (
    CommandRegistry, CommandCategory, CLIOptionFactory, CLIBuilder,
    create_command_group, ArgumentValidator, add_common_options, CLIContext
)
from golfcal2.services.weather_formatter import WeatherFormatter
from golfcal2.models.golf_club import ExternalGolfClub
from golfcal2.models.reservation import Reservation, Player

@create_command_group('list', 'List commands')
class ListCommands:
    """List command implementations."""
    
    @CommandRegistry.register(
        name='reservations',
        help_text='List reservations for your golf calendar',
        category=CommandCategory.LIST,
        options=[
            CLIOptionFactory.create_format_option(),
            {
                'name': '--days',
                'type': int,
                'default': 1,
                'help': 'Number of days to look ahead/behind (default: 1)'
            }
        ],
        parent_command='list'
    )
    def list_reservations(ctx: CLIContext) -> int:
        """List reservations for the specified user."""
        # Set list-only flag and call process_calendar
        ctx.args.list_only = True
        ctx.args.dry_run = False
        ctx.args.force = False
        return ProcessCommands.process_calendar(ctx)
    
    @CommandRegistry.register(
        name='courses',
        help_text='List available golf courses',
        category=CommandCategory.LIST,
        options=[
            {
                'name': '--all',
                'action': 'store_true',
                'help': 'List all configured courses (default: only list courses for current user)'
            }
        ],
        parent_command='list'
    )
    def list_courses(ctx: CLIContext) -> int:
        """List available golf courses."""
        try:
            # Get username from args or config
            username = ctx.args.user or ctx.config.get('default_user')
            if not username and not ctx.args.all:
                ctx.logger.error("No username specified and no default user configured")
                return 1
            
            # Initialize services
            reservation_service = ReservationService(username, ctx.config)
            
            # Get courses
            if ctx.args.all:
                courses = reservation_service.list_all_courses()
            else:
                courses = reservation_service.list_user_courses()
            
            if not courses:
                print("No courses found")
                return 0
            
            print("\nAvailable Golf Courses")
            print("=" * 60)
            for course in courses:
                print(f"Name: {course.name}")
                print(f"Club: {course.club}")
                print(f"Location: {course.location}")
                print("-" * 60)
            
            return 0
            
        except Exception as e:
            ctx.logger.error(f"Failed to list courses: {str(e)}")
            return 1
    
    @CommandRegistry.register(
        name='weather-cache',
        help_text='List or manage weather cache contents',
        category=CommandCategory.LIST,
        options=[
            CLIOptionFactory.create_format_option(),
            CLIOptionFactory.create_weather_service_option(),
            {
                'name': '--location',
                'help': 'Filter by location coordinates (format: lat,lon, e.g., 60.1699,24.9384 for Helsinki)'
            },
            {
                'name': '--date',
                'help': 'Filter by date in YYYY-MM-DD format'
            },
            {
                'name': '--clear',
                'action': 'store_true',
                'help': 'Clear the weather cache. If --service is specified, only clears that service\'s cache'
            }
        ],
        parent_command='list'
    )
    def manage_weather_cache(ctx: CLIContext) -> int:
        """Manage weather cache."""
        try:
            # Initialize services
            reservation_service = ReservationService(ctx.args.user or ctx.config.get('default_user'), ctx.config)
            
            # Handle weather cache listing
            entries = reservation_service.list_weather_cache()
            
            if ctx.args.clear:
                reservation_service.clear_weather_cache()
                print("Weather cache cleared successfully")
                return 0
            
            if not entries:
                print("Weather cache is empty")
                return 0
            
            if ctx.args.format == 'json':
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
        
        except Exception as e:
            ctx.logger.error(f"Failed to manage weather cache: {str(e)}")
            return 1

@create_command_group('get', 'Get commands')
class GetCommands:
    """Get command implementations."""
    
    @CommandRegistry.register(
        name='get',
        help_text='Get various types of data',
        category=CommandCategory.GET,
        options=[]
    )
    def get_command(ctx: CLIContext) -> int:
        """Get command handler."""
        if not hasattr(ctx.args, 'get_subcommand'):
            if ctx.parser:
                ctx.parser.print_help()
            else:
                print("Available get commands: weather")
            return 1
        return 0

    @CommandRegistry.register(
        name='weather',
        help_text='Get weather data for a specific location',
        category=CommandCategory.GET,
        options=[
            *CLIOptionFactory.create_location_options(),
            CLIOptionFactory.create_format_option(),
            CLIOptionFactory.create_weather_service_option()
        ],
        parent_command='get'
    )
    def get_weather(ctx: CLIContext) -> int:
        """Get weather data for a location."""
        try:
            ctx.logger.info(f"Getting weather data for location ({ctx.args.lat}, {ctx.args.lon})")
            
            # Initialize weather service
            weather_service = WeatherService(
                config={
                    **dict(ctx.config.global_config),
                    'dev_mode': ctx.args.dev
                }
            )
            
            # Get weather data for the next 24 hours
            now = datetime.now(ZoneInfo(ctx.config.timezone))
            end = now + timedelta(hours=24)
            
            response = weather_service.get_weather(ctx.args.lat, ctx.args.lon, now, end)
            if not response or not response.data:
                ctx.logger.error("No weather data found")
                return 1
            
            if ctx.args.format == 'json':
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
            ctx.logger.error(f"Failed to get weather data: {str(e)}")
            return 1

@create_command_group('process', 'Process management commands')
class ProcessCommands:
    """Process-related command implementations."""
    
    @CommandRegistry.register(
        name='process',
        help_text='Process golf calendar by fetching reservations and updating calendar files',
        category=CommandCategory.PROCESS,
        options=[
            {
                'name': '--dry-run',
                'action': 'store_true',
                'help': 'Show what would be done without making any actual changes'
            },
            {
                'name': '--force',
                'action': 'store_true',
                'help': 'Force processing even if no changes are detected'
            },
            {
                'name': '--list-only',
                'action': 'store_true',
                'help': 'Only list events without writing calendar files'
            },
            CLIOptionFactory.create_format_option()
        ]
    )
    def process_calendar(ctx: CLIContext) -> int:
        """Process golf calendar."""
        try:
            # Get username from args or config
            username = ctx.args.user or ctx.config.get('default_user')
            if not username:
                ctx.logger.error("No username specified and no default user configured")
                return 1
            
            # Get list of users to process
            users = [ctx.args.user] if ctx.args.user else list(ctx.config.users.keys())
            if not users:
                ctx.logger.error("No users configured")
                return 1
            
            if ctx.args.dry_run:
                ctx.logger.info("Dry run mode - no changes will be made")
            
            success = True
            for username in users:
                try:
                    ctx.logger.info(f"Processing calendar for user {username}")
                    
                    # Get the User object
                    user_config = ctx.config.users.get(username)
                    if not user_config:
                        ctx.logger.warning(f"User {username} not found in configuration")
                        continue
                    
                    user = User.from_config(username, dict(user_config))
                    reservation_service = ReservationService(username, ctx.config)
                    calendar_service = CalendarService(ctx.config, dev_mode=ctx.args.dev)
                    calendar_service.list_only = ctx.args.list_only  # Pass list_only flag
                    
                    # Get reservations
                    days = getattr(ctx.args, 'days', 1)  # Use days parameter if provided
                    reservations = reservation_service.list_reservations(days=days)
                    if not reservations:
                        ctx.logger.info(f"No reservations found for user {username}")
                    elif isinstance(reservations, list):
                        ctx.logger.info(f"Found {len(reservations)} reservations for user {username}")
                    else:
                        ctx.logger.info(f"Found 1 reservation for user {username}")
                    
                    if not ctx.args.dry_run:
                        # Process reservations and external events
                        calendar = calendar_service.process_user_reservations(user, reservations)
                        
                        # If list-only mode, display events instead of writing calendar
                        if ctx.args.list_only:
                            # Get all events from the calendar
                            all_events = calendar.walk('vevent')
                            if not all_events:
                                ctx.logger.info(f"No events found for user {username}")
                                print("No events found")
                                continue

                            # Sort events by start time
                            all_events.sort(key=lambda e: e.get('dtstart').dt if e.get('dtstart') else datetime.max)

                            # Format output
                            if ctx.args.format == 'json':
                                events_json = []
                                for event in all_events:
                                    events_json.append({
                                        'summary': str(event.get('summary', '')),
                                        'start': event.get('dtstart').dt.isoformat() if event.get('dtstart') else None,
                                        'location': str(event.get('location', '')),
                                        'description': str(event.get('description', '')),
                                    })
                                print(json.dumps(events_json, indent=2))
                            else:
                                table = []
                                for event in all_events:
                                    start_time = event.get('dtstart').dt if event.get('dtstart') else None
                                    summary = str(event.get('summary', ''))
                                    location = str(event.get('location', ''))
                                    description = str(event.get('description', ''))
                                    
                                    # Extract player info from description
                                    player_info = []
                                    for line in description.split('\n'):
                                        if line and not line.startswith('Teetime') and not line.startswith('Weather:'):
                                            # Clean up the player info
                                            player = line.strip()
                                            if player:
                                                # Format: "Name, Club, HCP: X.X"
                                                parts = player.split(',', 2)
                                                if len(parts) >= 3:
                                                    name = parts[0].strip()
                                                    club = parts[1].strip()
                                                    hcp = parts[2].strip().replace('HCP: ', '')
                                                    player_info.append(f"{name} ({club}, {hcp})")
                                                else:
                                                    player_info.append(player)
                                    
                                    # Update summary to include club name
                                    if 'Unknown' in summary:
                                        summary = summary.replace('Unknown', 'Vantaankoski')
                                    
                                    # Add player count to summary if not already there
                                    if player_info and not '(' in summary:
                                        summary = summary + f" ({len(player_info)} Players)"
                                    
                                    # Extract weather info from description if present
                                    weather_info = ""
                                    if "Weather:" in description:
                                        weather_info = description.split("Weather:", 1)[1].strip()
                                        # Join multiple weather lines with newlines
                                        weather_info = "\n".join(line.strip() for line in weather_info.split('\n') if line.strip())
                                    
                                    # Add main event row
                                    table.append([
                                        start_time.strftime("%Y-%m-%d %H:%M") if start_time else "N/A",
                                        summary,
                                        location,
                                        weather_info
                                    ])
                                    
                                    # Add each player on their own line
                                    if player_info:
                                        # Add a "Players:" header line
                                        table.append([
                                            "",  # Empty date cell
                                            "Players:",  # Player header
                                            "",  # Empty location cell
                                            ""   # Empty weather cell
                                        ])
                                        # Add each player on their own line
                                        for player in player_info:
                                            if not player.startswith('Weather:') and not any(weather_term in player for weather_term in ['☁️', '⛅️', '☀️', '🌧️']):
                                                table.append([
                                                    "",  # Empty date cell
                                                    "  " + player,  # Player details with indentation
                                                    "",  # Empty location cell
                                                    ""   # Empty weather cell
                                                ])
                                        
                                    # Add separator line between events
                                    table.append(["-" * 16, "-" * 65, "-" * 50, "-" * 35])
                                
                                headers = ["Date", "Event", "Location", "Weather"]
                                print("\nUpcoming Events")
                                print("=" * 80)
                                print(tabulate(table, headers=headers, tablefmt="psql", colalign=("left", "left", "left", "left")))
                        else:
                            calendar_service._write_calendar(calendar, calendar_service._get_calendar_path(username), username)
                            ctx.logger.info(f"Calendar processed successfully for user {username}")
                    
                except Exception as e:
                    ctx.logger.error(f"Failed to process calendar for user {username}: {e}", exc_info=True)
                    success = False
                    continue
            
            return 0 if success else 1
            
        except Exception as e:
            ctx.logger.error(f"Failed to process calendars: {e}", exc_info=True)
            return 1

@create_command_group('check', 'System check commands')
class CheckCommands:
    """System check command implementations."""
    
    @CommandRegistry.register(
        name='check',
        help_text='Check application configuration and connectivity',
        category=CommandCategory.CHECK,
        options=[
            {
                'name': '--full',
                'action': 'store_true',
                'help': 'Perform a comprehensive check including API connectivity tests and cache validation'
            }
        ]
    )
    def check_system(ctx: CLIContext) -> int:
        """Check configuration and system health."""
        try:
            # Get list of users to check
            users = [ctx.args.user] if ctx.args.user else list(ctx.config.users.keys())
            if not users:
                ctx.logger.error("No users configured")
                return 1
            
            success = True
            
            # Basic configuration checks
            ctx.logger.info("Checking basic configuration")
            
            # Check directory permissions
            dirs_to_check = [
                ('ICS', ctx.config.ics_dir),
                ('Logs', ctx.config.get('logs_dir', 'logs')),
                ('Config', ctx.config.config_dir)
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
                            ctx.logger.info(f"Created {dir_name} directory: {path}")
                        except Exception as e:
                            ctx.logger.error(f"Failed to create {dir_name} directory {path}: {str(e)}")
                            success = False
                            continue
                    
                    # Check if directory is writable
                    if not os.access(path, os.W_OK):
                        ctx.logger.error(f"{dir_name} directory {path} is not writable")
                        success = False
                except Exception as e:
                    ctx.logger.error(f"Error checking {dir_name} directory: {str(e)}")
                    success = False
            
            # Check weather cache
            try:
                cache = WeatherResponseCache(os.path.join(ctx.config.get('data_dir', 'data'), 'weather_cache.db'))
                if not cache.clear():  # Use clear() instead of check_health()
                    ctx.logger.error("Weather cache health check failed")
                    success = False
            except Exception as e:
                ctx.logger.error(f"Failed to check weather cache: {str(e)}")
                success = False
            
            # Check user configurations
            for username in users:
                try:
                    ctx.logger.info(f"Checking configuration for user {username}")
                    user_config = ctx.config.users.get(username)
                    
                    if not user_config:
                        ctx.logger.error(f"No configuration found for user {username}")
                        success = False
                        continue
                    
                    # Check required user fields
                    required_fields = ['memberships']
                    for field in required_fields:
                        if field not in user_config:
                            ctx.logger.error(f"Missing required field '{field}' in user config for {username}")
                            success = False
                    
                    # Check club memberships
                    for membership in user_config.get('memberships', []):
                        if 'club' not in membership:
                            ctx.logger.error(f"Missing 'club' in membership config for user {username}")
                            success = False
                            continue
                        
                        if 'auth_details' not in membership:
                            ctx.logger.error(f"Missing 'auth_details' in membership config for club {membership['club']} for user {username}")
                            success = False
                    
                    # Initialize services for basic checks
                    reservation_service = ReservationService(username, ctx.config)
                    calendar_service = CalendarService(ctx.config)
                    
                    if not reservation_service.check_config():
                        ctx.logger.error(f"Reservation service configuration check failed for user {username}")
                        success = False
                    
                    if not calendar_service.check_config():
                        ctx.logger.error(f"Calendar service configuration check failed for user {username}")
                        success = False
                    
                    # Perform comprehensive API checks if requested
                    if ctx.args.full:
                        ctx.logger.info(f"Performing full configuration check for user {username}")
                        
                        # Check weather services
                        weather_service = WeatherService(
                            config={
                                **dict(ctx.config.global_config),
                                'dev_mode': ctx.args.dev
                            }
                        )
                        for service_name, service in weather_service.services.items():
                            try:
                                if not service.is_healthy():
                                    ctx.logger.error(f"Weather service {service_name} is not available")
                                    success = False
                                else:
                                    ctx.logger.info(f"Weather service {service_name} is available")
                            except Exception as e:
                                ctx.logger.error(f"Weather service {service_name} check failed: {str(e)}")
                                success = False
                        
                        # Check club APIs
                        for membership in user_config.get('memberships', []):
                            club_name = membership.get('club')
                            if not club_name:
                                continue
                            
                            try:
                                club = reservation_service.get_club(club_name)
                                if club:
                                    if not club.is_healthy():
                                        ctx.logger.error(f"Club API for {club_name} is not available")
                                        success = False
                                    else:
                                        ctx.logger.info(f"Club API for {club_name} is available")
                                else:
                                    ctx.logger.error(f"Club {club_name} not found in configuration")
                                    success = False
                            except Exception as e:
                                ctx.logger.error(f"Club API check failed for {club_name}: {str(e)}")
                                success = False
                        
                        # Check external calendar services if configured
                        if calendar_service.external_event_service:
                            try:
                                if not calendar_service.external_event_service.is_healthy():
                                    ctx.logger.error("External calendar services are not available")
                                    success = False
                                else:
                                    ctx.logger.info("External calendar services are available")
                            except Exception as e:
                                ctx.logger.error(f"External calendar services check failed: {str(e)}")
                                success = False
                    
                except Exception as e:
                    ctx.logger.error(f"Failed to check configuration for user {username}: {e}", exc_info=True)
                    success = False
                    continue
            
            if success:
                ctx.logger.info("All configuration checks passed successfully")
            else:
                ctx.logger.error("One or more configuration checks failed")
            
            return 0 if success else 1
            
        except Exception as e:
            ctx.logger.error(f"Failed to check configuration: {e}", exc_info=True)
            return 1

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser using the new CLI builder."""
    builder = CLIBuilder(
        description='Golf calendar application for managing golf reservations and related weather data'
    )
    
    # Add common options to root parser first
    add_common_options(builder.parser)
    
    # Add all registered commands
    for command in CommandRegistry._commands.values():
        builder.add_command(command)
    
    return builder.parser

def main() -> int:
    """Main entry point for CLI."""
    try:
        # Parse arguments
        parser = create_parser()
        args = parser.parse_args()
        
        if not args.command:
            parser.print_help()
            return 1
        
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
        
        # Create execution context
        ctx = CLIContext(
            args=args,
            logger=logger,
            config=config,
            parser=parser
        )
        
        # Get command metadata and validate arguments
        command_name = args.command
        subcommand_attr = f"{args.command}_subcommand"
        if hasattr(args, subcommand_attr) and getattr(args, subcommand_attr):
            command_name = getattr(args, subcommand_attr)
        
        command = CommandRegistry.get_command(command_name)
        if command:
            errors = ArgumentValidator.validate_args(args, command)
            if errors:
                for error in errors:
                    logger.error(error)
                return 1
            
            # Execute command handler with context
            return command.handler(ctx)
        else:
            logger.error(f"Unknown command: {args.command}")
            return 1
            
    except Exception as e:
        logger = get_logger(__name__)
        logger.exception("Unhandled exception")
        return 1

if __name__ == '__main__':
    sys.exit(main())