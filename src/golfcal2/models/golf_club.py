# golfclub.py

"""
Golf club models.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo

from golfcal2.models.user import Membership
from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.utils.timezone_utils import TimezoneManager
from golfcal2.services.auth_service import AuthService
from golfcal2.models.mixins import PlayerFetchMixin
from golfcal2.config.settings import AppConfig

@dataclass
class GolfClub(ABC, LoggerMixin):
    """Abstract base class for golf clubs."""
    name: str
    url: str
    address: str = "Unknown"
    timezone: str = "UTC"
    coordinates: Optional[Dict[str, float]] = None
    variant: Optional[str] = None
    product: Optional[str] = None
    auth_service: Optional[AuthService] = None
    club_details: Optional[Dict[str, Any]] = None
    _tz_manager: Optional[TimezoneManager] = None
    local_tz: Optional[ZoneInfo] = None
    utc_tz: Optional[ZoneInfo] = None
    config: Optional[AppConfig] = None

    def __post_init__(self):
        """Initialize after dataclass initialization."""
        super().__init__()
        
        # Configure logger
        for handler in self.logger.handlers:
            handler.set_name('golf_club')  # Ensure unique handler names
        self.logger.propagate = False  # Prevent duplicate logs
        
        # Initialize timezone manager with club's timezone
        if self._tz_manager is None:
            self._tz_manager = TimezoneManager(self.timezone)
            
        # Initialize coordinates if not set
        if self.coordinates is None:
            self.coordinates = {}

    @abstractmethod
    def fetch_reservations(self, membership: Membership) -> List[Dict[str, Any]]:
        """
        Fetch reservations for user with membership.
        
        Args:
            membership: User's membership details
            
        Returns:
            List of reservation dictionaries
            
        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError

    def get_event_summary(self, reservation: Dict[str, Any]) -> str:
        """
        Get event summary for reservation.
        
        Args:
            reservation: Reservation dictionary
            
        Returns:
            Event summary string
        """
        start_time = self.parse_start_time(reservation)
        return f"Teetime: {start_time.strftime('%H:%M')} {self.name} - {self.variant}"

    def get_event_location(self) -> str:
        """
        Get event location.
        
        Returns:
            Event location string
        """
        return self.address

    @abstractmethod
    def parse_start_time(self, reservation: Dict[str, Any]) -> datetime:
        """
        Parse start time from reservation.
        
        Args:
            reservation: Reservation dictionary
            
        Returns:
            Start time as datetime
            
        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError

    def get_end_time(self, start_time: datetime, duration: Dict[str, int]) -> datetime:
        """
        Calculate end time based on start time and duration.
        
        Args:
            start_time: Start time
            duration: Duration dictionary with hours and minutes
            
        Returns:
            End time as datetime
        """
        hours = duration.get("hours", 0)
        minutes = duration.get("minutes", 0)
        end_time = start_time + timedelta(hours=hours, minutes=minutes)
        # Ensure end_time has the same timezone as start_time
        if start_time.tzinfo and not end_time.tzinfo and self._tz_manager is not None:
            end_time = self._tz_manager.localize_datetime(end_time)
        return end_time

class BaseWiseGolfClub(GolfClub, PlayerFetchMixin):
    """Base class for WiseGolf implementations."""
    
    def __post_init__(self):
        """Initialize after dataclass initialization."""
        super().__post_init__()
        
        # Initialize coordinates from club details if available
        if self.club_details and 'coordinates' in self.club_details:
            coords = self.club_details['coordinates']
            if isinstance(coords, dict) and all(isinstance(v, float) for v in coords.values()):
                self.coordinates = coords

    def fetch_players_from_rest(self, reservation: Dict[str, Any], membership: Membership, api_class, rest_url: str) -> List[Dict[str, Any]]:
        """
        Base implementation for fetching players from REST API.
        
        Args:
            reservation: Reservation data
            membership: User's membership details
            api_class: API class to use
            rest_url: REST API URL
            
        Returns:
            List of player dictionaries
        """
        try:
            api = api_class(
                rest_url,
                self.auth_service,
                self.club_details,
                membership.__dict__
            )
            
            # Extract required fields for player fetch
            start_time = reservation.get('dateTimeStart', '')
            date = start_time.split()[0] if start_time else ''  # Get YYYY-MM-DD part
            
            player_request = {
                'productId': str(reservation.get('productId', '')),
                'date': date,
                'orderId': str(reservation.get('orderId', ''))
            }
            
            self.logger.debug(f"Fetching players with request: {player_request}")
            return api.get_players(player_request)
        except Exception as e:
            self.logger.error(f"Failed to fetch players from REST API: {e}", exc_info=True)
            return []

    def parse_start_time(self, reservation: Dict[str, Any]) -> datetime:
        """Parse start time from WiseGolf reservation."""
        start_time_str = reservation.get("dateTimeStart")
        if not start_time_str:
            raise ValueError("No start time in reservation")
        
        start_time = datetime.strptime(
            start_time_str,
            "%Y-%m-%d %H:%M:%S"
        )
        if self._tz_manager is not None:
            return self._tz_manager.localize_datetime(start_time)
        return start_time.replace(tzinfo=ZoneInfo(self.timezone))

class WiseGolfClub(BaseWiseGolfClub):
    """WiseGolf club implementation."""
    
    def fetch_reservations(self, membership: Membership) -> List[Dict[str, Any]]:
        """Fetch reservations from WiseGolf API."""
        from golfcal2.api.wise_golf import WiseGolfAPI
        
        if self.auth_service is None:
            self.logger.error("No auth service available")
            return []
            
        if self.club_details is None:
            self.logger.error("No club details available")
            return []
            
        self.logger.debug(f"Creating WiseGolfAPI instance with URL: {self.url}")
        api = WiseGolfAPI(
            self.url,
            self.auth_service,
            self.club_details,
            membership.__dict__
        )
        self.logger.debug("Fetching reservations")
        reservations = api.get_reservations()
        self.logger.debug(f"Got {len(reservations)} reservations")
        return reservations
    
    def fetch_players(self, reservation: Dict[str, Any], membership: Membership) -> List[Dict[str, Any]]:
        """Fetch players for a reservation."""
        from golfcal2.api.wise_golf import WiseGolfAPI
        
        rest_url = self.club_details.get('restUrl')
        if not rest_url:
            self.logger.error("No restUrl found in club_details")
            return []
            
        return self.fetch_players_from_rest(reservation, membership, WiseGolfAPI, rest_url)

class WiseGolf0Club(BaseWiseGolfClub):
    """WiseGolf0 golf club implementation."""

    def fetch_reservations(self, membership: Membership) -> List[Dict[str, Any]]:
        """Fetch reservations from WiseGolf0 API."""
        from golfcal2.api.wise_golf import WiseGolf0API
        
        if self.auth_service is None:
            self.logger.error("No auth service available")
            return []
            
        if self.club_details is None:
            self.logger.error("No club details available")
            return []
            
        self.logger.debug(f"Creating WiseGolf0API instance with URL: {self.url}")
        api = WiseGolf0API(
            self.url,
            self.auth_service,
            self.club_details,
            membership.__dict__
        )
        self.logger.debug("Fetching reservations")
        reservations = api.get_reservations()
        self.logger.debug(f"Got {len(reservations)} reservations")
        return reservations

    def fetch_players(self, reservation: Dict[str, Any], membership: Membership) -> List[Dict[str, Any]]:
        """Fetch players for a reservation from WiseGolf0 REST API."""
        from golfcal2.api.wise_golf import WiseGolf0API
        
        # Get the REST URL from the club's configuration
        rest_url = self.club_details.get('restUrl')
        if not rest_url:
            self.logger.error("No restUrl found in club_details")
            return []
        
        self.logger.debug(f"Creating WiseGolf0API instance with REST URL: {rest_url}")
        self.logger.debug(f"Club details: {self.club_details}")
        self.logger.debug(f"Fetching players for reservation: {reservation}")
        
        # Extract productId and date from reservation
        product_id = reservation.get('productId')
        if not product_id:
            self.logger.error("No productId found in reservation")
            return []
            
        # Extract date from dateTimeStart
        start_time_str = reservation.get('dateTimeStart')
        if not start_time_str:
            self.logger.error("No dateTimeStart found in reservation")
            return []
            
        date = start_time_str.split()[0]  # Get YYYY-MM-DD part
        order_id = reservation.get('orderId')  # Get orderId if available
        reservation_time_id = reservation.get('reservationTimeId')  # Get reservationTimeId
        
        try:
            api = WiseGolf0API(
                rest_url,
                self.auth_service,
                self.club_details,
                membership.__dict__
            )
            
            player_request = {
                'productId': str(product_id),
                'date': date,
                'orderId': str(order_id) if order_id else None
            }
            
            self.logger.debug(f"Fetching players with request: {player_request}")
            response = api.get_players(player_request)
            self.logger.debug(f"Got player response: {response}")
            
            # Filter players by reservationTimeId
            all_players = response.get('reservationsGolfPlayers', [])
            players = [p for p in all_players if str(p.get('reservationTimeId')) == str(reservation_time_id)]
            self.logger.debug(f"Filtered {len(players)} players for reservationTimeId {reservation_time_id}")
            
            return players
            
        except Exception as e:
            self.logger.error(f"Failed to fetch players from REST API: {e}", exc_info=True)
            return []

class NexGolfClub(GolfClub):
    """NexGolf golf club implementation."""
    
    def fetch_reservations(self, membership: Membership) -> List[Dict[str, Any]]:
        """Fetch reservations from NexGolf API."""
        from golfcal2.api.nex_golf import NexGolfAPI
        
        api = NexGolfAPI(self.url, membership.auth_details)
        return api.get_reservations()
    
    def parse_start_time(self, reservation: Dict[str, Any]) -> datetime:
        """Parse start time from NexGolf reservation."""
        start_time_str = reservation["startTime"]
        if not start_time_str:
            raise ValueError("No start time in reservation")
        
        start_time = datetime.strptime(
            start_time_str,
            "%H:%M %Y-%m-%d"
        )
        return self._tz_manager.localize_datetime(start_time)

class TeeTimeClub(GolfClub):
    """TeeTime golf club implementation."""
    
    def fetch_reservations(self, membership: Membership) -> List[Dict[str, Any]]:
        """Fetch reservations from TeeTime API."""
        from golfcal2.api.teetime import TeeTimeAPI
        
        self.logger.debug("TeeTimeClub: Starting fetch_reservations")
        self.logger.debug(f"TeeTimeClub: Club URL: {self.url}")
        self.logger.debug(f"TeeTimeClub: Membership details: {membership.__dict__}")
        self.logger.debug(f"TeeTimeClub: Club details: {self.club_details}")
        
        # Get auth details from membership
        auth_details = membership.auth_details
        self.logger.debug(f"TeeTimeClub: Auth details: {auth_details}")
        
        # Create API instance
        api = TeeTimeAPI(self.url, auth_details)
        self.logger.debug("TeeTimeClub: Created TeeTimeAPI instance")
        
        # Fetch reservations
        reservations = api.get_reservations()
        self.logger.debug(f"TeeTimeClub: Fetched {len(reservations)} reservations")
        
        return reservations
    
    def parse_start_time(self, reservation: Dict[str, Any]) -> datetime:
        """Parse start time from TeeTime reservation."""
        start_time_str = reservation["startTime"]
        if not start_time_str:
            raise ValueError("No start time in reservation")
        
        start_time = datetime.strptime(
            start_time_str,
            "%Y-%m-%d %H:%M:%S"
        )
        return self._tz_manager.localize_datetime(start_time)

@dataclass
class ExternalGolfClub(GolfClub):
    """Golf club for external events."""
    name: str
    url: str
    address: str = "Unknown"
    timezone: str = "UTC"
    coordinates: Optional[Dict[str, float]] = None  # Make coordinates optional
    variant: Optional[str] = None
    product: Optional[str] = None
    auth_service: Optional[AuthService] = None
    club_details: Optional[Dict[str, Any]] = None
    _tz_manager: Optional[TimezoneManager] = None
    local_tz: Optional[ZoneInfo] = None
    utc_tz: Optional[ZoneInfo] = None
    config: Optional[AppConfig] = None

    def get_event_location(self) -> str:
        """Get formatted location string."""
        return self.address

    def get_event_summary(self, reservation: Optional[Dict[str, Any]] = None) -> str:
        """Get event summary."""
        return f"Golf: {self.name}"

    def get_coordinates(self) -> Optional[Dict[str, float]]:
        """Get club coordinates."""
        return self.coordinates

    def get_timezone(self) -> str:
        """Get club timezone."""
        return self.timezone

    def fetch_reservations(self, membership: Membership) -> List[Dict[str, Any]]:
        """External clubs don't fetch reservations."""
        return []

    def parse_start_time(self, reservation: Dict[str, Any]) -> datetime:
        """External clubs don't parse start times."""
        return datetime.now(ZoneInfo(self.timezone))

class GolfClubFactory:
    """Factory for creating golf club instances."""
    
    _clubs: Dict[str, GolfClub] = {}  # Cache for club instances
    
    @classmethod
    def create_club(
        cls,
        club_details: Dict[str, Any],
        membership: Membership,
        auth_service: AuthService,
        config: AppConfig
    ) -> Optional[GolfClub]:
        """Create golf club instance based on type."""
        # Return cached club if available
        club_name = (
            club_details.get("name") or  # Explicit name
            membership.club or  # Club name from membership
            club_details.get("clubAbbreviation") or  # Club abbreviation
            club_details.get("type", "").title()  # Fallback to capitalized type
        )
        if club_name in cls._clubs:
            return cls._clubs[club_name]
            
        club_type = club_details.get("type")
        if not club_type:
            return None

        # Get appropriate URL based on club type
        if club_type == "wisegolf":
            url = club_details.get("ajaxUrl")  # Use ajaxUrl for WiseGolf
        elif club_type == "wisegolf0":
            url = club_details.get("shopURL")  # Use shopURL for WiseGolf0
        else:
            url = club_details.get("url")  # Use standard URL for others

        if not url:
            # Fallback to standard URL if specific URL not found
            url = club_details.get("url")
            if not url:
                raise ValueError(f"No URL found for club {club_name}")

        # Get timezone from club config, fallback to UTC
        timezone = club_details.get("timezone", "UTC")
        local_tz = ZoneInfo(timezone)
        utc_tz = ZoneInfo('UTC')

        common_args = {
            "name": club_name,
            "url": url,
            "variant": club_details.get("variant"),
            "product": club_details.get("product"),
            "address": club_details.get("address", "Unknown"),
            "timezone": timezone,
            "auth_service": auth_service,
            "club_details": club_details,
            "local_tz": local_tz,
            "utc_tz": utc_tz,
            "config": config
        }

        club: Optional[GolfClub] = None
        if club_type == "wisegolf":
            club = WiseGolfClub(**common_args)
        elif club_type == "wisegolf0":
            club = WiseGolf0Club(**common_args)
        elif club_type == "nexgolf":
            club = NexGolfClub(**common_args)
        elif club_type == "teetime":
            club = TeeTimeClub(**common_args)
        
        if club is not None:
            cls._clubs[club_name] = club
        
        return club

