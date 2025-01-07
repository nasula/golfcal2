# Weather Caching System

## Overview

The weather caching system consists of two main components:
1. `WeatherDatabase`: Handles caching of weather forecast data
2. `WeatherLocationCache`: Manages location data caching for different weather services

## Weather Database

### Purpose

The `WeatherDatabase` class provides a SQLite-based caching system for weather forecast data. It helps reduce API calls and improves response times by storing weather data with expiration times.

### Features

- SQLite-based storage
- Configurable schema per weather service
- Automatic expiration handling
- Thread-safe operations
- Error handling and logging

### Implementation

```python
class WeatherDatabase:
    def __init__(self, db_name: str, schema: Dict[str, List[str]]):
        """Initialize database with schema.
        
        Args:
            db_name: Name of the database file (without .db extension)
            schema: Dictionary of table names to column definitions
        """
```

### Key Methods

1. **get_weather_data**:
   - Retrieves cached weather data for specific location and times
   - Handles expiration checking
   - Returns data in standardized format

2. **store_weather_data**:
   - Stores weather forecasts with expiration time
   - Handles data validation
   - Supports batch operations

## Location Cache

### Purpose

The `WeatherLocationCache` class manages location data for different weather services, caching the mapping between coordinates and service-specific location identifiers.

### Features

- Separate tables for different services (AEMET, IPMA)
- Coordinate to location mapping
- Distance-based location lookup
- Automatic cache expiration
- Thread-safe operations

### Database Schema

1. **Municipalities Table (AEMET)**:
```sql
CREATE TABLE municipalities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    municipality_code TEXT NOT NULL,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    last_updated TIMESTAMP NOT NULL,
    UNIQUE(municipality_code)
)
```

2. **Locations Table (IPMA)**:
```sql
CREATE TABLE locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_code TEXT NOT NULL,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    last_updated TIMESTAMP NOT NULL,
    UNIQUE(location_code)
)
```

3. **Coordinate Mappings**:
```sql
CREATE TABLE coordinate_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    service TEXT NOT NULL,
    location_code TEXT NOT NULL,
    distance REAL NOT NULL,
    last_updated TIMESTAMP NOT NULL,
    UNIQUE(latitude, longitude, service)
)
```

### Key Methods

1. **get_municipality**:
   - Finds nearest AEMET municipality for coordinates
   - Uses Haversine distance calculation
   - Supports maximum age and distance limits
   ```python
   def get_municipality(
       self,
       lat: float,
       lon: float,
       max_age_days: int = 30,
       max_distance_km: float = 10.0
   ) -> Optional[Dict[str, Any]]
   ```

2. **get_ipma_location**:
   - Finds nearest IPMA location for coordinates
   - Similar functionality to get_municipality
   - Handles IPMA-specific location codes

3. **cache_municipality/cache_ipma_location**:
   - Stores location data with timestamps
   - Updates existing entries if needed
   - Maintains coordinate mappings

### Distance Calculation

The cache uses the Haversine formula to calculate distances between coordinates:

```python
def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great circle distance between points."""
    R = 6371  # Earth's radius in kilometers
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c
```

## Usage Guidelines

1. **Weather Data Caching**:
   - Cache duration should match service update frequency
   - Use appropriate block sizes for different timeframes
   - Handle cache misses gracefully

2. **Location Caching**:
   - Cache locations with reasonable expiry (default 30 days)
   - Use appropriate distance limits
   - Handle cache misses with API fallback

3. **Error Handling**:
   - Handle database connection errors
   - Validate data before caching
   - Log cache hits/misses

4. **Performance**:
   - Use batch operations when possible
   - Index frequently queried fields
   - Regular cleanup of expired data

## Maintenance

1. **Cache Cleanup**:
   ```python
   def cleanup(self, max_age_days: int = 30) -> None:
       """Remove expired cache entries."""
   ```

2. **Database Optimization**:
   - Regular VACUUM operations
   - Index maintenance
   - Monitor database size

3. **Error Monitoring**:
   - Log cache performance metrics
   - Monitor hit/miss ratios
   - Track API fallback frequency

## Testing

1. **Unit Tests**:
   - Test distance calculations
   - Test cache operations
   - Test expiration handling

2. **Integration Tests**:
   - Test with actual coordinates
   - Test cache invalidation
   - Test concurrent access

3. **Performance Tests**:
   - Test with large datasets
   - Test concurrent operations
   - Measure cache hit ratios
``` 