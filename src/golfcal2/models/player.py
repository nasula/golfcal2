from dataclasses import dataclass
from typing import Any


@dataclass
class Player:
    """Golf player."""
    name: str
    club: str
    handicap: float = 0.0  # Default to 0.0 if not provided

    @classmethod
    def from_wisegolf(cls, data: dict[str, Any]) -> "Player":
        """Create Player instance from WiseGolf data."""
        # Get name components
        first_name = data.get("firstName", "")
        family_name = data.get("familyName", "")
        
        # Handle empty name case
        if not first_name and not family_name:
            name = "Varattu"
        else:
            name = f"{first_name} {family_name}".strip()
        
        # Get club name from data
        club = data.get("club_abbreviation", data.get("clubName", "Unknown"))
        
        # Get handicap with fallback to 0
        handicap = float(data.get("handicapActive", 0))
        
        return cls(
            name=name,
            club=club,
            handicap=handicap
        )

    @classmethod
    def from_nexgolf(cls, data: dict[str, Any]) -> "Player":
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

    @classmethod
    def from_teetime(cls, data: dict[str, Any], club_info: dict[str, Any] | None = None) -> "Player":
        """Create Player instance from TeeTime data.
        
        Args:
            data: Player data from TeeTime API
            club_info: Optional club information from the reservation
        """
        # For TeeTime, we only get a player hash ID, not the actual name
        # We'll use a placeholder name with the hash
        name = f"Player-{data.get('idHash', 'Unknown')[:8]}"
        
        # Get club abbreviation from club info if available
        club = "Unknown"
        if club_info and isinstance(club_info, dict):
            club = club_info.get('abbrevitation', club_info.get('name', 'Unknown'))
        
        # Get handicap with fallback to 0
        handicap = float(data.get('handicap', 0))
        
        return cls(
            name=name,
            club=club,
            handicap=handicap
        ) 