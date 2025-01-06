from typing import Dict, List, Any
import requests
from datetime import datetime

from api.crm.base import BaseCRMImplementation
from api.models.reservation import Reservation, Player, CourseInfo
from models.mixins import APIAuthError

class WiseGolfImplementation(BaseCRMImplementation):
    """WiseGolf CRM implementation"""
    
    def authenticate(self) -> None:
        self.session = requests.Session()
        
        auth_response = self._make_request(
            'POST',
            '/auth/login',
            json={
                'username': self.auth_details['username'],
                'password': self.auth_details['password']
            }
        )
        
        token = auth_response.json().get('token')
        if not token:
            raise APIAuthError("No token in authentication response")
            
        self.session.headers.update({
            'Authorization': f'Bearer {token}'
        })
    
    def _fetch_reservations(self) -> List[Dict[str, Any]]:
        response = self._make_request('GET', '/reservations/my')
        return response.json()['reservations']
    
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        return Reservation(
            datetime_start=self._parse_datetime(
                raw_reservation["teeTime"], 
                fmt="%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            players=self._parse_players(raw_reservation),
            course_info=self._parse_course_info(raw_reservation)
        )
    
    def _parse_players(self, raw_reservation: Dict[str, Any]) -> List[Player]:
        return [
            Player(
                first_name=player.get('firstName', ''),
                family_name=player.get('lastName', ''),
                handicap=player.get('handicap'),
                club_abbreviation=player.get('homeClub', {}).get('abbreviation', '')
            )
            for player in raw_reservation.get('players', [])
        ]
    
    def _parse_course_info(self, raw_reservation: Dict[str, Any]) -> CourseInfo:
        course = raw_reservation.get('course', {})
        return CourseInfo(
            name=course.get('name', ''),
            holes=course.get('holes', 18),
            par=course.get('par', 72)
        ) 