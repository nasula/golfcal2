# API Documentation

## Overview

GolfCal2 integrates with multiple external APIs and provides internal service APIs. This documentation covers both external API integrations and internal service APIs.

## External APIs

### CRM Systems
- [CRM APIs Overview](crm_apis.md) - Golf club booking system integrations
  - WiseGolf API
  - NexGolf API
  - TeeTime API

### Weather Services
- [Weather APIs Overview](weather/README.md) - Weather data providers
  - [MET.no API](weather/met.md) - Nordic region weather service
  - [OpenMeteo API](weather/openmeteo.md) - Global primary weather service
  - [OpenWeather API](weather/openweather.md) - Global fallback weather service
  - [AEMET API](weather/aemet.md) - Iberian region weather service

## Internal Service APIs

### Core Services
- [Weather Service API](../services/weather/README.md) - Weather data management
  - Service selection
  - Data caching
  - Error handling

- [Calendar Service API](../services/calendar/README.md) - Calendar event management
  - Event creation
  - ICS file generation
  - Event updates

- [External Events API](../services/external-events/README.md) - External event integration
  - Event matching
  - Pattern recognition
  - Event processing

### Authentication
- [Authentication Service API](../services/auth/README.md) - Authentication management
  - Authentication strategies
  - Token management
  - Session handling

## API Guidelines

### Error Handling
- Standard error responses
- Rate limiting
- Retry strategies
- Error recovery

### Authentication
- API key management
- Token refresh
- Session management
- Security best practices

### Data Formats
- JSON structures
- Date/time formats
- Coordinate systems
- Weather codes

### Performance
- Caching strategies
- Rate limit handling
- Connection pooling
- Request optimization 