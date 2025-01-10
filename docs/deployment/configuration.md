# Configuration Guide

## Overview

GolfCal2 uses YAML configuration files to manage application settings, user preferences, and service configurations. This guide explains the configuration structure and options.

## Configuration Files

### Application Configuration

The main application configuration file (`config.yaml`) contains global settings and service configurations.

```yaml
global:
  timezone: "Europe/Helsinki"
  log_level: "INFO"
  cache_dir: "~/.golfcal2/cache"
  dev_mode: false

database:
  path: "~/.golfcal2/data.db"
  backup_dir: "~/.golfcal2/backups"
  backup_count: 5

logging:
  level: "INFO"
  file: "~/.golfcal2/logs/golfcal2.log"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  max_size: 10485760  # 10MB
  backup_count: 5

weather:
  primary: "met"
  backup: "openweather"
  cache_duration: 3600
  update_interval: 900
  providers:
    met:
      user_agent: "GolfCal2/0.6.0"
      timeout: 10
      retries: 3
    openweather:
      api_key: "your-key"
      timeout: 10
      retries: 3
    aemet:
      api_key: "your-key"
      timeout: 15
      retries: 3
    ipma:
      enabled: true
      timeout: 10
      retries: 3

calendar:
  ics_dir: "~/.golfcal2/calendars"
  sync_interval: 900
  max_events: 1000
  default_duration: 240

external_events:
  enabled: true
  sources: ["ical", "caldav"]
  sync_interval: 900
  max_events: 500
```

### User Configuration

User-specific settings are stored in `~/.golfcal2/users/{username}.yaml`.

```yaml
user:
  name: "John Doe"
  email: "john@example.com"
  timezone: "Europe/Helsinki"
  language: "en"
  default_club: "Helsinki Golf"

display:
  date_format: "%Y-%m-%d"
  time_format: "%H:%M"
  temperature_unit: "C"
  wind_speed_unit: "m/s"
  show_weather: true
  show_coordinates: false

memberships:
  - club: "Helsinki Golf"
    type: "wisegolf"
    auth:
      username: "john.doe"
      password: "secure-password"
  
  - club: "Espoo Golf"
    type: "nexgolf"
    auth:
      member_id: "12345"
      pin: "1234"
  
  - club: "Vantaa Golf"
    type: "teetime"
    auth:
      api_key: "your-key"

notifications:
  enabled: true
  email: true
  desktop: true
  advance_notice: 24  # hours
  weather_updates: true
```

## Configuration Options

### Global Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| timezone | string | "UTC" | Default timezone for dates/times |
| log_level | string | "INFO" | Logging level (DEBUG, INFO, WARNING, ERROR) |
| cache_dir | string | "~/.golfcal2/cache" | Directory for cached data |
| dev_mode | boolean | false | Enable development mode |

### Database Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| path | string | "~/.golfcal2/data.db" | SQLite database path |
| backup_dir | string | "~/.golfcal2/backups" | Backup directory |
| backup_count | integer | 5 | Number of backups to keep |

### Weather Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| primary | string | "met" | Primary weather provider |
| backup | string | "openweather" | Backup weather provider |
| cache_duration | integer | 3600 | Cache duration in seconds |
| update_interval | integer | 900 | Update interval in seconds |

### Calendar Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| ics_dir | string | "~/.golfcal2/calendars" | ICS file directory |
| sync_interval | integer | 900 | Sync interval in seconds |
| max_events | integer | 1000 | Maximum events to store |
| default_duration | integer | 240 | Default event duration (minutes) |

## Environment Variables

Environment variables can override configuration values:

```bash
# Global settings
GOLFCAL_TIMEZONE="Europe/London"
GOLFCAL_LOG_LEVEL="DEBUG"
GOLFCAL_DEV_MODE="true"

# Weather API keys
GOLFCAL_OPENWEATHER_API_KEY="your-key"
GOLFCAL_AEMET_API_KEY="your-key"

# Database settings
GOLFCAL_DB_PATH="/custom/path/data.db"
```

## Configuration Validation

The application validates configuration files on startup:

1. **Schema Validation**
   - Required fields
   - Data types
   - Value ranges

2. **Path Validation**
   - Directory existence
   - Write permissions
   - File access

3. **Service Validation**
   - API key validation
   - Service availability
   - Authentication

## Example Configurations

### Development Configuration

```yaml
global:
  timezone: "UTC"
  log_level: "DEBUG"
  dev_mode: true

database:
  path: ":memory:"

weather:
  primary: "mock"
  cache_duration: 60
  providers:
    mock:
      enabled: true
```

### Production Configuration

```yaml
global:
  timezone: "Europe/Helsinki"
  log_level: "INFO"
  dev_mode: false

database:
  path: "/var/lib/golfcal2/data.db"
  backup_dir: "/var/backups/golfcal2"
  backup_count: 7

logging:
  level: "INFO"
  file: "/var/log/golfcal2/app.log"
  max_size: 52428800  # 50MB
  backup_count: 10

weather:
  primary: "met"
  backup: "openweather"
  cache_duration: 3600
  update_interval: 900
```

### Testing Configuration

```yaml
global:
  timezone: "UTC"
  log_level: "DEBUG"
  dev_mode: true

database:
  path: ":memory:"

weather:
  primary: "mock"
  providers:
    mock:
      enabled: true
      responses:
        default:
          temperature: 20.0
          precipitation: 0.0
          wind_speed: 5.0
```

## Best Practices

1. **Security**
   - Use environment variables for sensitive data
   - Set appropriate file permissions
   - Validate user input

2. **Performance**
   - Optimize cache settings
   - Configure appropriate intervals
   - Monitor resource usage

3. **Maintenance**
   - Regular backup configuration
   - Log rotation settings
   - Update schedules

4. **Development**
   - Use development configuration
   - Enable debug logging
   - Mock external services

## Related Documentation

- [Deployment Guide](deployment.md)
- [Monitoring Guide](monitoring.md)
- [Architecture Overview](../architecture/overview.md)
``` 