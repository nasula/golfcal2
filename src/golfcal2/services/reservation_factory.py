from typing import Dict, Type
from golfcal2.services.reservation_processor import (
    ReservationProcessor,
    WiseGolfProcessor,
    WiseGolf0Processor,
    NexGolfProcessor,
    TeeTimeProcessor
)

class ReservationFactory:
    """Factory for creating reservation processors."""
    
    _registry: Dict[str, Type[ReservationProcessor]] = {
        'wisegolf': WiseGolfProcessor,
        'wisegolf0': WiseGolf0Processor,
        'nexgolf': NexGolfProcessor,
        'teetime': TeeTimeProcessor
    }
    
    @classmethod
    def get_processor(cls, club_type: str) -> Type[ReservationProcessor]:
        """Get processor for specific club type."""
        processor = cls._registry.get(club_type.lower())
        if not processor:
            raise ValueError(f"No processor registered for {club_type}")
        return processor
    
    @classmethod
    def register_processor(cls, club_type: str, processor: Type[ReservationProcessor]) -> None:
        """Register a new processor type."""
        cls._registry[club_type.lower()] = processor 