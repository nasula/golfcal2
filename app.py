"""
Main application module for golf calendar.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from .config.settings import AppConfig, load_config
from .services.calendar_service import CalendarService
from .services.reservation_service import ReservationService
from .models.user import User
from .models.reservation import Reservation
from .models.golf_club import GolfClubFactory, GolfClubConfig
from .services.weather_service import WeatherService

logger = logging.getLogger(__name__)

class GolfCalendarApp:
    """Main application class for golf calendar."""

    def __init__(self, config: AppConfig):
        """Initialize application with configuration."""
        self.config = config
        self.weather_service = WeatherService()
        self.calendar_service = CalendarService(self.config)
        self.reservation_service = ReservationService(self.weather_service, self.config)

    def initialize(self) -> None:
        """Initialize application services."""
        try:
            # Load and validate configurations
            self.config.validate()
            
            # Load club configurations
            club_data = self.config.load_club_config()
            self.clubs = {
                name: GolfClubFactory.create_from_dict({**data, 'name': name})
                for name, data in club_data.items()
            }

            # Load user configurations
            user_data = self.config.load_user_config()
            self.users = {
                name: User.from_config(name, data)
                for name, data in user_data.items()
            }

            logger.info("Application initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            raise

    def process_user_reservations(self, user_name: str) -> List[Reservation]:
        """Process reservations for a specific user."""
        try:
            user = self.users.get(user_name)
            if not user:
                raise ValueError(f"Unknown user: {user_name}")

            # Get reservations
            reservations = self.reservation_service.get_user_reservations(user)
            
            # Create calendar
            self.calendar_service.process_user_reservations(user, reservations)
            
            logger.info(f"Successfully processed reservations for {user_name}")
            return reservations

        except Exception as e:
            logger.error(f"Failed to process reservations for {user_name}: {e}")
            return []

    def process_all_users(self) -> Dict[str, List[Reservation]]:
        """Process reservations for all users."""
        results = {}
        for user_name in self.users:
            results[user_name] = self.process_user_reservations(user_name)
        return results

    def get_active_reservations(self, reference_time: Optional[datetime] = None) -> Dict[str, List[Reservation]]:
        """Get all active reservations."""
        if reference_time is None:
            reference_time = datetime.now()

        active_reservations = {}
        for user_name, reservations in self.process_all_users().items():
            active = [r for r in reservations if r.is_active(reference_time)]
            if active:
                active_reservations[user_name] = active

        return active_reservations

    def get_upcoming_reservations(self, reference_time: Optional[datetime] = None) -> Dict[str, List[Reservation]]:
        """Get all upcoming reservations."""
        if reference_time is None:
            reference_time = datetime.now()

        upcoming_reservations = {}
        for user_name, reservations in self.process_all_users().items():
            upcoming = [r for r in reservations if r.is_upcoming(reference_time)]
            if upcoming:
                upcoming_reservations[user_name] = upcoming

        return upcoming_reservations

    def check_overlapping_reservations(self) -> Dict[str, List[Tuple[Reservation, Reservation]]]:
        """Check for overlapping reservations for all users."""
        overlaps = {}
        
        for user_name, reservations in self.process_all_users().items():
            user_overlaps = []
            for i, res1 in enumerate(reservations):
                for res2 in reservations[i+1:]:
                    if res1.overlaps_with(res2):
                        user_overlaps.append((res1, res2))
            
            if user_overlaps:
                overlaps[user_name] = user_overlaps 