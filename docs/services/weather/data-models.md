# Weather Service Data Models

## Overview

The weather service system uses standardized data models to ensure consistent data handling across different weather service providers. This document describes the core data structures and their implementations.

## Core Data Types

### WeatherData

The primary data container for weather information:

```python
@dataclass
class WeatherData:
    temperature: float
    precipitation: float
    precipitation_probability: Optional[float]
    wind_speed: float
    wind_direction: Optional[str]
    symbol: str
    elaboration_time: datetime
    thunder_probability: Optional[float] = None
    block_duration: timedelta = timedelta(hours=1)
```

### WeatherResponse

Container for weather data with expiration information:

```python
@dataclass
class WeatherResponse:
    data: List[WeatherData]
    expires: datetime
```

## Weather Codes

Standard weather codes used across all services:

```python
class WeatherCode(str, Enum):
    CLEARSKY_DAY = 'clearsky_day'
    CLEARSKY_NIGHT = 'clearsky_night'
    FAIR_DAY = 'fair_day'
    FAIR_NIGHT = 'fair_night'
    PARTLYCLOUDY_DAY = 'partlycloudy_day'
    PARTLYCLOUDY_NIGHT = 'partlycloudy_night'
    CLOUDY = 'cloudy'
    FOG = 'fog'
    LIGHTRAIN = 'lightrain'
    RAIN = 'rain'
    HEAVYRAIN = 'heavyrain'
    RAINSHOWERS_DAY = 'rainshowers_day'
    RAINSHOWERS_NIGHT = 'rainshowers_night'
    THUNDER = 'thunder'
    RAINANDTHUNDER = 'rainandthunder'
    HEAVYRAINANDTHUNDER = 'heavyrainandthunder'
```

## Database Schema

Common schema for all weather services:

```sql
CREATE TABLE weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT NOT NULL,
    time TEXT NOT NULL,
    data_type TEXT NOT NULL DEFAULT "next_1_hours",
    air_temperature REAL,
    precipitation_amount REAL,
    wind_speed REAL,
    wind_from_direction REAL,
    probability_of_precipitation REAL,
    probability_of_thunder REAL,
    summary_code TEXT,
    expires TEXT,
    last_modified TEXT,
    UNIQUE(location, time, data_type)
)
```

## Data Fields

### Required Fields

The following fields must be present in all weather data:
- `location`: Coordinates in format "lat,lon"
- `time`: ISO format timestamp
- `air_temperature`: Temperature in Celsius
- `precipitation_amount`: Precipitation in mm/h
- `wind_speed`: Speed in m/s
- `summary_code`: Standard weather code

### Optional Fields

These fields may be NULL/None:
- `probability_of_precipitation`: 0-100%
- `probability_of_thunder`: 0-100%
- `wind_from_direction`: Degrees (0-360)

## Unit Standards

All weather services must convert their data to these standard units:

1. **Temperature**
   - Unit: Celsius
   - Range: -50°C to +50°C
   - Precision: 0.1°C

2. **Precipitation**
   - Unit: mm/hour
   - Range: 0 to 100 mm/h
   - Precision: 0.1 mm

3. **Wind Speed**
   - Unit: meters/second
   - Range: 0 to 100 m/s
   - Precision: 0.1 m/s

4. **Wind Direction**
   - Unit: degrees
   - Range: 0 to 360
   - Precision: 1 degree

5. **Probabilities**
   - Unit: percentage
   - Range: 0 to 100
   - Precision: 1%

## Service-Specific Mappings

### MET.no Codes

```python
SYMBOL_MAP = {
    'clearsky_day': WeatherCode.CLEARSKY_DAY,
    'clearsky_night': WeatherCode.CLEARSKY_NIGHT,
    'fair_day': WeatherCode.FAIR_DAY,
    'fair_night': WeatherCode.FAIR_NIGHT,
    'partlycloudy_day': WeatherCode.PARTLYCLOUDY_DAY,
    'partlycloudy_night': WeatherCode.PARTLYCLOUDY_NIGHT,
    'cloudy': WeatherCode.CLOUDY,
    'rainshowers_day': WeatherCode.RAINSHOWERS_DAY,
    'rainshowers_night': WeatherCode.RAINSHOWERS_NIGHT,
    'rain': WeatherCode.RAIN,
    'thunder': WeatherCode.THUNDER
}
```

### OpenWeather Codes

```python
WEATHER_CODE_MAP = {
    800: lambda h: 'clearsky_day' if 6 <= h <= 18 else 'clearsky_night',
    801: lambda h: 'fair_day' if 6 <= h <= 18 else 'fair_night',
    802: lambda h: 'partlycloudy_day' if 6 <= h <= 18 else 'partlycloudy_night',
    803: 'cloudy',
    804: 'cloudy',
    500: 'lightrain',
    501: 'rain',
    502: 'heavyrain',
    200: 'lightrainandthunder',
    201: 'rainandthunder',
    202: 'heavyrainandthunder'
}
```

## Data Validation

The system implements validation at multiple levels:

1. **Input Validation**
   - Coordinate ranges
   - Time ranges
   - Required fields presence

2. **Unit Validation**
   - Temperature range checks
   - Precipitation non-negative
   - Wind speed non-negative
   - Direction 0-360 degrees

3. **Format Validation**
   - ISO timestamp format
   - Coordinate format
   - Weather code validity

## Best Practices

1. **Data Conversion**
   - Always convert to standard units
   - Validate ranges after conversion
   - Handle missing data gracefully

2. **Time Handling**
   - Store times in UTC
   - Convert to local time for display
   - Use timezone-aware datetimes

3. **Cache Management**
   - Use standardized cache keys
   - Implement proper expiration
   - Handle cache misses

4. **Error Handling**
   - Validate data before storage
   - Handle conversion errors
   - Log validation failures 