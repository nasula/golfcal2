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

1. Process reservations:
```bash
python -m golfcal process
```

2. Development mode:
```bash
python -m golfcal --dev process
```

3. Specific user:
```bash
python -m golfcal -u "Your Name" process
```

## Next Steps

1. Read [CRM Integration](../development/crm_integration.md) for adding new golf clubs
2. Check [Weather Services](../development/weather_services.md) for weather provider details
3. See [Configuration](../deployment/configuration.md) for advanced settings 