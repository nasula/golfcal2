# Configuration Guide

This document describes the configuration files used in GolfCal.

## Configuration Files

### `api_keys.yaml`

API keys for various weather services:
```yaml
weather:
  # Spanish Meteorological Agency (AEMET)
  aemet: "your-key-here"
  
  # OpenWeather API (Mediterranean region)
  openweather: "optional-override"
```

### `test_events.yaml`

Test events for different weather services and regions:
```yaml
# Example test event
- name: "PGA Catalunya Tomorrow"
  location: "PGA Catalunya"
  coordinates:
    lat: 41.8789
    lon: 2.7649
  users:
    - "Jarkko"
  start_time: "tomorrow 09:30"
  end_time: "tomorrow 14:30"
  timezone: "Europe/Madrid"
  address: "Carretera N-II km 701, 17455 Caldes de Malavella, Girona, Spain"
```

Event configuration:
- `name`: Event name (used in calendar)
- `location`: Golf course name
- `coordinates`: Latitude and longitude
- `users`: List of users for the event
- `start_time`/`end_time`: Relative or absolute times
- `timezone`: IANA timezone name
- `address`: Full address for the location

Relative time formats:
- `tomorrow HH:MM`: Next day at specific time
- `N days HH:MM`: N days from now at specific time
- `YYYY-MM-DD HH:MM`: Specific date and time

### `external_events.yaml`

Configuration for external calendar events:
```yaml
# Example external event
- name: "Golf Costa Adeje"
  pattern: "Golf Costa Adeje"
  coordinates:
    lat: 28.0876
    lon: -16.7408
  timezone: "Atlantic/Canary"
  address: "Calle Alcojora, s/n, 38670 Adeje, Santa Cruz de Tenerife, Spain"
```

External event configuration:
- `name`: Display name for the event
- `pattern`: Pattern to match in calendar event title
- `coordinates`: Location for weather lookup
- `timezone`: Local timezone for the location
- `address`: Full address (used in calendar) 