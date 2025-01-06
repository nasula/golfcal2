# Introduction

GolfCal is an application that integrates golf course reservation systems with weather forecasts to provide comprehensive golf planning tools.

## Features

1. **CRM Integration**
   - Multiple golf course booking systems support
   - Standardized reservation data model
   - Automatic data synchronization

2. **Weather Services**
   - Region-specific weather providers
   - Accurate local forecasts
   - Automatic provider selection

3. **Calendar Integration**
   - Automatic event creation
   - Weather information embedding
   - External calendar support

## System Requirements

- Python 3.8 or higher
- SQLite database
- Internet connection for API access
- Appropriate API keys for weather services

## Quick Start

1. Install the package:
```bash
pip install golfcal
```

2. Configure your API keys in `api_keys.yaml`

3. Set up your golf clubs in `clubs.json`

4. Run the application:
```bash
python -m golfcal process
``` 