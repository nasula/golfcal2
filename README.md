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

### Process Reservations
```bash
# Process specific user (development mode)
python -m golfcal2 -u USERNAME --dev process

# Process with debug logging
python -m golfcal2 -u USERNAME -v process

# Process with debug logging to file
python -m golfcal2 -u USERNAME -v --log-file golfcal.log process
```

### List Reservations
```bash
# List reservations for specific user
python -m golfcal2 -u USERNAME list

# List reservations in development mode
python -m golfcal2 -u USERNAME --dev list
```

### Check Configuration
```bash
# Check configuration for specific user
python -m golfcal2 -u USERNAME check

# Check configuration in development mode
python -m golfcal2 -u USERNAME --dev check
```

### Global Options
- `-u USERNAME, --user USERNAME`: Specify the user (required)
- `--dev`: Enable development mode
- `-v, --verbose`: Enable verbose (debug) logging
- `--log-file LOG_FILE`: Specify log file path

### Commands
- `process`: Process reservations and create calendar files
- `list`: List current reservations
- `check`: Check configuration validity

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