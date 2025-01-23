from typing import Dict, List, Any
import requests
from datetime import datetime

from golfcal2.api.crm.base import BaseCRM
from golfcal2.api.models.reservation import Reservation, Player, CourseInfo
from golfcal2.models.mixins import APIAuthError

class NexGolfCRM(BaseCRM):
    """NexGolf CRM implementation"""
    
    def authenticate(self) -> None:
        """Authenticate with NexGolf API."""
        self.session = requests.Session()
        
        auth_response = self._make_request(
            'POST',
            '/api/login',
            data={
                'memberNumber': self.auth_details['member_id'],
                'pin': self.auth_details['pin']
            }
        )
        
        if not auth_response:
            raise APIAuthError("Authentication request failed")
            
        cookies = auth_response.cookies
        if not cookies:
            raise APIAuthError("No session cookies in authentication response")
            
        self.session.cookies.update(cookies)
    
    def get_reservations(self) -> List[Reservation]:
        """Get list of reservations."""
        raw_reservations = self._fetch_reservations()
        return [self.parse_reservation(res) for res in raw_reservations]
    
    def get_players(self, reservation: Reservation) -> List[Dict[str, Any]]:
        """Get players for a reservation."""
        response = self._make_request(
            'GET',
            f'/api/reservations/{reservation.id}/players'
        )
        return response.get('players', []) if response else []
    
    def _fetch_reservations(self) -> List[Dict[str, Any]]:
        """Fetch raw reservations from API."""
        end_date = datetime.now().replace(year=datetime.now().year + 1)
        
        response = self._make_request(
            'GET',
            '/api/reservations',
            params={
                'startDate': datetime.now().strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d')
            }
        )
        return response.get('bookings', []) if response else []
    
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        """Parse raw reservation data into Reservation model."""
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
        """Parse player data from reservation."""
        return [
            Player(
                first_name=player.get('firstName', ''),
                family_name=player.get('lastName', ''),
                handicap=float(player.get('handicap', 0)),
                club_abbreviation=player.get('club', {}).get('code', '')
            )
            for player in raw_reservation.get('players', [])
        ] 