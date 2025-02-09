# External Events Service API

## Overview

The External Events Service API manages non-golf events and their integration with the GolfCal2 calendar system. It handles event synchronization, weather data integration, and conflict detection with golf reservations.

## Service Interface

### Process Event

```python
def process_event(
    self,
    event_data: Union[str, Dict],
    source_type: str,
    check_conflicts: bool = True,
    include_weather: bool = True
) -> ExternalEvent:
    """Process external event from various sources.
    
    Args:
        event_data: Event data as string or dict
        source_type: Source format (ics/json/yaml)
        check_conflicts: Whether to check conflicts
        include_weather: Whether to include weather
        
    Returns:
        Processed external event
        
    Raises:
        EventError: Event processing failed
        ValidationError: Invalid event data
        ConflictError: Event conflicts detected
    """
```

### Import Events

```python
def import_events(
    self,
    source_path: str,
    source_type: str,
    recursive: bool = False
) -> List[ExternalEvent]:
    """Import events from file or directory.
    
    Args:
        source_path: Path to event source
        source_type: Source format
        recursive: Whether to process subdirectories
        
    Returns:
        List of imported events
        
    Raises:
        ImportError: Import operation failed
        ValidationError: Invalid event data
    """
```

### Sync Events

```python
def sync_events(
    self,
    source: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> SyncResult:
    """Synchronize events with source.
    
    Args:
        source: Event source identifier
        start_date: Optional sync start date
        end_date: Optional sync end date
        
    Returns:
        Synchronization results
        
    Raises:
        SyncError: Sync operation failed
    """
```

### Check Conflicts

```python
def check_conflicts(
    self,
    event: ExternalEvent,
    buffer_time: Optional[int] = None
) -> List[Conflict]:
    """Check for conflicts with other events.
    
    Args:
        event: Event to check
        buffer_time: Optional buffer in minutes
        
    Returns:
        List of detected conflicts
        
    Raises:
        ValidationError: Invalid event data
    """
```

## Data Models

### External Event

```python
@dataclass
class ExternalEvent:
    id: str                        # Unique event identifier
    title: str                     # Event title
    start_time: datetime           # Start time (UTC)
    end_time: datetime             # End time (UTC)
    location: Optional[Location]    # Event location
    description: Optional[str]      # Event description
    category: EventCategory        # Event category
    priority: EventPriority       # Event priority
    weather_data: Optional[WeatherResponse] = None  # Weather data
```

### Sync Result

```python
@dataclass
class SyncResult:
    added: List[ExternalEvent]     # Newly added events
    updated: List[ExternalEvent]   # Updated events
    deleted: List[str]            # Deleted event IDs
    failed: List[Tuple[str, str]] # Failed events with errors
    timestamp: datetime           # Sync completion time
```

### Conflict

```python
@dataclass
class Conflict:
    event: ExternalEvent          # Event being checked
    conflicting_event: Event      # Conflicting event
    type: ConflictType           # Type of conflict
    overlap: timedelta           # Overlap duration
```

### Event Priority

```python
class EventPriority(int, Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
```

## Usage Examples

### Process External Event

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Initialize service
event_service = ExternalEventService(config={
    'timezone': 'Europe/Helsinki'
})

# Process event
try:
    event_data = {
        'title': 'Team Meeting',
        'start_time': '2024-02-09T10:00:00+02:00',
        'end_time': '2024-02-09T11:30:00+02:00',
        'category': 'work',
        'priority': 3,
        'location': {
            'name': 'Office',
            'coordinates': {
                'lat': 60.1699,
                'lon': 24.9384
            }
        }
    }
    
    event = event_service.process_event(
        event_data=event_data,
        source_type='json',
        check_conflicts=True
    )
    
    print(f"Processed event: {event.title}")
    if event.weather_data:
        print(f"Weather: {event.weather_data.temperature}°C")
except ConflictError as e:
    print(f"Event conflicts: {e}")
except EventError as e:
    print(f"Processing failed: {e}")
```

### Import Events

```python
# Import events from directory
try:
    events = event_service.import_events(
        source_path='~/calendars',
        source_type='ics',
        recursive=True
    )
    
    print(f"Imported {len(events)} events")
    for event in events:
        print(f"Event: {event.title} at {event.start_time}")
except ImportError as e:
    print(f"Import failed: {e}")
```

### Check Conflicts

```python
# Check for conflicts
try:
    conflicts = event_service.check_conflicts(
        event=event,
        buffer_time=60  # 60 minutes buffer
    )
    
    if conflicts:
        print("Conflicts detected:")
        for conflict in conflicts:
            print(f"Conflicts with: {conflict.conflicting_event.title}")
            print(f"Overlap: {conflict.overlap}")
except ValidationError as e:
    print(f"Invalid event: {e}")
```

## Error Handling

### Error Types

```python
class EventError(Exception):
    """Base class for event errors."""
    pass

class ImportError(EventError):
    """Event import failed."""
    pass

class SyncError(EventError):
    """Event sync failed."""
    pass

class ConflictError(EventError):
    """Event conflict detected."""
    pass
```

### Error Handling Example

```python
try:
    event = event_service.process_event(event_data, 'json')
except ValidationError as e:
    print(f"Invalid event data: {e}")
    # Fix event data
except ConflictError as e:
    print(f"Event conflicts: {e}")
    # Handle conflicts
except EventError as e:
    print(f"Event error: {e}")
    # General error handling
```

## Configuration

```yaml
external_events:
  # Source settings
  sources:
    ics:
      enabled: true
      watch_directory: "~/calendars"
      sync_interval: 300  # seconds
    json:
      enabled: true
      api_enabled: true
    yaml:
      enabled: true
      config_file: "events.yaml"
  
  # Category settings
  categories:
    personal:
      color: "#4CAF50"
      icon: "person"
    work:
      color: "#2196F3"
      icon: "work"
    travel:
      color: "#FFC107"
      icon: "flight"
  
  # Conflict settings
  conflict_handling:
    buffer_time: 60  # minutes
    auto_resolve: true
    priority_rules:
      - {category: "work", priority: 3}
      - {category: "travel", priority: 3}
      - {category: "sports", priority: 2}
```

## Best Practices

1. **Event Processing**
   - Validate event data
   - Handle timezones correctly
   - Include weather when relevant
   - Set appropriate priorities

2. **Conflict Management**
   - Use appropriate buffer times
   - Consider event priorities
   - Handle recurring events
   - Document resolutions

3. **Synchronization**
   - Handle partial failures
   - Implement retry logic
   - Track sync status
   - Monitor performance

4. **Integration**
   - Coordinate with calendar
   - Include weather data
   - Handle notifications
   - Monitor sources 