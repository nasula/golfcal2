# GolfCal Services

This directory contains the core services used by GolfCal.

## Weather Services

GolfCal uses multiple weather services to provide accurate forecasts for different regions:

### Service Selection

The weather service is selected based on the golf course location:

1. **Met.no** (Nordic Weather Service)
   - Coverage: Nordic countries
   - Resolution: 1-hour blocks for next 48 hours, 6-hour blocks beyond
   - Example: Oslo Golf Club

2. **AEMET** (Spanish Weather Service)
   - Coverage: Spain (mainland and Canary Islands)
   - Resolution: Hourly for next 2 days, daily beyond
   - Example: PGA Catalunya, Golf Costa Adeje
   - Requires API key from [AEMET OpenData](https://opendata.aemet.es/centrodedescargas/inicio)

3. **IPMA** (Portuguese Weather Service)
   - Coverage: Portugal
   - Resolution: Daily forecasts
   - Example: Praia D'El Rey Golf Club

4. **OpenWeather** (Mediterranean Service)
   - Coverage: Mediterranean region
   - Resolution: 3-hour blocks
   - Example: Lykia Links Golf Club
   - Default API key provided, can be overridden

### Configuration

Weather service API keys are configured in `golfcal/config/api_keys.yaml`:

```yaml
weather:
  # Spanish Meteorological Agency (AEMET)
  # Get your key from: https://opendata.aemet.es/centrodedescargas/inicio
  aemet: ""  # Add your AEMET API key here
  
  # OpenWeather API (Mediterranean region)
  # Default key is provided, but you can override it here
  openweather: "default-key"  # Optional override
```

API keys can also be set via environment variables:
- `AEMET_API_KEY` for AEMET
- `OPENWEATHER_API_KEY` for OpenWeather

### Weather Data Format

All weather services return data in a standardized format:

```python
{
    'forecasts': [
        {
            'time': datetime,
            'data_type': 'next_1_hours',  # or 'next_3_hours', 'next_6_hours'
            'symbol_code': str,  # e.g., 'clearsky_day', 'cloudy'
            'air_temperature': float,  # Celsius
            'precipitation_amount': float,  # mm
            'wind_speed': float,  # m/s
            'wind_from_direction': float,  # degrees
            'probability_of_precipitation': float,  # 0-100
            'probability_of_thunder': float  # 0-100
        },
        # ... more forecasts
    ],
    'symbol_code': str,  # Summary symbol for the event
    'air_temperature': float,  # Average temperature
    'precipitation_amount': float,  # Total precipitation
    'wind_speed': float,  # Average wind speed
    'wind_from_direction': float,  # Predominant wind direction
    'probability_of_precipitation': float,
    'probability_of_thunder': float
}
```

### Testing

Test events for each weather service are defined in `golfcal/config/test_events.yaml`. These include:
- Events at different times (morning/afternoon)
- Different forecast ranges (tomorrow, 3 days, 7 days)
- Various locations to test each service

Run tests with:
```bash
python -m golfcal --dev -v process
```

### Service Implementation

Each weather service implements the `WeatherService` base class:
```python
class WeatherService:
    def get_weather(
        self,
        lat: float,
        lon: float,
        date: datetime,
        duration_minutes: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get weather data for given coordinates and date."""
        pass
```

Weather services handle:
- API rate limiting
- Error handling and retries
- Data parsing and normalization
- Timezone conversion
- Cache management (where applicable) 