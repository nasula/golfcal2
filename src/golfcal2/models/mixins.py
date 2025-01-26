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
                return []
            
            resp_data = ResponseData(response)
            
            if resp_data.is_dict():
                data = resp_data.as_dict()
                if 'rows' in data and 'reservationsGolfPlayers' in data:
                    return self._extract_players_wisegolf(data, reservation, skip_empty, skip_reserved)
                if 'reservationsGolfPlayers' in data:
                    return self._extract_players_wisegolf0(data, skip_empty, skip_reserved)
            
            if resp_data.is_list():
                return self._extract_players_from_list(resp_data.as_list(), skip_empty, skip_reserved)
            
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
        if not isinstance(response, dict) or 'reservationsGolfPlayers' not in response:
            self.logger.debug(f"Invalid response format: {type(response)}")
            return []
            
        players_list = response['reservationsGolfPlayers']
        rows = response.get('rows', [])
        self.logger.debug(f"Found {len(players_list)} players and {len(rows)} rows")
        
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
            response = api.get_players({
                'product_id': product_id,
                'date': reservation_date
            })
            
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