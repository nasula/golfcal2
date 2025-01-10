# Deployment Guide

## Overview

This guide explains how to deploy GolfCal2 in various environments, from development to production. It covers installation, configuration, and maintenance procedures.

## Prerequisites

- Python 3.10 or higher
- SQLite 3.x
- Git
- Virtual environment support
- Systemd (for service management)

## Installation

### From Source

1. Clone the repository:
```bash
git clone https://github.com/yourusername/golfcal2.git
cd golfcal2
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install the package:
```bash
pip install -e .
```

### Using pip

```bash
pip install golfcal2
```

## Directory Structure

Create required directories:

```bash
# Application directories
mkdir -p /opt/golfcal2
mkdir -p /var/lib/golfcal2/data
mkdir -p /var/log/golfcal2
mkdir -p /etc/golfcal2

# User directories
mkdir -p ~/.golfcal2/cache
mkdir -p ~/.golfcal2/calendars
```

## Configuration

### System Configuration

Create `/etc/golfcal2/config.yaml`:

```yaml
global:
  timezone: "Europe/Helsinki"
  log_level: "INFO"
  cache_dir: "/var/lib/golfcal2/cache"

database:
  path: "/var/lib/golfcal2/data/golfcal2.db"
  backup_dir: "/var/lib/golfcal2/backups"

logging:
  level: "INFO"
  file: "/var/log/golfcal2/app.log"
  max_size: 52428800  # 50MB
  backup_count: 10

weather:
  primary: "met"
  backup: "openweather"
  cache_duration: 3600
  providers:
    met:
      user_agent: "GolfCal2/0.6.0"
    openweather:
      api_key: "${OPENWEATHER_API_KEY}"
```

### User Configuration

Create `~/.golfcal2/config.yaml`:

```yaml
user:
  name: "John Doe"
  email: "john@example.com"
  timezone: "Europe/Helsinki"

memberships:
  - club: "Helsinki Golf"
    type: "wisegolf"
    auth:
      username: "${WISEGOLF_USERNAME}"
      password: "${WISEGOLF_PASSWORD}"
```

## Database Setup

1. Initialize database:
```bash
golfcal2-admin init-db
```

2. Run migrations:
```bash
golfcal2-admin migrate
```

3. Create backup directory:
```bash
mkdir -p /var/lib/golfcal2/backups
```

## Service Setup

### Systemd Service

Create `/etc/systemd/system/golfcal2.service`:

```ini
[Unit]
Description=GolfCal2 Service
After=network.target

[Service]
Type=simple
User=golfcal2
Group=golfcal2
Environment=PYTHONUNBUFFERED=1
Environment=GOLFCAL2_CONFIG=/etc/golfcal2/config.yaml
WorkingDirectory=/opt/golfcal2
ExecStart=/opt/golfcal2/venv/bin/golfcal2-service
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Service Management

```bash
# Enable and start service
systemctl enable golfcal2
systemctl start golfcal2

# Check status
systemctl status golfcal2

# View logs
journalctl -u golfcal2
```

## Backup and Recovery

### Backup Script

Create `/opt/golfcal2/scripts/backup.sh`:

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/var/lib/golfcal2/backups"
DB_PATH="/var/lib/golfcal2/data/golfcal2.db"
CONFIG_DIR="/etc/golfcal2"
MAX_BACKUPS=7

# Create backup filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/golfcal2_$TIMESTAMP.tar.gz"

# Create backup
tar czf "$BACKUP_FILE" \
    "$DB_PATH" \
    "$CONFIG_DIR" \
    /var/log/golfcal2

# Remove old backups
ls -t "$BACKUP_DIR"/golfcal2_*.tar.gz | \
    tail -n +$((MAX_BACKUPS + 1)) | \
    xargs -r rm
```

### Backup Automation

Add to crontab:

```bash
# Run backup daily at 3 AM
0 3 * * * /opt/golfcal2/scripts/backup.sh
```

### Recovery Procedure

1. Stop service:
```bash
systemctl stop golfcal2
```

2. Restore from backup:
```bash
cd /
tar xzf /var/lib/golfcal2/backups/golfcal2_20240110_030000.tar.gz
```

3. Run migrations:
```bash
golfcal2-admin migrate
```

4. Start service:
```bash
systemctl start golfcal2
```

## Monitoring

### Log Rotation

Create `/etc/logrotate.d/golfcal2`:

```
/var/log/golfcal2/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 golfcal2 golfcal2
    postrotate
        systemctl kill -s USR1 golfcal2.service
    endscript
}
```

### Health Check

Create monitoring script:

```python
#!/usr/bin/env python3

import requests
import sys

def check_health():
    """Check application health."""
    try:
        response = requests.get('http://localhost:5000/health')
        status = response.json()
        
        if not all(status['services'].values()):
            print("ERROR: Some services are unhealthy")
            sys.exit(1)
        
        print("OK: All services healthy")
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: Health check failed - {e}")
        sys.exit(2)

if __name__ == '__main__':
    check_health()
```

## Security

### File Permissions

```bash
# Set ownership
chown -R golfcal2:golfcal2 /opt/golfcal2
chown -R golfcal2:golfcal2 /var/lib/golfcal2
chown -R golfcal2:golfcal2 /var/log/golfcal2
chown -R root:golfcal2 /etc/golfcal2

# Set permissions
chmod 755 /opt/golfcal2
chmod 750 /var/lib/golfcal2
chmod 750 /var/log/golfcal2
chmod 750 /etc/golfcal2
chmod 640 /etc/golfcal2/*.yaml
```

### API Keys

Use environment variables for sensitive data:

```bash
# Add to /etc/golfcal2/environment
OPENWEATHER_API_KEY=your-key
AEMET_API_KEY=your-key
WISEGOLF_USERNAME=your-username
WISEGOLF_PASSWORD=your-password
```

## Maintenance

### Regular Tasks

1. **Daily**
   - Check logs for errors
   - Verify backups
   - Monitor disk space

2. **Weekly**
   - Review service metrics
   - Check for updates
   - Rotate logs

3. **Monthly**
   - Full backup
   - Security updates
   - Performance review

### Update Procedure

1. Stop service:
```bash
systemctl stop golfcal2
```

2. Backup data:
```bash
/opt/golfcal2/scripts/backup.sh
```

3. Update code:
```bash
cd /opt/golfcal2
git pull
source venv/bin/activate
pip install -U -r requirements.txt
```

4. Run migrations:
```bash
golfcal2-admin migrate
```

5. Start service:
```bash
systemctl start golfcal2
```

## Troubleshooting

### Common Issues

1. **Service Won't Start**
   - Check logs: `journalctl -u golfcal2`
   - Verify permissions
   - Check configuration

2. **Database Errors**
   - Check disk space
   - Verify permissions
   - Run integrity check

3. **API Failures**
   - Verify API keys
   - Check rate limits
   - Monitor response times

### Debug Mode

Enable debug mode in config:

```yaml
global:
  log_level: "DEBUG"
  dev_mode: true
```

## Related Documentation

- [Configuration Guide](configuration.md)
- [Monitoring Guide](monitoring.md)
- [Architecture Overview](../architecture/overview.md)
``` 