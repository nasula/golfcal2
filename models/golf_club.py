# golfclub.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo

from golfcal2.models.user import Membership
from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.services.auth_service import AuthService

@dataclass
class GolfClub(ABC, LoggerMixin):
    """Abstract base class for golf clubs."""
    name: str
    url: str
    variant: Optional[str] = None
    product: Optional[str] = None
    address: str = "Unknown"
    timezone: ZoneInfo = ZoneInfo("Europe/Helsinki")
    auth_service: Optional[AuthService] = None
    club_details: Optional[Dict[str, Any]] = None

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
            end_time = end_time.replace(tzinfo=start_time.tzinfo)
        return end_time

class WiseGolfClub(GolfClub):
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
        
        # Create API instance with REST URL
        api = WiseGolfAPI(rest_url, self.auth_service, self.club_details, membership)
        
        # Get the date from the reservation
        reservation_date = datetime.strptime(reservation["dateTimeStart"], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
        
        # Fetch players from the REST API
        response = api.get_players(
            product_id=reservation["productId"],
            date=reservation_date
        )
        
        # Extract players from the response
        if response and 'rows' in response and 'reservationsGolfPlayers' in response:
            # Find our reservation's row to get start time and resource
            our_row = next(
                (row for row in response['rows'] 
                 if row.get('reservationTimeId') == reservation.get('reservationTimeId')),
                None
            )
            if not our_row:
                return []
            
            # Get our start time and resource ID
            our_start = our_row.get('start')
            our_resource_id = our_row.get('resources', [{}])[0].get('resourceId')
            
            # Find all reservation time IDs that share our start time and resource
            related_time_ids = {
                row.get('reservationTimeId')
                for row in response['rows']
                if (row.get('start') == our_start and 
                    row.get('resources', [{}])[0].get('resourceId') == our_resource_id)
            }
            
            # Get all players from these related reservations
            players = []
            for player in response['reservationsGolfPlayers']:
                if player.get('reservationTimeId') in related_time_ids:
                    # Skip empty players but keep "Varattu"
                    if not player.get('firstName') and not player.get('familyName'):
                        continue
                        
                    players.append({
                        'firstName': player.get('firstName', ''),
                        'familyName': player.get('familyName', ''),
                        'clubName': player.get('clubName', ''),
                        'handicapActive': player.get('handicapActive'),
                        'clubAbbreviation': player.get('clubAbbreviation', '')
                    })
            return players
        
        return []

    def parse_start_time(self, reservation: Dict[str, Any]) -> datetime:
        """Parse start time from WiseGolf reservation."""
        start_time_str = reservation["dateTimeStart"]
        if not start_time_str:
            raise ValueError("No start time in reservation")
        
        return datetime.strptime(
            start_time_str,
            "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=self.timezone)

class WiseGolf0Club(GolfClub):
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
        
        # Create API instance with REST URL
        api = WiseGolf0API(rest_url, self.auth_service, self.club_details, membership)
        
        # Get the date from the reservation
        reservation_date = datetime.strptime(reservation["dateTimeStart"], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
        self.logger.debug(f"Fetching players for date: {reservation_date}, product_id: {reservation.get('productId')}")
        
        # Fetch players from the REST API
        response = api.get_players(
            product_id=reservation["productId"],
            date=reservation_date
        )
        
        # Extract players from the response
        if response and 'rows' in response and 'reservationsGolfPlayers' in response:
            # Find our reservation's row to get start time and resource
            our_row = next(
                (row for row in response['rows'] 
                 if row.get('reservationTimeId') == reservation.get('reservationTimeId')),
                None
            )
            if not our_row:
                return []
            
            # Get our start time and resource ID
            our_start = our_row.get('start')
            our_resource_id = our_row.get('resources', [{}])[0].get('resourceId')
            
            # Find all reservation time IDs that share our start time and resource
            related_time_ids = {
                row.get('reservationTimeId')
                for row in response['rows']
                if (row.get('start') == our_start and 
                    row.get('resources', [{}])[0].get('resourceId') == our_resource_id)
            }
            
            # Get all players from these related reservations
            players = []
            for player in response['reservationsGolfPlayers']:
                if player.get('reservationTimeId') in related_time_ids:
                    # Skip empty or "Varattu" players
                    if not player.get('firstName') and not player.get('familyName'):
                        continue
                    if player.get('familyName') == "Varattu":
                        continue
                        
                    players.append({
                        'name': f"{player.get('firstName', '')} {player.get('familyName', '')}".strip(),
                        'club': player.get('clubName', ''),
                        'handicap': player.get('handicapActive'),
                        'club_abbreviation': player.get('clubAbbreviation', '')
                    })
            return players
        
        return []

    def parse_start_time(self, reservation: Dict[str, Any]) -> datetime:
        """Parse start time from WiseGolf0 reservation."""
        start_time_str = reservation["dateTimeStart"]
        if not start_time_str:
            raise ValueError("No start time in reservation")
        
        return datetime.strptime(
            start_time_str,
            "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=self.timezone)

    def get_end_time(self, start_time: datetime, duration: Dict[str, int]) -> datetime:
        """Get end time for WiseGolf0 reservation."""
        return start_time + timedelta(
            hours=duration.get('hours', 0),
            minutes=duration.get('minutes', 0)
        )

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
        
        return datetime.strptime(
            start_time_str,
            "%H:%M %Y-%m-%d"
        ).replace(tzinfo=self.timezone)

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
        
        return datetime.strptime(
            start_time_str,
            "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=self.timezone)

class GolfClubFactory:
    """Factory for creating golf club instances."""
    
    @staticmethod
    def create_club(
        club_details: Dict[str, Any],
        membership: Membership,
        auth_service: AuthService
    ) -> Optional[GolfClub]:
        """Create golf club instance based on type."""
        import logging
        logger = logging.getLogger(__name__)
        
        club_type = club_details["type"]
        if not club_type:
            raise ValueError("No club type specified")
        
        logger.debug(f"Creating club of type: {club_type}")
        logger.debug(f"Club details: {club_details}")
        
        club_classes = {
            "wisegolf": WiseGolfClub,
            "wisegolf0": WiseGolf0Club,
            "nexgolf": NexGolfClub,
            "teetime": TeeTimeClub
        }
        
        club_class = club_classes.get(club_type)
        if not club_class:
            logger.warning(f"Unsupported club type: {club_type}")
            return None
        
        # Get the appropriate URL field based on club type
        if club_type == "wisegolf0":
            url = club_details.get("shopURL")  # Use shopURL for WiseGolf0
            if not url:
                logger.error("No shopURL specified for wisegolf0 club")
                raise ValueError("No shopURL specified for wisegolf0 club")
        elif club_type == "wisegolf":
            url = club_details.get("ajaxUrl")  # Use ajaxUrl for WiseGolf
            if not url:
                logger.error("No ajaxUrl specified for wisegolf club")
                raise ValueError("No ajaxUrl specified for wisegolf club")
        else:
            url = club_details.get("url")  # Use standard url for other types
            if not url:
                logger.error(f"No url specified for {club_type} club")
                raise ValueError(f"No url specified for {club_type} club")
        
        logger.debug(f"Creating {club_type} club with URL: {url}")
        
        club = club_class(
            name=club_details.get("name", "Unknown Club"),
            url=url,
            variant=club_details.get("variant"),
            product=club_details.get("product"),
            address=club_details.get("address", "Unknown"),
            timezone=ZoneInfo(club_details.get("timezone", "Europe/Helsinki")),
            auth_service=auth_service,
            club_details=club_details
        )
        
        logger.debug(f"Created club: {club.name} ({club_type})")
        return club

