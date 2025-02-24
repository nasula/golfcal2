from datetime import datetime
from typing import Any

import requests

from golfcal2.api.crm.base import BaseCRM
from golfcal2.api.models.reservation import CourseInfo
from golfcal2.api.models.reservation import Player
from golfcal2.api.models.reservation import Reservation
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
            
        # Get session cookie from response headers
        session_cookie = self.session.cookies.get('JSESSIONID')
        if not session_cookie:
            raise APIAuthError("No session cookie in authentication response")
            
        # Update session with cookie
        self.session.cookies.set('JSESSIONID', session_cookie)
    
    def get_reservations(self) -> list[Reservation]:
        """Get list of reservations.
        
        Returns:
            List of standardized Reservation objects
        """
        raw_reservations = self._fetch_reservations()
        return [self.parse_reservation(res) for res in raw_reservations]
    
    def get_players(self, reservation: Reservation) -> list[dict[str, Any]]:
        """Get players for a reservation.
        
        Args:
            reservation: Reservation to get players for
            
        Returns:
            List of player data dictionaries
        """
        if not reservation.id:
            return []
            
        response = self._make_request(
            'GET',
            f'/api/reservations/{reservation.id}/players'
        )
        
        if not response:
            return []
            
        players = response.get('players', [])
        if not isinstance(players, list):
            return []
            
        return players
    
    def _fetch_reservations(self) -> list[dict[str, Any]]:
        """Fetch raw reservations from API.
        
        Returns:
            List of raw reservation dictionaries
        """
        end_date = datetime.now().replace(year=datetime.now().year + 1)
        
        response = self._make_request(
            'GET',
            '/api/reservations',
            params={
                'endDate': end_date.strftime('%Y-%m-%d')
            }
        )
        
        if not response:
            return []
            
        reservations = response.get('reservations', [])
        if not isinstance(reservations, list):
            return []
            
        return reservations
    
    def parse_reservation(self, raw_reservation: dict[str, Any]) -> Reservation:
        """Convert raw NexGolf reservation to standard format.
        
        Args:
            raw_reservation: Raw reservation data from API
            
        Returns:
            Standardized Reservation object
        """
        return Reservation(
            id=str(raw_reservation.get('id', '')),
            datetime_start=self._parse_datetime(
                raw_reservation.get('startTime', ''),
                fmt="%Y-%m-%d %H:%M:%S"
            ),
            players=self._parse_players(raw_reservation),
            status=raw_reservation.get('status'),
            course_info=self._parse_course_details(raw_reservation)
        )
    
    def _parse_players(self, raw_reservation: dict[str, Any]) -> list[Player]:
        """Parse player information from raw reservation.
        
        Args:
            raw_reservation: Raw reservation data
            
        Returns:
            List of standardized Player objects
        """
        players = []
        for player_data in raw_reservation.get('players', []):
            if not isinstance(player_data, dict):
                continue
                
            players.append(Player(
                first_name=player_data.get('firstName', ''),
                family_name=player_data.get('lastName', ''),
                handicap=float(player_data.get('handicap', 0.0)),
                club_abbreviation=player_data.get('club', {}).get('abbreviation', '')
            ))
        return players
    
    def _parse_course_details(self, raw_reservation: dict[str, Any]) -> CourseInfo:
        """Parse course information from raw reservation.
        
        Args:
            raw_reservation: Raw reservation data
            
        Returns:
            Standardized CourseInfo object
        """
        course_data = raw_reservation.get('course', {})
        return CourseInfo(
            name=course_data.get('name', ''),
            holes=int(course_data.get('holes', 18)),
            par=int(course_data.get('par', 72))
        ) 