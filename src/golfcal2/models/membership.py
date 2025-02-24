"""
Membership model for golf calendar application.
"""

from dataclasses import dataclass
from dataclasses import field


@dataclass
class Membership:
    """Golf club membership details."""
    club: str
    club_abbreviation: str
    duration: dict[str, int]
    auth_details: dict[str, str] = field(default_factory=dict) 