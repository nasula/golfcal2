# Weather Services

This document describes the weather service implementations in GolfCal.

## WeatherService Interface

The `WeatherService` class serves as the base interface for implementing weather data providers. It provides a standardized way to fetch and process weather data from different sources while maintaining consistent data formats and error handling.

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

## Service Overview

GolfCal uses multiple weather services to provide accurate forecasts for different regions:

### 1. Met.no (Nordic Weather Service)
**Coverage**: Nordic countries
Features:
- High-resolution forecasts for Nordic region
- No API key required
- Free for non-commercial use

### 2. AEMET (Spanish Weather Service)
**Coverage**: Spain
Features:
- Official Spanish weather service
- Requires API key
- Municipality-based forecasts

### 3. IPMA (Portuguese Weather Service)
**Coverage**: Portugal
Features:
- Official Portuguese weather service
- No API key required
- Daily forecasts

### 4. OpenWeather (Mediterranean Service)
**Coverage**: Mediterranean region
Features:
- Wide coverage
- 3-hour interval forecasts
- 5-day forecast range

## Weather Codes

### Standard Weather Codes

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

## Service Selection

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

## Cache Management

The application uses different caching strategies:

### Met.no Weather Data Cache
- SQLite database storage
- Location and time-based caching
- Automatic expiry management

### Weather Station Cache (AEMET)
- 30-day station mapping cache
- Coordinate to station mapping
- Periodic updates

### Simple Memory Cache
- Used for IPMA and OpenWeather
- Short-term caching (1-3 hours)
- Automatic cleanup 