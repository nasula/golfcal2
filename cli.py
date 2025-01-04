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
    list_parser = subparsers.add_parser('list', help='List golf courses')
    list_parser.add_argument('--all', action='store_true', help='List all courses')
    
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
        
        reservation_service = ReservationService(config, args.user)
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
    """List golf courses."""
    try:
        logger.info(f"Listing courses for user {args.user}")
        
        reservation_service = ReservationService(config, args.user)
        courses = reservation_service.list_courses(include_all=args.all)
        
        if not courses:
            logger.info("No courses found")
            return 0
        
        for course in courses:
            print(f"- {course}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to list courses: {e}", exc_info=True)
        return 1

def check_command(args: argparse.Namespace, logger: logging.Logger, config: AppConfig) -> int:
    """Check configuration."""
    try:
        logger.info(f"Checking configuration for user {args.user}")
        
        if args.full:
            logger.info("Performing full configuration check")
            # TODO: Implement full check
        
        # Basic check
        reservation_service = ReservationService(config, args.user)
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
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    try:
        # Load config first
        config = load_config(dev_mode=args.dev, verbose=args.verbose)
        
        # Set up logging through config system
        setup_logging(config, dev_mode=args.dev, verbose=args.verbose)
        
        logger = get_logger(__name__)
        
        if not args.command:
            parser.print_help()
            return 0
        
        # Execute command
        if args.command == "process":
            return process_command(args, logger, config, is_dev=args.dev)
        elif args.command == "list":
            return list_command(args, logger, config)
        elif args.command == "check":
            return check_command(args, logger, config)
        else:
            logger.error(f"Unknown command: {args.command}")
            return 1 
    except Exception as e:
        logger.error(f"Failed to run CLI: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 