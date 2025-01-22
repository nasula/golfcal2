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
            self.debug("No weather data provided")
            return "No weather data available"
        
        # Get event timezone
        event_tz = self.start_time.tzinfo
        self.debug(
            "Starting weather data formatting",
            total_forecasts=len(weather_data),
            event_time_range=f"{self.start_time.isoformat()} to {self.end_time.isoformat()}",
            event_timezone=str(event_tz)
        )
        
        # Convert all forecasts to event timezone
        normalized_data = []
        for forecast in weather_data:
            if forecast.elaboration_time.tzinfo != event_tz:
                forecast.elaboration_time = forecast.elaboration_time.astimezone(event_tz)
            normalized_data.append(forecast)
        
        # Sort forecasts by time
        normalized_data = sorted(normalized_data, key=lambda x: x.elaboration_time)
        self.debug(
            "Sorted forecasts by time",
            times=[f.elaboration_time.isoformat() for f in normalized_data]
        )
        
        # Filter forecasts to only include those that overlap with event time range
        filtered_data = []
        
        for forecast in normalized_data:
            # For 6-hour blocks, include if the event overlaps with the block
            if '-' in forecast.symbol_time_range:
                start_hour = int(forecast.symbol_time_range.split('-')[0].split(':')[0])
                end_hour = int(forecast.symbol_time_range.split('-')[1].split(':')[0])
                forecast_start = forecast.elaboration_time.replace(hour=start_hour, minute=0)
                forecast_end = forecast.elaboration_time.replace(hour=end_hour, minute=0)
                if end_hour < start_hour:  # Handle blocks that cross midnight
                    forecast_end += timedelta(days=1)
                
                # Check if the event overlaps with this block
                # Event starts before block ends AND event ends after block starts
                if self.start_time < forecast_end and self.end_time > forecast_start:
                    filtered_data.append(forecast)
            else:
                # For hourly forecasts, use the original logic
                if self.start_time <= forecast.elaboration_time < self.end_time:
                    filtered_data.append(forecast)
        
        self.debug(
            "Filtered forecasts to event time range",
            original_count=len(normalized_data),
            filtered_count=len(filtered_data),
            filtered_times=[f.elaboration_time.isoformat() for f in filtered_data],
            start_time=self.start_time.isoformat(),
            end_time=self.end_time.isoformat()
        )
        
        formatted_lines = []
        for forecast in filtered_data:
            # Format time string based on symbol_time_range or just use the elaboration time
            if forecast.symbol_time_range:
                if '-' in forecast.symbol_time_range:
                    start_hour, end_hour = forecast.symbol_time_range.split('-')
                    # If it's a 1-hour block (end hour is start hour + 1), only show start time
                    start_h = int(start_hour.split(':')[0])
                    end_h = int(end_hour.split(':')[0])
                    if (end_h == (start_h + 1) % 24):
                        time_str = start_hour
                    else:
                        time_str = forecast.symbol_time_range
            else:
                time_str = forecast.elaboration_time.strftime('%H:%M')
            
            # Get weather symbol
            symbol = get_weather_symbol(forecast.symbol)
            
            # Build weather line with optional precipitation and thunder probability
            parts = [time_str, symbol, f"{forecast.temperature:.1f}°C", f"{forecast.wind_speed:.1f}m/s"]
            
            if forecast.precipitation_probability is not None and forecast.precipitation_probability > 5:
                if forecast.precipitation and forecast.precipitation > 0:
                    parts.append(f"💧{forecast.precipitation_probability:.0f}% {forecast.precipitation:.1f}mm")
                else:
                    parts.append(f"💧{forecast.precipitation_probability:.0f}%")
            
            if forecast.thunder_probability is not None and forecast.thunder_probability > 0:
                parts.append(f"⚡{forecast.thunder_probability:.0f}%")
            
            line = " ".join(parts)
            formatted_lines.append(line)
            self.debug(
                "Formatted forecast line",
                time=forecast.elaboration_time.isoformat(),
                symbol_time_range=forecast.symbol_time_range,
                temperature=forecast.temperature,
                wind_speed=forecast.wind_speed,
                symbol=forecast.symbol,
                formatted=line
            )
        
        result = "\n".join(formatted_lines)
        self.debug(
            "Completed weather data formatting",
            total_lines=len(formatted_lines),
            result=result
        )
        return result

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
        # Get club configuration to check for coordinates
        from golfcal2.config.settings import AppConfig
        config = AppConfig()
        club_config = config.clubs.get(self.membership.club)
        self.debug(f"Club config for {self.membership.club}: {club_config}")
        
        # Format basic reservation info
        output = [
            f"{self.start_time.strftime('%Y-%m-%d %H:%M')} - "
            f"{self.end_time.strftime('%H:%M')}: "
            f"{self.club.name} - {self.club.variant}"
        ]
        
        # Add player information
        if self.players:
            output.append("Players:")
            for player in self.players:
                output.append(f"  - {player.name} (HCP: {player.handicap})")
            output.append(f"Total HCP: {self.total_handicap}")
        
        # Add weather data if coordinates are available
        if club_config and 'coordinates' in club_config:
            self.debug(f"Found coordinates for {self.membership.club}: {club_config['coordinates']}")
            from golfcal2.services.weather_service import WeatherManager
            from golfcal2.utils.timezone_utils import TimezoneManager
            from zoneinfo import ZoneInfo
            
            tz_manager = TimezoneManager()
            # Ensure we're using ZoneInfo objects
            local_tz = ZoneInfo(tz_manager.timezone_name)
            utc_tz = ZoneInfo('UTC')
            
            weather_manager = WeatherManager(local_tz, utc_tz, config)
            
            weather_data = weather_manager.get_weather(
                lat=club_config['coordinates']['lat'],
                lon=club_config['coordinates']['lon'],
                start_time=self.start_time,
                end_time=self.end_time,
                club=self.membership.clubAbbreviation
            )
            
            if weather_data:
                self.debug(f"Got weather data for {self.membership.club}: {len(weather_data)} forecasts")
                output.append("\nWeather:")
                output.append(self._format_weather_data(weather_data))
            else:
                self.debug(f"No weather data returned for {self.membership.club}")
        else:
            self.debug(f"No coordinates found for {self.membership.club}")
        
        return "\n".join(output)

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

    @classmethod
    def from_external_event(cls, event_data: Dict[str, Any], user: User) -> "Reservation":
        """Create reservation from external event data."""
        from golfcal2.models.golf_club import ExternalGolfClub
        
        # Create external golf club
        club = ExternalGolfClub(
            name=event_data["name"],
            location=event_data["location"],
            coordinates=event_data["coordinates"],
            timezone=event_data["timezone"],
            address=event_data.get("address")
        )
        
        # Create a pseudo-membership for the external event
        membership = Membership(
            club=club.name,
            clubAbbreviation="EXT",  # External event marker
            duration={"hours": 0, "minutes": 0}  # Duration will be calculated from event times
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

