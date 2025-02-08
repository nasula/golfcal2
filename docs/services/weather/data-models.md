# Weather Service Data Models

## Overview

The weather service system uses standardized data models to ensure consistent data handling across different weather service providers. This document describes the core data structures and their implementations, following the strategy pattern.

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
    wind_direction: Optional[float]
    symbol: WeatherCode
    elaboration_time: datetime
    block_size: BlockSize
    thunder_probability: Optional[float] = None
```

### WeatherResponse

Container for weather data with metadata:

```python
@dataclass
class WeatherResponse:
    data: List[WeatherData]
    expires: datetime
    provider: str
    location: Location
```

### BlockSize

Standard block sizes for weather forecasts:

```python
class BlockSize(Enum):
    ONE_HOUR = timedelta(hours=1)
    THREE_HOURS = timedelta(hours=3)
    SIX_HOURS = timedelta(hours=6)
    TWELVE_HOURS = timedelta(hours=12)
```

### Location

Geographic location with validation:

```python
@dataclass
class Location:
    latitude: float
    longitude: float

    def __post_init__(self):
        if not (-90 <= self.latitude <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        if not (-180 <= self.longitude <= 180):
            raise ValueError("Longitude must be between -180 and 180")
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

## Cache Schema

Common cache schema for all weather services:

```python
@dataclass
class WeatherCache:
    key: str  # "{lat},{lon}:{provider}:{block_size}"
    data: WeatherResponse
    created_at: datetime
    expires_at: datetime
```

## Data Fields

### Required Fields

The following fields must be present in all weather data:
- `location`: Location object with validated coordinates
- `time`: ISO format timestamp with timezone
- `temperature`: Temperature in Celsius
- `precipitation`: Precipitation in mm/h
- `wind_speed`: Speed in m/s
- `symbol`: WeatherCode enum value
- `block_size`: BlockSize enum value

### Optional Fields

These fields may be NULL/None:
- `precipitation_probability`: 0-100%
- `thunder_probability`: 0-100%
- `wind_direction`: Degrees (0-360)

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

## Provider-Specific Mappings

### Met.no Strategy

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

BLOCK_SIZE_MAP = {
    'next_1_hours': BlockSize.ONE_HOUR,
    'next_6_hours': BlockSize.SIX_HOURS,
    'next_12_hours': BlockSize.TWELVE_HOURS
}
```

### OpenMeteo Strategy

```python
WMO_CODE_MAP = {
    0: WeatherCode.CLEARSKY_DAY,  # Clear sky
    1: WeatherCode.FAIR_DAY,      # Mainly clear
    2: WeatherCode.PARTLYCLOUDY_DAY,  # Partly cloudy
    3: WeatherCode.CLOUDY,        # Overcast
    45: WeatherCode.FOG,          # Foggy
    51: WeatherCode.LIGHTRAIN,    # Light drizzle
    53: WeatherCode.RAIN,         # Moderate drizzle
    55: WeatherCode.HEAVYRAIN,    # Dense drizzle
    95: WeatherCode.THUNDER,      # Thunderstorm
    96: WeatherCode.RAINANDTHUNDER,  # Thunderstorm with hail
    99: WeatherCode.HEAVYRAINANDTHUNDER  # Heavy thunderstorm with hail
}

BLOCK_SIZE_MAP = {
    'hourly': BlockSize.ONE_HOUR,
    '3hourly': BlockSize.THREE_HOURS,
    '6hourly': BlockSize.SIX_HOURS
}
```

## Data Validation

The system implements validation at multiple levels:

1. **Input Validation**
   - Location validation
   - Time ranges
   - Required fields presence
   - Block size validation

2. **Unit Validation**
   - Temperature range checks
   - Precipitation non-negative
   - Wind speed non-negative
   - Direction 0-360 degrees

3. **Format Validation**
   - ISO timestamp format
   - Weather code validity
   - Provider validity

## Best Practices

1. **Strategy Implementation**
   - Implement provider-specific logic in strategy classes
   - Use common interfaces for all providers
   - Handle provider-specific errors gracefully

2. **Data Conversion**
   - Convert to standard units in strategy classes
   - Validate ranges after conversion
   - Handle missing data gracefully

3. **Time Handling**
   - Store times in UTC
   - Convert to local time for display
   - Use timezone-aware datetimes

4. **Cache Management**
   - Use standardized cache keys
   - Implement proper expiration
   - Handle cache misses
   - Validate cached data on retrieval

5. **Geographic Selection**
   - Validate coordinates
   - Select appropriate provider based on location
   - Handle provider fallback 