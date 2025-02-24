"""
Reservation factory with strategy pattern implementation.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from golfcal2.models.golf_club import GolfClub
from golfcal2.models.reservation import Player, Reservation
from golfcal2.models.user import Membership, User
from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.utils.timezone_utils import TimezoneManager


class ReservationContext:
    """Context for reservation creation."""
    
    def __init__(
        self,
        club: GolfClub,
        user: User,
        membership: Membership,
        tz_manager: TimezoneManager | None = None
    ):
        self.club = club
        self.user = user
        self.membership = membership
        self.tz_manager = tz_manager or TimezoneManager()

class ReservationStrategy(ABC, LoggerMixin):
    """Base strategy for creating reservations."""
    
    @abstractmethod
    def create_reservation(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> Reservation:
        """Create a reservation from raw data."""
        pass
    
    @abstractmethod
    def extract_players(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> list[Player]:
        """Extract players from reservation data."""
        pass
    
    def parse_times(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> tuple[datetime, datetime]:
        """Parse start and end times from data."""
        pass

class WiseGolfStrategy(ReservationStrategy):
    """Strategy for WiseGolf reservations.
    
    Player Matching Logic:
    ---------------------
    Players are matched based on their start time and resource ID. This is because:
    1. Each player has a reservationTimeId that points to a row in the 'rows' array
    2. Each row contains a start time and a list of resources
    3. Players in the same reservation will have different reservationTimeIds but the same:
       - start time (exact match required)
       - resource ID (exact match required)
    4. There can be multiple reservationTimeIds for a single reservation
    
    The matching process:
    1. Get the start time and resource ID from our reservation
    2. Find all rows in player_data_list['rows'] that match both criteria
    3. Collect the reservationTimeIds from these matching rows
    4. Find all players whose reservationTimeId matches any of the collected IDs
    """
    
    def create_reservation(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> Reservation:
        """Create a WiseGolf reservation."""
        start_time, end_time = self.parse_times(data, context)
        players = self.extract_players(data, context)
        
        return Reservation(
            club=context.club,
            user=context.user,
            membership=context.membership,
            start_time=start_time,
            end_time=end_time,
            players=players,
            raw_data=data,
            _tz_manager=context.tz_manager
        )
    
    def parse_times(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> tuple[datetime, datetime]:
        """Parse start and end times from WiseGolf data."""
        start_time = datetime.strptime(data["dateTimeStart"], "%Y-%m-%d %H:%M:%S")
        start_time = context.tz_manager.localize_datetime(start_time)
        end_time = context.club.get_end_time(start_time, context.membership.duration)
        return start_time, end_time
    
    def extract_players(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> list[Player]:
        """Extract players from WiseGolf data.
        
        The function follows these steps:
        1. For future events, try to fetch additional players from the API
        2. From the API response, find all time slots that match our start time and resource ID
        3. Collect all players whose reservationTimeId matches any of our matching time slots
        4. If no players found from API, try using the raw data
        5. If still no players found, use the user as the default player
        
        Args:
            data: Raw reservation data containing dateTimeStart and resource information
            context: Context containing club, user, and membership information
            
        Returns:
            List of Player objects for this reservation
        """
        players: list[Player] = []
        
        # Try to fetch players for future events
        now = context.tz_manager.now()
        start_time = datetime.strptime(data["dateTimeStart"], "%Y-%m-%d %H:%M:%S")
        start_time = context.tz_manager.localize_datetime(start_time)
        is_future_event = start_time > now
        
        if is_future_event and hasattr(context.club, 'fetch_players'):
            try:
                player_data_list = context.club.fetch_players(data, context.membership)
                
                if isinstance(player_data_list, dict):
                    if 'reservationsGolfPlayers' in player_data_list and 'rows' in player_data_list:
                        # Get our reservation's details
                        our_start_time = data.get('dateTimeStart')
                        our_resource_id = None
                        if data.get('resources'):
                            our_resource_id = data['resources'][0].get('resourceId')
                        elif 'resourceId' in data:
                            our_resource_id = data.get('resourceId')
                        
                        # Find all time slots for this resource and start time
                        matching_time_ids = set()
                        for row in player_data_list['rows']:
                            if row.get('start') != our_start_time:
                                continue
                            
                            # Check if this row has our resource ID
                            for resource in row.get('resources', []):
                                if resource.get('resourceId') == our_resource_id:
                                    matching_time_ids.add(row.get('reservationTimeId'))
                                    break
                        
                        # Get all players that have any of these time IDs
                        for player in player_data_list['reservationsGolfPlayers']:
                            if player.get('reservationTimeId') in matching_time_ids:
                                players.append(Player.from_wisegolf(player))
            
            except Exception as e:
                self.error(f"Failed to fetch players: {e}", exc_info=True)
        
        # If no players found, try using the raw data
        if not players:
            if 'reservationsGolfPlayers' in data:
                # Get our time ID from the raw data
                our_time_id = data.get('reservationTimeId')
                
                # Find players with matching time ID
                for player_data in data['reservationsGolfPlayers']:
                    if player_data.get('reservationTimeId') == our_time_id:
                        players.append(Player.from_wisegolf(player_data))
        
        # If still no players found, add the user as default player
        if not players:
            players = [Player(
                name=context.user.name,
                club=context.membership.club_abbreviation,
                handicap=float(context.user.handicap or 0.0)
            )]
        
        return players

class WiseGolf0Strategy(WiseGolfStrategy):
    """Strategy for WiseGolf0 reservations.
    
    Player Matching Logic:
    ---------------------
    Players are matched based on their start time and resource ID. This is because:
    1. Each player has a reservationTimeId that points to a row in the 'rows' array
    2. Each row contains a start time and a list of resources
    3. Players in the same reservation will have different reservationTimeIds but the same:
       - start time (exact match required)
       - resource ID (exact match required)
    4. There can be multiple reservationTimeIds for a single reservation
    
    The matching process:
    1. Get the start time and resource ID from our reservation
    2. Find all rows in player_data_list['rows'] that match both criteria
    3. Collect the reservationTimeIds from these matching rows
    4. Find all players whose reservationTimeId matches any of the collected IDs
    """
    
    def parse_times(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> tuple[datetime, datetime]:
        """Parse start and end times from WiseGolf0 data."""
        start_time = datetime.strptime(data["dateTimeStart"], "%Y-%m-%d %H:%M:%S")
        start_time = context.tz_manager.localize_datetime(start_time)
        end_time = context.club.get_end_time(start_time, context.membership.duration)
        return start_time, end_time
    
    def extract_players(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> list[Player]:
        """Extract players from WiseGolf0 data.
        
        The function follows these steps:
        1. For future events, try to fetch additional players from the API
        2. From the API response, find all time slots that match our start time and resource ID
        3. Collect all players whose reservationTimeId matches any of our matching time slots
        4. If no players found from API, try using the raw data
        5. If still no players found, use the user as the default player
        
        Args:
            data: Raw reservation data containing dateTimeStart and resource information
            context: Context containing club, user, and membership information
            
        Returns:
            List of Player objects for this reservation
        """
        players: list[Player] = []
        
        # Try to fetch players for future events
        now = context.tz_manager.now()
        start_time = datetime.strptime(data["dateTimeStart"], "%Y-%m-%d %H:%M:%S")
        start_time = context.tz_manager.localize_datetime(start_time)
        is_future_event = start_time > now
        
        if is_future_event and hasattr(context.club, 'fetch_players'):
            try:
                player_data_list = context.club.fetch_players(data, context.membership)
                
                if isinstance(player_data_list, dict):
                    if 'reservationsGolfPlayers' in player_data_list and 'rows' in player_data_list:
                        # Get our reservation's details
                        our_start_time = data.get('dateTimeStart')
                        our_resource_id = None
                        if data.get('resources'):
                            our_resource_id = data['resources'][0].get('resourceId')
                        elif 'resourceId' in data:
                            our_resource_id = data.get('resourceId')
                        
                        # Find all time slots for this resource and start time
                        matching_time_ids = set()
                        for row in player_data_list['rows']:
                            if row.get('start') != our_start_time:
                                continue
                            
                            # Check if this row has our resource ID
                            for resource in row.get('resources', []):
                                if resource.get('resourceId') == our_resource_id:
                                    matching_time_ids.add(row.get('reservationTimeId'))
                                    break
                        
                        # Get all players that have any of these time IDs
                        for player in player_data_list['reservationsGolfPlayers']:
                            if player.get('reservationTimeId') in matching_time_ids:
                                players.append(Player.from_wisegolf(player))
            
            except Exception as e:
                self.error(f"Failed to fetch players: {e}", exc_info=True)
        
        # If no players found, try using the raw data
        if not players:
            if 'reservationsGolfPlayers' in data:
                # Get our time ID from the raw data
                our_time_id = data.get('reservationTimeId')
                
                # Find players with matching time ID
                for player_data in data['reservationsGolfPlayers']:
                    if player_data.get('reservationTimeId') == our_time_id:
                        players.append(Player.from_wisegolf(player_data))
        
        # If still no players found, add the user as default player
        if not players:
            players = [Player(
                name=context.user.name,
                club=context.membership.club_abbreviation,
                handicap=float(context.user.handicap or 0.0)
            )]
        
        return players

class NexGolfStrategy(ReservationStrategy):
    """Strategy for NexGolf reservations."""
    
    def create_reservation(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> Reservation:
        """Create a NexGolf reservation."""
        start_time, end_time = self.parse_times(data, context)
        players = self.extract_players(data, context)
        
        return Reservation(
            club=context.club,
            user=context.user,
            membership=context.membership,
            start_time=start_time,
            end_time=end_time,
            players=players,
            raw_data=data,
            _tz_manager=context.tz_manager
        )
    
    def parse_times(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> tuple[datetime, datetime]:
        """Parse start and end times from NexGolf data."""
        start_time = context.club.parse_start_time(data)
        if start_time.tzinfo is None:
            start_time = context.tz_manager.localize_datetime(start_time)
        end_time = context.club.get_end_time(start_time, context.membership.duration)
        return start_time, end_time
    
    def extract_players(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> list[Player]:
        """Extract players from NexGolf data."""
        players: list[Player] = []
        
        if "reservations" in data:
            try:
                for player_data in data["reservations"]:
                    if player_data and isinstance(player_data, dict):
                        player = Player.from_nexgolf(player_data)
                        players.append(player)
            except Exception as e:
                self.error(f"Failed to process NexGolf player data: {e}", exc_info=True)
        
        # If no players found, add the user as default player
        if not players:
            players = [Player(
                name=context.user.name,
                club=context.membership.club_abbreviation,
                handicap=float(context.user.handicap or 0.0)
            )]
        
        return players

class ExternalEventStrategy(ReservationStrategy):
    """Strategy for external event reservations."""
    
    def create_reservation(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> Reservation:
        """Create an external event reservation."""
        start_time, end_time = self.parse_times(data, context)
        players = self.extract_players(data, context)
        
        return Reservation(
            club=context.club,
            user=context.user,
            membership=context.membership,
            start_time=start_time,
            end_time=end_time,
            players=players,
            raw_data=data,
            _tz_manager=context.tz_manager
        )
    
    def parse_times(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> tuple[datetime, datetime]:
        """Parse start and end times from external event data."""
        if 'start_time' in data and 'end_time' in data:
            # Handle dynamic dates
            start = self._parse_dynamic_time(data['start_time'], context.club.timezone)
            end = self._parse_dynamic_time(data['end_time'], context.club.timezone)
        else:
            # Handle fixed dates
            start = datetime.fromisoformat(data['start'])
            end = datetime.fromisoformat(data['end'])
            
            # Set timezone if not already set
            if start.tzinfo is None:
                start = start.replace(tzinfo=ZoneInfo(context.club.timezone))
            if end.tzinfo is None:
                end = end.replace(tzinfo=ZoneInfo(context.club.timezone))
        
        return start, end
    
    def extract_players(
        self,
        data: dict[str, Any],
        context: ReservationContext
    ) -> list[Player]:
        """Extract players from external event data."""
        players = []
        if 'users' in data:
            for username in data['users']:
                players.append(Player(
                    name=username,
                    club="EXT",  # External event marker
                    handicap=0.0  # No handicap for external events
                ))
        return players
    
    def _parse_dynamic_time(self, time_str: str, timezone: str) -> datetime:
        """Parse dynamic time string (e.g., 'tomorrow 10:00')."""
        parts = time_str.split()
        if len(parts) != 2:
            raise ValueError(f"Invalid time format: {time_str}")
        
        time_parts = parts[1].split(':')
        if len(time_parts) != 2:
            raise ValueError(f"Invalid time format: {parts[1]}")
        
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        
        now = datetime.now(ZoneInfo(timezone))
        if parts[0] == 'tomorrow':
            target_date = now.date() + timedelta(days=1)
        elif parts[0] == 'today':
            target_date = now.date()
        else:
            # Format: "N days"
            try:
                days = int(parts[0].split()[0])
                target_date = now.date() + timedelta(days=days)
            except (ValueError, IndexError):
                raise ValueError(f"Invalid date format: {parts[0]}")
        
        return datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute), tzinfo=ZoneInfo(timezone))

class ReservationFactory:
    """Factory for creating reservations."""
    
    _strategies = {
        'wisegolf': WiseGolfStrategy(),
        'wisegolf0': WiseGolf0Strategy(),
        'nexgolf': NexGolfStrategy(),
        'external': ExternalEventStrategy()
    }
    
    @classmethod
    def create_reservation(
        cls,
        reservation_type: str,
        data: dict[str, Any],
        context: ReservationContext
    ) -> Reservation:
        """Create a reservation using the appropriate strategy."""
        strategy = cls._strategies.get(reservation_type)
        if not strategy:
            raise ValueError(f"Unsupported reservation type: {reservation_type}")
        
        return strategy.create_reservation(data, context) 