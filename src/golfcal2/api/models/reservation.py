from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class Player:
    first_name: str
    family_name: str
    handicap: Optional[float] = None
    club_abbreviation: Optional[str] = None

@dataclass
class CourseInfo:
    name: str
    holes: int = 18
    par: Optional[int] = None
    slope: Optional[float] = None

@dataclass
class Reservation:
    datetime_start: datetime
    players: List[Player]
    course_info: Optional[CourseInfo] = None
    booking_reference: Optional[str] = None
    status: Optional[str] = None 