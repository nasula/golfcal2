# Monitoring Guide

## Overview

GolfCal2 includes comprehensive monitoring capabilities to track application health, performance, and usage. This guide explains how to set up and use the monitoring features.

## Logging

### Log Configuration

Configure logging in `config.yaml`:

```yaml
logging:
  level: "INFO"
  file: "/var/log/golfcal2/app.log"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  max_size: 10485760  # 10MB
  backup_count: 5
  handlers:
    - type: "file"
      level: "INFO"
      filename: "/var/log/golfcal2/app.log"
    - type: "syslog"
      level: "WARNING"
      facility: "local0"
    - type: "stream"
      level: "DEBUG"
```

### Log Levels

1. **DEBUG**: Detailed information for debugging
   ```python
   logger.debug("Processing reservation: %s", reservation_id)
   ```

2. **INFO**: General operational information
   ```python
   logger.info("Successfully created reservation for %s", user_id)
   ```

3. **WARNING**: Warning messages for potential issues
   ```python
   logger.warning("Weather data unavailable for %s", coordinates)
   ```

4. **ERROR**: Error messages for failed operations
   ```python
   logger.error("Failed to create reservation: %s", error)
   ```

### Log Analysis

Example log parsing script:

```python
import re
from collections import defaultdict
from datetime import datetime

def analyze_logs(log_file):
    """Analyze application logs for patterns and issues."""
    patterns = {
        'error': r'ERROR.*?(?P<error>.*?)$',
        'warning': r'WARNING.*?(?P<warning>.*?)$',
        'api_call': r'API call to (?P<service>.*?) took (?P<time>\d+)ms'
    }
    
    stats = defaultdict(int)
    
    with open(log_file) as f:
        for line in f:
            for name, pattern in patterns.items():
                if match := re.search(pattern, line):
                    stats[name] += 1
                    if name in ['error', 'warning']:
                        print(f"{name.upper()}: {match.group(name)}")
    
    return stats
```

## Metrics

### System Metrics

1. **Resource Usage**
```python
def get_system_metrics():
    """Get system resource metrics."""
    return {
        'cpu_percent': psutil.cpu_percent(),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent,
        'open_files': len(psutil.Process().open_files()),
        'threads': len(psutil.Process().threads())
    }
```

2. **Database Metrics**
```python
def get_db_metrics():
    """Get database performance metrics."""
    return {
        'connections': db.get_connection_count(),
        'active_transactions': db.get_transaction_count(),
        'cache_hits': db.get_cache_stats()['hits'],
        'cache_misses': db.get_cache_stats()['misses']
    }
```

### Application Metrics

1. **Service Metrics**
```python
def get_service_metrics():
    """Get service performance metrics."""
    return {
        'active_users': len(user_manager.active_users),
        'reservations_today': reservation_service.get_daily_count(),
        'weather_cache_hits': weather_manager.cache_stats['hits'],
        'weather_cache_misses': weather_manager.cache_stats['misses']
    }
```

2. **API Metrics**
```python
def get_api_metrics():
    """Get API performance metrics."""
    return {
        'requests_per_minute': api_monitor.get_request_rate(),
        'average_response_time': api_monitor.get_average_response_time(),
        'error_rate': api_monitor.get_error_rate(),
        'active_connections': api_monitor.get_connection_count()
    }
```

## Health Checks

### Service Health

```python
class HealthCheck:
    def check_database(self):
        """Check database connectivity."""
        try:
            self.db.execute('SELECT 1')
            return True
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            return False
    
    def check_weather_services(self):
        """Check weather service availability."""
        results = {}
        for service in self.weather_manager.services.values():
            try:
                service.ping()
                results[service.name] = True
            except Exception as e:
                logger.error("Weather service %s health check failed: %s",
                           service.name, e)
                results[service.name] = False
        return results
    
    def check_club_apis(self):
        """Check golf club API availability."""
        results = {}
        for club in self.club_factory.get_active_clubs():
            try:
                club.check_availability()
                results[club.name] = True
            except Exception as e:
                logger.error("Club API %s health check failed: %s",
                           club.name, e)
                results[club.name] = False
        return results
```

### Monitoring Endpoints

```python
@app.route('/health')
def health_check():
    """Health check endpoint."""
    checker = HealthCheck()
    status = {
        'database': checker.check_database(),
        'weather_services': checker.check_weather_services(),
        'club_apis': checker.check_club_apis(),
        'system': get_system_metrics(),
        'timestamp': datetime.utcnow().isoformat()
    }
    return jsonify(status)

@app.route('/metrics')
def metrics():
    """Metrics endpoint."""
    return jsonify({
        'system': get_system_metrics(),
        'database': get_db_metrics(),
        'services': get_service_metrics(),
        'api': get_api_metrics(),
        'timestamp': datetime.utcnow().isoformat()
    })
```

## Alerting

### Alert Configuration

```yaml
alerts:
  email:
    enabled: true
    recipients:
      - "admin@example.com"
      - "oncall@example.com"
    
  slack:
    enabled: true
    webhook_url: "https://hooks.slack.com/services/..."
    channel: "#monitoring"
    
  thresholds:
    cpu_percent: 80
    memory_percent: 90
    disk_percent: 85
    error_rate: 0.05
    response_time: 5000
```

### Alert Implementation

```python
class AlertManager:
    def __init__(self, config):
        self.config = config
        self.notifiers = self._setup_notifiers()
    
    def check_thresholds(self, metrics):
        """Check metrics against thresholds."""
        alerts = []
        for metric, value in metrics.items():
            if threshold := self.config['thresholds'].get(metric):
                if value > threshold:
                    alerts.append({
                        'metric': metric,
                        'value': value,
                        'threshold': threshold,
                        'timestamp': datetime.utcnow().isoformat()
                    })
        return alerts
    
    def send_alerts(self, alerts):
        """Send alerts through configured channels."""
        for alert in alerts:
            message = self._format_alert(alert)
            for notifier in self.notifiers:
                try:
                    notifier.send(message)
                except Exception as e:
                    logger.error("Failed to send alert: %s", e)
    
    def _format_alert(self, alert):
        """Format alert message."""
        return (
            f"ALERT: {alert['metric']} exceeded threshold\n"
            f"Value: {alert['value']}\n"
            f"Threshold: {alert['threshold']}\n"
            f"Time: {alert['timestamp']}"
        )
```

## Dashboard

### Metrics Dashboard

```python
@app.route('/dashboard')
def dashboard():
    """Render metrics dashboard."""
    return render_template('dashboard.html', {
        'system_metrics': get_system_metrics(),
        'db_metrics': get_db_metrics(),
        'service_metrics': get_service_metrics(),
        'api_metrics': get_api_metrics(),
        'health_status': health_check(),
        'recent_alerts': alert_manager.get_recent_alerts()
    })
```

### Dashboard Components

1. **System Status**
   - CPU, memory, disk usage
   - Active connections
   - Thread count

2. **Service Status**
   - Weather service availability
   - Club API status
   - Database health

3. **Performance Metrics**
   - Response times
   - Cache hit rates
   - Error rates

4. **Usage Statistics**
   - Active users
   - Reservations per day
   - API calls per minute

## Best Practices

1. **Logging**
   - Use appropriate log levels
   - Include context in messages
   - Implement log rotation
   - Monitor log size

2. **Metrics**
   - Collect relevant metrics
   - Set appropriate thresholds
   - Monitor trends
   - Archive historical data

3. **Alerting**
   - Configure meaningful alerts
   - Avoid alert fatigue
   - Implement escalation
   - Document response procedures

4. **Maintenance**
   - Regular log analysis
   - Metric threshold review
   - Alert configuration updates
   - Dashboard improvements

## Related Documentation

- [Configuration Guide](configuration.md)
- [Deployment Guide](deployment.md)
- [Architecture Overview](../architecture/overview.md)
``` 