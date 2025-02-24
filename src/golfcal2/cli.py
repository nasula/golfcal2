"""
Command line interface for golf calendar application.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, cast
from zoneinfo import ZoneInfo

from icalendar import Calendar
from tabulate import tabulate

from golfcal2.config.error_aggregator import init_error_aggregator
from golfcal2.config.logging import setup_logging
from golfcal2.config.logging_config import ErrorAggregationConfig
from golfcal2.config.settings import ConfigurationManager
from golfcal2.config.types import AppConfig, UserConfig
from golfcal2.models.reservation import Reservation
from golfcal2.models.user import User
from golfcal2.services.calendar_service import CalendarService
from golfcal2.services.csv_import_service import CSVImportService
from golfcal2.services.reservation_service import ReservationService
from golfcal2.services.weather_database import WeatherResponseCache
from golfcal2.services.weather_service import WeatherService
from golfcal2.utils.cli_utils import (
    ArgumentValidator,
    CLIBuilder,
    CLIContext,
    CLIOptionFactory,
    CommandCategory,
    CommandRegistry,
    create_command_group,
)
from golfcal2.utils.logging_utils import get_logger


class GolfClubProtocol(Protocol):
    """Protocol for GolfClub attributes."""
    name: str
    club: str
    location: str
    is_healthy: bool

class CalendarServiceProtocol(Protocol):
    """Protocol for CalendarService attributes."""
    list_only: bool

class WeatherServiceProtocol(Protocol):
    """Protocol for WeatherService attributes."""
    services: dict[str, Any]

class ExternalEventServiceProtocol(Protocol):
    """Protocol for ExternalEventService attributes."""
    is_healthy: bool

class ConfigurationManagerProtocol(Protocol):
    """Protocol for ConfigurationManager."""
    def load_config(self, dev_mode: bool = False, verbose: bool = False) -> AppConfig:
        ...

@create_command_group('list', 'List commands')
class ListCommands:
    """List command implementations."""
    
    @staticmethod
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
            },
            {
                'name': '--exclude-other-wisegolf',
                'action': 'store_true',
                'help': 'Only show reservations from WiseGolf clubs in your memberships'
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
    
    @staticmethod
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
                print(f"Club: {course.get_event_summary({})}")
                print(f"Location: {course.get_event_location()}")
                print("-" * 60)
            
            return 0
            
        except Exception as e:
            ctx.logger.error(f"Failed to list courses: {e!s}")
            return 1
    
    @staticmethod
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
            ctx.logger.error(f"Failed to manage weather cache: {e!s}")
            return 1

@create_command_group('get', 'Get commands')
class GetCommands:
    """Get command implementations."""
    
    @staticmethod
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

    @staticmethod
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
            ctx.logger.error(f"Failed to get weather data: {e!s}")
            return 1

@create_command_group('process', 'Process management commands')
class ProcessCommands:
    """Process management commands."""

    @staticmethod
    @CommandRegistry.register(
        name='calendar',
        help_text='Process golf calendar by fetching reservations and updating calendar files',
        category=CommandCategory.PROCESS,
        parent_command='process',
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
            # Get list of users to process
            users: list[str] = [ctx.args.user] if ctx.args.user else list(ctx.config.users.keys())
            if not users:
                ctx.logger.error("No users configured")
                return 1
            
            if ctx.args.dry_run:
                ctx.logger.info("Dry run mode - no changes will be made")
            
            success: bool = True
            for username in users:
                try:
                    ctx.logger.info(f"Processing calendar for user {username}")
                    
                    # Get the User object
                    user_config: UserConfig | None = ctx.config.users.get(username)
                    if not user_config:
                        ctx.logger.warning(f"User {username} not found in configuration")
                        continue
                    
                    user: User = User.from_config(username, dict(user_config))
                    reservation_service: ReservationService = ReservationService(username, ctx.config)
                    calendar_service: CalendarService = CalendarService(ctx.config, dev_mode=ctx.args.dev)
                    calendar_service.list_only = ctx.args.list_only  # Set list_only flag
                    
                    # Get reservations
                    days: int = getattr(ctx.args, 'days', 1)  # Use days parameter if provided
                    exclude_other_wisegolf: bool = getattr(ctx.args, 'exclude_other_wisegolf', False)  # Get exclude_other_wisegolf flag
                    reservations: list[Reservation] = reservation_service.list_reservations(days=days, exclude_other_wisegolf=exclude_other_wisegolf)
                    if not reservations:
                        ctx.logger.info(f"No reservations found for user {username}")
                    elif isinstance(reservations, list):
                        ctx.logger.info(f"Found {len(reservations)} reservations for user {username}")
                    else:
                        ctx.logger.info(f"Found 1 reservation for user {username}")
                    
                    if not ctx.args.dry_run:
                        # Process reservations and external events
                        calendar: Calendar = calendar_service.process_user_reservations(user, reservations)
                        
                        # If list-only mode, display events instead of writing calendar
                        if ctx.args.list_only:
                            # Get all events from the calendar
                            all_events: list[Any] = calendar.walk('vevent')
                            if not all_events:
                                ctx.logger.info(f"No events found for user {username}")
                                print("No events found")
                            else:
                                # Sort events by start time
                                all_events.sort(key=lambda e: e.get('dtstart').dt if e.get('dtstart') else datetime.max)

                                # Format output based on format
                                if ctx.args.format == 'json':
                                    events_json: list[dict[str, Any]] = []
                                    for event in all_events:
                                        events_json.append({
                                            'summary': str(event.get('summary', '')),
                                            'start': event.get('dtstart').dt.isoformat() if event.get('dtstart') else None,
                                            'location': str(event.get('location', '')),
                                            'description': str(event.get('description', '')),
                                        })
                                    print(json.dumps(events_json, indent=2))
                                else:
                                    table: list[list[str]] = []
                                    for event in all_events:
                                        start_time: datetime | None = event.get('dtstart').dt if event.get('dtstart') else None
                                        summary: str = str(event.get('summary', ''))
                                        location: str = str(event.get('location', ''))
                                        description: str = str(event.get('description', ''))
                                        
                                        # Extract player info from description
                                        player_info: list[str] = []
                                        for line in description.split('\n'):
                                            if line and not line.startswith('Teetime') and not line.startswith('Weather:'):
                                                # Clean up the player info
                                                player: str = line.strip()
                                                if player:
                                                    # Format: "Name, Club, HCP: X.X"
                                                    parts: list[str] = player.split(',', 2)
                                                    if len(parts) >= 3:
                                                        name: str = parts[0].strip()
                                                        club: str = parts[1].strip()
                                                        hcp: str = parts[2].strip().replace('HCP: ', '')
                                                        player_info.append(f"{name} ({club}, {hcp})")
                                                    else:
                                                        player_info.append(player)
                                        
                                        # Update summary to include club name
                                        if 'Unknown' in summary:
                                            summary = summary.replace('Unknown', 'Vantaankoski')
                                        
                                        # Add player count to summary if not already there
                                        if player_info and '(' not in summary:
                                            summary = summary + f" ({len(player_info)} Players)"
                                        
                                        # Extract weather info from description if present
                                        weather_info: str = ""
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
            
            return 0 if success else 1
            
        except Exception as e:
            ctx.logger.error(f"Failed to process calendars: {e}", exc_info=True)
            return 1

@create_command_group('check', 'System check commands')
class CheckCommands:
    """System check command implementations."""
    
    @staticmethod
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
            users: list[str] = [ctx.args.user] if ctx.args.user else list(ctx.config.users.keys())
            if not users:
                ctx.logger.error("No users configured")
                return 1
            
            success: bool = True
            
            # Basic configuration checks
            ctx.logger.info("Checking basic configuration")
            
            # Check directory permissions
            dirs_to_check: list[tuple[str, str]] = [
                ('ICS', ctx.config.ics_dir),
                ('Logs', ctx.config.get('logs_dir', 'logs')),
                ('Config', ctx.config.config_dir)
            ]
            
            for dir_name, dir_path in dirs_to_check:
                try:
                    if os.path.isabs(dir_path):
                        path: Path = Path(dir_path)
                    else:
                        workspace_dir: Path = Path(__file__).parent.parent
                        path = workspace_dir / dir_path
                    
                    if not path.exists():
                        try:
                            path.mkdir(parents=True, exist_ok=True)
                            ctx.logger.info(f"Created {dir_name} directory: {path}")
                        except Exception as e:
                            ctx.logger.error(f"Failed to create {dir_name} directory {path}: {e!s}")
                            success = False
                    
                    # Check if directory is writable
                    if not os.access(path, os.W_OK):
                        ctx.logger.error(f"{dir_name} directory {path} is not writable")
                        success = False
                except Exception as e:
                    ctx.logger.error(f"Error checking {dir_name} directory: {e!s}")
                    success = False
            
            # Check weather cache
            try:
                cache: WeatherResponseCache = WeatherResponseCache(os.path.join(ctx.config.get('data_dir', 'data'), 'weather_cache.db'))
                cache.clear()  # Just clear the cache, don't check return value
            except Exception as e:
                ctx.logger.error(f"Failed to check weather cache: {e!s}")
                success = False
            
            # Check user configurations
            for username in users:
                try:
                    ctx.logger.info(f"Checking configuration for user {username}")
                    user_config: UserConfig | None = ctx.config.users.get(username)
                    
                    if not user_config:
                        ctx.logger.error(f"No configuration found for user {username}")
                        success = False
                        continue
                    
                    # Check required user fields
                    required_fields: list[str] = ['memberships']
                    for field in required_fields:
                        if field not in user_config:
                            ctx.logger.error(f"Missing required field '{field}' in user config for {username}")
                            success = False
                    
                    # Check club memberships
                    for membership in user_config.get('memberships', []):
                        if 'club' not in membership:
                            ctx.logger.error(f"Missing 'club' in membership config for user {username}")
                            success = False
                        elif 'auth_details' not in membership:
                            ctx.logger.error(f"Missing 'auth_details' in membership config for club {membership['club']} for user {username}")
                            success = False
                    
                    # Initialize services for basic checks
                    reservation_service: ReservationService = ReservationService(username, ctx.config)
                    calendar_service: CalendarService = CalendarService(ctx.config)
                    
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
                        weather_service: WeatherServiceProtocol = cast(WeatherServiceProtocol, WeatherService(
                            config={
                                **dict(ctx.config.global_config),
                                'dev_mode': ctx.args.dev
                            }
                        ))
                        for service_name, service in weather_service.services.items():
                            try:
                                if hasattr(service, 'is_healthy') and not service.is_healthy():
                                    ctx.logger.error(f"Weather service {service_name} is not available")
                                    success = False
                                else:
                                    ctx.logger.info(f"Weather service {service_name} is available")
                            except Exception as e:
                                ctx.logger.error(f"Weather service {service_name} check failed: {e!s}")
                                success = False
                        
                        # Check club APIs
                        for membership in user_config.get('memberships', []):
                            club_name: str | None = membership.get('club')
                            if not club_name:
                                continue
                            
                            try:
                                club: GolfClubProtocol | None = cast(GolfClubProtocol, reservation_service.get_club(club_name))
                                if club:
                                    if hasattr(club, 'is_healthy') and not club.is_healthy:
                                        ctx.logger.error(f"Club API for {club_name} is not available")
                                        success = False
                                    else:
                                        ctx.logger.info(f"Club API for {club_name} is available")
                                else:
                                    ctx.logger.error(f"Club {club_name} not found in configuration")
                                    success = False
                            except Exception as e:
                                ctx.logger.error(f"Club API check failed for {club_name}: {e!s}")
                                success = False
                        
                        # Check external calendar services if configured
                        if calendar_service.external_event_service:
                            try:
                                external_service: ExternalEventServiceProtocol = cast(ExternalEventServiceProtocol, calendar_service.external_event_service)
                                if not external_service.is_healthy:
                                    ctx.logger.error("External calendar services are not available")
                                    success = False
                                else:
                                    ctx.logger.info("External calendar services are available")
                            except Exception as e:
                                ctx.logger.error(f"External calendar services check failed: {e!s}")
                                success = False
                    
                except Exception as e:
                    ctx.logger.error(f"Failed to check configuration for user {username}: {e}", exc_info=True)
                    success = False
            
            if success:
                ctx.logger.info("All configuration checks passed successfully")
            else:
                ctx.logger.error("One or more configuration checks failed")
            
            return 0 if success else 1
            
        except Exception as e:
            ctx.logger.error(f"Failed to check configuration: {e}", exc_info=True)
            return 1

@create_command_group('import', 'Import commands')
class ImportCommands:
    """Import command implementations."""
    
    @staticmethod
    @CommandRegistry.register(
        name='csv',
        help_text='Import events from a CSV file',
        category=CommandCategory.IMPORT,
        options=[
            {
                'name': '--file',
                'type': str,
                'required': True,
                'help': 'Path to the CSV file to import'
            },
            {
                'name': '--recurring-until',
                'type': str,
                'help': 'Create weekly recurring events until this date (format: YYYY-MM-DD)'
            },
            {
                'name': '--recurrence-end',
                'type': str,
                'help': 'End date for recurring events, takes precedence over --recurring-until (format: YYYY-MM-DD)'
            },
            {
                'name': '--timezone',
                'type': str,
                'help': 'Timezone for the events (e.g. Europe/Helsinki, UTC)'
            },
            {
                'name': '--delimiter',
                'type': str,
                'default': ';',
                'help': 'CSV delimiter character (default: ;)'
            },
            {
                'name': '--temp-user',
                'type': str,
                'help': 'Create a temporary user with this name (if not in users.json)'
            }
        ],
        parent_command='import'
    )
    def import_csv(ctx: CLIContext) -> int:
        """Import events from a CSV file."""
        try:
            # Get or create user
            username: str | None = ctx.args.user or ctx.args.temp_user or ctx.config.get('default_user')
            if not username:
                ctx.logger.error("No username specified and no default user configured")
                return 1

            # Create temporary user if needed
            if ctx.args.temp_user:
                user: User = User(
                    name=username,
                    memberships=[],  # No memberships needed for external events
                    email=None,
                    phone=None,
                    handicap=None
                )
            else:
                # Get user from config
                user_config: UserConfig | None = ctx.config.get_user_config(username)
                if not user_config:
                    ctx.logger.error(f"User {username} not found in configuration")
                    return 1
                user = User.from_config(username, dict(user_config))

            # Parse recurring_until date if provided
            recurring_until: datetime | None = None
            if ctx.args.recurring_until:
                try:
                    recurring_until = datetime.strptime(ctx.args.recurring_until, "%Y-%m-%d")
                    recurring_until = recurring_until.replace(hour=23, minute=59, second=59)
                    recurring_until = recurring_until.replace(tzinfo=ZoneInfo(ctx.args.timezone or ctx.config.timezone))
                except ValueError:
                    ctx.logger.error("Invalid recurring-until date format. Use YYYY-MM-DD")
                    return 1

            # Parse recurrence_end date if provided
            recurrence_end: datetime | None = None
            if ctx.args.recurrence_end:
                try:
                    recurrence_end = datetime.strptime(ctx.args.recurrence_end, "%Y-%m-%d")
                    recurrence_end = recurrence_end.replace(hour=23, minute=59, second=59)
                    recurrence_end = recurrence_end.replace(tzinfo=ZoneInfo(ctx.args.timezone or ctx.config.timezone))
                except ValueError:
                    ctx.logger.error("Invalid recurrence-end date format. Use YYYY-MM-DD")
                    return 1

            # Initialize services
            csv_service: CSVImportService = CSVImportService(timezone=ctx.args.timezone or ctx.config.timezone)
            calendar_service: CalendarService = CalendarService(ctx.config)

            # Import reservations from CSV
            reservations: list[Reservation] = csv_service.import_from_csv(
                file_path=ctx.args.file,
                user=user,
                recurring_until=recurring_until,
                recurrence_end=recurrence_end,
                timezone=ctx.args.timezone,
                delimiter=ctx.args.delimiter
            )

            if not reservations:
                ctx.logger.warning("No events found in CSV file")
                return 0

            # Create calendar with imported events
            calendar_service.process_user_reservations(user, reservations)

            # Print summary
            print(f"\nImported {len(reservations)} events")
            if recurring_until:
                end_date = recurrence_end if recurrence_end else recurring_until
                print(f"Created weekly recurring events until {end_date.date()}")
            if ctx.args.timezone:
                print(f"Events created in timezone: {ctx.args.timezone}")

            return 0

        except Exception as e:
            ctx.logger.error(f"Failed to import CSV: {e!s}")
            return 1

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser using the new CLI builder."""
    builder = CLIBuilder(
        description='Golf calendar application for managing golf reservations and related weather data'
    )
    
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
        if hasattr(args, subcommand_attr):
            subcommand = getattr(args, subcommand_attr)
            if subcommand:
                command_name = subcommand
        
        command = CommandRegistry.get_command(command_name)
        if not command:
            logger.error(f"Unknown command: {args.command}")
            return 1
            
        errors = ArgumentValidator.validate_args(args, command)
        if errors:
            for error in errors:
                logger.error(error)
            return 1
        
        # Execute command handler with context
        return command.handler(ctx)
            
    except Exception:
        logger = get_logger(__name__)
        logger.exception("Unhandled exception")
        return 1

if __name__ == '__main__':
    sys.exit(main())