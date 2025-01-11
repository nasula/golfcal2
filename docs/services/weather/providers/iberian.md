# AEMET OpenData API

AEMET (Agencia Estatal de Meteorología) provides weather data for Spain through their OpenData API.

## API Overview

- Base URL: `https://opendata.aemet.es/opendata/api`
- Authentication: API key required in headers (`api_key`)
- Rate Limiting: Yes, with retry-after headers
- Update Schedule: Four times daily (03:00, 09:00, 15:00, 21:00 UTC)

## Endpoints

### Municipality Forecast (Hourly)

```
GET /prediccion/especifica/municipio/horaria/{municipio}
```

Returns hourly forecast data for next 48 hours. Municipality code format: 5 digits (e.g., "38001" for Adeje).

Response format:
```json
[
  {
    "origen": {
      "productor": "Agencia Estatal de Meteorología - AEMET",
      "web": "https://www.aemet.es",
      "enlace": "https://www.aemet.es/es/eltiempo/prediccion/municipios/horas/...",
      "language": "es",
      "copyright": "© AEMET",
      "notaLegal": "https://www.aemet.es/es/nota_legal"
    },
    "elaborado": "2025-01-11T18:27:13",
    "nombre": "Rosario, El",
    "provincia": "Santa Cruz de Tenerife (Tenerife)",
    "prediccion": {
      "dia": [
        {
          "estadoCielo": [
            {
              "value": "11",  // or "11n" for night
              "periodo": "12",  // Hour (00-23)
              "descripcion": "Despejado"
            }
          ],
          "precipitacion": [
            {
              "value": "0",
              "periodo": "12"  // Hour (00-23)
            }
          ],
          "probPrecipitacion": [
            {
              "value": "0",
              "periodo": "1218"  // Hour range (e.g., "1218" = 12:00-18:00)
            }
          ],
          "temperatura": [
            {
              "value": "18",
              "periodo": "13"  // Hour (00-23)
            }
          ],
          "sensTermica": [
            {
              "value": "18",
              "periodo": "13"  // Hour (00-23)
            }
          ],
          "humedadRelativa": [
            {
              "value": "18",
              "periodo": "13"  // Hour (00-23)
            }
          ],
          "vientoAndRachaMax": [
            {
              "direccion": ["E"],
              "velocidad": ["6"],  // km/h
              "periodo": "13"  // Hour (00-23)
            }
          ],
          "fecha": "2025-01-11T00:00:00",
          "orto": "07:58",  // Sunrise
          "ocaso": "18:28"  // Sunset
        }
      ]
    }
  }
]
```

### Municipality Forecast (Daily)

```
GET /prediccion/especifica/municipio/diaria/{municipio}
```

Returns daily forecast data for up to 7 days.

Response format:
```json
[
  {
    "origen": { /* Same as hourly format */ },
    "elaborado": "2025-01-11T18:27:13",
    "nombre": "Adeje",
    "provincia": "Santa Cruz de Tenerife (Tenerife)",
    "prediccion": {
      "dia": [
        {
          "probPrecipitacion": [
            {
              "value": 0,
              "periodo": "00-24"  // Period formats: "00-24", "00-12", "12-24", "00-06", etc.
            }
          ],
          "estadoCielo": [
            {
              "value": "11",  // or "11n" for night
              "periodo": "12-24",
              "descripcion": "Despejado"
            }
          ],
          "viento": [
            {
              "direccion": "SO",  // Cardinal directions in Spanish (SO = SW, O = W, etc.)
              "velocidad": 10,  // km/h
              "periodo": "12-24"
            }
          ],
          "temperatura": {
            "maxima": 26,
            "minima": 15,
            "dato": [  // Temperature at specific hours
              {
                "value": 24,
                "hora": 12
              }
            ]
          },
          "sensTermica": {  // Same format as temperatura
            "maxima": 26,
            "minima": 15,
            "dato": [/* ... */]
          },
          "humedadRelativa": {  // Same format as temperatura
            "maxima": 40,
            "minima": 35,
            "dato": [/* ... */]
          },
          "uvMax": 3,  // UV index
          "fecha": "2025-01-11T00:00:00"
        }
      ]
    }
  }
]
```

## Weather Codes

### Sky Condition Codes

- 11/11n: Despejado (Clear sky)
- 12/12n: Poco nuboso (Few clouds)
- 13/13n: Intervalos nubosos (Partly cloudy)
- 14/14n: Nuboso (Cloudy)
- 81/81n: Niebla (Fog)
- 82/82n: Bruma (Mist)

Note: Suffix 'n' indicates night conditions.

### Wind Direction Codes

Spanish to English mapping:
- N: North
- NE: Northeast
- E: East
- SE: Southeast
- S: South
- SO: Southwest (Spanish: Sudoeste)
- O: West (Spanish: Oeste)
- NO: Northwest (Spanish: Noroeste)
- C: Calm

## Data Update Schedule

AEMET updates their forecasts four times daily at:
- 03:00 UTC
- 09:00 UTC
- 15:00 UTC
- 21:00 UTC

## Forecast Ranges

- Hourly data: Next 48 hours
- 6-hourly data: Up to 96 hours (4 days)
- Daily data: Up to 7 days

## Error Handling

Common response codes:
- 200: Success
- 401: Unauthorized (Invalid API key)
- 404: Not Found (Invalid municipality code)
- 429: Too Many Requests (Rate limit exceeded)

Rate limit response includes a `Retry-After` header indicating seconds to wait before retrying. 