# Reservation Service API

## Overview

The Reservation Service API provides functionality for managing golf reservations across multiple club management systems. It handles reservation creation, modification, cancellation, and synchronization with calendar events.

## Service Interface

### Get Reservations

```python
def get_reservations(
    self,
    user: str,
    start_date: datetime,
    end_date: Optional[datetime] = None,
    include_weather: bool = True,
    club: Optional[str] = None
) -> List[Reservation]:
    """Get user's golf reservations.
    
    Args:
        user: User identifier
        start_date: Start date for reservations
        end_date: Optional end date
        include_weather: Whether to include weather data
        club: Optional club filter
        
    Returns:
        List of reservations
        
    Raises:
        ReservationError: Reservation fetch failed
        AuthError: Authentication failed
    """
```

### Create Reservation

```python
def create_reservation(
    self,
    user: str,
    club: str,
    tee_time: datetime,
    players: List[str],
    course: Optional[str] = None,
    cart: bool = False
) -> Reservation:
    """Create new golf reservation.
    
    Args:
        user: User making reservation
        club: Golf club identifier
        tee_time: Requested tee time
        players: List of player names
        course: Optional specific course
        cart: Whether to reserve cart
        
    Returns:
        Created reservation
        
    Raises:
        ReservationError: Reservation creation failed
        AuthError: Authentication failed
        ValidationError: Invalid parameters
    """
```

### Cancel Reservation

```python
def cancel_reservation(
    self,
    user: str,
    reservation_id: str,
    reason: Optional[str] = None
) -> bool:
    """Cancel existing reservation.
    
    Args:
        user: User cancelling reservation
        reservation_id: Reservation identifier
        reason: Optional cancellation reason
        
    Returns:
        True if cancelled successfully
        
    Raises:
        ReservationError: Cancellation failed
        AuthError: Authentication failed
    """
```

### Check Availability

```python
def check_availability(
    self,
    club: str,
    date: datetime,
    players: int = 1,
    course: Optional[str] = None
) -> List[TimeSlot]:
    """Check available tee times.
    
    Args:
        club: Golf club identifier
        date: Date to check
        players: Number of players
        course: Optional specific course
        
    Returns:
        List of available time slots
        
    Raises:
        ReservationError: Availability check failed
        ValidationError: Invalid parameters
    """
```

## Data Models

### Reservation

```python
@dataclass
class Reservation:
    id: str                        # Unique reservation ID
    club: str                      # Golf club identifier
    course: str                    # Course name
    tee_time: datetime             # Tee time (UTC)
    duration: timedelta            # Expected duration
    players: List[str]             # Player names
    booker: str                    # User who made reservation
    status: ReservationStatus      # Current status
    cart: bool = False             # Cart reserved
    weather: Optional[WeatherData] = None  # Weather data if available
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional data
```

### Time Slot

```python
@dataclass
class TimeSlot:
    time: datetime                 # Slot time (UTC)
    available_slots: int           # Number of available slots
    total_slots: int              # Total slots in group
    price: Optional[float] = None  # Price if available
    restrictions: Optional[List[str]] = None  # Any booking restrictions
```

### Reservation Status

```python
class ReservationStatus(str, Enum):
    PENDING = 'pending'       # Awaiting confirmation
    CONFIRMED = 'confirmed'   # Booking confirmed
    CANCELLED = 'cancelled'   # Booking cancelled
    COMPLETED = 'completed'   # Round completed
```

## Usage Examples

### Get User Reservations

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Initialize service
reservation_service = ReservationService(config={
    'timezone': 'Europe/Helsinki'
})

# Get reservations
try:
    reservations = reservation_service.get_reservations(
        user='john.doe',
        start_date=datetime.now(ZoneInfo('UTC')),
        end_date=datetime.now(ZoneInfo('UTC')) + timedelta(days=30),
        include_weather=True
    )
    
    for reservation in reservations:
        print(f"Tee time: {reservation.tee_time}")
        if reservation.weather:
            print(f"Weather: {reservation.weather.temperature}°C")
except ReservationError as e:
    print(f"Failed to get reservations: {e}")
```

### Create New Reservation

```python
# Create reservation
try:
    reservation = reservation_service.create_reservation(
        user='john.doe',
        club='Example Golf Club',
        tee_time=datetime.now(ZoneInfo('UTC')) + timedelta(days=2),
        players=['John Doe', 'Jane Doe'],
        course='Main Course',
        cart=True
    )
    
    print(f"Created reservation: {reservation.id}")
    print(f"Status: {reservation.status}")
except ValidationError as e:
    print(f"Invalid parameters: {e}")
except ReservationError as e:
    print(f"Reservation failed: {e}")
```

### Check Availability

```python
# Check available times
try:
    slots = reservation_service.check_availability(
        club='Example Golf Club',
        date=datetime.now(ZoneInfo('UTC')) + timedelta(days=1),
        players=2
    )
    
    for slot in slots:
        print(f"Time: {slot.time}, Available: {slot.available_slots}")
        if slot.price:
            print(f"Price: {slot.price}")
except ReservationError as e:
    print(f"Failed to check availability: {e}")
```

## Error Handling

### Error Types

```python
class ReservationError(Exception):
    """Base class for reservation errors."""
    pass

class BookingError(ReservationError):
    """Booking operation failed."""
    pass

class CancellationError(ReservationError):
    """Cancellation operation failed."""
    pass

class AvailabilityError(ReservationError):
    """Availability check failed."""
    pass
```

### Error Handling Example

```python
try:
    reservation = reservation_service.create_reservation(...)
except ValidationError as e:
    print(f"Invalid parameters: {e}")
    # Fix parameters
except BookingError as e:
    print(f"Booking failed: {e}")
    # Try different time/course
except ReservationError as e:
    print(f"Reservation error: {e}")
    # General error handling
```

## Configuration

```yaml
reservation:
  # Default settings
  default_duration:
    hours: 4
    minutes: 0
  
  # Club settings
  clubs:
    example_club:
      type: wisegolf
      url: "https://example.com/golf"
      timezone: "Europe/Helsinki"
      courses:
        - name: "Main Course"
          holes: 18
          default_duration:
            hours: 4
            minutes: 30
  
  # Booking settings
  max_advance_days: 14
  min_players: 1
  max_players: 4
  
  # Integration settings
  sync_calendar: true
  include_weather: true
```

## Best Practices

1. **Reservation Management**
   - Validate tee times
   - Check player limits
   - Handle club restrictions
   - Set appropriate durations

2. **Error Handling**
   - Use specific error types
   - Implement retries
   - Log booking failures
   - Handle timeouts

3. **Integration**
   - Sync with calendar
   - Include weather data
   - Handle notifications
   - Monitor club systems

4. **Performance**
   - Cache availability data
   - Batch operations
   - Handle rate limits
   - Monitor response times 