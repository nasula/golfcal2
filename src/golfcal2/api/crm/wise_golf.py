from typing import Any

import requests

from golfcal2.api.crm.base import BaseCRM
from golfcal2.api.models.reservation import CourseInfo, Player, Reservation
from golfcal2.models.mixins import APIAuthError


class WiseGolfCRM(BaseCRM):
    """WiseGolf CRM implementation"""
    
    def authenticate(self) -> None:
        """Authenticate with WiseGolf API."""
        self.session = requests.Session()
        
        auth_response = self._make_request(
            'POST',
            '/auth/login',
            json={
                'username': self.auth_details['username'],
                'password': self.auth_details['password']
            }
        )
        
        if not auth_response:
            raise APIAuthError("Authentication request failed")
            
        token = auth_response.get('token')
        if not token:
            raise APIAuthError("No token in authentication response")
            
        self.session.headers.update({
            'Authorization': f'Bearer {token}'
        })
    
    def get_reservations(self) -> list[Reservation]:
        """Get list of reservations."""
        raw_reservations = self._fetch_reservations()
        return [self.parse_reservation(res) for res in raw_reservations]
    
    def get_players(self, reservation: Reservation) -> list[dict[str, Any]]:
        """Get players for a reservation."""
        response = self._make_request(
            'GET', 
            f'/reservations/{reservation.id}/players'
        )
        return response.get('players', []) if response else []
    
    def _fetch_reservations(self) -> list[dict[str, Any]]:
        """Fetch raw reservations from API."""
        response = self._make_request('GET', '/reservations/my')
        return response.get('reservations', []) if response else []
    
    def parse_reservation(self, raw_reservation: dict[str, Any]) -> Reservation:
        """Parse raw reservation data into Reservation model."""
        return Reservation(
            datetime_start=self._parse_datetime(
                raw_reservation["teeTime"], 
                fmt="%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            players=self._parse_players(raw_reservation),
            course_info=self._parse_course_info(raw_reservation)
        )
    
    def _parse_players(self, raw_reservation: dict[str, Any]) -> list[Player]:
        """Parse player data from reservation."""
        return [
            Player(
                first_name=player.get('firstName', ''),
                family_name=player.get('lastName', ''),
                handicap=float(player.get('handicap', 0)),
                club_abbreviation=player.get('homeClub', {}).get('abbreviation', '')
            )
            for player in raw_reservation.get('players', [])
        ]
    
    def _parse_course_info(self, raw_reservation: dict[str, Any]) -> CourseInfo:
        """Parse course info from reservation."""
        course = raw_reservation.get('course', {})
        return CourseInfo(
            name=course.get('name', ''),
            holes=course.get('holes', 18),
            par=course.get('par', 72)
        ) 