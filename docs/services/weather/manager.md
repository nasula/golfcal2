# Weather Manager

## Overview

The `WeatherManager` is the central coordinator for weather services in GolfCal2. It manages multiple weather service providers and automatically selects the most appropriate service based on geographic location.

## Implementation

```python
class WeatherManager(WeatherService):
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: Dict[str, Any]):
        super().__init__(local_tz, utc_tz)
        self.config = config
        
        # Initialize weather services
        self.services = [
            MetWeatherService(local_tz, utc_tz, config),
            IberianWeatherService(local_tz, utc_tz, config),
            PortugueseWeatherService(local_tz, utc_tz, config),
            OpenWeatherService(local_tz, utc_tz, config, region="global")
        ]
```

## Service Selection

The manager selects the appropriate weather service based on coordinates:

```python
def select_weather_service(lat: float, lon: float) -> WeatherService:
    if 55 <= lat <= 72 and 3 <= lon <= 32:  # Nordic
        return MetNoWeatherService()
    elif -9.5 <= lon <= -6.2:  # Portugal
        return IberianWeatherService()  # IPMA
    elif -7 <= lon <= 5:  # Spain
        return IberianWeatherService()  # AEMET
    else:  # Global fallback
        return OpenWeatherService()
```

## Geographic Coverage

1. **Nordic Region (MET.no)**
   - Latitude: 55°N to 72°N
   - Longitude: 3°E to 32°E
   - Countries: Norway, Sweden, Finland, Denmark

2. **Iberian Peninsula**
   - **Portugal (IPMA)**
     - Longitude: -9.5°E to -6.2°E
     - Coverage: Mainland Portugal and islands
   - **Spain (AEMET)**
     - Longitude: -7°E to 5°E
     - Coverage: Mainland Spain and Canary Islands

3. **Global (OpenWeather)**
   - Coverage: All other regions
   - Used as fallback service

## Error Handling

The manager implements comprehensive error handling:

1. **Service Selection Errors**
   ```python
   if not selected_service:
       raise WeatherError(
           "No suitable weather service found",
           ErrorCode.SERVICE_UNAVAILABLE,
           {"lat": lat, "lon": lon}
       )
   ```

2. **Service Failures**
   ```python
   try:
       return service.get_weather(lat, lon, start_time, end_time)
   except WeatherError:
       # Try next service
       continue
   ```

3. **Fallback Strategy**
   - If primary service fails, try OpenWeather
   - If all services fail, raise WeatherError

## Integration Examples

### 1. Calendar Integration

```python
def get_weather_for_event(event: Event) -> WeatherResponse:
    return weather_manager.get_weather(
        lat=event.coordinates.lat,
        lon=event.coordinates.lon,
        start_time=event.start_time,
        end_time=event.end_time,
        club=event.club.name
    )
```

### 2. CLI Integration

```python
def list_weather(args: argparse.Namespace) -> None:
    weather_data = weather_manager.get_weather(
        lat=args.lat,
        lon=args.lon,
        start_time=args.start_time,
        end_time=args.end_time
    )
    print_weather_data(weather_data)
```

## Configuration

The manager requires configuration for API keys and service settings:

```yaml
api_keys:
  weather:
    openweather: "your-api-key"
    aemet: "your-api-key"
```

## Caching Strategy

The manager coordinates caching across services:

1. **Cache Key Format**
   ```python
   def _get_cache_key(self, lat: float, lon: float, club: str, base_time: datetime) -> str:
       return f"{club}_{lat:.4f}_{lon:.4f}_{base_time.strftime('%Y%m%d%H')}"
   ```

2. **Cache Duration**
   - Based on service update frequency
   - Aligned with service data refresh times
   - Configurable per service

## Best Practices

1. **Service Selection**
   - Use appropriate service for region
   - Consider service limitations
   - Handle edge cases gracefully

2. **Error Handling**
   - Implement service fallbacks
   - Log service failures
   - Provide meaningful error messages

3. **Performance**
   - Cache responses appropriately
   - Minimize API calls
   - Handle rate limits

4. **Data Consistency**
   - Normalize weather data
   - Validate responses
   - Handle timezone differences

## Monitoring

The manager includes monitoring capabilities:

1. **Logging**
   ```python
   self.debug(
       "Selected weather service",
       service=service.__class__.__name__,
       lat=lat,
       lon=lon
   )
   ```

2. **Error Tracking**
   - Service failures
   - API errors
   - Cache misses

3. **Performance Metrics**
   - Response times
   - Cache hit rates
   - API call counts 