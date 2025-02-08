"""
Mixins for golf club models.
"""

from typing import Dict, Any, List, Optional, Tuple, Union, Protocol, cast, Type, TypeVar, Set, Iterator
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import logging

# Ignore missing stubs for icalendar
import icalendar  # type: ignore

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.models.user import Membership
import requests
import time
from urllib.parse import urljoin

# Type aliases for icalendar types
ICalEvent = TypeVar('ICalEvent', bound=icalendar.Event)
ICalCalendar = TypeVar('ICalCalendar', bound=icalendar.Calendar)
ICalText = TypeVar('ICalText', bound=icalendar.vText)

class ResponseData:
    """
    A unified container for data that can be accessed as either a dict or a list.
    It uses runtime checks to validate whether the data is a dict or list before
    calling dict- or list-specific methods.
    """

    def __init__(self, data: Union[Dict[str, Any], List[Any]]) -> None:
        if not isinstance(data, (dict, list)):
            raise TypeError(f"Data must be either dict or list, got {type(data)}")
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value by key if data is a dict; otherwise, return default.
        """
        if isinstance(self._data, dict):
            return self._data.get(key, default)
        return default

    def __getitem__(self, key: Union[str, int]) -> Any:
        """
        Retrieve an item by string key if data is a dict, or integer index if data is a list.
        """
        if isinstance(self._data, dict):
            if not isinstance(key, str):
                raise TypeError("Cannot use a non-string key on a dict")
            return self._data[key]
        else:
            if not isinstance(key, int):
                raise TypeError("Cannot use a non-integer index on a list")
            return self._data[key]

    def append(self, item: Any) -> None:
        """
        Append an item if data is a list; otherwise, raise a TypeError.
        """
        if not isinstance(self._data, list):
            raise TypeError("Cannot append to a dictionary")
        self._data.append(item)

    def __len__(self) -> int:
        """
        Return the length of the underlying container.
        """
        return len(self._data)

    def __iter__(self) -> Iterator[Any]:
        """
        Iterate over keys if data is a dict, or items if data is a list.
        """
        return iter(self._data)

    def __bool__(self) -> bool:
        """
        Return True if the container is non-empty; False otherwise.
        """
        return bool(self._data)

    def is_dict(self) -> bool:
        """
        Return True if the underlying data is a dictionary.
        """
        return isinstance(self._data, dict)

    def is_list(self) -> bool:
        """
        Return True if the underlying data is a list.
        """
        return isinstance(self._data, list)

    def as_dict(self) -> Dict[str, Any]:
        """
        Return the underlying data as a dictionary.
        Raises TypeError if the data is not a dictionary.
        """
        if not isinstance(self._data, dict):
            raise TypeError("Data is not a dictionary")
        return self._data

    def as_list(self) -> List[Any]:
        """
        Return the underlying data as a list.
        Raises TypeError if the data is not a list.
        """
        if not isinstance(self._data, list):
            raise TypeError("Data is not a list")
        return self._data


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
    
    auth_service: Any
    club_details: Optional[Dict[str, Any]]
    
    def extract_players_from_response(
        self,
        response: Union[Dict[str, Any], List[Any]],
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
            if not response:
                self.logger.debug("Empty response")
                return []
            
            self.logger.debug(f"extract_players_from_response - Response type: {type(response)}")
            self.logger.debug(f"extract_players_from_response - Response: {response}")
            self.logger.debug(f"extract_players_from_response - Reservation: {reservation}")
            
            resp_data = ResponseData(response)
            
            if resp_data.is_dict():
                data = resp_data.as_dict()
                self.logger.debug(f"extract_players_from_response - Response keys: {list(data.keys())}")
                
                # If response has reservationsGolfPlayers and rows, it's a WiseGolf0 response
                if 'reservationsGolfPlayers' in data and 'rows' in data:
                    self.logger.debug("extract_players_from_response - Processing as WiseGolf0 response")
                    players = self._extract_players_wisegolf0(data, reservation, skip_empty, skip_reserved)
                    self.logger.debug(f"extract_players_from_response - Extracted {len(players)} players from WiseGolf0 response")
                    return players
                    
                # If response has only rows, it's a WiseGolf response
                elif 'rows' in data:
                    self.logger.debug("extract_players_from_response - Processing as WiseGolf response")
                    players = self._extract_players_wisegolf(data, reservation, skip_empty, skip_reserved)
                    self.logger.debug(f"extract_players_from_response - Extracted {len(players)} players from WiseGolf response")
                    return players
            
            if resp_data.is_list():
                self.logger.debug("extract_players_from_response - Processing as list response")
                players = self._extract_players_from_list(resp_data.as_list(), skip_empty, skip_reserved)
                self.logger.debug(f"extract_players_from_response - Extracted {len(players)} players from list response")
                return players
            
            self.logger.debug("extract_players_from_response - No matching response format found")
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to extract players from response: {e}", exc_info=True)
            self.logger.debug("Response:", exc_info=True)
            self.logger.debug(response)
            return []
    
    def _extract_players_wisegolf(
        self,
        response: Dict[str, Any],
        reservation: Dict[str, Any],
        skip_empty: bool,
        skip_reserved: bool
    ) -> List[Dict[str, Any]]:
        """Extract players from WiseGolf format response."""
        # Only include the player's own event
        player_data = {
            'firstName': reservation.get('firstName', ''),
            'familyName': reservation.get('familyName', ''),
            'name': f"{reservation.get('firstName', '')} {reservation.get('familyName', '')}".strip(),
            'clubName': '',
            'handicapActive': reservation.get('handicapActive'),
            'clubAbbreviation': reservation.get('clubAbbreviation', '')
        }
        
        self.logger.debug(f"Including player's own event: {player_data['name']} ({player_data['clubAbbreviation']}, {player_data['handicapActive']})")
        return [player_data]
    
    def _extract_players_wisegolf0(
        self,
        response: Dict[str, Any],
        reservation: Dict[str, Any],
        skip_empty: bool = True,
        skip_reserved: bool = True
    ) -> List[Dict[str, Any]]:
        """Extract players from WiseGolf0 format response.
        
        Players are matched based on their start time and resource ID. This is because:
        1. Each player has a reservationTimeId that points to a row in the 'rows' array
        2. Each row contains a start time and a list of resources
        3. Players in the same reservation will have different reservationTimeIds but the same:
           - start time (exact match required)
           - resource ID (exact match required)
        
        Args:
            response: Response data containing reservationsGolfPlayers and rows
            reservation: Current reservation data with dateTimeStart and resource info
            skip_empty: Whether to skip players with no name
            skip_reserved: Whether to skip "Varattu" players
            
        Returns:
            List of player data dictionaries
        """
        self.logger.debug(f"_extract_players_wisegolf0 - Starting extraction")
        self.logger.debug(f"_extract_players_wisegolf0 - Reservation: {reservation}")
        
        # Get the list of players from the response
        if not isinstance(response, dict) or 'reservationsGolfPlayers' not in response:
            self.logger.debug(f"_extract_players_wisegolf0 - Invalid response format: {type(response)}")
            return []
            
        players_list = response.get('reservationsGolfPlayers', [])
        rows = response.get('rows', [])
        
        self.logger.debug(f"_extract_players_wisegolf0 - Found {len(players_list)} players in response")
        self.logger.debug(f"_extract_players_wisegolf0 - Found {len(rows)} rows in response")
        
        # Get our reservation's details
        our_start_time = reservation.get('dateTimeStart')
        our_resource_id = None
        if 'resources' in reservation and reservation['resources']:
            our_resource_id = reservation['resources'][0].get('resourceId')
        elif 'resourceId' in reservation:
            our_resource_id = reservation.get('resourceId')
            
        self.logger.debug(f"_extract_players_wisegolf0 - Looking for players with start_time: {our_start_time} and resource_id: {our_resource_id}")
        
        # Find all time slots for this resource and start time
        matching_time_ids = set()
        for row in rows:
            if row.get('start') != our_start_time:
                continue
            
            # Check if this row has our resource ID
            for resource in row.get('resources', []):
                if resource.get('resourceId') == our_resource_id:
                    matching_time_ids.add(row.get('reservationTimeId'))
                    break
                    
        self.logger.debug(f"_extract_players_wisegolf0 - Found matching time IDs: {matching_time_ids}")
        
        # Get all players that have any of these time IDs
        players = []
        for player in players_list:
            if player.get('reservationTimeId') not in matching_time_ids:
                continue
                
            # Skip empty players if requested
            if skip_empty and not (player.get('firstName') or player.get('familyName')):
                self.logger.debug(f"_extract_players_wisegolf0 - Skipping empty player")
                continue
            
            # Skip "Varattu" players if requested
            if skip_reserved and player.get('name') == "Varattu":
                self.logger.debug(f"_extract_players_wisegolf0 - Skipping reserved player")
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
            self.logger.debug(f"_extract_players_wisegolf0 - Adding player: {player_data['name']} (time ID: {player.get('reservationTimeId')})")
            players.append(player_data)
        
        self.logger.debug(f"_extract_players_wisegolf0 - Extracted {len(players)} players")
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
        api_class: Type[Any],
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
            self.logger.debug(f"PlayerFetchMixin.fetch_players_from_rest - Starting with reservation: {reservation}")
            
            # Create API instance with REST URL
            self.logger.debug(f"PlayerFetchMixin.fetch_players_from_rest - Creating {api_class.__name__} instance with URL: {rest_url}")
            api = api_class(rest_url, self.auth_service, self.club_details, membership.__dict__)
            
            # Pass the full reservation data to get_players
            self.logger.debug(f"PlayerFetchMixin.fetch_players_from_rest - Calling get_players with reservation data")
            response = api.get_players(reservation)
            self.logger.debug(f"PlayerFetchMixin.fetch_players_from_rest - Got response: {response}")
            
            # Extract players from response
            self.logger.debug(f"PlayerFetchMixin.fetch_players_from_rest - Calling extract_players_from_response")
            players = self.extract_players_from_response(response, reservation)
            self.logger.debug(f"PlayerFetchMixin.fetch_players_from_rest - Extracted players: {players}")
            
            if not players:
                self.logger.debug("PlayerFetchMixin.fetch_players_from_rest - No players found from REST API, using reservation data")
                player_data = {
                    'firstName': reservation.get('firstName', ''),
                    'familyName': reservation.get('familyName', ''),
                    'name': f"{reservation.get('firstName', '')} {reservation.get('familyName', '')}".strip(),
                    'clubName': '',
                    'handicapActive': reservation.get('handicapActive'),
                    'clubAbbreviation': reservation.get('clubAbbreviation', '')
                }
                self.logger.debug(f"PlayerFetchMixin.fetch_players_from_rest - Added player from reservation data: {player_data['name']} ({player_data['clubAbbreviation']}, {player_data['handicapActive']})")
                return [player_data]
            
            return players
            
        except Exception as e:
            self.logger.error(f"Failed to fetch players from REST API: {e}", exc_info=True)
            return []

class ReservationHandlerMixin:
    """Mixin for handling reservations."""
    
    _reservation_logger: Optional[logging.Logger] = None
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this mixin."""
        if not hasattr(self, '_reservation_logger') or self._reservation_logger is None:
            logger_mixin = LoggerMixin()  # type: ignore[no-untyped-call]  # LoggerMixin.__init__ is untyped
            self._reservation_logger = logger_mixin.logger
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
        return bool(0 <= hours_old <= 24 * past_days)
    
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
        return bool(reservation.start_time <= now <= reservation.end_time)
    
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
        return bool(now < reservation.start_time <= future_limit)

class RequestHandlerMixin:
    """Mixin for handling HTTP requests."""
    
    base_url: str
    session: requests.Session
    
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
            return cast(Dict[str, Any], response.json())
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
    
    def __init__(self, config: Optional[Any] = None) -> None:
        """Initialize calendar mixin."""
        super().__init__()  # type: ignore[no-untyped-call]  # LoggerMixin.__init__ is untyped
        self._config = config
        self.seen_uids: Set[str] = set()
        
    @property
    def config(self) -> Optional[Any]:
        """Get config, either from instance or parent."""
        if hasattr(self, '_config') and self._config is not None:
            return self._config
        return getattr(super(), 'config', None)
    
    @config.setter
    def config(self, value: Any) -> None:
        """Set config value."""
        self._config = value
    
    def _add_event_to_calendar(
        self,
        event: Any,
        calendar: Any
    ) -> None:
        """Add an event to the calendar."""
        uid = event.get('uid')
        if uid and uid in self.seen_uids:
            self.logger.debug(f"Skipping duplicate event with UID: {uid}")
            return
            
        if uid:
            self.seen_uids.add(uid)
        calendar.add_component(event)
        self.logger.debug(f"Added event to calendar: {event.decoded('summary')}")
    
    def build_base_calendar(
        self,
        user_name: str,
        local_tz: ZoneInfo
    ) -> Any:
        """Create base calendar with metadata."""
        calendar = icalendar.Calendar()
        calendar.add('prodid', icalendar.vText('-//Golf Calendar//EN'))
        calendar.add('version', icalendar.vText('2.0'))
        calendar.add('calscale', icalendar.vText('GREGORIAN'))
        calendar.add('method', icalendar.vText('PUBLISH'))
        calendar.add('x-wr-calname', icalendar.vText(f'Golf Reservations - {user_name}'))
        calendar.add('x-wr-timezone', icalendar.vText(str(local_tz)))
        return calendar 