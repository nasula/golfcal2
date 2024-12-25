"""
Reservation model for golf calendar application.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.models.golf_club import GolfClub
from golfcal2.models.user import User, Membership

@dataclass
class Player:
    """Player details."""
    name: str
    club: str
    handicap: float

    @classmethod
    def from_wisegolf(cls, data: Dict[str, Any]) -> "Player":
        """Create Player instance from WiseGolf data."""
        # Extract name components
        first_name = data.get("firstName", data.get("name", "")).split()[0] if data.get("firstName", data.get("name", "")) else ""
        family_name = (
            data.get("familyName", "") or 
            " ".join(data.get("name", "").split()[1:]) if data.get("name", "") else ""
        )
        
        # Extract club abbreviation
        club = data.get("clubAbbreviation", data.get("club", "N/A"))
        
        # Extract handicap
        handicap_str = str(data.get("handicapActive", data.get("handicap", "0.0")))
        try:
            handicap = float(handicap_str)
        except (ValueError, TypeError):
            handicap = 0.0
        
        return cls(
            name=f"{first_name} {family_name}".strip(),
            club=club,
            handicap=handicap
        )

    @classmethod
    def from_nexgolf(cls, data: Dict[str, Any]) -> "Player":
        """Create Player instance from NexGolf data."""
        player_data = data["player"] if "player" in data else {}
        first_name = player_data["firstName"] if "firstName" in player_data else ""
        last_name = player_data["lastName"] if "lastName" in player_data else ""
        club_data = player_data["club"] if "club" in player_data else {}
        club = club_data["abbreviation"] if "abbreviation" in club_data else "N/A"
        handicap = float(player_data["handicap"]) if "handicap" in player_data else 0.0
        
        return cls(
            name=f"{first_name} {last_name}".strip(),
            club=club,
            handicap=handicap
        )

@dataclass
class Reservation(LoggerMixin):
    """Golf reservation."""
    club: GolfClub
    user: User
    membership: Membership
    start_time: datetime
    end_time: datetime
    players: List[Player]
    raw_data: Dict[str, Any]

    @property
    def total_handicap(self) -> float:
        """Calculate total handicap of all players."""
        return round(sum(p.handicap for p in self.players), 1)

    def get_event_summary(self) -> str:
        """Get event summary for calendar."""
        # Format time in 24-hour format
        time_str = self.start_time.strftime('%H:%M')
        
        # Get variant name (for WiseGolf0, it's in variantName field before the colon)
        if "variantName" in self.raw_data:
            variant = self.raw_data["variantName"].split(":")[0]
        else:
            variant = self.club.variant
        
        # Get player count and total handicap
        player_count = len(self.players)
        total_hcp = self.total_handicap
        
        # Build summary string
        summary = f"Golf: {self.club.name} {time_str} - {variant}"
        if player_count > 0:
            summary += f" ({player_count} Players, THCP: {total_hcp})"
        
        return summary

    def get_event_description(self, weather: Optional[str] = None) -> str:
        """Get event description for calendar."""
        description = [f"Teetime {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}"]
        
        # Add player details
        for player in self.players:
            player_info = f"{player.name}, {player.club}, HCP: {player.handicap}"
            description.append(player_info)
        
        # Add weather if available
        if weather:
            description.append(f"\nWeather:\n{weather}")
        
        return "\n".join(description)

    def get_event_location(self) -> str:
        """Get event location for calendar."""
        return self.club.get_event_location()

    def get_event_uid(self) -> str:
        """
        Get unique event ID based on club, time, resource, and user.
        
        The UID format is: {club_name}_{date}_{time}_{resource_id}_{user_name}
        This ensures uniqueness while allowing deduplication of the same reservation.
        """
        # Get resource ID from raw data
        resource_id = self.raw_data.get('resourceId', '0')
        if not resource_id and 'resources' in self.raw_data:
            # Try to get resource ID from resources array
            resources = self.raw_data.get('resources', [{}])
            if resources:
                resource_id = resources[0].get('resourceId', '0')
        
        # Format date and time components
        date_str = self.start_time.strftime('%Y%m%d')
        time_str = self.start_time.strftime('%H%M')
        
        # Create unique ID that includes all necessary components
        return f"{self.club.name}_{date_str}_{time_str}_{resource_id}_{self.user.name}"

    def format_for_display(self) -> str:
        """Format reservation for display in terminal."""
        return (
            f"{self.start_time.strftime('%Y-%m-%d %H:%M')} - "
            f"{self.end_time.strftime('%H:%M')}: "
            f"{self.club.name} - {self.club.variant}\n"
            f"Players: {', '.join(p.name for p in self.players)}"
        )

    def overlaps_with(self, other: "Reservation") -> bool:
        """Check if this reservation overlaps with another."""
        return (
            self.start_time < other.end_time and
            self.end_time > other.start_time
        )

    @classmethod
    def from_wisegolf(
        cls,
        data: Dict[str, Any],
        club: GolfClub,
        user: User,
        membership: Membership
    ) -> "Reservation":
        """Create Reservation instance from WiseGolf data."""
        # Create a temporary instance to access logger
        temp_instance = cls(
            club=club,
            user=user,
            membership=membership,
            start_time=datetime.now(),  # Temporary value
            end_time=datetime.now(),    # Temporary value
            players=[],
            raw_data=data
        )
        
        # Parse start time from the dateTimeStart field and make it timezone-aware
        start_time = datetime.strptime(data["dateTimeStart"], "%Y-%m-%d %H:%M:%S")
        start_time = start_time.replace(tzinfo=ZoneInfo("Europe/Helsinki"))
        end_time = club.get_end_time(start_time, membership.duration)
        
        # Extract players from response data
        players = []
        
        # Only fetch players for future events
        now = datetime.now(ZoneInfo("Europe/Helsinki"))
        is_future_event = start_time > now
        
        # Try to fetch players from REST API if the club supports it and it's a future event
        if is_future_event and hasattr(club, 'fetch_players'):
            try:
                player_data_list = club.fetch_players(data, membership)
                for player_data in player_data_list:
                    players.append(Player(
                        name=f"{player_data['firstName']} {player_data['familyName']}".strip(),
                        club=player_data.get('clubAbbreviation', 'Unknown'),
                        handicap=float(player_data.get('handicapActive', 54))
                    ))
            except Exception as e:
                temp_instance.logger.error(f"Failed to fetch players from REST API: {e}")
        
        # If no players found from REST API, try the old way
        if not players and "players" in data:
            for player_data in data["players"]:
                # Skip empty or "Varattu" players
                if not player_data.get("firstName") and not player_data.get("familyName"):
                    continue
                if player_data.get("familyName") == "Varattu":
                    continue
                    
                players.append(Player(
                    name=f"{player_data['firstName']} {player_data['familyName']}".strip(),
                    club=player_data.get('clubAbbreviation', 'Unknown'),
                    handicap=float(player_data.get('handicapActive', 54))
                ))
        
        # If still no valid players found, add the user as the only player
        if not players:
            players = [Player(
                name=user.name,
                club=membership.clubAbbreviation,
                handicap=user.handicap
            )]
        
        return cls(
            club=club,
            user=user,
            membership=membership,
            start_time=start_time,
            end_time=end_time,
            players=players,
            raw_data=data
        )

    @classmethod
    def from_nexgolf(
        cls,
        data: Dict[str, Any],
        club: GolfClub,
        user: User,
        membership: Membership
    ) -> "Reservation":
        """Create Reservation instance from NexGolf data."""
        start_time = club.parse_start_time(data)
        end_time = club.get_end_time(start_time, membership.duration)
        
        # Extract players from response data
        players = []
        if "reservations" in data:
            for player_data in data["reservations"]:
                players.append(Player.from_nexgolf(player_data))
        
        return cls(
            club=club,
            user=user,
            membership=membership,
            start_time=start_time,
            end_time=end_time,
            players=players,
            raw_data=data
        )

    @classmethod
    def from_wisegolf0(
        cls,
        data: Dict[str, Any],
        club: GolfClub,
        user: User,
        membership: Membership
    ) -> "Reservation":
        """Create Reservation instance from WiseGolf0 data."""
        # Create a temporary instance to access logger
        temp_instance = cls(
            club=club,
            user=user,
            membership=membership,
            start_time=datetime.now(),  # Temporary value
            end_time=datetime.now(),    # Temporary value
            players=[],
            raw_data=data
        )
        
        # Parse start time from the dateTimeStart field and make it timezone-aware
        start_time = datetime.strptime(data["dateTimeStart"], "%Y-%m-%d %H:%M:%S")
        start_time = start_time.replace(tzinfo=ZoneInfo("Europe/Helsinki"))
        
        # Calculate end time using duration from membership
        end_time = club.get_end_time(start_time, membership.duration)
        
        # Extract players from response data
        players = []
        
        # Only fetch players for future events
        now = datetime.now(ZoneInfo("Europe/Helsinki"))
        is_future_event = start_time > now
        
        # Try to fetch players from REST API if the club supports it and it's a future event
        if is_future_event and hasattr(club, 'fetch_players'):
            try:
                player_data_list = club.fetch_players(data, membership)
                for player_data in player_data_list:
                    # Check if we have all required fields
                    if all(key in player_data for key in ['firstName', 'familyName', 'clubAbbreviation', 'handicapActive']):
                        players.append(Player(
                            name=f"{player_data['firstName']} {player_data['familyName']}".strip(),
                            club=player_data.get('clubAbbreviation', 'Unknown'),
                            handicap=float(player_data.get('handicapActive', 54))
                        ))
            except Exception as e:
                temp_instance.logger.error(f"Failed to fetch players from REST API: {e}")
                temp_instance.logger.debug(f"Player data that caused error: {player_data_list if 'player_data_list' in locals() else 'No data fetched'}")
        
        # If no players found from REST API, use the reservation data itself
        if not players and all(key in data for key in ["firstName", "familyName"]):
            players.append(Player(
                name=f"{data['firstName']} {data['familyName']}".strip(),
                club=data.get('clubAbbreviation', 'Unknown'),
                handicap=float(data.get('handicapActive', 54))
            ))
        
        # Create and return the reservation instance
        return cls(
            club=club,
            user=user,
            membership=membership,
            start_time=start_time,
            end_time=end_time,
            players=players,
            raw_data=data
        )

