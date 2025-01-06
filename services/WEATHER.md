# Weather Service Documentation

## WeatherService Interface

The `WeatherService` class serves as the base interface for implementing weather data providers in the application. It provides a standardized way to fetch and process weather data from different sources while maintaining consistent data formats and error handling.

### Base Class Overview

```python
class WeatherService(EnhancedLoggerMixin):
    def __init__(self, local_tz, utc_tz):
        # Initialize timezones and logging
        pass

    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        # Main public interface for fetching weather data
        pass

    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        # Abstract method to be implemented by subclasses
        raise NotImplementedError("Subclasses must implement _fetch_forecasts")

    def get_block_size(self, hours_ahead: float) -> int:
        # Get forecast block size based on how far ahead the forecast is
        raise NotImplementedError("Subclasses must implement get_block_size")
```

### Required Methods

1. `_fetch_forecasts`: Implement the actual weather data fetching logic
   ```python
   def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
       # Fetch and process weather data from your service
       # Return a list of WeatherData objects
   ```

2. `get_block_size`: Define how forecasts should be grouped based on time
   ```python
   def get_block_size(self, hours_ahead: float) -> int:
       # Return block size in hours (e.g., 1 for hourly forecasts, 6 for 6-hour blocks)
       # Example:
       if hours_ahead <= 48:
           return 1  # Hourly forecasts for first 48 hours
       return 6     # 6-hour blocks beyond that
   ```

### Implementing a New Weather Service

To implement a new weather service:

1. Create a new class that inherits from `WeatherService`:
   ```python
   class MyWeatherService(WeatherService):
       def __init__(self, local_tz, utc_tz, config):
           super().__init__(local_tz, utc_tz)
           # Initialize service-specific configuration
   ```

2. Implement the required methods:
   - `_fetch_forecasts`: Fetch and process weather data
   - `get_block_size`: Define forecast grouping logic

3. Return weather data in the standardized `WeatherData` format:
   ```python
   WeatherData(
       temperature=float,          # Temperature in Celsius
       precipitation=float,        # Precipitation amount in mm
       precipitation_probability=float,  # Probability as percentage (0-100)
       wind_speed=float,          # Wind speed in m/s
       wind_direction=str,        # Wind direction in degrees or cardinal points
       symbol=str,                # Weather symbol code (see WeatherCode class)
       elaboration_time=datetime, # Forecast time (timezone-aware)
       thunder_probability=float  # Thunder probability as percentage (0-100)
   )
   ```

### Key Implementation Details

1. **Error Handling**:
   - Use the provided `handle_errors` decorator for consistent error handling
   - Log errors appropriately using the inherited logger
   - Return empty list on errors to maintain graceful degradation

2. **Time Handling**:
   - Always use timezone-aware datetime objects
   - Convert between timezones using the provided `local_tz` and `utc_tz`
   - Ensure forecasts are within the requested time range
   - Use `get_block_size` to determine appropriate forecast grouping

3. **Data Formatting**:
   - Map service-specific weather codes to standard `WeatherCode` values
   - Convert units to standard formats (e.g., m/s for wind speed)
   - Ensure all required fields in `WeatherData` are populated

4. **Caching (Optional)**:
   - Implement caching if your service has rate limits
   - Use the provided `WeatherDatabase` for persistent storage
   - Handle cache invalidation appropriately

### Best Practices

1. **API Rate Limiting**:
   - Implement appropriate rate limiting for your service
   - Use the `_min_call_interval` property to control request spacing
   - Cache responses when possible to minimize API calls

2. **Logging**:
   - Use the inherited logger for consistent log formatting
   - Include relevant context in log messages
   - Use appropriate log levels (debug, info, warning, error)

3. **Error Recovery**:
   - Handle API errors gracefully
   - Provide meaningful error messages
   - Fall back to cached data when possible

4. **Data Validation**:
   - Validate all input parameters
   - Verify API responses before processing
   - Handle missing or invalid data gracefully

5. **Block Size Implementation**:
   - Consider service data resolution when implementing `get_block_size`
   - Account for varying forecast accuracy over time
   - Document block size logic clearly
   - Consider caching block size results if calculation is expensive

### Example Implementation

```python
class ExampleWeatherService(WeatherService):
    def __init__(self, local_tz, utc_tz, config):
        super().__init__(local_tz, utc_tz)
        self.api_key = config.global_config['api_keys']['weather']['example']
        self.endpoint = "https://api.example.com/weather"
        self._min_call_interval = timedelta(seconds=1)

    def get_block_size(self, hours_ahead: float) -> int:
        """Get forecast block size based on time ahead.
        
        Our example service provides:
        - Hourly forecasts for first 48 hours
        - 3-hour blocks for 48-72 hours
        - 6-hour blocks beyond that
        """
        if hours_ahead <= 48:
            return 1
        elif hours_ahead <= 72:
            return 3
        return 6

    @log_execution(level='DEBUG', include_args=True)
    def _fetch_forecasts(self, lat: float, lon: float, start_time: datetime, end_time: datetime) -> List[WeatherData]:
        try:
            # Fetch data from API
            response = requests.get(
                self.endpoint,
                params={
                    'lat': lat,
                    'lon': lon,
                    'apikey': self.api_key
                }
            )
            response.raise_for_status()
            data = response.json()

            # Process and convert to WeatherData objects
            forecasts = []
            for item in data['forecasts']:
                forecast_time = datetime.fromisoformat(item['time'])
                if start_time <= forecast_time <= end_time:
                    forecasts.append(WeatherData(
                        temperature=float(item['temp']),
                        precipitation=float(item['precip']),
                        precipitation_probability=float(item['precip_prob']),
                        wind_speed=float(item['wind_speed']),
                        wind_direction=str(item['wind_dir']),
                        symbol=self._map_weather_code(item['condition']),
                        elaboration_time=forecast_time,
                        thunder_probability=float(item.get('thunder_prob', 0))
                    ))

            return forecasts

        except Exception as e:
            self.error(
                "Failed to fetch weather data",
                exc_info=e,
                service=self.__class__.__name__
            )
            return []
```

# GolfCal Weather Services

Detailed documentation of the weather services used in GolfCal.

## Service Overview

GolfCal uses multiple weather services to provide accurate forecasts for different regions:

### 1. Met.no (Nordic Weather Service)

**Coverage**: Nordic countries (Norway, Sweden, Finland, Denmark)
**API Documentation**: https://api.met.no/weatherapi/

Features:
- High-resolution forecasts for Nordic region
- No API key required
- Free for non-commercial use
- Requires proper User-Agent header

Data Resolution:
- Next 48 hours: 1-hour intervals
- Beyond 48 hours: 6-hour intervals

Example Response:
```json
{
    "type": "Feature",
    "geometry": {
        "type": "Point",
        "coordinates": [10.8282, 59.8940]
    },
    "properties": {
        "timeseries": [
            {
                "time": "2024-12-25T12:00:00Z",
                "data": {
                    "instant": {
                        "details": {
                            "air_temperature": 2.3,
                            "wind_speed": 3.2,
                            "wind_from_direction": 180.0
                        }
                    },
                    "next_1_hours": {
                        "summary": {
                            "symbol_code": "cloudy"
                        },
                        "details": {
                            "precipitation_amount": 0.0
                        }
                    }
                }
            }
        ]
    }
}
```

### 2. AEMET (Spanish Weather Service)

**Coverage**: Spain (mainland and islands)
**API Documentation**: https://opendata.aemet.es/dist/index.html

Features:
- Official Spanish weather service
- Requires API key (free registration)
- Supports both hourly and daily forecasts
- Municipality-based forecasts

Data Resolution:
- Next 2 days: Hourly intervals
- Beyond 2 days: Daily intervals (morning/afternoon)

Municipality Mapping:
- Uses weather station database
- Coordinates → Nearest station → Municipality
- Database refreshed every 30 days
- Example: PGA Catalunya → Caldes de Malavella (17033)

Example Response:
```json
{
    "prediccion": {
        "dia": [
            {
                "fecha": "2024-12-25",
                "temperatura": [
                    {
                        "value": 15.2,
                        "periodo": "09"
                    }
                ],
                "precipitacion": [
                    {
                        "value": 0.0,
                        "probabilidad": 5,
                        "periodo": "09"
                    }
                ],
                "viento": [
                    {
                        "direccion": 180,
                        "velocidad": 3.2,
                        "periodo": "09"
                    }
                ],
                "estadoCielo": [
                    {
                        "value": "11",
                        "periodo": "09"
                    }
                ]
            }
        ]
    }
}
```

### 3. IPMA (Portuguese Weather Service)

**Coverage**: Portugal (mainland and islands)
**API Documentation**: https://api.ipma.pt/

Features:
- Official Portuguese weather service
- No API key required
- Daily forecasts with 10-day range
- Location-based forecasts

Data Resolution:
- Daily intervals with:
  - Morning (06:00-12:00)
  - Afternoon (12:00-18:00)
  - Evening (18:00-24:00)

Example Response:
```json
{
    "data": [
        {
            "precipitaProb": "15.0",
            "tMin": "12.0",
            "tMax": "18.0",
            "predWindDir": "N",
            "idWeatherType": 2,
            "classWindSpeed": 2,
            "forecastDate": "2024-12-25"
        }
    ]
}
```

### 4. OpenWeather (Mediterranean Service)

**Coverage**: Mediterranean region
**API Documentation**: https://openweathermap.org/api

Features:
- Wide coverage of Mediterranean region
- Default API key provided
- 3-hour interval forecasts
- 5-day forecast range

Data Resolution:
- 3-hour intervals for all forecasts
- Consistent format across forecast range

Example Response:
```json
{
    "list": [
        {
            "dt": 1703505600,
            "main": {
                "temp": 15.2,
                "feels_like": 14.8,
                "humidity": 76
            },
            "weather": [
                {
                    "id": 801,
                    "main": "Clouds",
                    "description": "few clouds"
                }
            ],
            "wind": {
                "speed": 3.2,
                "deg": 180
            },
            "rain": {
                "3h": 0.0
            }
        }
    ]
}
```

## Weather Codes

### Standard Weather Codes

GolfCal uses a standardized set of weather codes across all services:

```python
class WeatherCode:
    CLEAR_DAY = "clearsky_day"
    CLEAR_NIGHT = "clearsky_night"
    FAIR_DAY = "fair_day"
    FAIR_NIGHT = "fair_night"
    PARTLY_CLOUDY_DAY = "partlycloudy_day"
    PARTLY_CLOUDY_NIGHT = "partlycloudy_night"
    CLOUDY = "cloudy"
    LIGHT_RAIN = "lightrain"
    RAIN = "rain"
    HEAVY_RAIN = "heavyrain"
    RAIN_AND_THUNDER = "rainandthunder"
    HEAVY_RAIN_AND_THUNDER = "heavyrainandthunder"
    LIGHT_SNOW = "lightsnow"
    SNOW = "snow"
    HEAVY_SNOW = "heavysnow"
    LIGHT_SLEET = "lightsleet"
    HEAVY_SLEET = "heavysleet"
    FOG = "fog"
```

### Service-Specific Mappings

#### AEMET Codes
```python
{
    '11': WeatherCode.CLEAR_DAY,
    '11n': WeatherCode.CLEAR_NIGHT,
    '12': WeatherCode.FAIR_DAY,
    '12n': WeatherCode.FAIR_NIGHT,
    '13': WeatherCode.PARTLY_CLOUDY_DAY,
    '13n': WeatherCode.PARTLY_CLOUDY_NIGHT,
    '14': WeatherCode.CLOUDY,
    '15': WeatherCode.LIGHT_RAIN,
    # ... etc
}
```

#### IPMA Codes
```python
{
    1: WeatherCode.CLEAR_DAY,
    2: WeatherCode.FAIR_DAY,
    3: WeatherCode.PARTLY_CLOUDY_DAY,
    4: WeatherCode.CLOUDY,
    5: WeatherCode.LIGHT_RAIN,
    # ... etc
}
```

## Service Selection

The weather service is selected based on coordinates:

```python
def select_weather_service(lat: float, lon: float) -> WeatherService:
    """Select appropriate weather service based on coordinates."""
    if 55 <= lat <= 72 and 3 <= lon <= 32:  # Nordic
        return MetNoWeatherService()
    elif -9.5 <= lon <= -6.2:  # Portugal
        return IberianWeatherService()  # IPMA
    elif -7 <= lon <= 5:  # Spain
        return IberianWeatherService()  # AEMET
    else:  # Mediterranean
        return MediterraneanWeatherService()  # OpenWeather
```

## Testing

### Test Events

Test events are defined in `test_events.yaml` to cover:
1. Different time ranges:
   - Tomorrow (hourly forecasts)
   - 3 days ahead (daily forecasts)
   - 7 days ahead (long-range)

2. Different times of day:
   - Morning (sunrise handling)
   - Afternoon (peak temperatures)
   - Evening (sunset handling)

3. Different regions:
   - Nordic (Oslo GC)
   - Spain mainland (PGA Catalunya)
   - Canary Islands (Costa Adeje)
   - Portugal (Praia D'El Rey)
   - Mediterranean (Lykia Links)

### Running Tests

```bash
# Basic test with all events
python -m golfcal --dev process

# Verbose mode for debugging
python -m golfcal --dev -v process

# Test specific user's events
python -m golfcal --dev -u Jarkko process
```

## Error Handling

Each service implements specific error handling:

1. Rate Limiting:
   - Met.no: 20 requests/second
   - AEMET: 10 requests/minute
   - IPMA: No explicit limit
   - OpenWeather: 60 requests/minute

2. Retry Logic:
   - Maximum 3 retries
   - Exponential backoff
   - Different delays for rate limits

3. Data Validation:
   - Coordinate bounds checking
   - Temperature range validation
   - Missing data handling

## Cache Management

The application uses different caching strategies depending on the weather service provider. Here's how each one works:

### Met.no Weather Data Cache

Met.no weather data is stored in a SQLite database for efficient retrieval and management. This approach:
- Reduces API calls to Met.no's servers
- Respects their rate limits
- Ensures we have historical data when needed

#### How it works:

1. **Data Storage**
   - Weather data is stored by location (latitude/longitude) and time
   - Each weather parameter (temperature, wind, etc.) is stored separately
   - Both 1-hour and 6-hour forecasts are supported
   - Cache expiry is managed based on Met.no's API headers

2. **Cache Flow**
   - First, check if we have non-expired data in the database
   - If data is missing or expired, fetch from Met.no's API
   - New data is stored with expiry time from API response
   - Failed API requests use exponential backoff

3. **Data Cleanup**
   - Expired entries are automatically removed
   - Database is periodically optimized
   - Error logs help track cache performance

### Weather Station Cache (AEMET)

AEMET (Spanish weather service) requires mapping coordinates to weather stations. This mapping is cached because:
- Station locations rarely change
- It reduces unnecessary API calls
- It speeds up weather data lookups

The cache:
- Updates every 30 days
- Stores station details (name, location, etc.)
- Maps coordinates to nearest stations

### Simple Memory Cache

For services with simpler needs (IPMA and OpenWeather), we use in-memory caching:

1. **IPMA (Portugal)**
   - Caches weather data for 1 hour
   - Uses coordinate-based keys
   - Simple but effective for short-term use

2. **OpenWeather**
   - Different cache durations based on forecast type:
     * 3-hour forecasts: cached for 1 hour
     * Daily forecasts: cached for 3 hours
   - Automatic cleanup of expired data
   - Thread-safe implementation

### Cache Maintenance

The system automatically maintains its caches:

1. **Database Maintenance**
   - Removes expired weather data
   - Cleans up old station mappings
   - Optimizes database periodically

2. **Memory Cache Cleanup**
   - Removes expired entries on each request
   - Performs full reset daily
   - Manages memory usage automatically

This caching system ensures efficient operation while respecting API limits and keeping data fresh. 