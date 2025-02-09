# Calendar Service API

## Overview

The Calendar Service API provides functionality for managing calendar events, including golf reservations and external events. It handles event creation, modification, synchronization, and weather data integration.

## Service Interface

### Process Reservation

```python
def process_reservation(
    self,
    reservation: Reservation,
    include_weather: bool = True
) -> CalendarEvent:
    """Process golf reservation into calendar event.
    
    Args:
        reservation: Golf reservation data
        include_weather: Whether to fetch weather data
        
    Returns:
        CalendarEvent with processed data
        
    Raises:
        CalendarError: Processing failed
        WeatherError: Weather data fetch failed
    """
```

### Process External Event

```python
def process_external_event(
    self,
    event: ExternalEvent,
    check_conflicts: bool = True
) -> CalendarEvent:
    """Process external event into calendar event.
    
    Args:
        event: External event data
        check_conflicts: Whether to check for conflicts
        
    Returns:
        CalendarEvent with processed data
        
    Raises:
        CalendarError: Processing failed
        ConflictError: Event conflicts detected
    """
```

### Generate Calendar

```python
def generate_calendar(
    self,
    user: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> str:
    """Generate ICS calendar file for user.
    
    Args:
        user: User identifier
        start_date: Optional start date filter
        end_date: Optional end date filter
        
    Returns:
        Path to generated ICS file
        
    Raises:
        CalendarError: Calendar generation failed
    """
```

## Data Models

### Calendar Event

```python
@dataclass
class CalendarEvent:
    id: str                        # Unique event identifier
    title: str                     # Event title
    start_time: datetime           # Start time (UTC)
    end_time: datetime             # End time (UTC)
    location: Optional[Location]    # Event location
    description: Optional[str]      # Event description
    category: EventCategory        # Event category
    weather: Optional[WeatherData] # Weather data if available
    source: EventSource           # Event source type
    metadata: Dict[str, Any]      # Additional event data
```

### Event Source

```python
class EventSource(str, Enum):
    GOLF = 'golf'           # Golf reservation
    EXTERNAL = 'external'   # External event
    MANUAL = 'manual'       # Manually created
```

### Event Category

```python
class EventCategory(str, Enum):
    GOLF = 'golf'          # Golf events
    PERSONAL = 'personal'  # Personal events
    WORK = 'work'          # Work events
    TRAVEL = 'travel'      # Travel events
    SPORTS = 'sports'      # Sports events
    SOCIAL = 'social'      # Social events
    OTHER = 'other'        # Other events
```

## Usage Examples

### Process Golf Reservation

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Initialize service
calendar_service = CalendarService(config={
    'timezone': 'Europe/Helsinki',
    'ics_path': '~/calendars'
})

# Process reservation
try:
    reservation = Reservation(
        datetime_start=datetime.now(ZoneInfo('UTC')),
        players=['John Doe'],
        course_info=CourseInfo(name='Example Golf Club')
    )
    
    event = calendar_service.process_reservation(
        reservation=reservation,
        include_weather=True
    )
    
    print(f"Created event: {event.title}")
    if event.weather:
        print(f"Weather: {event.weather.temperature}°C")
except CalendarError as e:
    print(f"Failed to process reservation: {e}")
```

### Handle External Event

```python
# Process external event
try:
    external_event = ExternalEvent(
        id='123',
        title='Team Meeting',
        start_time=datetime.now(ZoneInfo('UTC')),
        end_time=datetime.now(ZoneInfo('UTC')) + timedelta(hours=1),
        category=EventCategory.WORK,
        priority=EventPriority.NORMAL
    )
    
    event = calendar_service.process_external_event(
        event=external_event,
        check_conflicts=True
    )
    
    print(f"Created event: {event.title}")
except ConflictError as e:
    print(f"Event conflicts: {e}")
except CalendarError as e:
    print(f"Failed to process event: {e}")
```

### Generate Calendar File

```python
# Generate calendar for user
try:
    ics_path = calendar_service.generate_calendar(
        user='john.doe',
        start_date=datetime.now(ZoneInfo('UTC')),
        end_date=datetime.now(ZoneInfo('UTC')) + timedelta(days=30)
    )
    
    print(f"Calendar generated: {ics_path}")
except CalendarError as e:
    print(f"Failed to generate calendar: {e}")
```

## Error Handling

### Error Types

```python
class CalendarError(Exception):
    """Base class for calendar service errors."""
    pass

class ConflictError(CalendarError):
    """Event conflict detected."""
    pass

class ValidationError(CalendarError):
    """Event validation failed."""
    pass

class GenerationError(CalendarError):
    """Calendar generation failed."""
    pass
```

### Error Handling Example

```python
try:
    event = calendar_service.process_external_event(external_event)
except ConflictError as e:
    print(f"Conflict detected: {e}")
    # Handle conflict (e.g., reschedule)
except ValidationError as e:
    print(f"Invalid event data: {e}")
    # Fix event data
except CalendarError as e:
    print(f"Calendar error: {e}")
    # General error handling
```

## Configuration

```yaml
calendar:
  # Directory settings
  ics_path: "~/calendars"
  backup_path: "~/calendars/backup"
  
  # Calendar settings
  default_duration: 
    hours: 4
    minutes: 0
  
  # Conflict handling
  conflict_buffer: 60  # minutes
  auto_resolve: true
  
  # Weather integration
  include_weather: true
  weather_threshold: 24  # hours
```

## Best Practices

1. **Event Processing**
   - Validate event data
   - Handle timezone conversion
   - Include weather when relevant
   - Set appropriate metadata

2. **Conflict Management**
   - Check for conflicts
   - Use appropriate buffer times
   - Handle recurring events
   - Document resolution rules

3. **Calendar Generation**
   - Use consistent formats
   - Include all event data
   - Handle large calendars
   - Implement backup strategy

4. **Integration**
   - Coordinate with weather service
   - Handle external events
   - Manage synchronization
   - Monitor performance 