from typing import Dict, List, Any
import requests

from api.crm.base import BaseCRMImplementation
from api.models.reservation import Reservation, Player, CourseInfo
from models.mixins import APIAuthError

class TeeTimeImplementation(BaseCRMImplementation):
    """TeeTime CRM implementation"""
    
    def authenticate(self) -> None:
        self.session = requests.Session()
        
        # TeeTime uses API key authentication
        self.session.headers.update({
            'X-API-Key': self.auth_details['api_key'],
            'X-Club-ID': self.auth_details['club_id']
        })
        
        # Verify credentials
        test_response = self._make_request('GET', '/api/verify')
        if not test_response.ok:
            raise APIAuthError("Invalid API credentials")
    
    def _fetch_reservations(self) -> List[Dict[str, Any]]:
        response = self._make_request(
            'GET',
            '/api/bookings',
            params={'member_id': self.auth_details['member_id']}
        )
        return response.json()['data']
    
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        return Reservation(
            datetime_start=self._parse_datetime(
                raw_reservation["teeTime"], 
                fmt="%Y-%m-%d %H:%M:%S"
            ),
            players=self._parse_players(raw_reservation),
            course_info=self._parse_course_details(raw_reservation)
        )
    
    def _parse_players(self, raw_reservation: Dict[str, Any]) -> List[Player]:
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
        course = raw_reservation.get('course', {})
        return CourseInfo(
            name=course.get('name'),
            holes=course.get('holes'),
            slope=course.get('slope')
        ) 