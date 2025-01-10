# GolfCal2 Architecture Overview

## Introduction

GolfCal2 is a command-line calendar application designed to manage golf reservations and events. It integrates with various golf club systems and weather services to provide comprehensive information about golf activities.

## System Architecture

```mermaid
graph TD
    CLI[CLI Interface] --> CS[Calendar Service]
    CLI --> RS[Reservation Service]
    CS --> WM[Weather Manager]
    CS --> EES[External Event Service]
    RS --> WM
    RS --> GCF[Golf Club Factory]
    GCF --> WG[WiseGolf API]
    GCF --> NX[Nexgolf API]
    GCF --> TG[Teetime API]
    WM --> MET[MET.no]
    WM --> OW[OpenWeather]
    WM --> AE[AEMET]
    WM --> IP[IPMA]
    CS --> DB[(SQLite DB)]
    RS --> DB
```

## Core Components

### 1. Command Line Interface (CLI)
- Entry point for user interactions
- Handles command parsing and execution
- Manages user configuration
- Provides formatted output

### 2. Calendar Service
- Manages calendar events and reservations
- Integrates weather information
- Handles event conflicts
- Provides calendar views

### 3. Reservation Service
- Processes golf reservations
- Integrates with club systems
- Manages user memberships
- Handles booking confirmations

### 4. Weather Manager
- Coordinates weather services
- Caches weather data
- Handles provider fallback
- Normalizes weather formats

### 5. External Event Service
- Manages non-golf events
- Integrates with calendars
- Handles recurring events
- Provides event notifications

## Data Flow

### Reservation Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant RS as Reservation Service
    participant GC as Golf Club
    participant WM as Weather Manager
    participant DB as Database

    User->>CLI: Create Reservation
    CLI->>RS: Process Request
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

### Weather Integration Flow

```mermaid
sequenceDiagram
    participant CS as Calendar Service
    participant WM as Weather Manager
    participant Cache as Weather Cache
    participant Primary as Primary Provider
    participant Backup as Backup Provider
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

## Configuration

### Application Config
```yaml
global:
  timezone: "Europe/Helsinki"
  log_level: "INFO"
  cache_dir: "~/.golfcal2/cache"

database:
  path: "~/.golfcal2/data.db"
  backup_dir: "~/.golfcal2/backups"

weather:
  primary: "met"
  backup: "openweather"
  cache_duration: 3600
  providers:
    met:
      user_agent: "GolfCal2/0.6.0"
    openweather:
      api_key: "your-key"
```

### User Config
```yaml
user:
  name: "John Doe"
  email: "john@example.com"
  timezone: "Europe/Helsinki"
  
memberships:
  - club: "Helsinki Golf"
    type: "wisegolf"
    auth:
      username: "john.doe"
      password: "secure-password"
  
  - club: "Espoo Golf"
    type: "nexgolf"
    auth:
      member_id: "12345"
      pin: "1234"
```

## Error Handling

### Error Types
1. **User Errors**
   - Invalid input
   - Missing configuration
   - Authentication failures

2. **System Errors**
   - Database errors
   - Network failures
   - Service unavailability

3. **Integration Errors**
   - API failures
   - Data format mismatches
   - Timeout errors

### Error Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Service
    participant External

    User->>CLI: Command
    CLI->>Service: Request
    alt Success
        Service->>External: API Call
        External-->>Service: Response
        Service-->>CLI: Result
        CLI-->>User: Success
    else User Error
        Service-->>CLI: ValidationError
        CLI-->>User: Error Message
    else System Error
        Service-->>CLI: SystemError
        CLI-->>User: Error + Instructions
    else Integration Error
        External-->>Service: API Error
        Service-->>CLI: IntegrationError
        CLI-->>User: Error + Fallback
    end
```

## Security

### Authentication
- Secure credential storage
- API key management
- Session handling
- Token refresh

### Data Protection
- Encrypted storage
- Secure communication
- Data validation
- Access control

## Performance

### Caching Strategy
- Weather data caching
- Club data caching
- Configuration caching
- Cache invalidation

### Optimization
- Parallel requests
- Connection pooling
- Query optimization
- Resource cleanup

## Related Documentation

- [Service Architecture](services.md)
- [Data Flow](data-flow.md)
- [Configuration Guide](../deployment/configuration.md) 