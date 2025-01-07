# Weather Data Models and Schemas

## Overview

The weather service system uses standardized data models and database schemas to ensure consistent data handling across different weather service providers. This document describes the core data structures and their implementations.

## Database Schemas

### Common Weather Table

All weather services share a common base schema for storing weather data:

```sql
CREATE TABLE weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT NOT NULL,
    time TEXT NOT NULL,
    data_type TEXT NOT NULL DEFAULT "next_1_hours",
    air_temperature REAL,
    precipitation_amount REAL,
    precipitation_max REAL,
    precipitation_min REAL,
    precipitation_rate REAL,
    precipitation_intensity REAL,
    wind_speed REAL,
    wind_from_direction REAL,
    wind_speed_gust REAL,
    probability_of_precipitation REAL,
    probability_of_thunder REAL,
    air_pressure REAL,
    cloud_area_fraction REAL,
    fog_area_fraction REAL,
    relative_humidity REAL,
    ultraviolet_index REAL,
    dew_point_temperature REAL,
    temperature_max REAL,
    temperature_min REAL,
    summary_code TEXT,
    expires TEXT,
    last_modified TEXT,
    UNIQUE(location, time, data_type)
)
```

### Service-Specific Schemas

1. **Iberian Schema (AEMET)**:
   ```python
   IBERIAN_SCHEMA = {
       'weather': WEATHER_COLUMNS,
       'stations': [
           'station_id',
           'name',
           'latitude',
           'longitude',
           'altitude',
           'region',
           'province',
           'municipality'
       ]
   }
   ```

2. **Portuguese Schema (IPMA)**:
   ```python
   PORTUGUESE_SCHEMA = {
       'weather': WEATHER_COLUMNS
   }
   ```

3. **Mediterranean Schema (OpenWeather)**:
   ```python
   MEDITERRANEAN_SCHEMA = {
       'weather': WEATHER_COLUMNS
   }
   ```

4. **MET Schema (Nordic)**:
   ```python
   MET_SCHEMA = {
       'weather': WEATHER_COLUMNS
   }
   ```

## Data Types

### Weather Data Fields

1. **Location and Time**:
   - `location`: Unique location identifier (e.g., "lat,lon")
   - `time`: Forecast timestamp in ISO format
   - `data_type`: Forecast block type (e.g., "next_1_hours")

2. **Temperature**:
   - `air_temperature`: Current temperature in Celsius
   - `temperature_max`: Maximum temperature in period
   - `temperature_min`: Minimum temperature in period
   - `dew_point_temperature`: Dew point in Celsius

3. **Precipitation**:
   - `precipitation_amount`: Amount in mm
   - `precipitation_max`: Maximum amount in period
   - `precipitation_min`: Minimum amount in period
   - `precipitation_rate`: Rate in mm/hour
   - `precipitation_intensity`: Qualitative intensity
   - `probability_of_precipitation`: Percentage chance

4. **Wind**:
   - `wind_speed`: Speed in meters/second
   - `wind_from_direction`: Direction in degrees
   - `wind_speed_gust`: Gust speed in meters/second

5. **Atmospheric Conditions**:
   - `air_pressure`: Pressure in hPa
   - `cloud_area_fraction`: Cloud cover percentage
   - `fog_area_fraction`: Fog density percentage
   - `relative_humidity`: Humidity percentage
   - `ultraviolet_index`: UV index value

6. **Metadata**:
   - `summary_code`: Weather condition code
   - `expires`: Cache expiration time
   - `last_modified`: Last update time

### Weather Codes

Standard weather codes used across all services:

```python
class WeatherCode(str, Enum):
    CLEARSKY_DAY = 'clearsky_day'
    CLEARSKY_NIGHT = 'clearsky_night'
    FAIR_DAY = 'fair_day'
    FAIR_NIGHT = 'fair_night'
    PARTLY_CLOUDY_DAY = 'partlycloudy_day'
    PARTLY_CLOUDY_NIGHT = 'partlycloudy_night'
    CLOUDY = 'cloudy'
    FOG = 'fog'
    LIGHTRAIN = 'lightrain'
    RAIN = 'rain'
    HEAVYRAIN = 'heavyrain'
    RAINSHOWERS_DAY = 'rainshowers_day'
    RAINSHOWERS_NIGHT = 'rainshowers_night'
    HEAVYRAINSHOWERS_DAY = 'heavyrainshowers_day'
    HEAVYRAINSHOWERS_NIGHT = 'heavyrainshowers_night'
    THUNDER = 'thunder'
    RAINANDTHUNDER = 'rainandthunder'
    HEAVYRAINANDTHUNDER = 'heavyrainandthunder'
    SLEET = 'sleet'
    LIGHTSLEET = 'lightsleet'
    HEAVYSLEET = 'heavysleet'
    SNOW = 'snow'
    LIGHTSNOW = 'lightsnow'
    HEAVYSNOW = 'heavysnow'
```

## Data Validation

### Required Fields

The following fields must be present in all weather data:
- `location`
- `time`
- `air_temperature`
- `precipitation_amount`
- `wind_speed`
- `summary_code`

### Optional Fields

Optional fields may be NULL/None:
- All precipitation probabilities
- Wind direction
- Atmospheric conditions
- UV index
- Temperature extremes

### Units

All weather services must convert their data to these standard units:
- Temperature: Celsius
- Precipitation: millimeters
- Wind speed: meters/second
- Pressure: hectopascals (hPa)
- Direction: degrees (0-360)
- Probabilities: percentage (0-100)

## Usage Guidelines

1. **Data Storage**:
   - Use appropriate data types for each field
   - Maintain unique constraints
   - Handle NULL values appropriately

2. **Data Conversion**:
   - Convert units before storage
   - Map weather codes to standard codes
   - Handle timezone conversions

3. **Data Validation**:
   - Check required fields
   - Validate value ranges
   - Verify data types

4. **Performance**:
   - Index frequently queried fields
   - Use appropriate field types
   - Consider partitioning for large datasets

## Testing

1. **Schema Tests**:
   - Test table creation
   - Test constraints
   - Test indexes

2. **Data Tests**:
   - Test data insertion
   - Test data retrieval
   - Test data validation

3. **Integration Tests**:
   - Test with actual weather data
   - Test data conversion
   - Test error handling 