# Data Flow

## Overview

GolfCal2's data flow is designed to efficiently process golf reservations, integrate weather data, and manage calendar events. This document details the various data flows within the system.

## Reservation Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant RS as ReservationService
    participant GCF as GolfClubFactory
    participant GC as GolfClub
    participant AS as AuthService
    participant WM as WeatherManager
    participant CS as CalendarService
    participant DB as Database

    User->>CLI: Request Reservations
    CLI->>RS: Process Request
    
    loop For Each Membership
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
            RS->>WM: Get Weather
            WM-->>RS: Weather Data
            RS->>CS: Create Calendar Event
            CS->>DB: Store Event
            DB-->>CS: Success
            CS-->>RS: Event Created
        end
    end
    
    RS-->>CLI: Processed Reservations
    CLI-->>User: Display Results
```

## Weather Flow

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

## Error Flow

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

## Golf Club System Flows

### WiseGolf Flow

```mermaid
sequenceDiagram
    participant RS as ReservationService
    participant GC as WiseGolfClub
    participant API as WiseGolfAPI
    participant REST as WiseGolfREST

    RS->>GC: Fetch Reservations
    GC->>API: Get Reservations
    API-->>GC: Raw Reservations
    
    loop For Each Future Reservation
        GC->>REST: Fetch Players
        Note right of REST: Uses REST API endpoint<br/>for player data
        REST-->>GC: Player Data
        GC->>GC: Parse Player Data
    end
    
    GC-->>RS: Processed Reservations
```

### NexGolf Flow

```mermaid
sequenceDiagram
    participant RS as ReservationService
    participant GC as NexGolfClub
    participant API as NexGolfAPI
    
    RS->>GC: Fetch Reservations
    GC->>API: Get Reservations
    Note right of API: Uses single API endpoint<br/>with date range parameter
    API-->>GC: Raw Reservations with Players
    GC->>GC: Parse Reservation Data
    GC-->>RS: Processed Reservations
```

### Key Differences

1. **Authentication**
   - WiseGolf: Token-based authentication with REST API
   - NexGolf: Cookie-based session authentication

2. **Player Data**
   - WiseGolf: Separate REST API call required for player data
   - NexGolf: Player data included in main reservation response

3. **Data Format**
   - WiseGolf: Two different API formats (AJAX and REST)
   - NexGolf: Single unified API format

4. **Date Handling**
   - WiseGolf: Server returns local times
   - NexGolf: Server returns UTC times with timezone info

5. **API Structure**
   - WiseGolf: Split between AJAX API (reservations) and REST API (players)
   - NexGolf: Single API endpoint with query parameters

## Related Documentation

- [Architecture Overview](overview.md)
- [Service Architecture](services.md)
- [Database Schema](../deployment/database.md)
```