# GolfCal2 Documentation

## Overview

GolfCal2 is a command-line calendar application for managing golf reservations and events. It integrates with various golf club systems and weather services to provide comprehensive information about your golf activities.

## Documentation Structure

```
docs/
├── architecture/           # System architecture documentation
│   ├── overview.md        # High-level system overview
│   ├── services.md        # Service layer design
│   ├── error_handling.md  # Error handling patterns
│   └── data-flow.md       # Data flow diagrams
├── services/              # Service-specific documentation
│   ├── weather/           # Weather services
│   │   ├── README.md      # Weather service overview
│   │   ├── manager.md     # Weather service implementation
│   │   ├── data-models.md # Weather data structures
│   │   └── providers/     # Weather service strategies
│   ├── calendar/          # Calendar service docs
│   ├── reservation/       # Reservation service docs
│   └── external-events/   # External events service docs
├── api/                   # API documentation
│   ├── README.md         # API overview
│   ├── weather/          # Weather API docs
│   │   ├── met.md        # Met.no strategy
│   │   └── openmeteo.md  # OpenMeteo strategy
│   ├── crm/              # CRM API docs
│   │   ├── wisegolf.md   # WiseGolf API
│   │   ├── nexgolf.md    # NexGolf API
│   │   └── teetime.md    # TeeTime API
│   └── guidelines/       # API guidelines
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
- [Error Handling](architecture/error_handling.md)
- [Data Flow](architecture/data-flow.md)

### Services
- [Calendar Service](services/calendar/README.md)
- [Reservation Service](services/reservation/README.md)
- [Weather Service](services/weather/README.md)
- [External Events](services/external-events/README.md)

### APIs
- [API Overview](api/README.md)
- Weather APIs:
  - [Met.no Strategy](api/weather/met.md)
  - [OpenMeteo Strategy](api/weather/openmeteo.md)
  - [Weather Strategy Interface](api/weather/strategy.md)
- CRM APIs:
  - [WiseGolf API](api/crm/wisegolf.md)
  - [NexGolf API](api/crm/nexgolf.md)
  - [TeeTime API](api/crm/teetime.md)
- Guidelines:
  - [Error Handling](api/guidelines/errors.md)
  - [Strategy Pattern](api/guidelines/strategy.md)
  - [Authentication](api/guidelines/auth.md)
  - [Caching](api/guidelines/caching.md)

## Features

### Core Features
- Golf reservation management
- Calendar integration
- Weather information
- External event support

### Weather Integration
- Strategy pattern implementation
- Geographic-based provider selection:
  - Met.no for Nordic/Baltic regions
  - OpenMeteo for global coverage
- Block size patterns:
  - Short range: 1-hour blocks
  - Medium range: 3/6-hour blocks
  - Long range: 6/12-hour blocks
- Automatic fallback handling
- Efficient caching system

### Golf Club Support
- Multiple club systems
- Automated reservations
- Membership management
- Availability checking

## Design Patterns

### Strategy Pattern
- Weather service providers
- Authentication methods
- Club system integrations

### Caching
- Weather data caching
- Response caching
- Cache invalidation
- Memory optimization

### Error Handling
- Type-safe errors
- Context-aware errors
- Automatic fallbacks
- Error aggregation

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](development/contributing.md) for details on how to get started.

## License

GolfCal2 is licensed under the MIT License. See the [LICENSE](../LICENSE) file for details. 