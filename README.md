# Golf Calendar

A Python application for managing golf reservations and creating calendar files. This is the refactored version with improved architecture and features.

## Features

- Fetch golf reservations from multiple booking systems:
  - WiseGolf: Full API support with token or cookie auth
  - NexGolf: Cookie-based authentication
  - TeeTime: Query parameter authentication
- Create iCalendar (.ics) files with:
  - Tee time reservations
  - Player information and handicaps
  - Weather forecasts (temperature, precipitation, wind)
  - Location and course details
- Support for multiple users and golf clubs
- Automatic calendar updates
- Weather information integration
- Comprehensive logging with rotation and compression
- Development features:
  - Dry run mode
  - JSON output format
  - Multiple check types
  - Debug logging

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd golfcal
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration Examples

### Club Configuration (`config/clubs.json`)
```json
{
  "SHG": {
    "type": "wisegolf",
    "url": "https://ajax.shg.fi/?reservations=getusergolfreservations",
    "public_url": "https://api.shg.fi/api/1.0/reservations/?",
    "cookie_name": "token",
    "auth_type": "token_appauth",
    "crm": "wisegolf",
    "address": "Rinnekodintie 23, 02980 ESPOO, Finland",
    "clubAbbreviation": "SHG",
    "product_Ids": {
      "53": {"description": "18 holes", "group": "A"},
      "140": {"description": "9 holes", "group": "A"}
    }
  }
}
```

### User Configuration (`config/users.json`)
```json
{
  "John": {
    "email": "john@example.com",
    "memberships": [
      {
        "club": "SHG",
        "duration": {
          "hours": 2,
          "minutes": 0
        },
        "auth_details": {
          "token": "your-auth-token"
        }
      }
    ]
  }
}
```

## Usage Examples

### Process Golf Calendar
```bash
# Process all users
golfcal2 process

# Process specific user
golfcal2 -U USERNAME process

# Dry run to see what would be done
golfcal2 process --dry-run

# Force processing even if no changes detected
golfcal2 process --force
```

### List Information
```bash
# List all golf courses for current user
golfcal2 list courses

# List all configured courses
golfcal2 list courses --all

# List reservations
golfcal2 list reservations

# List only active reservations
golfcal2 list reservations --active

# List upcoming reservations for next 7 days
golfcal2 list reservations --upcoming --days 7

# List reservations in JSON format
golfcal2 list reservations --format json

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

### Check Configuration
```bash
# Basic configuration check
golfcal2 check

# Full check including API connectivity
golfcal2 check --full
```

### Global Options
- `-U USERNAME, --user USERNAME`: Process specific user only (default: process all configured users)
- `--dev`: Run in development mode with additional debug output and test data
- `-v, --verbose`: Enable verbose logging output
- `--log-file PATH`: Path to write log output (default: logs to stdout)

### Commands
- `process`: Process golf calendar by fetching reservations and updating calendar files
  - `--dry-run`: Show what would be done without making changes
  - `--force`: Force processing even if no changes detected

- `list`: List various types of information
  - `courses`: List available golf courses
    - `--all`: List all configured courses (default: only current user's courses)
  
  - `reservations`: List golf reservations
    - `--active`: Show only currently active reservations
    - `--upcoming`: Show only upcoming reservations
    - `--format`: Output format ('text' or 'json', default: text)
    - `--days`: Number of days to look ahead/behind (default: 1)
  
  - `weather-cache`: List or manage weather cache contents
    - `--service`: Filter by service ('met', 'portuguese', 'iberian')
    - `--location`: Filter by coordinates (format: lat,lon)
    - `--date`: Filter by date (format: YYYY-MM-DD)
    - `--format`: Output format ('text' or 'json', default: text)
    - `--clear`: Clear the cache (optionally for specific service)

- `check`: Check application configuration and connectivity
  - `--full`: Perform comprehensive check including API tests

## Troubleshooting Guide

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
python -m golfcal -v --log-file debug.log process
```

2. Check configuration:
```bash
python -m golfcal check
```

3. Test specific components:
```bash
# Test reservation fetching
python -m golfcal -u USERNAME list --active

# Test weather service
python -m golfcal -v process --dry-run
```

### Log File Analysis

The log files contain structured information:
```
2024-01-23 10:00:00 - golfcal.services.reservation_service - INFO - Processing user John
2024-01-23 10:00:01 - golfcal.api.wise_golf - DEBUG - API response: {...}
2024-01-23 10:00:02 - golfcal.services.weather_service - INFO - Fetching weather for SHG
```

Use log rotation to manage file size:
```bash
python -m golfcal --log-file golfcal.log process
```

## Development

The codebase follows a modular architecture:

```
golfcal/
├── api/            # API clients for different golf systems
├── models/         # Data models and business logic
├── services/       # Core services (calendar, reservations, weather)
├── utils/          # Utility functions and helpers
└── config/         # Configuration management
```

### Documentation

### API Documentation
- [API Overview](docs/api/README.md) - Complete API documentation
  - [CRM APIs](docs/api/crm_apis.md) - Golf club booking systems
  - [Weather APIs](docs/api/weather/README.md) - Weather service providers
  - [Service APIs](docs/services/README.md) - Internal service APIs

### Development Documentation
- [Service Documentation](docs/services/README.md) - Core service implementations
- [Configuration Guide](docs/deployment/configuration.md) - Configuration file formats
- [Development Setup](docs/development/setup.md) - Setting up development environment

## Development

The codebase follows a modular architecture:

```
golfcal/
├── api/            # API clients for different golf systems
├── models/         # Data models and business logic
├── services/       # Core services (calendar, reservations, weather)
├── utils/          # Utility functions and helpers
└── config/         # Configuration management
```

### Documentation

- [API Documentation](docs/api/crm_apis.md) - Details on CRM system integrations
- [Service Documentation](docs/services/README.md) - Core service implementations
- [Configuration Guide](docs/deployment/configuration.md) - Configuration file formats
- [Development Setup](docs/development/setup.md) - Setting up development environment

### Development Mode

Use the `--dev` flag for development features:
```bash
python -m golfcal --dev process  # Adds -dev suffix to calendar files
```

### Logging

Comprehensive logging is available:
```bash
# Enable verbose logging
python -m golfcal -v process

# Log to file with rotation
python -m golfcal --log-file golfcal.log process
```

Logs are automatically rotated at 10MB and compressed.

## Testing

Run tests with:
```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_api.py

# Run with coverage
python -m pytest --cov=golfcal tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

[Add license information] 