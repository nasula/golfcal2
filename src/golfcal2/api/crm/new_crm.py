from typing import Any

from golfcal2.api.crm.base import BaseCRM
from golfcal2.api.models.reservation import CourseInfo, Player, Reservation


class NewCRM(BaseCRM):
    """Implementation of a new CRM system."""

    def get_reservations(self) -> list[Reservation]:
        """Get reservations from the CRM system.
        
        Returns:
            List of standardized Reservation objects
        
        Raises:
            NotImplementedError: Method not implemented yet
        """
        raw_reservations = self._fetch_reservations()
        return [self.parse_reservation(res) for res in raw_reservations]

    def get_players(self, reservation: Reservation) -> list[dict[str, Any]]:
        """Get players for a reservation.
        
        Args:
            reservation: Reservation to get players for
            
        Returns:
            List of player data dictionaries
            
        Raises:
            NotImplementedError: Method not implemented yet
        """
        if not reservation.id:
            return []
            
        response = self._make_request(
            'GET',
            f'/reservations/{reservation.id}/players'
        )
        
        if not response:
            return []
            
        players = response.get('players', [])
        if not isinstance(players, list):
            return []
            
        return players

    def authenticate(self) -> None:
        """Authenticate with the CRM system.
        
        Raises:
            NotImplementedError: Method not implemented yet
        """
        raise NotImplementedError("Method not implemented")
    
    def _fetch_reservations(self) -> list[dict[str, Any]]:
        """Fetch raw reservations from the CRM system.
        
        Returns:
            List of raw reservation dictionaries
            
        Raises:
            APIError: If request fails
        """
        response = self._make_request('GET', '/reservations')
        if not response:
            return []
            
        data = response.get('reservations', [])
        if not isinstance(data, list):
            return []
            
        return data
    
    def parse_reservation(self, raw_reservation: dict[str, Any]) -> Reservation:
        """Convert raw CRM reservation to standard format.
        
        Args:
            raw_reservation: Raw reservation data from API
            
        Returns:
            Standardized Reservation object
        """
        return Reservation(
            id=str(raw_reservation.get('id', '')),
            datetime_start=self._parse_datetime(
                raw_reservation.get('startTime', ''),
                fmt="%Y-%m-%dT%H:%M:%S"  # CRM-specific format
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