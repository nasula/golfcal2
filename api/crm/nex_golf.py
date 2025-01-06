from typing import Dict, List, Any
import requests
from datetime import datetime

from api.crm.base import BaseCRMImplementation
from api.models.reservation import Reservation, Player, CourseInfo
from models.mixins import APIAuthError

class NexGolfImplementation(BaseCRMImplementation):
    """NexGolf CRM implementation"""
    
    def authenticate(self) -> None:
        self.session = requests.Session()
        
        auth_response = self._make_request(
            'POST',
            '/api/login',
            data={
                'memberNumber': self.auth_details['member_id'],
                'pin': self.auth_details['pin']
            }
        )
        
        cookies = auth_response.cookies
        if not cookies:
            raise APIAuthError("No session cookies in authentication response")
            
        self.session.cookies.update(cookies)
    
    def _fetch_reservations(self) -> List[Dict[str, Any]]:
        end_date = datetime.now().replace(year=datetime.now().year + 1)
        
        response = self._make_request(
            'GET',
            '/api/reservations',
            params={
                'startDate': datetime.now().strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d')
            }
        )
        return response.json()['bookings']
    
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        return Reservation(
            datetime_start=self._parse_datetime(
                raw_reservation["startDateTime"], 
                fmt="%Y-%m-%d %H:%M"
            ),
            players=self._parse_players(raw_reservation),
            booking_reference=raw_reservation.get("bookingReference"),
            status=raw_reservation.get("status")
        )
    
    def _parse_players(self, raw_reservation: Dict[str, Any]) -> List[Player]:
        return [
            Player(
                first_name=player.get('firstName', ''),
                family_name=player.get('lastName', ''),
                handicap=float(player.get('handicap', 0)),
                club_abbreviation=player.get('club', {}).get('code', '')
            )
            for player in raw_reservation.get('players', [])
        ] 