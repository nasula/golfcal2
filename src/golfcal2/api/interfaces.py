from abc import ABC, abstractmethod
from typing import Any


class CRMInterface(ABC):
    """Interface defining required methods for CRM integrations"""
    
    @abstractmethod
    def get_reservations(self) -> list[dict[str, Any]]:
        """Fetch user's reservations from the CRM system."""
        pass
    
    @abstractmethod
    def parse_reservation(self, raw_reservation: dict[str, Any]) -> dict[str, Any]:
        """Convert CRM-specific reservation format to standard internal format"""
        pass
    
    @abstractmethod
    def authenticate(self) -> None:
        """Handle CRM-specific authentication"""
        pass 