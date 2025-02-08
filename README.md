# GolfCal2

A Python application for managing golf reservations and creating calendar integrations.

## Features

- Fetch golf reservations from multiple booking systems:
  - WiseGolf
  - NexGolf
  - TeeTime
- Create iCalendar files for easy calendar integration
- Weather forecast integration for golf sessions
- Automated notifications via Pushover
- Service mode for continuous calendar updates
- Command-line interface for manual operations

## Installation

### Using pip

```bash
pip install golfcal2
```

### Development Installation

```bash
# Clone the repository
git clone https://github.com/jahonen/golfcal2
cd golfcal2

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"
```

## Configuration

1. Create a configuration directory:
```bash
mkdir -p ~/.config/golfcal2
```

2. Copy the example configuration files:
```bash
cp src/golfcal2/config/config.yaml ~/.config/golfcal2/
cp src/golfcal2/config/clubs.json ~/.config/golfcal2/
cp src/golfcal2/config/users.json ~/.config/golfcal2/
```

3. Edit the configuration files according to your needs:
- `config.yaml`: Global settings and API keys
- `clubs.json`: Golf club configurations
- `users.json`: User profiles and memberships

## Usage

### Command Line Interface

```bash
# List all reservations
golfcal2 list reservations

# Process calendar for all users
golfcal2 process calendar

# Process calendar for a specific user
golfcal2 process calendar -u username

# Check configuration
golfcal2 check config

# Get weather forecast for a specific location
golfcal2 get weather --lat 60.1699 --lon 24.9384
```

### Service Mode

Run as a system service for continuous calendar updates:

```bash
# Install the service
sudo cp golfcal2.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable golfcal2
sudo systemctl start golfcal2

# Check service status
sudo systemctl status golfcal2
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=golfcal2

# Run specific test file
pytest tests/test_cli.py
```

### Code Style

The project uses Ruff for code formatting and linting:

```bash
# Check code style
ruff check .

# Fix code style issues
ruff check --fix .
```

### Type Checking

```bash
# Run type checking
mypy src/golfcal2
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request 