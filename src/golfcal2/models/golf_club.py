# golfclub.py

"""
Golf club models.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, cast, Type, TypeVar, Protocol, NoReturn
from zoneinfo import ZoneInfo

from golfcal2.models.user import Membership
from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.utils.timezone_utils import TimezoneManager
from golfcal2.services.auth_service import AuthService
from golfcal2.models.mixins import PlayerFetchMixin
from golfcal2.api.wise_golf import WiseGolfAPI, WiseGolf0API
from golfcal2.api.nex_golf import NexGolfAPI
from golfcal2.api.teetime import TeeTimeAPI
from golfcal2.config import settings

# Type definitions
ApiClass = TypeVar('ApiClass', bound=Union[WiseGolfAPI, WiseGolf0API])

class AppConfigProtocol(Protocol):
    """Protocol for AppConfig."""
    users: Dict[str, Any]
    clubs: Dict[str, Any]
    global_config: Dict[str, Any]
    api_keys: Dict[str, str]

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
    config: Optional[AppConfigProtocol] = None

    def __post_init__(self) -> None:
        """Initialize after dataclass initialization."""
        # Initialize LoggerMixin properly
        LoggerMixin.__init__(self)  # type: ignore[no-untyped-call]
        
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

    def _ensure_timezone_manager(self) -> TimezoneManager:
        """Ensure timezone manager is initialized."""
        if self._tz_manager is None:
            self._tz_manager = TimezoneManager(self.timezone)
        return self._tz_manager

    def _ensure_auth_service(self) -> AuthService:
        """Ensure auth service is initialized."""
        if self.auth_service is None:
            self.logger.error("No auth service available")
            raise ValueError("No auth service available")
        return self.auth_service

    def _ensure_club_details(self) -> Dict[str, Any]:
        """Ensure club details are initialized."""
        if self.club_details is None:
            self.logger.error("No club details available")
            raise ValueError("No club details available")
        return self.club_details

    def fetch_players(self, reservation: Dict[str, Any], membership: Membership) -> List[Dict[str, Any]]:
        """
        Fetch players for a specific reservation.
        Default implementation returns empty list for clubs that don't support player fetching.
        
        Args:
            reservation: Reservation data
            membership: User's membership details
            
        Returns:
            List of player dictionaries
        """
        return []

    def localize_datetime(self, dt: datetime) -> datetime:
        """
        Localize datetime to club's timezone.
        
        Args:
            dt: Datetime to localize
            
        Returns:
            Localized datetime
        """
        tz_manager = self._ensure_timezone_manager()
        return tz_manager.localize_datetime(dt)

    def get_event_summary(self, reservation: Dict[str, Any]) -> str:
        """
        Get event summary for reservation.
        
        Args:
            reservation: Reservation data
            
        Returns:
            Event summary string
        """
        if self.variant:
            return f"{self.name} ({self.variant})"
        return self.name

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
        if start_time.tzinfo and not end_time.tzinfo:
            tz_manager = self._ensure_timezone_manager()
            end_time = tz_manager.localize_datetime(end_time)
        return end_time

class BaseWiseGolfClub(GolfClub, PlayerFetchMixin):
    """Base class for WiseGolf clubs."""
    
    def __init__(
        self,
        name: str,
        url: str,
        address: str = "Unknown",
        timezone: str = "UTC",
        coordinates: Optional[Dict[str, float]] = None,
        variant: Optional[str] = None,
        product: Optional[str] = None,
        auth_service: Optional[AuthService] = None,
        club_details: Optional[Dict[str, Any]] = None,
        config: Optional[AppConfigProtocol] = None
    ) -> None:
        """Initialize WiseGolf club."""
        super().__init__(
            name=name,
            url=url,
            address=address,
            timezone=timezone,
            coordinates=coordinates,
            variant=variant,
            product=product,
            auth_service=auth_service,
            club_details=club_details,
            config=config
        )

    @abstractmethod
    def fetch_reservations(self, membership: Membership) -> List[Dict[str, Any]]:
        """Fetch reservations from WiseGolf API."""
        raise NotImplementedError

    def fetch_players_from_rest(
        self,
        reservation: Dict[str, Any],
        membership: Membership,
        api_class: Type[ApiClass],
        rest_url: str
    ) -> List[Dict[str, Any]]:
        """Fetch players from REST API."""
        auth_service = self._ensure_auth_service()
        club_details = self._ensure_club_details()
        
        self.logger.debug(f"Creating {api_class.__name__} instance with URL: {rest_url}")
        api = api_class(
            rest_url,
            auth_service,
            club_details,
            membership.__dict__
        )
        
        self.logger.debug("Fetching players")
        response = api.get_players(reservation)
        self.logger.debug(f"Got response: {response}")
        
        # Return the response directly without converting to list
        return response

    def parse_start_time(self, reservation: Dict[str, Any]) -> datetime:
        """Parse start time from WiseGolf reservation."""
        start_time_str = reservation.get("dateTimeStart")
        if not start_time_str:
            raise ValueError("No start time in reservation")
        
        start_time = datetime.strptime(
            start_time_str,
            "%Y-%m-%d %H:%M:%S"
        )
        
        tz_manager = self._ensure_timezone_manager()
        return tz_manager.localize_datetime(start_time)

class WiseGolfClub(BaseWiseGolfClub):
    """WiseGolf club implementation."""
    
    def fetch_reservations(self, membership: Membership) -> List[Dict[str, Any]]:
        """Fetch reservations from WiseGolf API."""
        auth_service = self._ensure_auth_service()
        club_details = self._ensure_club_details()
            
        self.logger.debug(f"Creating WiseGolfAPI instance with URL: {self.url}")
        api = WiseGolfAPI(
            self.url,
            auth_service,
            club_details,
            membership.__dict__
        )
        self.logger.debug("Fetching reservations")
        reservations = api.get_reservations()
        self.logger.debug(f"Got {len(reservations)} reservations")
        return reservations
    
    def fetch_players(self, reservation: Dict[str, Any], membership: Membership) -> List[Dict[str, Any]]:
        """Fetch players for a reservation."""
        club_details = self._ensure_club_details()
            
        rest_url = club_details.get('restUrl')
        if not rest_url:
            self.logger.error("No restUrl found in club_details")
            return []
            
        self.logger.debug(f"WiseGolfClub.fetch_players - Calling fetch_players_from_rest with rest_url: {rest_url}")
        response = self.fetch_players_from_rest(reservation, membership, WiseGolfAPI, rest_url)
        self.logger.debug(f"WiseGolfClub.fetch_players - Got response: {response}")
        
        # Extract players from response if it's a dictionary with reservationsGolfPlayers
        if isinstance(response, dict) and 'reservationsGolfPlayers' in response:
            return response
        
        # Return empty list if response is not in expected format
        self.logger.warning(f"Unexpected response format: {type(response)}")
        return []

class WiseGolf0Club(BaseWiseGolfClub):
    """WiseGolf0 golf club implementation."""
    
    def fetch_reservations(self, membership: Membership) -> List[Dict[str, Any]]:
        """Fetch reservations from WiseGolf0 API."""
        auth_service = self._ensure_auth_service()
        club_details = self._ensure_club_details()
            
        rest_url = club_details.get('restUrl')
        if not rest_url:
            self.logger.error("No restUrl found in club_details")
            return []
            
        self.logger.debug(f"Creating WiseGolf0API instance with URL: {rest_url}")
        api = WiseGolf0API(
            rest_url,
            auth_service,
            club_details,
            membership.__dict__
        )
        self.logger.debug("Fetching reservations")
        reservations = api.get_reservations()
        self.logger.debug(f"Got {len(reservations)} reservations")
        return reservations
    
    def fetch_players(self, reservation: Dict[str, Any], membership: Membership) -> List[Dict[str, Any]]:
        """Fetch players for a reservation."""
        self.logger.debug(f"WiseGolf0Club.fetch_players - Starting with reservation: {reservation}")
        
        club_details = self._ensure_club_details()
            
        rest_url = club_details.get('restUrl')
        if not rest_url:
            self.logger.error("No restUrl found in club_details")
            return []
            
        self.logger.debug(f"WiseGolf0Club.fetch_players - Calling fetch_players_from_rest with rest_url: {rest_url}")
        response = self.fetch_players_from_rest(reservation, membership, WiseGolf0API, rest_url)
        self.logger.debug(f"WiseGolf0Club.fetch_players - Got response: {response}")
        
        # Extract players from response if it's a dictionary with reservationsGolfPlayers
        if isinstance(response, dict) and 'reservationsGolfPlayers' in response:
            return response
        
        # Return empty list if response is not in expected format
        self.logger.warning(f"Unexpected response format: {type(response)}")
        return []

class NexGolfClub(GolfClub):
    """NexGolf golf club implementation."""
    
    def fetch_reservations(self, membership: Membership) -> List[Dict[str, Any]]:
        """Fetch reservations from NexGolf API."""
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
        tz_manager = self._ensure_timezone_manager()
        return tz_manager.localize_datetime(start_time)

class TeeTimeClub(GolfClub):
    """TeeTime golf club implementation."""
    
    def fetch_reservations(self, membership: Membership) -> List[Dict[str, Any]]:
        """Fetch reservations from TeeTime API."""
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
        tz_manager = self._ensure_timezone_manager()
        return tz_manager.localize_datetime(start_time)

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
    config: Optional[AppConfigProtocol] = None

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
        config: AppConfigProtocol
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

        common_args = {
            "name": club_name,
            "url": url,
            "variant": club_details.get("variant"),
            "product": club_details.get("product"),
            "address": club_details.get("address", "Unknown"),
            "timezone": timezone,
            "auth_service": auth_service,
            "club_details": club_details,
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

