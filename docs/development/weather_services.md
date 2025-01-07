# Weather Services

This document describes the weather service architecture and implementations in GolfCal.

## Architecture Overview

### WeatherManager

The `WeatherManager` class serves as the central coordinator for all weather services:

```python
class WeatherManager(EnhancedLoggerMixin):
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: AppConfig):
        """Initialize weather services with timezone and configuration."""
        self.services = {
            'mediterranean': MediterraneanWeatherService(local_tz, utc_tz, config),
            'iberian': IberianWeatherService(local_tz, utc_tz, config),
            'met': MetWeatherService(local_tz, utc_tz, config),
            'portuguese': PortugueseWeatherService(local_tz, utc_tz, config)
        }
        
        self.regions = {
            'norway': {
                'service': 'met',
                'bounds': (57.0, 71.5, 4.0, 31.5)  # lat_min, lat_max, lon_min, lon_max
            },
            'mediterranean': {
                'service': 'mediterranean',
                'bounds': (35.0, 45.0, 20.0, 45.0)
            },
            'portugal': {
                'service': 'portuguese',
                'bounds': (36.5, 42.5, -9.5, -7.5)
            },
            'spain_mainland': {
                'service': 'iberian',
                'bounds': (36.0, 44.0, -7.5, 3.5)
            },
            'spain_canary': {
                'service': 'iberian',
                'bounds': (27.5, 29.5, -18.5, -13.0)
            }
        }
```

### WeatherService Interface

The `WeatherService` class provides the base interface that all regional weather services must implement:

```python
class WeatherService(EnhancedLoggerMixin):
    """Base class for regional weather service implementations."""
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: AppConfig):
        """Initialize with timezone settings and configuration."""
        self.local_tz = local_tz
        self.utc_tz = utc_tz
        self.config = config
        self._setup_logging()
    
    @abstractmethod
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        """Fetch weather data for given coordinates and time range."""
        pass
    
    @abstractmethod
    def get_block_size(self, hours_ahead: float) -> int:
        """Get forecast block size based on forecast time."""
        pass
```

## Regional Services

### 1. Met Weather Service (Nordic)
- **Coverage**: Norway and surrounding Nordic regions
- **API**: Met.no LocationForecast 2.0
- **Features**:
  - High-resolution forecasts
  - No API key required
  - 1-hour intervals for first 24 hours
  - 6-hour intervals thereafter
  - Direct thunder probability from API
- **Block Sizes**:
  - 1 hour for 0-24 hours ahead
  - 6 hours for 24-48 hours ahead
  - 12 hours beyond 48 hours
- **Thunder Calculation**:
  - Uses API's `probability_of_thunder` field
  - Falls back to symbol code analysis if API data unavailable
  - Heavy thunder: 80%, Light thunder: 20%, Medium: 50%

### 2. Iberian Weather Service (Spain)
- **Coverage**: Spain mainland and Canary Islands
- **API**: AEMET OpenData
- **Features**:
  - Official Spanish meteorological service
  - Requires API key
  - Municipality-based forecasts
  - Separate handling for mainland and islands
  - Thunder probability from weather descriptions
- **Block Sizes**:
  - 1 hour for first 48 hours
  - 3 hours thereafter
- **Thunder Calculation**:
  - Based on "tormenta" keyword in weather descriptions
  - Default 50% probability when thunder is mentioned

### 3. Portuguese Weather Service
- **Coverage**: Portugal mainland
- **API**: IPMA API
- **Features**:
  - Official Portuguese weather service
  - No API key required
  - Daily forecasts with hourly details
  - 10-day forecast range
  - Thunder codes in weather types
- **Block Sizes**:
  - 1 hour for first 24 hours
  - 3 hours for 24-72 hours
  - 6 hours beyond 72 hours
- **Thunder Calculation**:
  - Based on IPMA weather type codes
  - Types 6, 7, 9 indicate thunder conditions
  - Default 50% probability for thunder weather types

### 4. Mediterranean Weather Service
- **Coverage**: Mediterranean region
- **API**: OpenWeather API
- **Features**:
  - Wide coverage area
  - 3-hour interval forecasts
  - 5-day forecast range
  - Comprehensive weather data
  - Detailed thunder probability calculation
- **Block Sizes**:
  - 3 hours consistently
- **Thunder Calculation**:
  - Based on OpenWeather codes (2xx series)
  - Probability mapping:
    - 200: 30% (Light thunderstorm)
    - 201: 60% (Thunderstorm)
    - 202: 90% (Heavy thunderstorm)
    - 210: 20% (Light thunderstorm)
    - 211: 50% (Thunderstorm)
    - 212: 80% (Heavy thunderstorm)
    - 221: 40% (Ragged thunderstorm)
    - 230: 25% (Light thunderstorm with drizzle)
    - 231: 45% (Thunderstorm with drizzle)
    - 232: 65% (Heavy thunderstorm with drizzle)

## Weather Data Model

```python
@dataclass
class WeatherData:
    elaboration_time: datetime
    temperature: float  # Celsius
    precipitation_probability: float  # 0-100%
    wind_speed: float  # meters/second
    wind_direction: float  # degrees (0-360)
    weather_symbol: str
    cloud_coverage: Optional[float] = None  # 0-100%
    thunder_probability: Optional[float] = None  # 0-100%
```

## Weather Codes

The application uses a standardized set of weather codes across all services:

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
    THUNDER = 'thunder'
    RAINANDTHUNDER = 'rainandthunder'
    HEAVYRAINANDTHUNDER = 'heavyrainandthunder'
```

These codes are mapped to display symbols (emojis) using the `get_weather_symbol()` function:

```python
def get_weather_symbol(symbol_code: str) -> str:
    """Map weather symbol codes to emojis."""
    # Returns appropriate emoji for the weather code
    # e.g., 'clearsky_day' -> '☀️', 'rain' -> '🌧️', etc.
```

## Caching Strategy

### 1. Location-based Cache
- SQLite database for persistent storage
- Caches weather data by location and time range
- Automatic expiration based on forecast age
- Configurable cache duration per service

### 2. Memory Cache
- In-memory caching for frequent requests
- Short-term caching (1-3 hours)
- Automatic cleanup of expired entries
- Reduces API calls for same location/time

### 3. Station Cache
- Caches weather station mappings
- Used by AEMET and IPMA services
- 30-day validity for mappings
- Periodic background updates

## Error Handling

Weather services implement comprehensive error handling:

```python
@handle_errors(WeatherError, "weather", "get weather data")
def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
    try:
        data = self._fetch_weather_data(lat, lon, start_time, end_time)
        return [self._parse_weather_data(item) for item in data]
    except Exception as e:
        raise WeatherError(
            f"Failed to get weather data: {str(e)}",
            ErrorCode.SERVICE_ERROR,
            {
                "coordinates": {"lat": lat, "lon": lon},
                "timeframe": {"start": start_time, "end": end_time}
            }
        )
```

## Best Practices

1. **Service Selection**
   - Use `WeatherManager` for all weather data requests
   - Let the manager handle service selection
   - Provide accurate coordinates

2. **Error Handling**
   - Handle service-specific errors appropriately
   - Implement proper retries
   - Use fallback services when available

3. **Data Processing**
   - Convert all units to standard format
   - Validate data ranges
   - Handle timezone conversions properly

4. **Caching**
   - Use appropriate cache strategy
   - Implement cache invalidation
   - Handle cache misses gracefully 

## Data Processing

### 1. Unit Standardization
- Temperature: Always in Celsius
- Wind Speed: Converted to meters/second
- Wind Direction: Normalized to 0-360 degrees
- Probabilities: Converted to percentages (0-100)

### 2. Thunder Probability Processing
- Each service implements its own calculation method
- Probabilities normalized to 0-100% scale
- Default to 0% when no thunder data available
- Higher probabilities for severe conditions
- Service-specific mappings for weather codes

### 3. Time Handling
- All times converted to UTC internally
- Local timezone handling for display
- Proper handling of forecast blocks
- Time-based data aggregation

## Caching Strategy

### 1. Location-based Cache
- SQLite database for persistent storage
- Caches weather data by location and time range
- Automatic expiration based on forecast age
- Configurable cache duration per service

### 2. Memory Cache
- In-memory caching for frequent requests
- Short-term caching (1-3 hours)
- Automatic cleanup of expired entries
- Reduces API calls for same location/time

### 3. Station Cache
- Caches weather station mappings
- Used by AEMET and IPMA services
- 30-day validity for mappings
- Periodic background updates 