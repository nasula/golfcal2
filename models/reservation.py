"""
Reservation model for golf calendar application.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple, Union
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.utils.timezone_utils import TimezoneManager
from golfcal2.models.golf_club import GolfClub
from golfcal2.models.user import User, Membership
from golfcal2.services.weather_types import WeatherData, get_weather_symbol

class PlayerDataExtractor:
    """Helper class for extracting player data from different formats."""
    
    @staticmethod
    def extract_name(data: Dict[str, Any], format_type: str) -> Tuple[str, str]:
        """Extract first and last name from player data."""
        if format_type == "wisegolf":
            first_name = data.get("firstName", data.get("name", "")).split()[0] if data.get("firstName", data.get("name", "")) else ""
            family_name = (
                data.get("familyName", "") or 
                " ".join(data.get("name", "").split()[1:]) if data.get("name", "") else ""
            )
        elif format_type == "nexgolf":
            player_data = data.get("player", {})
            first_name = player_data.get("firstName", "")
            family_name = player_data.get("lastName", "")
        else:
            raise ValueError(f"Unsupported format: {format_type}")
        return first_name.strip(), family_name.strip()

    @staticmethod
    def extract_club(data: Dict[str, Any], format_type: str) -> str:
        """Extract club abbreviation from player data."""
        if format_type == "wisegolf":
            return data.get("clubAbbreviation", data.get("club", "N/A"))
        elif format_type == "nexgolf":
            return data.get("player", {}).get("club", {}).get("abbreviation", "N/A")
        raise ValueError(f"Unsupported format: {format_type}")

    @staticmethod
    def extract_handicap(data: Dict[str, Any], format_type: str) -> float:
        """Extract handicap from player data."""
        try:
            if format_type == "wisegolf":
                handicap_str = str(data.get("handicapActive", data.get("handicap", "0.0")))
            elif format_type == "nexgolf":
                handicap_str = str(data.get("player", {}).get("handicap", "0.0"))
            else:
                return 0.0
            return float(handicap_str)
        except (ValueError, TypeError):
            return 0.0

@dataclass
class Player:
    """Player details."""
    name: str
    club: str
    handicap: float

    @classmethod
    def from_wisegolf(cls, data: Dict[str, Any]) -> "Player":
        """Create Player instance from WiseGolf data."""
        try:
            # Try new extractor first
            first_name, family_name = PlayerDataExtractor.extract_name(data, "wisegolf")
            club = PlayerDataExtractor.extract_club(data, "wisegolf")
            handicap = PlayerDataExtractor.extract_handicap(data, "wisegolf")
            
            return cls(
                name=f"{first_name} {family_name}".strip(),
                club=club,
                handicap=handicap
            )
        except Exception:
            # Fallback to original implementation for backward compatibility
            first_name = data.get("firstName", data.get("name", "")).split()[0] if data.get("firstName", data.get("name", "")) else ""
            family_name = (
                data.get("familyName", "") or 
                " ".join(data.get("name", "").split()[1:]) if data.get("name", "") else ""
            )
            
            club = data.get("clubAbbreviation", data.get("club", "N/A"))
            
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
        try:
            # Try new extractor first
            first_name, family_name = PlayerDataExtractor.extract_name(data, "nexgolf")
            club = PlayerDataExtractor.extract_club(data, "nexgolf")
            handicap = PlayerDataExtractor.extract_handicap(data, "nexgolf")
            
            return cls(
                name=f"{first_name} {family_name}".strip(),
                club=club,
                handicap=handicap
            )
        except Exception:
            # Fallback to original implementation for backward compatibility
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
    _tz_manager: Optional[TimezoneManager] = None

    def __post_init__(self):
        """Initialize after dataclass creation."""
        super().__init__()
        if self._tz_manager is None:
            self._tz_manager = TimezoneManager()

    def _extract_resource_id(self) -> str:
        """Extract resource ID from raw data."""
        resource_id = self.raw_data.get('resourceId', '0')
        if not resource_id and 'resources' in self.raw_data:
            resources = self.raw_data.get('resources', [{}])
            if resources:
                resource_id = resources[0].get('resourceId', '0')
        return str(resource_id)

    def _fetch_players(self, start_time: datetime) -> List[Player]:
        """Fetch players for the reservation."""
        players = []
        now = self._tz_manager.now()
        is_future_event = start_time > now

        if is_future_event and hasattr(self.club, 'fetch_players'):
            try:
                player_data_list = self.club.fetch_players(self.raw_data, self.membership)
                # Use the appropriate player factory method based on club type
                club_type = getattr(self.club, 'type', 'wisegolf')
                for player_data in player_data_list:
                    if club_type == 'nexgolf':
                        players.append(Player.from_nexgolf(player_data))
                    elif club_type in ('wisegolf', 'wisegolf0'):
                        players.append(Player.from_wisegolf(player_data))
                    else:
                        self.logger.warning(f"Unknown club type {club_type}, using wisegolf format")
                        players.append(Player.from_wisegolf(player_data))
            except Exception as e:
                self.logger.error(f"Failed to fetch players: {e}")
                self.logger.debug(f"Player data that caused error: {player_data_list if 'player_data_list' in locals() else 'No data fetched'}")
        
        return players

    @property
    def total_handicap(self) -> float:
        """Calculate total handicap of all players."""
        return round(sum(p.handicap for p in self.players), 1)

    @property
    def uid(self) -> str:
        """
        Get unique event ID based on club, time, resource, and user.
        
        The UID format is: {club_name}_{date}_{time}_{resource_id}_{user_name}
        This ensures uniqueness while allowing deduplication of the same reservation.
        """
        resource_id = self._extract_resource_id()
        
        # Format date and time components
        date_str = self.start_time.strftime('%Y%m%d')
        time_str = self.start_time.strftime('%H%M')
        
        # Create unique ID that includes all necessary components
        return f"{self.club.name}_{date_str}_{time_str}_{resource_id}_{self.user.name}"

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

    def _format_weather_data(self, weather_data: List[WeatherData]) -> str:
        """Format weather data into a human-readable string."""
        if not weather_data:
            return "No weather data available"
        
        formatted_lines = []
        for forecast in weather_data:
            time_str = forecast.elaboration_time.strftime('%H:%M')
            symbol = get_weather_symbol(forecast.symbol)
            temp = f"{forecast.temperature:.1f}°C"
            wind = f"{forecast.wind_speed:.1f}m/s"
            
            # Build weather line with optional precipitation and thunder probability
            parts = [f"{time_str}", symbol, temp, wind]
            
            if forecast.precipitation_probability is not None and forecast.precipitation_probability > 0:
                parts.append(f"💧{forecast.precipitation_probability:.1f}%")
            
            # Add thunder probability if available (assuming it's in the raw data)
            # This might need to be added to the WeatherData class if not already present
            thunder_prob = getattr(forecast, 'thunder_probability', None)
            if thunder_prob is not None and thunder_prob > 0:
                parts.append(f"⚡{thunder_prob:.1f}%")
            
            formatted_lines.append(" ".join(parts))
        
        return "\n".join(formatted_lines)

    def get_event_description(self, weather: Optional[Union[str, List[WeatherData]]] = None) -> str:
        """Get event description for calendar."""
        description = [f"Teetime {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}"]
        
        # Add player details
        for player in self.players:
            player_info = f"{player.name}, {player.club}, HCP: {player.handicap}"
            description.append(player_info)
        
        # Add weather if available
        if weather:
            description.append("\nWeather:")
            if isinstance(weather, str):
                description.append(weather)
            else:
                description.append(self._format_weather_data(weather))
        
        return "\n".join(description)

    def get_event_location(self) -> str:
        """Get event location for calendar."""
        return self.club.get_event_location()

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
        membership: Membership,
        tz_manager: Optional[TimezoneManager] = None
    ) -> "Reservation":
        """Create Reservation instance from WiseGolf data."""
        if tz_manager is None:
            tz_manager = TimezoneManager()
            
        # Create a temporary instance to access logger
        temp_instance = cls(
            club=club,
            user=user,
            membership=membership,
            start_time=datetime.now(),  # Temporary value
            end_time=datetime.now(),    # Temporary value
            players=[],
            raw_data=data,
            _tz_manager=tz_manager
        )
        
        # Parse start time from the dateTimeStart field and make it timezone-aware
        start_time = datetime.strptime(data["dateTimeStart"], "%Y-%m-%d %H:%M:%S")
        start_time = tz_manager.localize_datetime(start_time)
        end_time = club.get_end_time(start_time, membership.duration)
        
        # Try to fetch players using the new helper method
        players = temp_instance._fetch_players(start_time)
        
        # If no players found from helper method, try the old way
        if not players and "players" in data:
            for player_data in data["players"]:
                # Skip empty players but keep "Varattu"
                if not player_data.get("firstName") and not player_data.get("familyName"):
                    continue
                    
                players.append(Player.from_wisegolf(player_data))
        
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
            raw_data=data,
            _tz_manager=tz_manager
        )

    @classmethod
    def from_nexgolf(
        cls,
        data: Dict[str, Any],
        club: GolfClub,
        user: User,
        membership: Membership,
        tz_manager: Optional[TimezoneManager] = None
    ) -> "Reservation":
        """Create Reservation instance from NexGolf data."""
        if tz_manager is None:
            tz_manager = TimezoneManager()
            
        # Create temporary instance for helper methods
        temp_instance = cls(
            club=club,
            user=user,
            membership=membership,
            start_time=datetime.now(),  # Temporary value
            end_time=datetime.now(),    # Temporary value
            players=[],
            raw_data=data,
            _tz_manager=tz_manager
        )
        
        start_time = club.parse_start_time(data)
        if start_time.tzinfo is None:
            start_time = tz_manager.localize_datetime(start_time)
        end_time = club.get_end_time(start_time, membership.duration)
        
        # Try to fetch players using the helper method first
        players = temp_instance._fetch_players(start_time)
        
        # If no players found, try the old way
        if not players and "reservations" in data:
            for player_data in data["reservations"]:
                players.append(Player.from_nexgolf(player_data))
        
        # If still no players, add the user as default player
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
            raw_data=data,
            _tz_manager=tz_manager
        )

    @classmethod
    def from_wisegolf0(
        cls,
        data: Dict[str, Any],
        club: GolfClub,
        user: User,
        membership: Membership,
        tz_manager: Optional[TimezoneManager] = None
    ) -> "Reservation":
        """Create Reservation instance from WiseGolf0 data."""
        if tz_manager is None:
            tz_manager = TimezoneManager()
            
        # Create a temporary instance to access logger
        temp_instance = cls(
            club=club,
            user=user,
            membership=membership,
            start_time=datetime.now(),  # Temporary value
            end_time=datetime.now(),    # Temporary value
            players=[],
            raw_data=data,
            _tz_manager=tz_manager
        )
        
        # Parse start time from the dateTimeStart field and make it timezone-aware
        start_time = datetime.strptime(data["dateTimeStart"], "%Y-%m-%d %H:%M:%S")
        start_time = tz_manager.localize_datetime(start_time)
        
        # Calculate end time using duration from membership
        end_time = club.get_end_time(start_time, membership.duration)
        
        # Extract players from response data
        players = []
        
        # Only fetch players for future events
        now = tz_manager.now()
        is_future_event = start_time > now
        
        # Try to fetch players from REST API if the club supports it and it's a future event
        if is_future_event and hasattr(club, 'fetch_players'):
            try:
                temp_instance.logger.debug(f"Fetching players for reservation: {data}")
                player_data_list = club.fetch_players(data, membership)
                temp_instance.logger.debug(f"Got player data list: {player_data_list}")
                
                for player_data in player_data_list:
                    # Skip empty or "Varattu" players
                    if not player_data.get('name') and not (player_data.get('firstName') or player_data.get('familyName')):
                        continue
                    if player_data.get('name') == "Varattu":
                        continue
                    
                    # Get player name - try different formats
                    name = player_data.get('name', '')
                    if not name and (player_data.get('firstName') or player_data.get('familyName')):
                        name = f"{player_data.get('firstName', '')} {player_data.get('familyName', '')}".strip()
                    
                    # Get club abbreviation - try different formats
                    club_abbr = (
                        player_data.get('club_abbreviation') or
                        player_data.get('clubAbbreviation') or
                        player_data.get('clubName', 'Unknown')
                    )
                    
                    # Get handicap - try different formats
                    try:
                        handicap = float(
                            player_data.get('handicap') or
                            player_data.get('handicapActive') or
                            54
                        )
                    except (ValueError, TypeError):
                        handicap = 54
                    
                    players.append(Player(
                        name=name,
                        club=club_abbr,
                        handicap=handicap
                    ))
                    temp_instance.logger.debug(f"Added player: {name} ({club_abbr}, {handicap})")
                
            except Exception as e:
                temp_instance.logger.error(f"Failed to fetch players from REST API: {e}")
                temp_instance.logger.debug(f"Player data that caused error: {player_data_list if 'player_data_list' in locals() else 'No data fetched'}")
        
        # If no players found from REST API, use the reservation data itself
        if not players:
            temp_instance.logger.debug("No players found from REST API, using reservation data")
            if all(key in data for key in ["firstName", "familyName"]):
                name = f"{data['firstName']} {data['familyName']}".strip()
                club_abbr = data.get('clubAbbreviation', 'Unknown')
                try:
                    handicap = float(data.get('handicapActive', 54))
                except (ValueError, TypeError):
                    handicap = 54
                
                players.append(Player(
                    name=name,
                    club=club_abbr,
                    handicap=handicap
                ))
                temp_instance.logger.debug(f"Added player from reservation data: {name} ({club_abbr}, {handicap})")
            else:
                temp_instance.logger.debug("No player data found in reservation, using user data")
                players.append(Player(
                    name=user.name,
                    club=membership.clubAbbreviation,
                    handicap=user.handicap
                ))
        
        # Create and return the reservation instance
        return cls(
            club=club,
            user=user,
            membership=membership,
            start_time=start_time,
            end_time=end_time,
            players=players,
            raw_data=data,
            _tz_manager=tz_manager
        )

