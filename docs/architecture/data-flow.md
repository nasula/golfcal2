# Data Flow

## Overview

GolfCal2's data flow is designed to efficiently process golf reservations, integrate weather data, and manage calendar events. This document details the various data flows within the system.

## Reservation Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant RS as ReservationService
    participant GC as GolfClub
    participant WM as WeatherManager
    participant CS as CalendarService
    participant DB as Database

    User->>CLI: Create Reservation
    CLI->>RS: process_request()
    
    RS->>GC: check_availability()
    GC-->>RS: available_times
    
    RS->>GC: create_reservation()
    GC-->>RS: reservation_confirmation
    
    RS->>WM: get_weather()
    WM-->>RS: weather_data
    
    RS->>CS: create_event()
    CS->>DB: store_event()
    DB-->>CS: confirmation
    
    CS-->>RS: event_created
    RS-->>CLI: success
    CLI-->>User: confirmation
```

## Weather Integration Flow

```mermaid
sequenceDiagram
    participant CS as CalendarService
    participant WM as WeatherManager
    participant Cache as WeatherCache
    participant Primary as PrimaryProvider
    participant Backup as BackupProvider
    participant DB as Database

    CS->>WM: get_weather()
    
    WM->>Cache: check_cache()
    alt Cache Hit
        Cache-->>WM: cached_data
    else Cache Miss
        WM->>Primary: request_weather()
        alt Primary Success
            Primary-->>WM: weather_data
        else Primary Failure
            WM->>Backup: request_weather()
            Backup-->>WM: weather_data
        end
        WM->>Cache: update_cache()
        WM->>DB: store_weather()
    end
    
    WM-->>CS: weather_data
```

## Calendar Event Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant CS as CalendarService
    participant EES as ExternalEventService
    participant WM as WeatherManager
    participant DB as Database

    User->>CLI: list_events()
    CLI->>CS: get_events()
    
    par Golf Events
        CS->>DB: get_reservations()
        DB-->>CS: reservations
    and External Events
        CS->>EES: get_external_events()
        EES-->>CS: external_events
    end
    
    loop For Each Event
        CS->>WM: get_weather()
        WM-->>CS: weather_data
    end
    
    CS-->>CLI: events_with_weather
    CLI-->>User: formatted_output
```

## Data Models

### Reservation Data

```mermaid
classDiagram
    class Reservation {
        +str id
        +str club_name
        +datetime start_time
        +datetime end_time
        +List[str] players
        +Dict coordinates
        +Dict weather_data
        +str status
        +create()
        +cancel()
        +update()
    }
    
    class Club {
        +str name
        +str api_type
        +Dict coordinates
        +str address
        +check_availability()
        +create_reservation()
        +cancel_reservation()
    }
    
    class WeatherData {
        +float temperature
        +float precipitation
        +float wind_speed
        +str condition
        +datetime timestamp
        +update()
        +is_valid()
    }
    
    Reservation --> Club
    Reservation --> WeatherData
```

### Event Data

```mermaid
classDiagram
    class CalendarEvent {
        +str id
        +str title
        +datetime start_time
        +datetime end_time
        +str location
        +Dict weather_data
        +str event_type
        +create()
        +update()
        +delete()
    }
    
    class ExternalEvent {
        +str id
        +str source
        +str title
        +datetime start_time
        +datetime end_time
        +str location
        +Dict weather_data
        +sync()
        +update()
    }
    
    class EventBuilder {
        +build_from_reservation()
        +build_from_external()
        +add_weather()
        +validate()
    }
    
    CalendarEvent <|-- ExternalEvent
    EventBuilder --> CalendarEvent
```

## Data Storage

### Database Schema

```sql
-- Reservations
CREATE TABLE reservations (
    id TEXT PRIMARY KEY,
    club_name TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    players TEXT NOT NULL,
    coordinates TEXT NOT NULL,
    weather_data TEXT,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Weather Data
CREATE TABLE weather (
    id INTEGER PRIMARY KEY,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    temperature REAL,
    precipitation REAL,
    wind_speed REAL,
    condition TEXT,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(latitude, longitude, timestamp)
);

-- Calendar Events
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    location TEXT,
    weather_data TEXT,
    event_type TEXT NOT NULL,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Data Transformations

### Reservation Processing

```mermaid
graph TD
    A[Raw Reservation] --> B[Validate Data]
    B --> C[Format Times]
    C --> D[Get Weather]
    D --> E[Create Event]
    E --> F[Store Data]
    
    subgraph Validation
        B
    end
    
    subgraph Processing
        C
        D
    end
    
    subgraph Storage
        E
        F
    end
```

### Weather Processing

```mermaid
graph TD
    A[Weather Request] --> B[Check Cache]
    B --> C{Cache Hit?}
    C -->|Yes| D[Return Cached]
    C -->|No| E[Fetch New]
    E --> F[Transform Data]
    F --> G[Cache Data]
    G --> H[Return Data]
    
    subgraph Cache
        B
        C
        D
    end
    
    subgraph API
        E
        F
    end
    
    subgraph Storage
        G
        H
    end
```

## Error Handling

### Error Flow

```mermaid
sequenceDiagram
    participant User
    participant Service
    participant External
    participant Logger
    participant Monitoring

    User->>Service: Request
    
    alt Success
        Service->>External: API Call
        External-->>Service: Response
        Service-->>User: Result
    else User Error
        Service-->>User: Error Message
        Service->>Logger: Log Warning
    else System Error
        Service->>Logger: Log Error
        Service->>Monitoring: Alert
        Service-->>User: Error + Instructions
    else Integration Error
        External-->>Service: API Error
        Service->>Logger: Log Error
        Service-->>User: Error + Fallback
    end
```

## Related Documentation

- [Architecture Overview](overview.md)
- [Service Architecture](services.md)
- [Database Schema](../deployment/database.md)
``` 