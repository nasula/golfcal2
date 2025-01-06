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
"""

from typing import Dict, List

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

# OpenWeather schema
MEDITERRANEAN_SCHEMA = {
    'weather': WEATHER_COLUMNS
}

# Met schema
MET_SCHEMA = {
    'weather': WEATHER_COLUMNS
}
