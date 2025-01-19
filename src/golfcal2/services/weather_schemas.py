"""Weather service database schemas.

Weather services:
- IPMA (Instituto Português do Mar e da Atmosfera)
  - API: https://api.ipma.pt/open-data/
  - Daily forecasts for Portuguese cities and islands
  - Updates twice daily at 10:00 and 20:00 UTC
  - No API key required, but should inform webmaster@ipma.pt about usage
  - Must cite IPMA as data source

- AEMET (Agencia Estatal de Meteorología)
  - API: https://opendata.aemet.es/
  - Daily forecasts for Spanish cities and islands
  - Updates multiple times per day
  - Requires API key from https://opendata.aemet.es/centrodedescargas/altaUsuario
  - Must cite AEMET as data source

- OpenWeather
  - API: https://api.openweathermap.org/
  - Global coverage with 5-day forecasts
  - Updates every 3 hours
  - Requires API key from https://openweathermap.org/
  - Free tier: 60 calls/minute
"""

from typing import Dict, List

# Common weather table columns
WEATHER_COLUMNS = [
    'id INTEGER PRIMARY KEY AUTOINCREMENT',
    'location TEXT NOT NULL',
    'time TEXT NOT NULL',
    'data_type TEXT NOT NULL DEFAULT "next_1_hours"',
    'air_temperature REAL',
    'precipitation_amount REAL',
    'precipitation_max REAL',
    'precipitation_min REAL',
    'precipitation_rate REAL',
    'precipitation_intensity REAL',
    'wind_speed REAL',
    'wind_from_direction REAL',
    'wind_speed_gust REAL',
    'probability_of_precipitation REAL',
    'probability_of_thunder REAL',
    'air_pressure REAL',
    'cloud_area_fraction REAL',
    'fog_area_fraction REAL',
    'relative_humidity REAL',
    'ultraviolet_index REAL',
    'dew_point_temperature REAL',
    'temperature_max REAL',
    'temperature_min REAL',
    'summary_code TEXT',
    'block_duration_hours REAL',
    'expires TEXT',
    'last_modified TEXT',
    'UNIQUE(location, time, data_type)'
]

IBERIAN_SCHEMA: Dict[str, List[str]] = {
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

# Portuguese schema
PORTUGUESE_SCHEMA = {
    'weather': WEATHER_COLUMNS
}

# OpenWeather schema (used for both global and Mediterranean regions)
OPEN_WEATHER_SCHEMA = {
    'weather': WEATHER_COLUMNS
}

# Met schema
MET_SCHEMA = {
    'weather': WEATHER_COLUMNS
}
