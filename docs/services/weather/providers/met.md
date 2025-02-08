# Met.no Weather Service

## Overview

Met.no (Norwegian Meteorological Institute) weather service strategy implementation. This service provides high-quality weather forecasts for Nordic and Baltic regions.

## Coverage Area

1. Nordic Countries (55°N-71°N, 4°E-32°E):
   - Norway
   - Sweden
   - Finland
   - Denmark

2. Baltic Countries (53°N-59°N, 21°E-28°E):
   - Estonia
   - Latvia
   - Lithuania

## Block Size Pattern

Met.no provides forecasts with varying granularity based on forecast range:

1. Short Range (<48 hours):
   - 1-hour blocks
   - Highest accuracy
   - Complete weather data

2. Medium Range (48 hours - 7 days):
   - 6-hour blocks
   - Good accuracy
   - Most weather parameters available

3. Long Range (>7 days):
   - 12-hour blocks
   - Reduced accuracy
   - Basic weather parameters

## Implementation

```python
class MetWeatherStrategy(WeatherStrategy):
    """Weather strategy for Norwegian Meteorological Institute (MET)."""
    
    service_type: str = "met"
    
    def get_block_size(self, hours_ahead: float) -> int:
        """Get block size based on forecast range.
        
        Met.no provides:
        - 1-hour blocks for first 48 hours
        - 6-hour blocks for days 3-7
        - 12-hour blocks beyond day 7
        """
        if hours_ahead <= 48:
            return 1
        elif hours_ahead <= 168:  # 7 days
            return 6
        else:
            return 12

    def get_weather(self) -> Optional[WeatherResponse]:
        """Get weather data from Met.no."""
        try:
            # Fetch data with appropriate User-Agent
            response = self._fetch_forecasts(
                self.context.lat,
                self.context.lon,
                self.context.start_time,
                self.context.end_time
            )
            
            if response:
                return self._parse_response(response)
            return None
            
        except Exception as e:
            self.error(f"Error fetching Met.no forecast: {e}")
            return None

    def get_expiry_time(self) -> datetime:
        """Get expiry time for cached weather data.
        
        Met.no updates forecasts every hour at HH:00.
        We expire the cache 5 minutes before the next hour
        to ensure fresh data.
        """
        now = datetime.now(self.context.utc_tz)
        next_hour = (now + timedelta(hours=1)).replace(
            minute=0,
            second=0,
            microsecond=0
        )
        return next_hour - timedelta(minutes=5)
```

## API Usage

1. Required Headers:
   ```python
   headers = {
       'User-Agent': 'golfcal2/1.0.0 (contact@example.com)'
   }
   ```

2. Rate Limiting:
   - Maximum 20 requests per second
   - Courtesy rate limit of 1 request per second recommended

3. Response Format:
   ```json
   {
     "type": "Feature",
     "properties": {
       "timeseries": [
         {
           "time": "2024-02-08T12:00:00Z",
           "data": {
             "instant": {
               "details": {
                 "air_temperature": 5.2,
                 "wind_speed": 3.1,
                 "relative_humidity": 82.1
               }
             },
             "next_1_hours": {
               "summary": {
                 "symbol_code": "cloudy"
               },
               "details": {
                 "precipitation_amount": 0.2
               }
             }
           }
         }
       ]
     }
   }
   ```

## Error Handling

1. Service Errors:
   - Connection timeouts
   - Rate limiting
   - Invalid coordinates
   - Parse errors

2. Data Validation:
   - Temperature range checks
   - Wind speed validation
   - Precipitation probability limits

## Testing

Test cases cover:
1. Short-range forecasts (Oslo GC Tomorrow)
2. Medium-range forecasts (Oslo GC 4 Days)
3. Long-range forecasts (Oslo GC Next Week)
4. Edge cases:
   - Timezone handling
   - DST transitions
   - Arctic locations 