"""
Command-line interface for golf calendar application.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

from golfcal2.config.settings import load_config, AppConfig
from golfcal2.services.calendar_service import CalendarService
from golfcal2.services.reservation_service import ReservationService
from golfcal2.utils.logging_utils import setup_logging, get_logger
from golfcal2.models.user import User

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for CLI."""
    parser = argparse.ArgumentParser(
        description="Golf Calendar - Manage golf reservations and create calendar files"
    )
    
    # Common arguments
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--log-file",
        help="Log file path"
    )
    parser.add_argument(
        "-u", "--user",
        help="Process only specified user (development/testing mode)"
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Development mode - adds -dev suffix to calendar files"
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Process command
    process_parser = subparsers.add_parser(
        "process",
        help="Process reservations and create calendar files"
    )
    process_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to include past reservations (default: 7)"
    )
    process_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without creating calendar files"
    )
    
    # List command
    list_parser = subparsers.add_parser(
        "list",
        help="List reservations"
    )
    list_parser.add_argument(
        "--active",
        action="store_true",
        help="Show only active reservations"
    )
    list_parser.add_argument(
        "--upcoming",
        action="store_true",
        help="Show only upcoming reservations"
    )
    list_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look ahead/behind (default: 7)"
    )
    list_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    
    # Check command
    check_parser = subparsers.add_parser(
        "check",
        help="Check reservations for issues"
    )
    check_parser.add_argument(
        "--check",
        choices=["overlaps", "past", "future", "players", "times", "all"],
        default="all",
        help="Type of check to perform (default: all)"
    )
    check_parser.add_argument(
        "--future-threshold",
        type=int,
        default=4,
        help="Hours between reservations to flag as potential conflict (default: 4)"
    )
    
    return parser

def get_users_to_process(args: argparse.Namespace, config: AppConfig, logger: logging.Logger) -> Dict[str, Any]:
    """Get users to process based on command line arguments.
    
    Args:
        args: Command line arguments
        config: Application configuration
        logger: Logger instance
        
    Returns:
        Dictionary of users to process, mapping user names to their configurations.
        Returns empty dict if specified user is not found.
    """
    if args.user:
        if args.user not in config.users:
            logger.error(f"User '{args.user}' not found in configuration")
            return {}
        logger.debug(f"Development mode: Processing only user {args.user}")
        return {args.user: config.users[args.user]}
    
    logger.debug(f"Processing all {len(config.users)} users")
    return config.users

def process_command(args: argparse.Namespace, logger: logging.Logger, is_dev: bool = False) -> int:
    """Process reservations and create calendar files.
    
    Args:
        args: Command line arguments including:
            - days: Number of days of past reservations to include
            - user (optional): Process only this user
            - dev (optional): Add -dev suffix to calendar files
            - dry_run: Show what would be done without creating files
        logger: Logger instance
        is_dev: Whether to run in development mode
        
    Returns:
        0 on success, 1 on failure
    """
    try:
        logger.debug("Loading configuration...")
        config = load_config()
        logger.debug("Creating services...")
        dev_mode = args.dev or is_dev
        calendar_service = CalendarService(config, dev_mode=dev_mode)
        
        users = get_users_to_process(args, config, logger)
        if not users:
            return 1
        
        if args.dry_run:
            logger.info("Dry run mode - no files will be created")
        
        for user_name, user_config in users.items():
            try:
                logger.info(f"Processing reservations for {user_name}")
                reservation_service = ReservationService(config, user_name)
                _, reservations = reservation_service.process_user(
                    user_name,
                    user_config,
                    past_days=args.days
                )
                user = User.from_config(user_name, user_config)
                
                if args.dry_run:
                    logger.info(f"Would process {len(reservations)} reservations for {user_name}")
                    for reservation in reservations:
                        logger.info(f"  - {reservation.format_for_display()}")
                else:
                    calendar_service.process_user_reservations(user, reservations)
                    logger.info(f"Successfully processed calendar for {user_name}")
            except Exception as e:
                logger.error(f"Failed to process calendar for {user_name}: {e}", exc_info=True)
                if args.user:  # If processing single user, fail immediately
                    return 1
        
        return 0
    
    except Exception as e:
        logger.error(f"Failed to process reservations: {e}", exc_info=True)
        return 1

def list_command(args: argparse.Namespace, logger: logging.Logger) -> int:
    """List reservations for users.
    
    Args:
        args: Command line arguments including:
            - active: Show only active reservations
            - upcoming: Show only upcoming reservations
            - days: Number of days to look ahead/behind
            - user (optional): List only this user's reservations
            - format: Output format (text or json)
        logger: Logger instance
        
    Returns:
        0 on success, 1 on failure
    """
    try:
        config = load_config()
        users = get_users_to_process(args, config, logger)
        if not users:
            return 1
        
        all_reservations = []
        for user_name, user_config in users.items():
            reservation_service = ReservationService(config, user_name)
            reservations = reservation_service.list_reservations(
                active_only=args.active,
                upcoming_only=args.upcoming,
                days=args.days
            )
            
            if not reservations:
                logger.info(f"No reservations found for user {user_name}")
                continue
            
            if args.format == "json":
                all_reservations.extend([{
                    "user": user_name,
                    "date": r.start_time.isoformat(),
                    "club": r.club,
                    "players": [p.name for p in r.players],
                    "status": "active" if r.is_active() else "upcoming" if r.is_upcoming() else "past"
                } for r in reservations])
            else:
                logger.info(f"Listing reservations for user {user_name}")
                for reservation in reservations:
                    print(reservation.format_for_display())
        
        if args.format == "json" and all_reservations:
            import json
            print(json.dumps(all_reservations, indent=2))
        
        return 0
    
    except Exception as e:
        logger.error(f"Failed to list reservations: {e}")
        return 1

def check_command(args: argparse.Namespace, logger: logging.Logger) -> int:
    """Check reservations for potential issues.
    
    Args:
        args: Command line arguments including:
            - check: Type of check to perform (overlaps, past, future, players, times, all)
            - user (optional): Check only this user's reservations
            - future_threshold: Hours between reservations to flag as conflict
        logger: Logger instance
        
    Returns:
        0 if no issues found, 1 if issues found or on error
    """
    try:
        config = load_config()
        users = get_users_to_process(args, config, logger)
        if not users:
            return 1
        
        has_issues = False
        for user_name, user_config in users.items():
            reservation_service = ReservationService(config, user_name)
            all_reservations = reservation_service.list_reservations()
            
            # Overlapping reservations
            if args.check in ["overlaps", "all"]:
                overlaps = reservation_service.check_overlaps()
                if overlaps:
                    logger.warning(f"Found overlapping reservations for user {user_name}:")
                    for overlap in overlaps:
                        print(overlap.format_for_display())
                    has_issues = True
                else:
                    logger.info(f"No overlapping reservations found for user {user_name}")
            
            # Past reservations
            if args.check in ["past", "all"]:
                past = [r for r in all_reservations if r.is_past()]
                if past:
                    logger.warning(f"Found {len(past)} past reservations for user {user_name}:")
                    for reservation in past:
                        print(reservation.format_for_display())
                    has_issues = True
                else:
                    logger.info(f"No past reservations found for user {user_name}")
            
            # Future conflicts (reservations too close together)
            if args.check in ["future", "all"]:
                future = sorted([r for r in all_reservations if r.is_upcoming()], 
                              key=lambda x: x.start_time)
                for i in range(len(future) - 1):
                    time_diff = (future[i + 1].start_time - future[i].end_time).total_seconds() / 3600
                    if time_diff < args.future_threshold:
                        logger.warning(f"Found close reservations for user {user_name} "
                                     f"({time_diff:.1f} hours apart):")
                        print(future[i].format_for_display())
                        print(future[i + 1].format_for_display())
                        has_issues = True
            
            # Missing or incomplete player information
            if args.check in ["players", "all"]:
                incomplete = [r for r in all_reservations if not r.players]
                if incomplete:
                    logger.warning(f"Found {len(incomplete)} reservations with missing player "
                                 f"information for user {user_name}:")
                    for reservation in incomplete:
                        print(reservation.format_for_display())
                    has_issues = True
            
            # Unusual tee times (very early or late)
            if args.check in ["times", "all"]:
                unusual = [r for r in all_reservations 
                          if r.start_time.hour < 6 or r.start_time.hour > 20]
                if unusual:
                    logger.warning(f"Found {len(unusual)} reservations at unusual times "
                                 f"for user {user_name}:")
                    for reservation in unusual:
                        print(reservation.format_for_display())
                    has_issues = True
        
        return 1 if has_issues else 0
    
    except Exception as e:
        logger.error(f"Failed to check reservations: {e}")
        return 1

def main() -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Set up logging based on command line arguments
    setup_logging(
        level='WARNING',
        log_file=args.log_file,
        dev_mode=args.dev,
        verbose=args.verbose
    )
    
    logger = get_logger(__name__)
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute command
    if args.command == "process":
        return process_command(args, logger, is_dev=args.dev)
    elif args.command == "list":
        return list_command(args, logger)
    elif args.command == "check":
        return check_command(args, logger)
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1 