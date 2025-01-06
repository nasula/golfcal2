# Environment Setup

## Development Environment

### Requirements

- Python 3.8+
- pip
- git
- SQLite3

### Python Dependencies

```bash
# Core dependencies
pip install requests pandas pytz

# Testing dependencies
pip install pytest pytest-cov pytest-mock

# Development tools
pip install black mypy flake8
```

### Environment Variables

```bash
# Base configuration
export GOLFCAL_ENV=development
export GOLFCAL_CONFIG_DIR=/path/to/config

# Weather service keys
export AEMET_API_KEY=your-key
export OPENWEATHER_API_KEY=your-key

# Debug settings
export GOLFCAL_DEBUG=1
export GOLFCAL_LOG_LEVEL=DEBUG
```

## Production Environment

### System Requirements

- Linux server (Ubuntu 20.04 LTS recommended)
- Python 3.8+
- Systemd for service management
- 1GB RAM minimum
- 10GB disk space

### Installation

1. Create service user:
```bash
sudo useradd -r -s /bin/false golfcal
```

2. Set up directories:
```bash
sudo mkdir -p /opt/golfcal
sudo mkdir -p /var/log/golfcal
sudo mkdir -p /etc/golfcal
```

3. Install application:
```bash
sudo pip3 install golfcal
```

### Service Configuration

Create systemd service file `/etc/systemd/system/golfcal.service`:
```ini
[Unit]
Description=GolfCal Service
After=network.target

[Service]
Type=simple
User=golfcal
Group=golfcal
Environment=GOLFCAL_ENV=production
Environment=GOLFCAL_CONFIG_DIR=/etc/golfcal
ExecStart=/usr/local/bin/golfcal process
Restart=always

[Install]
WantedBy=multi-user.target
```

### Logging Configuration

Configure `/etc/golfcal/logging.yaml`:
```yaml
version: 1
formatters:
  standard:
    format: '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
handlers:
  file:
    class: logging.handlers.RotatingFileHandler
    filename: /var/log/golfcal/golfcal.log
    maxBytes: 10485760
    backupCount: 5
    formatter: standard
root:
  level: INFO
  handlers: [file]
```

### Security Considerations

1. File permissions:
```bash
sudo chown -R golfcal:golfcal /opt/golfcal
sudo chown -R golfcal:golfcal /var/log/golfcal
sudo chmod 750 /etc/golfcal
```

2. API keys:
```bash
sudo chmod 600 /etc/golfcal/api_keys.yaml
```

3. SSL certificates:
```bash
sudo mkdir /etc/golfcal/certs
sudo chmod 700 /etc/golfcal/certs
``` 