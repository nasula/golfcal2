from abc import ABC, abstractmethod
from typing import Dict, List, Any

class CRMInterface(ABC):
    """Interface defining required methods for CRM integrations"""
    
    @abstractmethod
    def get_reservations(self) -> List[Dict[str, Any]]:
        """Fetch user's reservations from the CRM system."""
        pass
    
    @abstractmethod
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Dict[str, Any]:
        """Convert CRM-specific reservation format to standard internal format"""
        pass
    
    @abstractmethod
    def authenticate(self) -> None:
        """Handle CRM-specific authentication"""
        pass 