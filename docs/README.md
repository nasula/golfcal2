# GolfCal2 Documentation

## Overview

GolfCal2 is a command-line calendar application for managing golf reservations and events. It integrates with various golf club systems and weather services to provide comprehensive information about your golf activities.

## Documentation Structure

```
docs/
├── architecture/           # System architecture documentation
│   ├── overview.md        # High-level system overview
│   ├── services.md        # Service layer design
│   └── data-flow.md       # Data flow diagrams
├── services/              # Service-specific documentation
│   ├── weather/           # Weather services
│   │   ├── overview.md    # Weather service architecture
│   │   ├── manager.md     # WeatherManager implementation
│   │   ├── data-models.md # Weather data structures
│   │   └── providers/     # Weather service providers
│   ├── calendar/          # Calendar service docs
│   ├── reservation/       # Reservation service docs
│   └── external-events/   # External events service docs
├── development/           # Development documentation
│   ├── setup.md          # Development setup guide
│   ├── testing.md        # Testing guide
│   └── contributing.md    # Contribution guidelines
└── deployment/           # Deployment documentation
    ├── configuration.md  # Configuration guide
    └── monitoring.md     # Monitoring and logging
```

## Quick Links

### For Users
- [Getting Started](architecture/overview.md)
- [Configuration Guide](deployment/configuration.md)
- [Command Line Interface](services/cli.md)

### For Developers
- [Development Setup](development/setup.md)
- [Contributing Guidelines](development/contributing.md)
- [Testing Guide](development/testing.md)

### Architecture
- [System Overview](architecture/overview.md)
- [Service Architecture](architecture/services.md)
- [Data Flow](architecture/data-flow.md)

### Services
- [Calendar Service](services/calendar/README.md)
- [Reservation Service](services/reservation/README.md)
- [Weather Services](services/weather/README.md)
- [External Events](services/external-events/README.md)

## Features

### Core Features
- Golf reservation management
- Calendar integration
- Weather information
- External event support

### Weather Integration
- Multiple weather providers
- Location-based forecasts
- Automatic updates
- Caching support

### Golf Club Support
- Multiple club systems
- Automated reservations
- Membership management
- Availability checking

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](development/contributing.md) for details on how to get started.

## License

GolfCal2 is licensed under the MIT License. See the [LICENSE](../LICENSE) file for details. 