# Weather Service Manager

## Overview

The Weather Service Manager implements a strategy pattern for weather services, with improved caching and error handling. It coordinates between Met.no and OpenMeteo services based on geographical location.

## Service Selection

The manager uses the following logic to select a weather service:

1. For Nordic and Baltic regions:
   - Uses Met.no service (55°N-71°N, 4°E-32°E for Nordic)
   - Also covers Baltic countries (53°N-59°N, 21°E-28°E)
   - Falls back to OpenMeteo if Met.no fails

2. For all other locations:
   - Uses OpenMeteo service as primary provider
   - Falls back to Met.no if OpenMeteo fails

## Implementation

```python
class WeatherService:
    """Unified weather service."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize service."""
        self.config = config
        self.local_tz = ZoneInfo(config.get('timezone', 'UTC'))
        self.utc_tz = ZoneInfo('UTC')
        
        # Initialize caches
        self.location_cache = WeatherLocationCache(config)
        self.response_cache = WeatherResponseCache(cache_path)
        
        # Register strategies
        self._strategies = {}
        self.register_strategy('met', MetWeatherStrategy)
        self.register_strategy('openmeteo', OpenMeteoStrategy)
    
    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        service_type: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Get weather data using appropriate strategy."""
        try:
            # Create context
            context = WeatherContext(
                lat=lat,
                lon=lon,
                start_time=start_time,
                end_time=end_time,
                local_tz=self.local_tz,
                utc_tz=self.utc_tz,
                config=self.config
            )
            
            # Try cache first
            cached_response = self.response_cache.get_response(...)
            if cached_response:
                return WeatherResponse.from_dict(cached_response)
            
            # Select and use strategy
            service_type = service_type or self._select_service_for_location(lat, lon)
            strategy = self._get_strategy(service_type, context)
            response = strategy.get_weather()
            
            # Handle fallbacks
            if not response and service_type == 'openmeteo':
                met_strategy = self._get_strategy('met', context)
                response = met_strategy.get_weather()
            
            # Cache successful responses
            if response:
                self.response_cache.store_response(...)
            
            return response
            
        except Exception as e:
            aggregate_error(str(e), "weather_service", str(e.__traceback__))
            return None
```

## Block Size Handling

Each weather service implements its own block size pattern:

1. Met.no:
   - 1-hour blocks for first 48 hours
   - 6-hour blocks for days 3-7
   - 12-hour blocks beyond day 7

2. OpenMeteo:
   - 1-hour blocks for first 48 hours
   - 3-hour blocks for days 3-7
   - 6-hour blocks beyond day 7

## Test Coverage

The service includes test events for comprehensive coverage:

1. Time ranges:
   - Short range (<48h)
   - Medium range (48h-7d)
   - Long range (>7d)

2. Geographical coverage:
   - Nordic region (Met.no primary)
   - Mediterranean (OpenMeteo primary)
   - Different timezones (e.g., Canary Islands)

## Integration Example

```python
# Initialize service
weather_service = WeatherService(config={
    'timezone': 'Europe/Oslo',
    'dev_mode': False,
    'directories': {
        'cache': '~/.cache/golfcal2'
    }
})

# Get weather for Oslo Golf Club
try:
    weather = weather_service.get_weather(
        lat=59.8940,
        lon=10.8282,
        start_time=datetime.now(ZoneInfo('Europe/Oslo')),
        end_time=datetime.now(ZoneInfo('Europe/Oslo')) + timedelta(hours=24)
    )
    if weather:
        print(f"Temperature: {weather.data[0].temperature}°C")
except Exception as e:
    print(f"Weather data unavailable: {e}") 