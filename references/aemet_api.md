# AEMET OpenData API Reference

## Base URL
```
https://opendata.aemet.es/opendata/api
```

## Authentication
- API key required in headers: `api_key: YOUR_API_KEY`
- Get API key from [AEMET OpenData Portal](https://opendata.aemet.es/)

## Endpoints

### Get Municipality List
```
GET /maestro/municipios
```

Response format:
```json
{
    "descripcion": "exito",
    "estado": 200,
    "datos": "https://opendata.aemet.es/opendata/sh/[hash]",
    "metadatos": "https://opendata.aemet.es/opendata/sh/[hash]"
}
```

Municipality data format:
```json
[
    {
        "latitud": "40°32'54.450744\"",
        "id_old": "44004",
        "url": "ababuj-id44001",
        "latitud_dec": "40.54845854",
        "altitud": "1372",
        "capital": "Ababuj",
        "num_hab": "65",
        "zona_comarcal": "624401",
        "longitud_dec": "-0.80780117",
        "longitud": "0°48'28.084212\"W"
    },
    ...
]
```

### Get Hourly Forecast for Municipality
```
GET /prediccion/especifica/municipio/horaria/{municipio}
```

Parameters:
- `municipio`: 5-digit municipality code (padded with leading zeros)

Response format:
```json
{
    "descripcion": "exito",
    "estado": 200,
    "datos": "https://opendata.aemet.es/opendata/sh/[hash]",
    "metadatos": "https://opendata.aemet.es/opendata/sh/[hash]"
}
```

Forecast data format:
```json
[{
    "origen": {
        "productor": "Agencia Estatal de Meteorología - AEMET",
        "web": "https://www.aemet.es",
        "enlace": "https://www.aemet.es/es/eltiempo/prediccion/municipios/horas/[municipio]",
        "language": "es",
        "copyright": "© AEMET",
        "notaLegal": "https://www.aemet.es/es/nota_legal"
    },
    "elaborado": "2025-01-04T14:53:07",
    "nombre": "Municipality Name",
    "provincia": "Province",
    "prediccion": {
        "dia": [{
            "fecha": "2025-01-05",
            "temperatura": [
                {"periodo": "0", "value": 20},
                {"periodo": "1", "value": 19},
                ...
            ],
            "precipitacion": [
                {"periodo": "0", "value": 0},
                {"periodo": "1", "value": 0},
                ...
            ],
            "estadoCielo": [
                {"periodo": "0", "value": "11", "descripcion": "Despejado"},
                {"periodo": "1", "value": "11n", "descripcion": "Despejado"},
                ...
            ],
            "viento": [
                {
                    "periodo": "0",
                    "direccion": "N",
                    "velocidad": 10
                },
                ...
            ],
            "probPrecipitacion": [
                {"periodo": "0", "value": 0},
                {"periodo": "1", "value": 5},
                ...
            ]
        }]
    }
}]
```

## Weather Codes

### Sky Condition Codes
- 11/11n: Clear sky (day/night)
- 12/12n: Slightly cloudy (day/night)
- 13/13n: Intervals of clouds (day/night)
- 14: Cloudy
- 15: Very cloudy
- 16: Overcast
- 17: High clouds
- 23-26: Rain (various intensities)
- 33-36: Snow (various intensities)
- 43-46: Rain and snow mix
- 51-54: Thunderstorms
- 61-64: Snow with thunder
- 71-74: Rain with thunder

### Wind Directions
Cardinal directions: N, NNE, NE, ENE, E, ESE, SE, SSE, S, SSW, SW, WSW, W, WNW, NW, NNW

## Rate Limiting
- Minimum 1 second between requests
- 429 status code indicates rate limit exceeded
- Retry-After header indicates wait time

## Error Codes
- 200: Success
- 404: Not found
- 429: Rate limit exceeded
- Other 4xx/5xx: Various API errors 