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
    variant: Optional[str] = None
    product: Optional[str] = None
    address: str = "Unknown"
    timezone: str = "UTC"
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
        hours = duration["hours"] if "hours" in duration else 0
        minutes = duration["minutes"] if "minutes" in duration else 0
        end_time = start_time + timedelta(hours=hours, minutes=minutes)
        # Ensure end_time has the same timezone as start_time
        if start_time.tzinfo and not end_time.tzinfo:
            end_time = self._tz_manager.localize_datetime(end_time)
        return end_time

class WiseGolfClub(GolfClub, PlayerFetchMixin):
    """WiseGolf golf club implementation."""
    
    def fetch_reservations(self, membership: Membership) -> List[Dict[str, Any]]:
        """Fetch reservations from WiseGolf API."""
        from golfcal2.api.wise_golf import WiseGolfAPI
        
        api = WiseGolfAPI(self.url, self.auth_service, self.club_details, membership)
        return api.get_reservations()

    def fetch_players(self, reservation: Dict[str, Any], membership: Membership) -> List[Dict[str, Any]]:
        """Fetch players for a reservation from WiseGolf REST API."""
        from golfcal2.api.wise_golf import WiseGolfAPI
        
        # Get the REST URL from the club's configuration
        rest_url = self.url.replace("ajax.", "api.")  # Convert ajax URL to REST API URL
        if not rest_url.endswith("/api/1.0"):
            rest_url += "/api/1.0"
        
        return self.fetch_players_from_rest(reservation, membership, WiseGolfAPI, rest_url)
    
    def parse_start_time(self, reservation: Dict[str, Any]) -> datetime:
        """Parse start time from WiseGolf reservation."""
        start_time_str = reservation["dateTimeStart"]
        if not start_time_str:
            raise ValueError("No start time in reservation")
        
        start_time = datetime.strptime(
            start_time_str,
            "%Y-%m-%d %H:%M:%S"
        )
        return self._tz_manager.localize_datetime(start_time)

class WiseGolf0Club(GolfClub, PlayerFetchMixin):
    """WiseGolf0 golf club implementation."""
    
    def fetch_reservations(self, membership: Membership) -> List[Dict[str, Any]]:
        """Fetch reservations from WiseGolf0 API."""
        from golfcal2.api.wise_golf import WiseGolf0API
        
        self.logger.debug(f"Creating WiseGolf0API instance with URL: {self.url}")
        api = WiseGolf0API(self.url, self.auth_service, self.club_details, membership)
        self.logger.debug("Fetching reservations")
        reservations = api.get_reservations()
        self.logger.debug(f"Got {len(reservations)} reservations")
        return reservations

    def fetch_players(self, reservation: Dict[str, Any], membership: Membership) -> List[Dict[str, Any]]:
        """Fetch players for a reservation from WiseGolf0 REST API."""
        from golfcal2.api.wise_golf import WiseGolf0API
        
        # Get the REST URL from the club's configuration
        rest_url = self.club_details.get('restUrl')  # Use restUrl directly from club_details
        if not rest_url:
            self.logger.error("No restUrl found in club_details")
            return []
        
        self.logger.debug(f"Creating WiseGolf0API instance with REST URL: {rest_url}")
        self.logger.debug(f"Club details: {self.club_details}")
        
        return self.fetch_players_from_rest(reservation, membership, WiseGolf0API, rest_url)
    
    def parse_start_time(self, reservation: Dict[str, Any]) -> datetime:
        """Parse start time from WiseGolf0 reservation."""
        start_time_str = reservation["dateTimeStart"]
        if not start_time_str:
            raise ValueError("No start time in reservation")
        
        start_time = datetime.strptime(
            start_time_str,
            "%Y-%m-%d %H:%M:%S"
        )
        return self._tz_manager.localize_datetime(start_time)

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

class GolfClubFactory:
    """Factory for creating golf club instances."""
    
    @staticmethod
    def create_club(
        club_details: Dict[str, Any],
        membership: Membership,
        auth_service: AuthService,
        config: AppConfig
    ) -> Optional[GolfClub]:
        """Create golf club instance based on type."""
        club_type = club_details.get("type")
        if not club_type:
            return None

        # Get club name with fallbacks
        club_name = (
            club_details.get("name") or  # Explicit name
            membership.club or  # Club name from membership
            club_details.get("clubAbbreviation") or  # Club abbreviation
            club_type.title()  # Fallback to capitalized type
        )

        # Get appropriate URL based on club type
        if club_type == "wisegolf":
            url = club_details.get("ajaxUrl") or club_details.get("url")
        elif club_type == "wisegolf0":
            url = club_details.get("shopURL") or club_details.get("url")
        else:
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

        if club_type == "wisegolf":
            return WiseGolfClub(**common_args)
        elif club_type == "wisegolf0":
            return WiseGolf0Club(**common_args)
        elif club_type == "nexgolf":
            return NexGolfClub(**common_args)
        elif club_type == "teetime":
            return TeeTimeClub(**common_args)
        
        return None

