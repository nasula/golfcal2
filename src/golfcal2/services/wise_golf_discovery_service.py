"""Service for discovering and fetching from all WiseGolf clubs."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError
from concurrent.futures import as_completed
from pathlib import Path
from typing import Any

from golfcal2.config.settings import AppConfig
from golfcal2.models.golf_club import WiseGolfClub
from golfcal2.models.user import Membership
from golfcal2.services.auth_service import AuthService
from golfcal2.utils.logging_utils import EnhancedLoggerMixin


class WiseGolfDiscoveryService(EnhancedLoggerMixin):
    """Service for discovering and fetching from all WiseGolf clubs."""
    
    def __init__(self, config: AppConfig):
        """Initialize service.
        
        Args:
            config: Application configuration
        """
        super().__init__()
        self.config = config
        self.endpoints_file = Path(os.path.dirname(os.path.dirname(__file__))) / 'config' / 'wisegolf_endpoints.json'
        self.seen_reservation_ids: set[str] = set()
        
        # Initialize club data caches
        self.club_details_cache: dict[str, dict[str, Any]] = {}
        self.coordinates_cache: dict[str, dict[str, Any]] = {}
        
        # Load static club data
        self._load_static_club_data()
        
    def _load_static_club_data(self) -> None:
        """Load static club data from configuration files."""
        try:
            # Load club coordinates
            coordinates_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'config_data',
                'club_coordinates.json'
            )
            if os.path.exists(coordinates_path):
                with open(coordinates_path) as f:
                    self.coordinates_cache = json.load(f)
                self.debug(f"Loaded {len(self.coordinates_cache)} club coordinates")
            else:
                self.warning(f"Club coordinates file not found: {coordinates_path}")
            
            # Load detailed club info
            details_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'config_data',
                'wisegolf_club_details.json'
            )
            if os.path.exists(details_path):
                with open(details_path) as f:
                    data = json.load(f)
                    if 'rows' in data:
                        for club in data['rows']:
                            if 'clubId' in club:
                                self.club_details_cache[club['clubId']] = club
                self.debug(f"Loaded {len(self.club_details_cache)} club details")
            else:
                self.warning(f"Club details file not found: {details_path}")
                
        except Exception as e:
            self.error(f"Failed to load static club data: {e}", exc_info=True)
            
    def enrich_club_config(self, club_id: str, basic_config: dict[str, Any]) -> dict[str, Any]:
        """Enrich basic club configuration with detailed data.
        
        Args:
            club_id: Club ID to look up details for
            basic_config: Basic club configuration to enrich
            
        Returns:
            Enriched club configuration
        """
        enriched_config = basic_config.copy()
        
        try:
            # Add detailed club info if available
            if club_id in self.club_details_cache:
                details = self.club_details_cache[club_id]
                enriched_config.update({
                    'name': details.get('name', enriched_config.get('name')),
                    'address': details.get('streetAddress'),
                    'city': details.get('city'),
                    'postCode': details.get('postCode'),
                    'contact': {
                        'phone': details.get('phoneNumber'),
                        'email': details.get('email')
                    },
                    'drivingInstructions': details.get('drivingInstructions')
                })
            
            # Add coordinates if available
            club_abbr = enriched_config.get('club_abbreviation')
            if club_abbr and club_abbr in self.coordinates_cache:
                coords = self.coordinates_cache[club_abbr]
                enriched_config['coordinates'] = {
                    'lat': float(coords.get('latitude', 0)),
                    'lon': float(coords.get('longitude', 0))
                }
            
        except Exception as e:
            self.error(f"Failed to enrich club config for {club_id}: {e}")
            
        return enriched_config

    def load_endpoints(self) -> dict[str, Any]:
        """Load WiseGolf API endpoints configuration."""
        try:
            with open(self.endpoints_file) as f:
                return json.load(f)
        except Exception as e:
            self.error(f"Failed to load WiseGolf endpoints: {e}")
            return {"hosts": []}
            
    def get_unique_clubs(self) -> list[dict[str, Any]]:
        """Get list of unique WiseGolf clubs."""
        endpoints = self.load_endpoints()
        wisegolf_clubs_raw = [
            club for club in endpoints.get('hosts', [])
            if club.get('sessionType') == 'wisegolf' and
            club.get('softwareVendorName', 'WiseNetwork') == 'WiseNetwork'  # Only include WiseNetwork clubs
        ]
        
        # Deduplicate clubs based on golfClubId
        unique_clubs = {}
        for club in wisegolf_clubs_raw:
            club_id = str(club.get('golfClubId', '')) or club.get('name')
            
            # Skip if it's a duplicate and the existing one is not a special case
            if club_id in unique_clubs:
                existing = unique_clubs[club_id]
                # Keep the special case version if it exists
                if not existing.get('isNonClub') and club.get('isNonClub'):
                    unique_clubs[club_id] = club
                else:
                    self.debug(f"Duplicate club found and skipped: {club_id}")
                continue
                
            unique_clubs[club_id] = club
                
        return list(unique_clubs.values())
        
    def fetch_from_all_clubs(
        self,
        membership: Membership,
        auth_service: AuthService
    ) -> list[dict[str, Any]]:
        """Fetch reservations from all WiseGolf clubs.
        
        Args:
            membership: User's membership details
            auth_service: Authentication service
            
        Returns:
            List of reservations from all clubs
        """
        all_reservations = []
        unique_clubs = self.get_unique_clubs()
        
        # Get max workers from config, default to 5 if not set
        max_workers = self.config.get('max_workers', 5)
        self.debug(f"Fetching reservations from {len(unique_clubs)} WiseGolf clubs using {max_workers} workers")
        
        # Create temporary clubs for each endpoint
        club_instances = []
        for club_config in unique_clubs:
            try:
                # Skip clubs that disable guest sign-on if not explicitly configured
                if (
                    club_config.get('disableGuestSignOn', False) and 
                    club_config.get('golfClubId') != membership.club_abbreviation
                ):
                    self.debug(f"Skipping club {club_config['name']} due to disabled guest sign-on")
                    continue
                
                # Create basic club details
                basic_details = {
                    **club_config,
                    'type': 'wisegolf',
                    'auth_type': 'wisegolf',
                    'cookie_name': 'wisegolf',
                    'url': club_config['ajaxUrl'],
                    'public_url': club_config['baseUrl'],
                    'restUrl': club_config['restUrl'],
                    'useRestLogin': club_config.get('useRestLogin', False),
                }
                
                # Add optional fields if present
                if 'articleCategory' in club_config:
                    basic_details['articleCategory'] = club_config['articleCategory']
                if 'isNonClub' in club_config:
                    basic_details['isNonClub'] = club_config['isNonClub']
                
                # Enrich with static data
                club_id = str(club_config.get('golfClubId', ''))
                enriched_details = self.enrich_club_config(club_id, basic_details)
                
                club = WiseGolfClub(
                    name=club_config.get('displayName', club_config['name']),
                    url=club_config['ajaxUrl'],
                    address=enriched_details.get('address', ""),
                    timezone="Europe/Helsinki",  # Default timezone
                    auth_service=auth_service,
                    club_details=enriched_details,
                    club_abbreviation=club_id or club_config['name']
                )
                club_instances.append(club)
            except Exception as e:
                self.error(f"Failed to create club instance: {e}")
                
        # Fetch from all clubs in parallel with timeout handling
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_club = {
                executor.submit(self._fetch_club_reservations, club, membership): club
                for club in club_instances
            }
            
            # Process completed tasks with timeout
            for future in as_completed(future_to_club):
                club = future_to_club[future]
                try:
                    # Add timeout to prevent hanging on slow responses
                    club_reservations = future.result(timeout=30)
                    if club_reservations:
                        # Add unique reservations
                        for reservation in club_reservations:
                            reservation_id = reservation.get('reservationTimeId') or reservation.get('orderId')
                            if reservation_id not in self.seen_reservation_ids:
                                # Enrich reservation with club details
                                reservation['clubDetails'] = self.club_details_cache.get(
                                    str(reservation.get('golfClubId', '')),
                                    {}
                                )
                                all_reservations.append(reservation)
                                self.seen_reservation_ids.add(reservation_id)
                except TimeoutError:
                    self.error(f"Timeout while fetching from club {club.name}")
                except Exception as e:
                    self.error(f"Failed to fetch from club {club.name}: {e}")
                    
        return all_reservations
        
    def _fetch_club_reservations(
        self,
        club: WiseGolfClub,
        membership: Membership
    ) -> list[dict[str, Any]] | None:
        """Fetch reservations from a single club.
        
        Args:
            club: Club to fetch from
            membership: User's membership details
            
        Returns:
            List of reservations or None if fetch fails
        """
        try:
            self.debug(f"Fetching reservations from {club.name}")
            return club.fetch_reservations(membership)
        except Exception as e:
            self.error(f"Failed to fetch reservations from {club.name}: {e}")
            return None 