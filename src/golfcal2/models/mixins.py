"""
Mixins for golf club models.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

import icalendar  # type: ignore
from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.models.user import Membership
import requests
import time
from urllib.parse import urljoin

class APIError(Exception):
    """Base API error."""
    pass

class APITimeoutError(APIError):
    """API timeout error."""
    pass

class APIResponseError(APIError):
    """API response error."""
    pass

class APIAuthError(APIError):
    """API authentication error."""
    pass

class PlayerFetchMixin(LoggerMixin):
    """Mixin for player fetching functionality."""
    
    def extract_players_from_response(
        self,
        response: Dict[str, Any],
        reservation: Dict[str, Any],
        skip_empty: bool = True,
        skip_reserved: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Extract players from API response.
        
        Args:
            response: API response data
            reservation: Reservation data
            skip_empty: Whether to skip empty player entries
            skip_reserved: Whether to skip "Varattu" entries
            
        Returns:
            List of player dictionaries
        """
        try:
            self.logger.debug(f"Extracting players from response: {response}")
            self.logger.debug(f"For reservation: {reservation}")
            
            # Handle old format (wisegolf)
            if response and 'rows' in response and 'reservationsGolfPlayers' in response:
                return self._extract_players_wisegolf(response, reservation, skip_empty, skip_reserved)
            
            # Handle new format (wisegolf0)
            if response and 'reservationsGolfPlayers' in response:
                return self._extract_players_wisegolf0(response, skip_empty, skip_reserved)
            elif response and 'players' in response:
                return self._extract_players_wisegolf0(response, skip_empty, skip_reserved)
            
            # Handle direct player list format
            if isinstance(response, list):
                return self._extract_players_from_list(response, skip_empty, skip_reserved)
            
            self.logger.debug(f"No recognized response format found. Response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to extract players from response: {e}", exc_info=True)
            return []
    
    def _extract_players_wisegolf(
        self,
        response: Dict[str, Any],
        reservation: Dict[str, Any],
        skip_empty: bool,
        skip_reserved: bool
    ) -> List[Dict[str, Any]]:
        """Extract players from WiseGolf format response."""
        # Find our reservation's row to get start time and resource
        our_row = next(
            (row for row in response['rows'] 
             if row.get('reservationTimeId') == reservation.get('reservationTimeId')),
            None
        )
        if not our_row:
            self.logger.debug("Reservation row not found in response")
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
            if player.get('reservationTimeId') not in related_time_ids:
                continue
            
            # Skip empty players if requested
            if skip_empty and not (player.get('firstName') or player.get('familyName')):
                continue
            
            # Skip "Varattu" players if requested
            if skip_reserved and player.get('name') == "Varattu":
                continue
            
            # Extract player data
            player_data = {
                'firstName': player.get('firstName', ''),
                'familyName': player.get('familyName', ''),
                'name': player.get('name', ''),
                'clubName': player.get('clubName', ''),
                'handicapActive': player.get('handicapActive'),
                'clubAbbreviation': player.get('clubAbbreviation', '')
            }
            players.append(player_data)
        
        return players
    
    def _extract_players_wisegolf0(
        self,
        response: Dict[str, Any],
        skip_empty: bool,
        skip_reserved: bool
    ) -> List[Dict[str, Any]]:
        """Extract players from WiseGolf0 format response."""
        self.logger.debug(f"Extracting players from WiseGolf0 response: {response}")
        
        # Get the list of players from the response
        if isinstance(response, dict):
            if 'reservationsGolfPlayers' in response:
                players_list = response['reservationsGolfPlayers']
                # Get the rows to match reservation times
                rows = response.get('rows', [])
                self.logger.debug(f"Found {len(players_list)} players and {len(rows)} rows")
            else:
                self.logger.debug(f"No reservationsGolfPlayers found in response. Keys: {list(response.keys())}")
                return []
        else:
            self.logger.debug(f"Response is not a dict: {type(response)}")
            return []
        
        players = []
        for player in players_list:
            # Skip empty players if requested
            if skip_empty and not (player.get('firstName') or player.get('familyName')):
                continue
            
            # Skip "Varattu" players if requested
            if skip_reserved and player.get('name') == "Varattu":
                continue
            
            # Extract player data
            player_data = {
                'firstName': player.get('firstName', ''),
                'familyName': player.get('familyName', ''),
                'name': f"{player.get('firstName', '')} {player.get('familyName', '')}".strip(),
                'clubName': player.get('clubName', ''),
                'handicapActive': player.get('handicapActive'),
                'clubAbbreviation': player.get('clubAbbreviation', '')
            }
            players.append(player_data)
        
        self.logger.debug(f"Extracted {len(players)} players")
        return players
    
    def _extract_players_from_list(
        self,
        players: List[Dict[str, Any]],
        skip_empty: bool,
        skip_reserved: bool
    ) -> List[Dict[str, Any]]:
        """Extract players from a direct list of players."""
        result = []
        for player in players:
            # Skip empty players if requested
            if skip_empty and not (player.get('firstName') or player.get('familyName')):
                continue
            
            # Skip "Varattu" players if requested
            if skip_reserved and player.get('name') == "Varattu":
                continue
            
            # Extract player data
            player_data = {
                'firstName': player.get('firstName', ''),
                'familyName': player.get('familyName', ''),
                'name': player.get('name', ''),
                'clubName': player.get('clubName', ''),
                'handicapActive': player.get('handicapActive'),
                'clubAbbreviation': player.get('clubAbbreviation', '')
            }
            result.append(player_data)
        
        return result
    
    def fetch_players_from_rest(
        self,
        reservation: Dict[str, Any],
        membership: Membership,
        api_class: Any,
        rest_url: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch players from REST API.

        Args:
            reservation: Reservation data
            membership: User's membership details
            api_class: API client class to use
            rest_url: REST API URL
            
        Returns:
            List of player dictionaries
        """
        try:
            self.logger.debug(f"Fetching players from REST API for reservation: {reservation}")
            self.logger.debug(f"Using API class: {api_class.__name__}")
            self.logger.debug(f"REST URL: {rest_url}")
            
            # Create API instance with REST URL
            api = api_class(rest_url, self.auth_service, self.club_details, membership.__dict__)
            
            # Get the date from the reservation
            reservation_date = datetime.strptime(
                reservation["dateTimeStart"],
                "%Y-%m-%d %H:%M:%S"
            ).strftime("%Y-%m-%d")
            
            self.logger.debug(f"Fetching players for date: {reservation_date}")
            
            # Get product ID, falling back to resourceId if not available
            product_id = reservation.get("productId")
            if not product_id and 'resources' in reservation:
                resources = reservation.get('resources', [{}])
                if resources:
                    product_id = resources[0].get('resourceId')
            
            if not product_id:
                self.logger.warning("No product ID found in reservation")
                return []
            
            self.logger.debug(f"Using product ID: {product_id}")
            
            # Fetch players from the REST API
            response = api.get_players(
                product_id=product_id,
                date=reservation_date
            )
            
            self.logger.debug(f"Got player response type: {type(response)}")
            self.logger.debug(f"Got player response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
            self.logger.debug(f"Got player response: {response}")
            
            players = self.extract_players_from_response(response, reservation)
            self.logger.debug(f"Extracted {len(players)} players")
            return players
            
        except Exception as e:
            self.logger.error(f"Failed to fetch players from REST API: {e}")
            return []

class ReservationHandlerMixin:
    """Mixin for handling reservations."""
    
    @property
    def logger(self):
        """Get logger for this mixin."""
        if not hasattr(self, '_reservation_logger'):
            self._reservation_logger = LoggerMixin().logger
        return self._reservation_logger
    
    def _should_include_reservation(
        self,
        reservation: Any,
        past_days: int,
        local_tz: ZoneInfo
    ) -> bool:
        """
        Check if reservation should be included based on date.
        
        Args:
            reservation: Reservation to check
            past_days: Number of days to include past reservations
            local_tz: Local timezone
            
        Returns:
            True if reservation should be included
        """
        now = datetime.now(local_tz)
        
        # Include future reservations
        if reservation.start_time > now:
            return True
        
        # Include past reservations within past_days (24 hours)
        hours_old = (now - reservation.start_time).total_seconds() / 3600
        return 0 <= hours_old <= 24 * past_days
    
    def _is_active(
        self,
        reservation: Any,
        now: datetime
    ) -> bool:
        """
        Check if reservation is currently active.
        
        Args:
            reservation: Reservation to check
            now: Current time
            
        Returns:
            True if reservation is active
        """
        return reservation.start_time <= now <= reservation.end_time
    
    def _is_upcoming(
        self,
        reservation: Any,
        now: datetime,
        days: int
    ) -> bool:
        """
        Check if reservation is upcoming within days.
        
        Args:
            reservation: Reservation to check
            now: Current time
            days: Number of days to look ahead
            
        Returns:
            True if reservation is upcoming
        """
        future_limit = now + timedelta(days=days)
        return now < reservation.start_time <= future_limit

class RequestHandlerMixin:
    """Mixin for handling HTTP requests."""
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Make HTTP request with error handling."""
        url = urljoin(self.base_url, endpoint)
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout as e:
            raise APITimeoutError(f"Request timed out: {e}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise APIAuthError(f"Authentication failed: {e}")
            raise APIResponseError(f"HTTP error: {e}")
        except requests.exceptions.RequestException as e:
            raise APIError(f"Request failed: {e}")
        except ValueError as e:
            raise APIResponseError(f"Invalid JSON response: {e}")

class CalendarMixin(LoggerMixin):
    """Mixin for calendar-related functionality."""
    
    def __init__(self, config=None):
        """Initialize calendar mixin."""
        super().__init__()
        self._config = config
        
    @property
    def config(self):
        """Get config, either from instance or parent."""
        if hasattr(self, '_config') and self._config is not None:
            return self._config
        return getattr(super(), 'config', None)
    
    @config.setter
    def config(self, value):
        """Set config value."""
        self._config = value
    
    def _add_event_to_calendar(
        self,
        event: icalendar.Event,
        calendar: icalendar.Calendar
    ) -> None:
        """Add an event to the calendar."""
        uid = event.get('uid')
        if uid and hasattr(self, 'seen_uids') and uid in self.seen_uids:
            self.logger.debug(f"Skipping duplicate event with UID: {uid}")
            return
            
        if uid and hasattr(self, 'seen_uids'):
            self.seen_uids.add(uid)
        calendar.add_component(event)
        self.logger.debug(f"Added event to calendar: {event.decoded('summary')}")
    
    def build_base_calendar(
        self,
        user_name: str,
        local_tz: ZoneInfo
    ) -> icalendar.Calendar:
        """Create base calendar with metadata."""
        calendar = icalendar.Calendar()
        calendar.add('prodid', icalendar.vText('-//Golf Calendar//EN'))
        calendar.add('version', icalendar.vText('2.0'))
        calendar.add('calscale', icalendar.vText('GREGORIAN'))
        calendar.add('method', icalendar.vText('PUBLISH'))
        calendar.add('x-wr-calname', icalendar.vText(f'Golf Reservations - {user_name}'))
        calendar.add('x-wr-timezone', icalendar.vText(str(local_tz)))
        return calendar 