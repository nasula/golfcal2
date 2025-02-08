# GolfCal2 Architecture Overview

## Introduction

GolfCal2 is a command-line application designed to manage golf reservations and events. It integrates with multiple golf club booking systems, weather services, and calendar systems to provide comprehensive golf activity management.

## System Architecture

```mermaid
graph TD
    CLI[CLI Interface] --> CS[Calendar Service]
    CLI --> RS[Reservation Service]
    CLI --> WS[Weather Service]
    CLI --> EES[External Event Service]
    
    CS --> WS
    CS --> EES
    CS --> DB[(SQLite DB)]
    
    RS --> WS
    RS --> GCF[Golf Club Factory]
    RS --> AS[Auth Service]
    RS --> DB
    
    GCF --> WG[WiseGolf API]
    GCF --> WG0[WiseGolf0 API]
    GCF --> NG[NexGolf API]
    GCF --> TT[TeeTime API]
    
    WS --> Met[Met.no Strategy]
    WS --> OM[OpenMeteo Strategy]
    WS --> Cache[Weather Cache]
    WS --> DB
    
    AS --> TS[Token Strategy]
    AS --> CS2[Cookie Strategy]
    AS --> QS[Query Strategy]
    AS --> BS[Basic Strategy]
```

## Core Services

### 1. Calendar Service
- Manages calendar events and reservations
- Integrates weather information
- Handles event conflicts and overlaps
- Generates ICS calendar files
- Processes external events
- Components:
  - Calendar Builder
  - Reservation Builder
  - External Event Builder
  - Weather Integration

### 2. Reservation Service
- Processes golf reservations
- Integrates with multiple club systems
- Manages user memberships
- Handles booking confirmations
- Components:
  - Golf Club Factory
  - Authentication Service
  - Weather Integration
  - Reservation Handler

### 3. Weather Service
- Implements strategy pattern for providers
- Geographic-based service selection
- Caching with expiry management
- Automatic fallback handling
- Block size management
- Providers:
  - Met.no Strategy (Nordic/Baltic)
  - OpenMeteo Strategy (Global)
- Block Sizes:
  - Met.no: 1h/6h/12h blocks
  - OpenMeteo: 1h/3h/6h blocks

### 4. Authentication Service
- Manages authentication strategies
- Handles API credentials
- Secure token storage
- Session management
- Strategies:
  - Token Authentication
  - Cookie Authentication
  - Query Parameter
  - Basic Auth

### 5. External Event Service
- Manages non-golf events
- Calendar integration
- Event synchronization
- Notification handling
- Components:
  - Event Processor
  - Calendar Sync
  - Weather Integration

## Data Flow

### Reservation Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant RS as ReservationService
    participant GCF as GolfClubFactory
    participant GC as GolfClub
    participant AS as AuthService
    participant WS as WeatherService
    participant DB as Database

    User->>CLI: Request Reservations
    CLI->>RS: Process Request
    RS->>GCF: Create Club Instance
    GCF-->>RS: Club Instance
    RS->>AS: Get Auth Headers
    AS-->>RS: Auth Token/Cookie
    RS->>GC: Fetch Reservations
    GC->>GC: Make API Request
    GC-->>RS: Raw Reservations
    
    loop For Each Reservation
        alt Future Reservation
            RS->>GC: Fetch Players
            GC-->>RS: Player Data
        end
        RS->>WS: Get Weather
        WS->>WS: Select Strategy
        WS-->>RS: Weather Data
        RS->>DB: Store Processed Data
        DB-->>RS: Confirmation
    end
    
    RS-->>CLI: Processed Reservations
    CLI-->>User: Display Results
```

### Weather Integration

```mermaid
sequenceDiagram
    participant CS as CalendarService
    participant WS as WeatherService
    participant Cache as WeatherCache
    participant Met as Met.no Strategy
    participant OM as OpenMeteo Strategy
    participant DB as Database

    CS->>WS: Request Weather
    WS->>Cache: Check Cache
    alt Cache Hit
        Cache-->>WS: Cached Data
    else Cache Miss
        WS->>WS: Select Strategy
        alt Nordic/Baltic Location
            WS->>Met: Get Weather
            Met-->>WS: Weather Data
        else Other Location
            WS->>OM: Get Weather
            alt OpenMeteo Success
                OM-->>WS: Weather Data
            else OpenMeteo Failure
                WS->>Met: Fallback
                Met-->>WS: Weather Data
            end
        end
        WS->>Cache: Update Cache
        WS->>DB: Store Data
    end
    WS-->>CS: Weather Data
```

## Configuration Structure

```yaml
# Global settings
global:
  timezone: "Europe/Helsinki"
  log_level: "INFO"
  cache_dir: "~/.golfcal2/cache"

# Database configuration
database:
  path: "~/.golfcal2/data.db"
  backup_dir: "~/.golfcal2/backups"
  backup_count: 7

# Weather service configuration
weather:
  cache_duration: 3600
  providers:
    met:
      user_agent: "GolfCal2/1.0.0"
    openmeteo:
      enabled: true
```

## Error Handling

```mermaid
sequenceDiagram
    participant User
    participant Service
    participant Strategy
    participant Cache
    participant Logger
    participant Monitor

    User->>Service: Request
    
    alt Cache Hit
        Service->>Cache: Check Cache
        Cache-->>Service: Cached Data
        Service-->>User: Result
    else Cache Miss
        Service->>Strategy: Execute Strategy
        alt Strategy Success
            Strategy-->>Service: Result
            Service->>Cache: Update Cache
            Service-->>User: Result
        else Primary Strategy Failure
            Service->>Strategy: Try Fallback
            Strategy-->>Service: Result
            Service->>Logger: Log Warning
            Service-->>User: Result
        else Complete Failure
            Service->>Logger: Log Error
            Service->>Monitor: Alert
            Service-->>User: Error Message
        end
    end
```

## Security

### Authentication
- Secure credential storage
- API key management
- Token-based authentication
- Session handling
- Token refresh mechanisms

### Data Protection
- Encrypted storage
- Secure communication
- Input validation
- Access control
- Sensitive data masking

## Performance

### Caching Strategy
- Weather data caching
- Response caching
- Cache invalidation
- Memory optimization
- Disk usage management

## Related Documentation

- [Service Architecture](services.md)
- [Data Flow](data-flow.md)
- [Configuration Guide](../deployment/configuration.md)
- [CLI Documentation](../services/cli.md) 