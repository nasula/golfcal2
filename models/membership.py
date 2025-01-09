"""
Membership model for golf calendar application.
"""

from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class Membership:
    """Golf club membership details."""
    club: str
    clubAbbreviation: str
    duration: Dict[str, int]
    auth_details: Dict[str, str] = field(default_factory=dict) 