"""
Reservation model for golf calendar application.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple, Union, cast
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.utils.timezone_utils import TimezoneManager
from golfcal2.models.golf_club import GolfClub, ExternalGolfClub
from golfcal2.models.user import User, Membership
from golfcal2.services.weather_types import WeatherData, WeatherResponse, get_weather_symbol
from golfcal2.services.weather_formatter import WeatherFormatter

class PlayerDataExtractor:
    """Helper class for extracting player data from different formats."""
    
    @staticmethod
    def extract_name(data: Dict[str, Any], format_type: str) -> Tuple[str, str]:
        """Extract first and last name from player data."""
        first_name = ""
        family_name = ""
        
        if format_type == "wisegolf":
            name = data.get("firstName", data.get("name", ""))
            first_name = name.split()[0] if name else ""
            family_name = (
                data.get("familyName", "") or 
                " ".join(name.split()[1:]) if name else ""
            )
        elif format_type == "nexgolf":
            player_data = data.get("player", {})
            first_name = str(player_data.get("firstName", ""))
            family_name = str(player_data.get("lastName", ""))
        else:
            raise ValueError(f"Unsupported format: {format_type}")
        return first_name.strip(), family_name.strip()

    @staticmethod
    def extract_club(data: Dict[str, Any], format_type: str) -> str:
        """Extract club abbreviation from player data."""
        if format_type == "wisegolf":
            return str(data.get("clubAbbreviation", data.get("club", "N/A")))
        elif format_type == "nexgolf":
            return str(data.get("player", {}).get("club", {}).get("abbreviation", "N/A"))
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

    def __post_init__(self):
        """Ensure all fields have valid values."""
        self.name = str(self.name) if self.name is not None else "Unknown"
        self.club = str(self.club) if self.club is not None else "Unknown"
        try:
            self.handicap = float(self.handicap) if self.handicap is not None else 0.0
        except (TypeError, ValueError):
            self.handicap = 0.0

    @classmethod
    def from_wisegolf(cls, data: Dict[str, Any]) -> "Player":
        """Create Player instance from WiseGolf data."""
        try:
            # Try new extractor first
            first_name, family_name = PlayerDataExtractor.extract_name(data, "wisegolf")
            club = PlayerDataExtractor.extract_club(data, "wisegolf")
            handicap = PlayerDataExtractor.extract_handicap(data, "wisegolf")
            
            return cls(
                name=f"{first_name} {family_name}".strip() or "Unknown",
                club=club or "Unknown",
                handicap=handicap
            )
        except Exception:
            # Fallback to original implementation for backward compatibility
            first_name = data.get("firstName", data.get("name", "")).split()[0] if data.get("firstName", data.get("name", "")) else ""
            family_name = (
                data.get("familyName", "") or 
                " ".join(data.get("name", "").split()[1:]) if data.get("name", "") else ""
            )
            
            club = data.get("clubAbbreviation", data.get("club", "Unknown"))
            
            handicap_str = str(data.get("handicapActive", data.get("handicap", "0.0")))
            try:
                handicap = float(handicap_str)
            except (ValueError, TypeError):
                handicap = 0.0
            
            return cls(
                name=f"{first_name} {family_name}".strip() or "Unknown",
                club=club or "Unknown",
                handicap=handicap
            )

    @classmethod
    def from_nexgolf(cls, data: Dict[str, Any]) -> "Player":
        """Create Player instance from NexGolf data."""
        try:
            # Get player data from the correct location in the structure
            player_data = data.get("player", {}) if isinstance(data.get("player"), dict) else {}
            
            # Extract name components with safe defaults
            first_name = str(player_data.get("firstName", "")).strip()
            last_name = str(player_data.get("lastName", "")).strip()
            
            # Extract club data safely
            club_data = player_data.get("club", {}) if isinstance(player_data.get("club"), dict) else {}
            club = str(club_data.get("abbreviation", "Unknown")).strip()
            
            # Handle potential None values in handicap
            try:
                handicap = float(player_data.get("handicap", 0.0))
            except (TypeError, ValueError):
                handicap = 0.0

            # Build name with fallback
            name = f"{first_name} {last_name}".strip() or "Unknown"

            return cls(
                name=name,
                club=club,
                handicap=handicap
            )
        except Exception as e:
            logger.error(f"Error creating player from NexGolf data: {str(e)}, data: {data}")
            return cls(name="Unknown Player", club="Unknown", handicap=0.0)

@dataclass
class Reservation(LoggerMixin):
    """Golf reservation."""
    club: GolfClub
    user: User
    membership: Membership
    start_time: datetime
    end_time: datetime
    players: List[Player] = field(default_factory=list)
    raw_data: Optional[Dict[str, Any]] = None
    _tz_manager: Optional[TimezoneManager] = None
    weather_summary: Optional[str] = None

    def __post_init__(self) -> None:
        """Initialize after dataclass creation."""
        super().__init__()
        self.set_log_context(service="reservation")
        if self._tz_manager is None:
            self._tz_manager = TimezoneManager()
        self.utc_tz = ZoneInfo('UTC')

    @property
    def title(self) -> str:
        """Get event title."""
        try:
            self.debug("Getting event title")
            self.debug(f"Club info: name={self.club.name if self.club else 'None'}, abbr={getattr(self.club, 'clubAbbreviation', None)}")
            
            # Get club abbreviation with fallbacks
            club_abbr = None
            if self.club and hasattr(self.club, 'clubAbbreviation'):
                club_abbr = self.club.clubAbbreviation
            if not club_abbr and hasattr(self.membership, 'clubAbbreviation'):
                club_abbr = self.membership.clubAbbreviation
            if not club_abbr:
                club_abbr = "GOLF"  # Final fallback
                
            self.debug(f"Using club abbreviation: {club_abbr}")
            
            # Get variant name if available
            variant = None
            if isinstance(self.raw_data, dict) and "variantName" in self.raw_data:
                variant = self.raw_data["variantName"]
            elif hasattr(self.club, 'variant') and self.club.variant:
                variant = self.club.variant
            elif isinstance(self.raw_data, dict) and 'course' in self.raw_data:
                course_data = self.raw_data['course']
                if isinstance(course_data, dict) and 'name' in course_data:
                    variant = course_data['name']
            
            self.debug(f"Using variant: {variant}")
            
            # Format time
            time_str = self.start_time.strftime("%H:%M") if self.start_time else ""
            self.debug(f"Using time string: {time_str}")
            
            # Build title
            if variant:
                title = f"Golf: {club_abbr} - {variant} @{time_str}"
            else:
                title = f"Golf: {club_abbr} @{time_str}"
                
            self.debug(f"Final title: {title}")
            return title
            
        except Exception as e:
            self.error(f"Error getting event title: {e}")
            return "Golf Reservation"

    @property
    def location(self) -> str:
        """Get event location."""
        return self.club.get_event_location() if hasattr(self.club, 'get_event_location') else ''

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
        players: List[Player] = []
        if self._tz_manager is None:
            self._tz_manager = TimezoneManager()
        now = self._tz_manager.now()
        is_future_event = start_time > now

        self.logger.debug(f"Fetching players for start_time={start_time}, is_future_event={is_future_event}")

        # For past events, only use raw data
        if not is_future_event:
            self.logger.debug("Past event - using raw data only")
            if isinstance(self.raw_data, dict):
                # First try to create player from the main reservation data
                if all(key in self.raw_data for key in ["firstName", "familyName"]):
                    player = Player(
                        name=f"{self.raw_data['firstName']} {self.raw_data['familyName']}".strip(),
                        club=self.raw_data.get('clubAbbreviation', 'Unknown'),
                        handicap=float(self.raw_data.get('handicapActive', 0.0))
                    )
                    players.append(player)
                    self.logger.debug(f"Added player from raw data: {player.name} ({player.club}, {player.handicap})")
            return players

        # For future events, try to fetch additional players
        if hasattr(self.club, 'fetch_players'):
            try:
                self.logger.debug(f"Calling club.fetch_players with raw_data: {self.raw_data}")
                player_data_list = self.club.fetch_players(self.raw_data, self.membership)
                self.logger.debug(f"Got response from club.fetch_players: {player_data_list}")
                
                # Check if we got a dictionary with reservationsGolfPlayers and rows
                if isinstance(player_data_list, dict):
                    if 'reservationsGolfPlayers' in player_data_list and 'rows' in player_data_list:
                        self.logger.debug("Found reservationsGolfPlayers and rows in response")
                        
                        # Get our reservation's details
                        our_reservation_time_id = self.raw_data.get('reservationTimeId')
                        our_order_id = self.raw_data.get('orderId')
                        
                        self.logger.debug(f"Looking for players with reservationTimeId: {our_reservation_time_id} and orderId: {our_order_id}")
                        
                        # Find players that match our reservationTimeId or orderId
                        matching_players = [
                            player for player in player_data_list['reservationsGolfPlayers']
                            if (player.get('reservationTimeId') == our_reservation_time_id or
                                player.get('orderId') == our_order_id)
                        ]
                        
                        self.logger.debug(f"Found {len(matching_players)} players for this reservation")
                        
                        # Convert each matching player to a Player object
                        for player_data in matching_players:
                            self.logger.debug(f"Processing player data: {player_data}")
                            players.append(Player.from_wisegolf(player_data))
                            self.logger.debug(f"Added player: {players[-1].name} ({players[-1].club}, {players[-1].handicap})")
                    else:
                        self.logger.warning(f"Unexpected response format from club.fetch_players: {type(player_data_list)}")
                    
            except Exception as e:
                self.logger.error(f"Failed to fetch players: {e}", exc_info=True)
                self.logger.debug(f"Player data that caused error: {player_data_list if 'player_data_list' in locals() else 'No data fetched'}")
        
        # If no players found, try using the raw data
        if not players:
            self.logger.debug("No players found from REST API, using reservation data")
            if isinstance(self.raw_data, dict):
                if all(key in self.raw_data for key in ["firstName", "familyName"]):
                    player = Player(
                        name=f"{self.raw_data['firstName']} {self.raw_data['familyName']}".strip(),
                        club=self.raw_data.get('clubAbbreviation', 'Unknown'),
                        handicap=float(self.raw_data.get('handicapActive', 0.0))
                    )
                    players.append(player)
                    self.logger.debug(f"Added player from reservation data: {player.name} ({player.club}, {player.handicap})")
        
        return players

    @property
    def total_handicap(self) -> float:
        """Calculate total handicap of all players."""
        try:
            if not self.players:
                return 0.0
            total = 0.0
            for player in self.players:
                if player and hasattr(player, 'handicap'):
                    try:
                        handicap = float(player.handicap) if player.handicap is not None else 0.0
                        total += handicap
                    except (TypeError, ValueError):
                        continue
            return round(total, 1)
        except Exception as e:
            self.logger.error(f"Error calculating total handicap: {str(e)}")
            return 0.0

    @property
    def uid(self) -> str:
        """
        Get unique event ID based on club, time, resource, and user.
        
        The UID format is: {club_name}_{date}_{time}_{resource_id}_{user_name}
        This ensures uniqueness while allowing deduplication of the same reservation.
        """
        resource_id = self._extract_resource_id()
        
        # Format date and time components
        date_str = self.start_time.strftime('%Y%m%d') if self.start_time else '00000000'
        time_str = self.start_time.strftime('%H%M') if self.start_time else '0000'
        
        # Create unique ID that includes all necessary components
        return f"{self.club.name if self.club else 'Unknown'}_{date_str}_{time_str}_{resource_id}_{self.user.name if self.user else 'Unknown'}"

    def get_event_summary(self) -> str:
        """Get event summary for calendar."""
        try:
            # Debug log raw data
            self.logger.debug(f"Summary: Raw data type: {type(self.raw_data)}")
            self.logger.debug(f"Summary: Club info: name={getattr(self.club, 'name', None)}, abbr={getattr(self.club, 'abbreviation', None)}")
            self.logger.debug(f"Summary: Start time: {self.start_time}")
            
            # Format time in 24-hour format
            time_str = self.start_time.strftime('%H:%M') if self.start_time else 'Unknown'
            self.logger.debug(f"Summary: Formatted time: {time_str}")
            
            # Get club abbreviation with safer handling
            club_abbr = 'Unknown'
            if self.club and hasattr(self.club, 'abbreviation'):
                club_abbr = str(self.club.abbreviation) if self.club.abbreviation is not None else 'Unknown'
            self.logger.debug(f"Summary: Club abbreviation: {club_abbr}")
            
            # Build summary string based on data source
            if isinstance(self.raw_data, dict):
                self.logger.debug(f"Summary: Raw data keys: {self.raw_data.keys()}")
                if 'variantName' in self.raw_data:  # WiseGolf format
                    variant_parts = self.raw_data["variantName"].split(":")
                    variant = variant_parts[0] if variant_parts else 'Unknown'
                    self.logger.debug(f"Summary: WiseGolf variant: {variant}")
                    summary = f"Golf: {club_abbr} - {variant} @{time_str}"
                else:  # NexGolf format
                    # Get course name from NexGolf data
                    course_name = None
                    if 'course' in self.raw_data and isinstance(self.raw_data['course'], dict):
                        course_name = str(self.raw_data['course'].get('name', ''))
                        self.logger.debug(f"Summary: NexGolf course name: {course_name}")
                    summary = f"Golf: {club_abbr} - {course_name} @{time_str}" if course_name else f"Golf: {club_abbr} @{time_str}"
            else:
                summary = f"Golf: {club_abbr} @{time_str}"
            self.logger.debug(f"Summary: Base summary: {summary}")
            
            # Add player info with safer handling
            try:
                player_count = len(self.players) if self.players else 0
                self.logger.debug(f"Summary: Player count: {player_count}")
                if player_count > 0:
                    total_hcp = self.total_handicap  # This is now safely handled in the property
                    self.logger.debug(f"Summary: Total handicap: {total_hcp}")
                    summary += f" ({player_count} Players, THCP: {total_hcp:.1f})"
                self.logger.debug(f"Summary: Final summary: {summary}")
            except Exception as e:
                self.logger.error(f"Error adding player info to summary: {str(e)}")
            
            return summary
        except Exception as e:
            self.logger.error(f"Error formatting event summary: {str(e)}, raw_data: {self.raw_data}")
            return "Golf Reservation"

    def _format_weather_data(self, weather_data: Union[WeatherResponse, List[WeatherData]]) -> str:
        """Format weather data into a human-readable string."""
        return WeatherFormatter.format_forecast(
            weather_data,
            start_time=self.start_time if self.start_time else datetime.now(),
            end_time=self.end_time if self.end_time else datetime.now() + timedelta(hours=1)
        )

    def get_event_description(self, weather: Optional[Union[str, List[WeatherData]]] = None) -> str:
        """Get event description for calendar."""
        try:
            description = []
            
            # Add time with safe handling
            if self.start_time:
                description.append(f"Teetime {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                description.append("Teetime Unknown")
            
            # Add player details with safe handling
            if self.players:
                for player in self.players:
                    if player:
                        name = str(player.name) if player.name else "Unknown"
                        club = str(player.club) if player.club else "Unknown"
                        handicap = float(player.handicap) if player.handicap is not None else 0.0
                        player_info = f"{name}, {club}, HCP: {handicap:.1f}"
                        description.append(player_info)
            
            # Add weather if available
            if weather:
                description.append("\nWeather:")
                if isinstance(weather, str):
                    description.append(str(weather))
                else:
                    try:
                        description.append(self._format_weather_data(weather))
                    except Exception as e:
                        self.logger.error(f"Error formatting weather data: {str(e)}")
                        description.append("Weather data unavailable")
            
            return "\n".join(description)
        except Exception as e:
            self.logger.error(f"Error formatting event description: {str(e)}")
            return "Error formatting event description"

    def get_event_location(self) -> str:
        """Get event location for calendar."""
        return self.club.get_event_location()

    def format_for_display(self) -> str:
        """Format reservation for display with safe string handling."""
        try:
            # Safely format all fields
            club_name = str(self.club.name) if self.club else "Unknown Club"
            start_time = str(self.start_time) if self.start_time else "Unknown Start"
            end_time = str(self.end_time) if self.end_time else "Unknown End"
            
            # Format players safely
            players = ", ".join([
                str(p.name) if p else "Unknown Player" 
                for p in self.players
            ]) if self.players else "No players"
            
            return (
                f"Reservation at {club_name}\n"
                f"Time: {start_time} - {end_time}\n"
                f"Players: {players}"
            )
        except Exception as e:
            self.logger.error(f"Error formatting reservation: {str(e)}")
            return "Error formatting reservation details"

    def format_with_weather(self, weather_data: List[WeatherData]) -> str:
        """Format reservation with weather using safe string handling."""
        try:
            base_info = self.format_for_display()
            
            # Safely format weather
            weather_str = "\n".join([
                f"{str(w.time)}: {str(w.temperature)}°C, {str(w.precipitation)}mm rain"
                for w in weather_data
            ]) if weather_data else "No weather data available"
            
            return f"{base_info}\nWeather Forecast:\n{weather_str}"
        except Exception as e:
            self.logger.error(f"Error formatting weather: {str(e)}")
            return f"{self.format_for_display()}\nError formatting weather data"

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
            raw_data=data,
            _tz_manager=tz_manager
        )
        
        # Parse start time from the dateTimeStart field and make it timezone-aware
        start_time = datetime.strptime(data["dateTimeStart"], "%Y-%m-%d %H:%M:%S")
        start_time = tz_manager.localize_datetime(start_time)
        end_time = club.get_end_time(start_time, membership.duration)
        
        # Try to fetch players using the new helper method
        players: List[Player] = temp_instance._fetch_players(start_time)
        
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
                handicap=float(user.handicap or 0.0)
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
            raw_data=data,
            _tz_manager=tz_manager
        )
        
        temp_instance.logger.debug(f"Processing NexGolf data: {data}")
        
        # Parse start time using club's method
        start_time = club.parse_start_time(data)
        if start_time.tzinfo is None:
            start_time = tz_manager.localize_datetime(start_time)
        end_time = club.get_end_time(start_time, membership.duration)
        
        temp_instance.logger.debug(f"Parsed times: start={start_time}, end={end_time}")
        
        # Initialize players list
        players: List[Player] = []
        
        # Process players from NexGolf format
        if "players" in data:
            temp_instance.logger.debug(f"Processing NexGolf players: {data.get('players')}")
            try:
                for player_data in data["players"]:
                    temp_instance.logger.debug(f"Processing player data: {player_data}")
                    if player_data and isinstance(player_data, dict):
                        player = Player.from_nexgolf(player_data)
                        players.append(player)
                        temp_instance.logger.debug(f"Added player: {player.name} ({player.club}, {player.handicap})")
            except Exception as e:
                temp_instance.logger.error(f"Failed to process NexGolf player data: {e}", exc_info=True)
                temp_instance.logger.debug(f"Raw data that caused error: {data}")
        
        # If no players found, add the user as default player
        if not players:
            temp_instance.logger.debug(f"No players found, using user as default: {user.name}")
            players = [Player(
                name=user.name,
                club=membership.clubAbbreviation,
                handicap=float(user.handicap or 0.0)
            )]
        
        temp_instance.logger.debug(f"Final players list: {[f'{p.name} ({p.club})' for p in players]}")
        
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
            raw_data=data,
            _tz_manager=tz_manager
        )
        
        # Parse start time from the dateTimeStart field and make it timezone-aware
        try:
            start_time = datetime.strptime(data["dateTimeStart"], "%Y-%m-%d %H:%M:%S")
            start_time = tz_manager.localize_datetime(start_time)
        except (KeyError, ValueError) as e:
            temp_instance.logger.error(f"Failed to parse start time from data: {e}")
            # Try using club's parse_start_time as fallback
            start_time = club.parse_start_time(data)
            if start_time.tzinfo is None:
                start_time = tz_manager.localize_datetime(start_time)
        
        # Calculate end time using duration from membership
        end_time = club.get_end_time(start_time, membership.duration)
        
        # Extract players from response data
        players: List[Player] = []
        
        # Only fetch players for future events
        now = tz_manager.now()
        is_future_event = start_time > now
        
        # Try to fetch players from REST API if it's a future event
        if is_future_event:
            try:
                temp_instance.logger.debug(f"Fetching players for reservation: {data}")
                
                # Prepare reservation data for API call
                api_reservation = {
                    'dateTimeStart': data['dateTimeStart'],
                    'dateTimeEnd': data['dateTimeEnd'],
                    'orderId': data['orderId'],
                    'reservationTimeId': data['reservationTimeId'],
                    'productId': data.get('productId'),
                    'resources': data.get('resources', [{'resourceId': data.get('resourceId'), 'quantity': 1}] if data.get('resourceId') else None)
                }
                
                temp_instance.logger.debug(f"Calling fetch_players with reservation: {api_reservation}")
                response = club.fetch_players(api_reservation, membership)
                temp_instance.logger.debug(f"Got API response: {response}")
                
                # Process each player using WiseGolf0 format
                if isinstance(response, dict):
                    if 'reservationsGolfPlayers' in response:
                        # Get our reservation's timeId and orderId
                        reservation_time_id = data.get('reservationTimeId')
                        order_id = data.get('orderId')
                        temp_instance.logger.debug(f"Looking for players with reservationTimeId: {reservation_time_id} and orderId: {order_id}")
                        
                        # Filter players that match our reservation's timeId or orderId
                        reservation_players = [
                            player for player in response['reservationsGolfPlayers']
                            if (player.get('reservationTimeId') == reservation_time_id or
                                player.get('orderId') == order_id)
                        ]
                        
                        temp_instance.logger.debug(f"Found {len(reservation_players)} players for this reservation")
                        
                        for player_data in reservation_players:
                            temp_instance.logger.debug(f"Processing player data: {player_data}")
                            players.append(Player.from_wisegolf(player_data))
                            temp_instance.logger.debug(f"Added player: {players[-1].name} ({players[-1].club}, {players[-1].handicap})")
                    else:
                        temp_instance.logger.warning(f"Unexpected format in API response: {type(response)}")
                    
                # If no players found from API response, try using the raw data
                if not players:
                    temp_instance.logger.debug("No players found from API response, checking raw data")
                    if 'reservationsGolfPlayers' in data:
                        for player_data in data['reservationsGolfPlayers']:
                            if player_data.get('reservationTimeId') == data.get('reservationTimeId'):
                                players.append(Player.from_wisegolf(player_data))
                                temp_instance.logger.debug(f"Added player from raw data: {players[-1].name} ({players[-1].club}, {players[-1].handicap})")
            except Exception as e:
                temp_instance.logger.error(f"Failed to fetch players from REST API: {e}", exc_info=True)
                temp_instance.logger.debug(f"Player data that caused error: {response if 'response' in locals() else 'No data fetched'}")
        
        # If no players found from REST API, use the reservation data itself
        if not players:
            temp_instance.logger.debug("No players found from REST API, using reservation data")
            if all(key in data for key in ["firstName", "familyName"]):
                players.append(Player.from_wisegolf(data))
                temp_instance.logger.debug(f"Added player from reservation data: {players[-1].name} ({players[-1].club}, {players[-1].handicap})")
            else:
                temp_instance.logger.debug("No player data found in reservation, using user data")
                players.append(Player(
                    name=user.name,
                    club=membership.clubAbbreviation,
                    handicap=float(user.handicap or 0.0)
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

    @classmethod
    def from_external_event(cls, event_data: Dict[str, Any], user: User) -> "Reservation":
        """Create reservation from external event data."""
        # Create external golf club
        club = ExternalGolfClub(
            name=event_data["name"],
            url="",  # External events don't have URLs
            coordinates=event_data.get("coordinates"),
            timezone=event_data["timezone"],
            address=event_data.get("address", "Unknown")
        )
        
        # Create a pseudo-membership for the external event
        membership = Membership(
            club=club.name,
            clubAbbreviation="EXT",  # External event marker
            duration={"hours": 0, "minutes": 0},  # Duration will be calculated from event times
            auth_details={}  # External events don't need auth details
        )
        
        # Parse start and end times
        if 'start_time' in event_data and 'end_time' in event_data:
            # Handle dynamic dates
            start = cls._parse_dynamic_time(event_data['start_time'], club.timezone)
            end = cls._parse_dynamic_time(event_data['end_time'], club.timezone)
        else:
            # Handle fixed dates
            start = datetime.fromisoformat(event_data['start'])
            end = datetime.fromisoformat(event_data['end'])
            
            # Set timezone if not already set
            if start.tzinfo is None:
                start = start.replace(tzinfo=ZoneInfo(club.timezone))
            if end.tzinfo is None:
                end = end.replace(tzinfo=ZoneInfo(club.timezone))
        
        # Create players list from event users
        players = []
        if 'users' in event_data:
            for username in event_data['users']:
                players.append(Player(
                    name=username,
                    club="EXT",  # External event marker
                    handicap=0.0  # No handicap for external events
                ))
        
        return cls(
            club=club,
            user=user,
            membership=membership,
            start_time=start,
            end_time=end,
            players=players,
            raw_data=event_data
        )

    @staticmethod
    def _parse_dynamic_time(time_str: str, timezone: str) -> datetime:
        """Parse dynamic time string (e.g., 'tomorrow 10:00' or '3 days 09:30')."""
        parts = time_str.split()
        
        # Get current date in the target timezone
        now = datetime.now(ZoneInfo(timezone))
        
        # Parse the time part (always the last part)
        time_part = parts[-1]
        time_parts = time_part.split(':')
        if len(time_parts) != 2:
            raise ValueError(f"Invalid time format: {time_part}")
        
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        
        # Initialize result with today's date and the specified time
        result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Handle date part
        if len(parts) == 2:
            if parts[0] == 'tomorrow':
                result += timedelta(days=1)
            elif parts[0] == 'today':
                pass  # Already set to today
            elif parts[0].isdigit():
                # Format: "N days"
                days = int(parts[0])
                result += timedelta(days=days)
            else:
                raise ValueError(f"Invalid date format: {parts[0]}")
        elif len(parts) == 3:
            if parts[1] == 'days':
                # Format: "N days HH:MM"
                try:
                    days = int(parts[0])
                    result += timedelta(days=days)
                except ValueError:
                    raise ValueError(f"Invalid number of days: {parts[0]}")
            else:
                raise ValueError(f"Invalid format: expected 'days' but got '{parts[1]}'")
        else:
            raise ValueError(f"Invalid time format: {time_str}")
        
        return result

