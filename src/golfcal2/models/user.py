"""
User model for golf calendar application.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
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
            return club_info.get('clubAbbreviation', abbr)
    
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
    def from_config(cls, name: str, config: Dict[str, Any]) -> "User":
        """
        Create User instance from configuration dictionary.
        
        Args:
            name: User name
            config: User configuration dictionary
            
        Returns:
            User instance
            
        Raises:
            ValueError: If configuration is invalid
        """
        logger = logging.getLogger(__name__)
        
        logger.debug(f"Creating user {name} from config")
        logger.debug(f"Config: {config}")
        
        if not isinstance(config, dict):
            raise ValueError(f"Invalid user configuration for {name}")
        
        if "memberships" not in config:
            raise ValueError(f"No memberships specified for user {name}")
        
        memberships = []
        for membership_config in config.get("memberships", []):
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
                logger.debug(f"Created membership: {membership.__dict__}")
                memberships.append(membership)
            except Exception as e:
                logger.error(f"Failed to create membership from config: {e}", exc_info=True)
        
        # Try to get handicap from config, default to 54 if not found
        try:
            handicap = float(config.get("handicap", 54))
        except (ValueError, TypeError):
            handicap = 54
        
        user = cls(
            name=name,
            email=config.get("email"),
            phone=config.get("phone"),
            handicap=handicap,
            memberships=memberships
        )
        logger.debug(f"Created user: {user.__dict__}")
        return user
    
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