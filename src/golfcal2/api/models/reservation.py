from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class Player:
    first_name: str
    family_name: str
    handicap: float
    club_abbreviation: str = ''

@dataclass
class CourseInfo:
    name: str
    holes: int = 18
    par: int = 72

@dataclass
class Reservation:
    datetime_start: datetime
    players: List[Player]
    id: Optional[str] = None
    booking_reference: Optional[str] = None
    status: Optional[str] = None
    course_info: Optional[CourseInfo] = None 