from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from golfcal2.models.reservation import Reservation
from golfcal2.models.user import User
from golfcal2.models.golf_club import GolfClub

class ReservationProcessor(ABC):
    """Base class for reservation processors."""
    
    @classmethod
    @abstractmethod
    def create_reservation(
        cls,
        raw_data: Dict[str, Any],
        user: User,
        club: GolfClub,
        membership: Optional[Any] = None
    ) -> Reservation:
        """Create Reservation object from raw API data."""
        pass

class WiseGolfProcessor(ReservationProcessor):
    @classmethod
    def create_reservation(cls, raw_data: Dict[str, Any], user: User, club: GolfClub, membership: Optional[Any] = None) -> Reservation:
        return Reservation.from_wisegolf(raw_data, club, user, membership)

class WiseGolf0Processor(ReservationProcessor):
    @classmethod
    def create_reservation(cls, raw_data: Dict[str, Any], user: User, club: GolfClub, membership: Optional[Any] = None) -> Reservation:
        return Reservation.from_wisegolf0(raw_data, club, user, membership)

class NexGolfProcessor(ReservationProcessor):
    @classmethod
    def create_reservation(cls, raw_data: Dict[str, Any], user: User, club: GolfClub, membership: Optional[Any] = None) -> Reservation:
        return Reservation.from_nexgolf(raw_data, club, user, membership)

class TeeTimeProcessor(ReservationProcessor):
    @classmethod
    def create_reservation(cls, raw_data: Dict[str, Any], user: User, club: GolfClub, membership: Optional[Any] = None) -> Reservation:
        return Reservation.from_teetime(raw_data, club, user, membership) 