# Getting Started

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/golfcal.git
cd golfcal
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

### 1. Weather Services

Create `api_keys.yaml`:
```yaml
weather:
  aemet: "your-aemet-key"
  openweather: "your-openweather-key"
```

### 2. Golf Clubs

Configure `clubs.json`:
```json
{
    "My Golf Club": {
        "type": "wise_golf",
        "name": "My Golf Club",
        "url": "https://api.mygolfclub.com",
        "timezone": "Europe/Helsinki"
    }
}
```

### 3. User Settings

Set up `config/user_settings.yaml`:
```yaml
users:
  - name: "Your Name"
    crm_credentials:
      my_golf_club:
        username: "your-username"
        password: "your-password"
```

## Basic Usage

The application provides several commands for managing golf reservations and related data:

### 1. Process Golf Calendar

This is the main command that fetches reservations and creates calendar files:

```bash
# Process all users
golfcal2 process

# Process specific user
golfcal2 -U "Your Name" process

# Test run without making changes
golfcal2 process --dry-run
```

### 2. List Information

View various types of information:

```bash
# List your golf courses
golfcal2 list courses

# List your reservations
golfcal2 list reservations

# List weather cache
golfcal2 list weather-cache
```

### 3. Check Configuration

Verify your setup:

```bash
# Basic configuration check
golfcal2 check

# Full system check
golfcal2 check --full
```

## Command Line Interface

### Global Options

These options can be used with any command:

- `-U, --user USERNAME`: Process specific user only
  ```bash
  golfcal2 -U "Your Name" process
  ```

- `--dev`: Enable development mode
  ```bash
  golfcal2 --dev process
  ```

- `-v, --verbose`: Enable detailed logging
  ```bash
  golfcal2 -v process
  ```

- `--log-file PATH`: Write logs to file
  ```bash
  golfcal2 --log-file golfcal.log process
  ```

### Main Commands

#### process
Process golf calendar by fetching reservations and updating calendar files.

Options:
- `--dry-run`: Preview changes without applying them
- `--force`: Process even if no changes detected

```bash
# Preview changes
golfcal2 process --dry-run

# Force update
golfcal2 process --force
```

#### list
List various types of information with three subcommands:

1. `courses`: List golf courses
   - `--all`: Show all configured courses
   ```bash
   golfcal2 list courses --all
   ```

2. `reservations`: List golf reservations
   - `--active`: Show only active reservations
   - `--upcoming`: Show only future reservations
   - `--days N`: Look N days ahead/behind
   - `--format`: Output as 'text' or 'json'
   ```bash
   # Show upcoming week's reservations
   golfcal2 list reservations --upcoming --days 7
   
   # Show as JSON
   golfcal2 list reservations --format json
   ```

3. `weather-cache`: Manage weather cache
   - `--service`: Filter by service ('met', 'portuguese', 'iberian')
   - `--location`: Filter by coordinates (lat,lon)
   - `--date`: Filter by date (YYYY-MM-DD)
   - `--format`: Output as 'text' or 'json'
   - `--clear`: Clear cache data
   ```bash
   # View MET.no cache
   golfcal2 list weather-cache --service met
   
   # Clear Portuguese weather cache
   golfcal2 list weather-cache --service portuguese --clear
   ```

#### check
Verify configuration and connectivity.

Options:
- `--full`: Run comprehensive checks

```bash
# Full system check
golfcal2 check --full
```

## Next Steps

1. Read [CRM Integration](../development/crm_integration.md) for adding new golf clubs
2. Check [Weather Services](../development/weather_services.md) for weather provider details
3. See [Configuration](../deployment/configuration.md) for advanced settings 