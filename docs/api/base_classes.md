# Base Classes

## WeatherService

The `WeatherService` class provides the base interface for weather service implementations.

```python
class WeatherService(EnhancedLoggerMixin):
    """Base class for weather service implementations."""
    
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Fetch weather data for given coordinates and time range."""
        pass

    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Implement service-specific forecast fetching."""
        pass

    def get_block_size(self, hours_ahead: float) -> int:
        """Get forecast block size based on forecast time."""
        pass
```

## CRMInterface

The `CRMInterface` defines the contract that all CRM implementations must follow:

```python
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
```

## BaseCRMImplementation

The `BaseCRMImplementation` provides common functionality for CRM implementations:

```python
class BaseCRMImplementation(CRMInterface):
    """Base class for CRM implementations with common functionality"""
    
    def __init__(self, url: str, auth_details: Dict[str, Any]):
        self.url = url.rstrip('/')
        self.auth_details = auth_details
        self.session: Optional[requests.Session] = None
        self.timeout = 30
        self._retry_count = 3
    
    def get_reservations(self) -> List[Reservation]:
        """Template method that handles retries and conversion to standard model"""
        if not self.session:
            self.authenticate()
        
        for attempt in range(self._retry_count):
            try:
                raw_reservations = self._fetch_reservations()
                return [self.parse_reservation(res) for res in raw_reservations]
            except requests.Timeout as e:
                if attempt == self._retry_count - 1:
                    raise APITimeoutError(f"Timeout fetching reservations: {str(e)}")
            except requests.RequestException as e:
                if attempt == self._retry_count - 1:
                    raise APIError(f"Error fetching reservations: {str(e)}")
``` 