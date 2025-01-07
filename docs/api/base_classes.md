# Base Classes

## Weather Services

### WeatherManager

The `WeatherManager` class orchestrates multiple weather services based on geographical regions.

```python
class WeatherManager(EnhancedLoggerMixin):
    """Weather service manager for coordinating multiple regional weather services."""
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: AppConfig):
        """Initialize weather services with timezone and configuration."""
        
    def get_weather(
        self, 
        club: str, 
        teetime: datetime, 
        coordinates: Dict[str, float], 
        duration_minutes: Optional[int] = None
    ) -> Optional[str]:
        """Get weather data for a specific time and location."""
```

### WeatherService

The `WeatherService` class provides the base interface that all regional weather services implement:

```python
class WeatherService:
    """Base class for regional weather service implementations."""
    
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Fetch weather data for given coordinates and time range."""
        
    def get_block_size(self, hours_ahead: float) -> int:
        """Get forecast block size based on forecast time."""
```

## CRM Integration

### CRMInterface

The `CRMInterface` defines the contract that all CRM implementations must follow:

```python
class CRMInterface(ABC):
    """Interface defining required methods for CRM integrations"""
    
    @abstractmethod
    def authenticate(self) -> None:
        """Handle CRM-specific authentication"""
        
    @abstractmethod
    def get_reservations(self) -> List[Reservation]:
        """Fetch user's reservations from the CRM system"""
        
    @abstractmethod
    def parse_reservation(self, raw_reservation: Dict[str, Any]) -> Reservation:
        """Convert CRM-specific reservation format to standard Reservation model"""
```

### BaseCRMImplementation

The `BaseCRMImplementation` provides common functionality for CRM implementations:

```python
class BaseCRMImplementation(CRMInterface):
    """Enhanced base class for CRM implementations with common functionality"""
    
    def __init__(self, url: str, auth_details: Dict[str, Any]):
        """Initialize with API URL and authentication details."""
        self.url = url.rstrip('/')
        self.auth_details = auth_details
        self.session: Optional[requests.Session] = None
        self.timeout = 30
        self._retry_count = 3
    
    def get_reservations(self) -> List[Reservation]:
        """Template method that handles retries and conversion to standard model."""
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Enhanced request helper with authentication retry and error handling."""
        
    def _parse_datetime(self, value: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime:
        """Enhanced datetime parser with timezone handling."""
```

## Error Handling

The base implementations use specialized error types for different scenarios:

- `APIError`: Base class for API-related errors
- `APITimeoutError`: Raised on request timeouts
- `APIResponseError`: Raised on invalid responses
- `APIAuthError`: Raised on authentication failures

## Usage Guidelines

1. **Weather Services**
   - Use `WeatherManager` to handle weather data fetching
   - Implement regional services by extending `WeatherService`
   - Handle timezone conversions appropriately

2. **CRM Integration**
   - Extend `BaseCRMImplementation` for new CRM systems
   - Implement required abstract methods
   - Use the provided error handling mechanisms
   - Utilize helper methods for common operations

3. **Error Handling**
   - Use appropriate error types
   - Include context in error messages
   - Implement proper retry mechanisms
   - Handle authentication failures gracefully
``` 