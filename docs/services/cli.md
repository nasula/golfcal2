# Command Line Interface (CLI)

## Overview

GolfCal2 provides a command-line interface for managing golf reservations, weather data, and calendar integration. The CLI supports various commands for processing calendars, listing information, and checking system status.

## Global Options

| Option | Description |
|--------|-------------|
| `-u, --user USERNAME` | Process specific user only (default: all configured users) |
| `--dev` | Run in development mode with additional debug output |
| `-v, --verbose` | Enable verbose logging output |
| `--log-file PATH` | Path to write log output (default: stdout) |

## Commands

### Process Calendar

Process golf calendar by fetching reservations and updating calendar files.

```bash
golfcal2 process [options]
```

Options:
- `--dry-run`: Show what would be done without making changes
- `--force`: Force processing even if no changes detected

Examples:
```bash
# Process all users
golfcal2 process

# Process specific user
golfcal2 -u USERNAME process

# Dry run to see what would be done
golfcal2 process --dry-run

# Force processing even if no changes detected
golfcal2 process --force
```

### List Information

List various types of information about courses, reservations, and weather cache.

```bash
golfcal2 list <type> [options]
```

#### List Courses

```bash
golfcal2 list courses [options]
```

Options:
- `--all`: List all configured courses (default: only current user's courses)

Examples:
```bash
# List all golf courses for current user
golfcal2 list courses

# List all configured courses
golfcal2 list courses --all
```

#### List Reservations

```bash
golfcal2 list reservations [options]
```

Options:
- `--active`: Show only currently active reservations
- `--upcoming`: Show only upcoming reservations
- `--format`: Output format ('text' or 'json', default: text)
- `--days N`: Number of days to look ahead/behind (default: 1)

Examples:
```bash
# List all reservations
golfcal2 list reservations

# List only active reservations
golfcal2 list reservations --active

# List upcoming reservations for next 7 days
golfcal2 list reservations --upcoming --days 7

# List reservations in JSON format
golfcal2 list reservations --format json
```

Example output (text format):
```
Reservations for John Doe:
============================================================
2024-01-20 10:00 - 14:30: Helsinki Golf Club
Location: Golfpolku 1, Helsinki
Players: John Doe (HCP: 15.4), Jane Smith (HCP: 22.1)
Weather: 18°C, Wind: 3 m/s, Precipitation: 0.1mm (10%)
------------------------------------------------------------
```

#### List Weather Cache

```bash
golfcal2 list weather-cache [options]
```

Options:
- `--service`: Filter by service ('met', 'portuguese', 'iberian')
- `--location`: Filter by coordinates (format: lat,lon)
- `--date`: Filter by date (format: YYYY-MM-DD)
- `--format`: Output format ('text' or 'json', default: text)
- `--clear`: Clear the cache (optionally for specific service)

Examples:
```bash
# List weather cache contents
golfcal2 list weather-cache

# List weather cache for specific service
golfcal2 list weather-cache --service met

# List weather cache for specific date
golfcal2 list weather-cache --date 2025-01-11

# Clear weather cache (use with caution)
golfcal2 list weather-cache --clear

# Clear specific service's cache
golfcal2 list weather-cache --service met --clear
```

Example output (text format):
```
Weather Cache Contents
============================================================
Service: met
Location: 60.1699,24.9384
Start Time: 2024-01-20 10:00:00
End Time: 2024-01-20 14:30:00
Expires: 2024-01-20 16:00:00
------------------------------------------------------------
```

### Get Weather Data

Get weather forecast for a specific location.

```bash
golfcal2 get weather [options]
```

Required options:
- `--lat`: Latitude of the location (e.g., 60.1699 for Helsinki)
- `--lon`: Longitude of the location (e.g., 24.9384 for Helsinki)

Optional options:
- `--service`: Weather service to use ('met', 'portuguese', 'iberian')
- `--format`: Output format ('text' or 'json', default: text)

Example output (text format):
```
Weather Forecast
---------------
Time: 2024-01-20 10:00:00
Temperature: 18°C
Precipitation: 0.1 mm
Wind: 3 m/s from 180°
Precipitation probability: 10%
Summary: partly_cloudy

Expires: 2024-01-20 16:00:00
```

### Check System

Check application configuration and connectivity.

```bash
golfcal2 check [options]
```

Options:
- `--full`: Perform comprehensive check including API connectivity tests and cache validation

Examples:
```bash
# Basic configuration check
golfcal2 check

# Full check including API connectivity
golfcal2 check --full
```

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error (details in log output) |

## Environment Variables

The CLI behavior can be modified using environment variables:

```bash
# Global settings
GOLFCAL_TIMEZONE="Europe/Helsinki"
GOLFCAL_LOG_LEVEL="INFO"

# Weather API keys
GOLFCAL_AEMET_API_KEY="your-key"
GOLFCAL_OPENWEATHER_API_KEY="your-key"

# Directory paths
GOLFCAL_CONFIG_DIR="/path/to/config"
GOLFCAL_LOGS_DIR="/path/to/logs"
GOLFCAL_ICS_DIR="/path/to/ics"
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   ```
   ERROR - Failed to authenticate: Invalid token
   ```
   - Check auth token/cookie in user config
   - Verify club API is accessible
   - Enable verbose logging to see API responses

2. **Missing Weather Data**
   ```
   WARNING - Could not fetch weather data for club
   ```
   - Check club coordinates in config
   - Verify weather service API status
   - Check network connectivity

3. **Calendar File Issues**
   ```
   ERROR - Failed to write calendar file
   ```
   - Check directory permissions
   - Verify no file locks
   - Ensure sufficient disk space

### Debug Steps

1. Enable verbose logging:
```bash
golfcal2 -v --log-file debug.log process
```

2. Check configuration:
```bash
golfcal2 check
```

3. Test specific components:
```bash
# Test reservation fetching
golfcal2 -u USERNAME list --active

# Test weather service
golfcal2 -v process --dry-run
```

### Log File Analysis

The log files contain structured information:
```
2024-01-23 10:00:00 - golfcal.services.reservation_service - INFO - Processing user John
2024-01-23 10:00:01 - golfcal.api.wise_golf - DEBUG - API response: {...}
2024-01-23 10:00:02 - golfcal.services.weather_service - INFO - Fetching weather for SHG
```

## Development Mode

Running with `--dev` enables:
- Additional debug output
- More verbose error messages
- Test data usage where applicable
- Performance metrics
- Detailed API interaction logs 