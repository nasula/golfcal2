# GolfCal2 Architecture Overview

## Introduction

GolfCal2 is a command-line application designed to manage golf reservations and events. It integrates with multiple golf club booking systems, weather services, and calendar systems to provide comprehensive golf activity management.

## System Architecture

```mermaid
graph TD
    CLI[CLI Interface] --> CS[Calendar Service]
    CLI --> RS[Reservation Service]
    CLI --> WM[Weather Manager]
    CLI --> EES[External Event Service]
    
    CS --> WM
    CS --> EES
    CS --> DB[(SQLite DB)]
    
    RS --> WM
    RS --> GCF[Golf Club Factory]
    RS --> AS[Auth Service]
    RS --> DB
    
    GCF --> WG[WiseGolf API]
    GCF --> WG0[WiseGolf0 API]
    GCF --> NG[NexGolf API]
    GCF --> TT[TeeTime API]
    
    WM --> MET[MET.no]
    WM --> OW[OpenWeather]
    WM --> AE[AEMET]
    WM --> IP[IPMA]
    WM --> OM[OpenMeteo]
    WM --> Cache[Weather Cache]
    
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

### 3. Weather Manager
- Coordinates multiple weather services
- Regional service selection
- Caches weather data
- Handles provider fallback
- Normalizes weather formats
- Providers:
  - MET.no (Nordic countries)
  - AEMET (Spain)
  - IPMA (Portugal)
  - OpenWeather (Mediterranean)
  - OpenMeteo (Global)

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
    participant AS as AuthService
    participant GC as GolfClub
    participant WM as WeatherManager
    participant DB as Database

    User->>CLI: Create Reservation
    CLI->>RS: Process Request
    RS->>AS: Authenticate
    AS-->>RS: Auth Token
    RS->>GC: Check Availability
    GC-->>RS: Available Times
    RS->>GC: Book Time
    GC-->>RS: Confirmation
    RS->>WM: Get Weather
    WM-->>RS: Weather Data
    RS->>DB: Store Reservation
    DB-->>RS: Confirmation
    RS-->>CLI: Success
    CLI-->>User: Confirmation
```

### Weather Integration

```mermaid
sequenceDiagram
    participant CS as CalendarService
    participant WM as WeatherManager
    participant Cache as WeatherCache
    participant Primary as PrimaryProvider
    participant Backup as BackupProvider
    participant DB as Database

    CS->>WM: Request Weather
    WM->>Cache: Check Cache
    alt Cache Hit
        Cache-->>WM: Cached Data
    else Cache Miss
        WM->>Primary: Request Data
        alt Primary Success
            Primary-->>WM: Weather Data
        else Primary Failure
            WM->>Backup: Request Data
            Backup-->>WM: Weather Data
        end
        WM->>Cache: Update Cache
        WM->>DB: Store Data
    end
    WM-->>CS: Weather Data
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
  primary: "met"
  backup: "openweather"
  cache_duration: 3600
  providers:
    met:
      user_agent: "GolfCal2/1.0.0"
    openweather:
      api_key: "your-key"
    aemet:
      api_key: "your-key"
    ipma:
      enabled: true
```

## Error Handling

```mermaid
sequenceDiagram
    participant User
    participant Service
    participant External
    participant Logger
    participant Monitor

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
        Service->>Monitor: Alert
        Service-->>User: Error + Instructions
    else Integration Error
        External-->>Service: API Error
        Service->>Logger: Log Error
        Service-->>User: Error + Fallback
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
- Club data caching
- Configuration caching
- Cache invalidation
- Cache cleanup

### Optimization
- Parallel requests
- Connection pooling
- Query optimization
- Resource cleanup
- Memory management

## Related Documentation

- [Service Architecture](services.md)
- [Data Flow](data-flow.md)
- [Configuration Guide](../deployment/configuration.md)
- [CLI Documentation](../services/cli.md) 