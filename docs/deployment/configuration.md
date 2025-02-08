# Configuration Guide

## Overview

GolfCal2 uses a modular YAML-based configuration system with separate files for different aspects of the application. The main configuration files are located in the `config` directory.

## Core Configuration Files

### Main Configuration (`config.yaml`)

The main configuration file contains global settings and basic service configurations:

```yaml
# Global configuration
timezone: "Europe/Helsinki"

# Directory paths
directories:
  ics: "ics"
  config: "config"
  logs: "logs"
  cache: "~/.golfcal2/cache"

# Weather service configuration
weather:
  cache_duration: 3600  # Cache duration in seconds
  providers:
    met:
      user_agent: "GolfCal2/1.0.0"  # Required for Met.no
    openmeteo:
      enabled: true  # No API key needed

# Default durations for golf rounds
default_durations:
  regular: { "hours": 4, "minutes": 30 }
  short: { "hours": 2, "minutes": 0 }

# Default reminder settings
default_reminder_minutes: -60

# Default application timezone
default_timezone: "Europe/Helsinki"
```

### Logging Configuration (`logging_config.yaml`)

Comprehensive logging configuration with service-specific settings:

```yaml
# Global logging settings
default_level: WARNING
dev_level: INFO
verbose_level: DEBUG

# Error aggregation settings
error_aggregation:
  enabled: true
  report_interval: 3600  # Report every hour
  error_threshold: 5     # Report after 5 occurrences
  time_threshold: 300    # Or after 5 minutes

# File logging settings
file:
  enabled: true
  path: logs/golfcal.log
  max_size_mb: 50
  backup_count: 7
  format: json
  include_timestamp: true

# Service-specific logging
services:
  weather_service:
    level: DEBUG
    file:
      path: logs/weather.log
      max_size_mb: 20
      components:
        met: DEBUG
        openmeteo: DEBUG
  calendar_service:
    level: DEBUG
    file:
      path: logs/calendar.log
      max_size_mb: 30
  auth:
    level: WARNING
    file:
      path: logs/auth.log
      max_size_mb: 10
```

### Club Configuration (`clubs.json`)

Defines golf club specific settings and integration details:

```json
{
  "Example Golf Club": {
    "name": "Example Golf Club",
    "type": "wisegolf",
    "url": "https://example.com/golf",
    "timezone": "Europe/Helsinki",
    "variant": "Main Course",
    "address": "123 Golf Street, Example City",
    "coordinates": {
      "lat": 60.1699,
      "lon": 24.9384
    }
  }
}
```

### User Configuration (`users.json`)

Contains user-specific settings and club memberships:

```json
{
  "John Doe": {
    "timezone": "Europe/Helsinki",
    "duration": {
      "hours": 4,
      "minutes": 0
    },
    "memberships": [
      {
        "club": "Example Golf Club",
        "auth_details": {
          "type": "wisegolf",
          "auth_type": "token",
          "token": "your-token-here"
        }
      }
    ]
  }
}
```

## Environment Variables

Key settings can be overridden using environment variables:

```bash
# Global settings
GOLFCAL_TIMEZONE="Europe/Helsinki"
GOLFCAL_LOG_LEVEL="INFO"

# Directory paths
GOLFCAL_CONFIG_DIR="/path/to/config"
GOLFCAL_LOGS_DIR="/path/to/logs"
GOLFCAL_ICS_DIR="/path/to/ics"
GOLFCAL_CACHE_DIR="/path/to/cache"
```

## Sensitive Data Handling

The application includes comprehensive sensitive data masking in logs:

```yaml
sensitive_data:
  enabled: true
  global_fields:
    - password
    - token
    - api_key
    - secret
    - auth
    - cookie
    - session_id
    - wisegolf_token
    - nexgolf_token
  mask_pattern: "***MASKED***"
```

## Development Configuration

For development environments, use the example configuration files:
- `config.yaml.example`
- `logging_config.yaml.example`
- `clubs.json.example`
- `users.json.example`

Copy these files without the `.example` extension and modify them according to your needs.

## Configuration Validation

The application validates configurations through:
1. Schema validation in `config/validation.py`
2. Environment variable processing in `config/env.py`
3. Configuration utilities in `config/utils.py`

## Service-Specific Settings

### Weather Service
- Strategy pattern for weather providers
- Geographic-based provider selection:
  - Met.no: Nordic/Baltic regions (55°N-71°N, 4°E-32°E)
  - OpenMeteo: Global coverage
- Block size patterns:
  - Met.no: 1h/6h/12h blocks
  - OpenMeteo: 1h/3h/6h blocks
- Automatic fallback handling
- Configurable caching

### Calendar Integration
- ICS file generation and management
- External calendar synchronization
- Configurable update intervals

### Logging System
- Service-specific log files
- Strategy-specific logging levels
- Error aggregation
- Sensitive data masking
- Correlation ID tracking

## Production Deployment

For production environments:
1. Use environment variables for sensitive data
2. Configure appropriate log levels and rotation
3. Set up proper file permissions for config files
4. Enable error aggregation
5. Configure backup settings for logs and data
6. Set up appropriate cache directories
``` 