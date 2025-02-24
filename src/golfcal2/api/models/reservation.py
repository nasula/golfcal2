from dataclasses import dataclass
from datetime import datetime


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
    players: list[Player]
    id: str | None = None
    booking_reference: str | None = None
    status: str | None = None
    course_info: CourseInfo | None = None 