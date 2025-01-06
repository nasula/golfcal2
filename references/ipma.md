# IPMA API Documentation

Source: [IPMA API Homepage](https://api.ipma.pt)

## Overview

The IPMA (Instituto Português do Mar e da Atmosfera) API provides weather forecast data for Portuguese cities and islands. The data is updated twice daily, at 10:00 UTC and 20:00 UTC.

## Authentication

No API key is required. However, IPMA requests that users:
1. Send an email to webmaster@ipma.pt informing about the usage
2. Cite IPMA as the data source
3. Read and comply with the terms of use

## Endpoints

### Location List
```
GET https://api.ipma.pt/open-data/distrits-islands.json
```

Returns a list of available locations with their coordinates and IDs.

Example response:
```json
[
  {
    "local": "Aveiro",
    "globalIdLocal": 1010500,
    "latitude": "40.6",
    "longitude": "-8.7"
  }
]
```

### Daily Forecast
```
GET https://api.ipma.pt/open-data/forecast/meteorology/cities/daily/{globalIdLocal}.json
```

Returns daily forecasts for a specific location.

Example response:
```json
{
  "owner": "IPMA",
  "country": "PT",
  "data": [
    {
      "precipitaProb": "0.0",
      "tMin": "7.6",
      "tMax": "13.3",
      "predWindDir": "N",
      "idWeatherType": 2,
      "classWindSpeed": 2,
      "longitude": "-9.1",
      "forecastDate": "2018-01-26",
      "latitude": "38.8"
    }
  ],
  "globalIdLocal": 1110600,
  "dataUpdate": "2018-01-26T09:02:03"
}
```

### Weather Types

| ID | Description (PT) | Description (EN) |
|----|-----------------|-----------------|
| 0 | Sem informação | No information |
| 1 | Céu limpo | Clear sky |
| 2 | Céu pouco nublado | Partly cloudy |
| 3 | Céu parcialmente nublado | Cloudy |
| 4 | Céu muito nublado | Overcast |
| 5 | Aguaceiros fracos | Light rain showers |
| 6 | Aguaceiros e trovoada | Rain showers and thunder |
| 7 | Chuva forte e trovoada | Heavy rain and thunder |
| 8 | Aguaceiros de neve | Snow showers |
| 9 | Trovoada | Thunder |
| 10 | Chuva forte | Heavy rain |
| 11 | Neve forte | Heavy snow |
| 12 | Chuva fraca | Light rain |
| 13 | Neve fraca | Light snow |
| 14 | Chuva e neve | Rain and snow |
| 15 | Nevoeiro | Fog |
| 16 | Nevoeiro intenso | Heavy fog |
| 17 | Geada | Frost |
| 18 | Nuvens altas | High clouds |

### Wind Speed Classes

| Class | Description (PT) | Description (EN) | Speed Range |
|-------|-----------------|-----------------|-------------|
| 1 | Fraco | Weak | < 15 km/h |
| 2 | Moderado | Moderate | 15-35 km/h |
| 3 | Forte | Strong | 35-55 km/h |
| 4 | Muito forte | Very strong | > 55 km/h |

### Wind Directions

Standard cardinal and intercardinal directions: N, NNE, NE, ENE, E, ESE, SE, SSE, S, SSW, SW, WSW, W, WNW, NW, NNW

## Terms of Use

1. The API is provided by IPMA for public use
2. Users should inform IPMA about their usage via email
3. IPMA must be cited as the data source
4. The service may be interrupted or modified without prior notice
5. Data is updated twice daily (10:00 UTC and 20:00 UTC)
6. Times are provided in UTC

## Rate Limiting

While no specific rate limits are documented, it's recommended to:
1. Cache responses when possible
2. Limit requests to a reasonable frequency (e.g., 1 request per second)
3. Only fetch data when needed 