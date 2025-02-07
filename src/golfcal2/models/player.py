from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class Player:
    """Golf player."""
    name: str
    club: str
    handicap: float = 0.0  # Default to 0.0 if not provided

    @classmethod
    def from_wisegolf(cls, data: Dict[str, Any]) -> "Player":
        """Create Player instance from WiseGolf data."""
        # Get name components
        first_name = data.get("firstName", "")
        family_name = data.get("familyName", "")
        
        # Handle empty name case
        if not first_name and not family_name:
            name = "Varattu"
        else:
            name = f"{first_name} {family_name}".strip()
        
        # Get club abbreviation or name
        club = data.get("clubAbbreviation", data.get("clubName", "Unknown"))
        
        # Get handicap with fallback to 0
        handicap = float(data.get("handicapActive", 0))
        
        return cls(
            name=name,
            club=club,
            handicap=handicap
        )

    @classmethod
    def from_nexgolf(cls, data: Dict[str, Any]) -> "Player":
        """Create Player instance from NexGolf data."""
        # Get name components directly from data
        first_name = data.get("firstName", "")
        last_name = data.get("lastName", "")
        
        # Handle empty name case
        if not first_name and not last_name:
            name = "Varattu"
        else:
            name = f"{first_name} {last_name}".strip()
        
        # Get club abbreviation or name
        club_data = data.get("club", {})
        club = club_data.get("abbreviation", club_data.get("name", "Unknown"))
        
        # Get handicap with fallback to 0
        handicap = float(data.get("handicap", 0))
        
        return cls(
            name=name,
            club=club,
            handicap=handicap
        ) 