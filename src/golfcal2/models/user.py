"""
User model for golf calendar application.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Union, cast
import os
import json
import logging

def get_club_abbreviation(club_name: str) -> str:
    """Get club abbreviation from clubs.json configuration."""
    # Get the package's config directory
    config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
    clubs_file = os.path.join(config_dir, 'clubs.json')
    
    with open(clubs_file, 'r') as f:
        clubs_config = json.load(f)
    
    for abbr, club_info in clubs_config.items():
        if club_info.get('club', '') == club_name or abbr == club_name:
            return str(club_info.get('clubAbbreviation', abbr))
    
    return club_name  # Fallback to using the club name itself

@dataclass
class Membership:
    """Golf club membership details."""
    club: str
    clubAbbreviation: str
    duration: Dict[str, int]
    auth_details: Dict[str, str]

@dataclass
class User:
    """User model."""
    name: str
    memberships: List[Membership]
    email: Optional[str] = None
    phone: Optional[str] = None
    handicap: Optional[float] = None

    @classmethod
    def from_config(cls, name: str, config: Union[Dict[str, Any], "User"]) -> "User":
        """
        Create User instance from configuration dictionary.
        
        Args:
            name: User name
            config: User configuration dictionary or User instance
            
        Returns:
            User instance
            
        Raises:
            ValueError: If configuration is invalid
        """
        logger = logging.getLogger(__name__)
        
        logger.debug(f"Creating user {name} from config")
        logger.debug(f"Config: {config}")
        
        # Convert config to dictionary if it's a User instance
        if isinstance(config, User):
            config_dict = {
                'email': config.email,
                'phone': config.phone,
                'handicap': config.handicap,
                'memberships': [
                    {
                        'club': m.club,
                        'clubAbbreviation': m.clubAbbreviation,
                        'duration': m.duration,
                        'auth_details': m.auth_details
                    }
                    for m in config.memberships
                ]
            }
            config = config_dict
        
        # Handle nested memberships structure
        if isinstance(config, dict) and isinstance(config.get('memberships'), dict):
            memberships_data = cast(Dict[str, Any], config['memberships'])
            config = {
                'email': memberships_data.get('email'),
                'phone': memberships_data.get('phone'),
                'memberships': memberships_data.get('memberships', [])
            }
        
        if not isinstance(config, dict):
            raise ValueError(f"Invalid user configuration for {name}")
        
        if "memberships" not in config:
            raise ValueError(f"No memberships specified for user {name}")
        
        memberships = []
        for membership_config in config["memberships"]:
            logger.debug(f"Processing membership config: {membership_config}")
            try:
                club = membership_config["club"]
                club_abbreviation = get_club_abbreviation(club)
                logger.debug(f"Got club abbreviation for {club}: {club_abbreviation}")
                
                membership = Membership(
                    club=club,
                    clubAbbreviation=club_abbreviation,
                    auth_details=membership_config.get("auth_details", {}),
                    duration=membership_config.get("duration", {"hours": 4})
                )
                memberships.append(membership)
            except KeyError as e:
                logger.error(f"Missing required field in membership config: {e}")
                continue
        
        return cls(
            name=name,
            email=config.get('email'),
            phone=config.get('phone'),
            handicap=config.get('handicap'),
            memberships=memberships
        )
    
    def get_membership(self, club: str) -> Membership:
        """
        Get membership for specified club.
        
        Args:
            club: Club name
            
        Returns:
            Membership instance
            
        Raises:
            ValueError: If user has no membership for specified club
        """
        for membership in self.memberships:
            if membership.club == club:
                return membership
        
        raise ValueError(f"User {self.name} has no membership for club {club}")
    
    def has_membership(self, club: str) -> bool:
        """
        Check if user has membership for specified club.
        
        Args:
            club: Club name
            
        Returns:
            True if user has membership for club, False otherwise
        """
        return any(m.club == club for m in self.memberships)

    def get_service_name(self) -> str:
        """Get service name."""
        return str(self.__class__.__name__)

    def get_service_version(self) -> str:
        """Get service version."""
        return "1.0.0"

    def get_service_description(self) -> str:
        """Get service description."""
        return "Base service mixin"