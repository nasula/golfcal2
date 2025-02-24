from typing import Dict, List, Any, cast
import requests

from golfcal2.api.crm.base import BaseCRM
from golfcal2.api.models.reservation import Reservation, Player, CourseInfo
from golfcal2.models.mixins import APIAuthError, APIResponseError, APITimeoutError

class TeeTimeAPI(BaseCRM):
    """Implementation of the TeeTime API."""
    
    def authenticate(self) -> None:
        """Authenticate with TeeTime API using API key."""
        self.session = requests.Session()
        
        # TeeTime uses API key authentication
        self.session.headers.update({
            'X-API-Key': self.auth_details['api_key'],
            'X-Club-ID': self.auth_details['club_id']
        })
        
        # Verify credentials
        test_response = self._make_request('GET', '/api/verify')
        if not test_response:
            raise APIAuthError("Invalid API credentials")
    
    def get_reservations(self) -> List[Reservation]:
        """Get list of reservations from TeeTime API.
        
        Returns:
            List of standardized Reservation objects
        """
        raw_reservations = self._fetch_reservations()
        return [self.parse_reservation(res) for res in raw_reservations]
    
    def get_players(self, reservation: Reservation) -> List[Dict[str, Any]]:
        """Get players for a reservation.
        
        Args:
            reservation: Reservation to get players for
            
        Returns:
            List of player data dictionaries
        """
        # Convert Player objects to dictionaries
        return [{
            'first_name': player.first_name,
            'family_name': player.family_name,
            'handicap': player.handicap,
            'club_abbreviation': player.club_abbreviation
        } for player in reservation.players]
    
    def _fetch_reservations(self) -> List[Dict[str, Any]]:
        """Fetch raw reservation data from TeeTime API.
        
        Returns:
            List of raw reservation dictionaries
        """
        response = self._make_request(
            'GET',
            '/api/bookings',
            params={'member_id': self.auth_details['member_id']}
        )
        
        if not response or 'data' not in response:
            return []
            
        data = response.get('data', [])
        if not isinstance(data, list):
            return []
            
        return data
    
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        """Convert raw TeeTime reservation to standard format.
        
        Args:
            raw_reservation: Raw reservation data from API
            
        Returns:
            Standardized Reservation object
        """
        return Reservation(
            datetime_start=self._parse_datetime(
                raw_reservation["teeTime"], 
                fmt="%Y-%m-%d %H:%M:%S"
            ),
            players=self._parse_players(raw_reservation),
            course_info=self._parse_course_details(raw_reservation)
        )
    
    def _parse_players(self, raw_reservation: Dict[str, Any]) -> List[Player]:
        """Parse player information from raw reservation.
        
        Args:
            raw_reservation: Raw reservation data
            
        Returns:
            List of standardized Player objects
        """
        return [
            Player(
                first_name=player.get('name', {}).get('first', ''),
                family_name=player.get('name', {}).get('last', ''),
                handicap=player.get('handicapIndex'),
                club_abbreviation=player.get('memberClub', {}).get('shortCode', '')
            )
            for player in raw_reservation.get('playerList', [])
        ]
    
    def _parse_course_details(self, raw_reservation: Dict[str, Any]) -> CourseInfo:
        """Parse course information from raw reservation.
        
        Args:
            raw_reservation: Raw reservation data
            
        Returns:
            Standardized CourseInfo object
        """
        course = raw_reservation.get('course', {})
        return CourseInfo(
            name=course.get('name', ''),
            holes=course.get('holes', 18),
            par=course.get('par', 72)  # Using par instead of slope
        ) 