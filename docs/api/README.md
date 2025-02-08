# API Documentation

## Overview

This directory contains detailed documentation for all external and internal APIs used in GolfCal2.

## CRM APIs

Golf club management system integrations:

- [WiseGolf API](crm/wisegolf.md) - Modern and legacy WiseGolf implementations
- [NexGolf API](crm/nexgolf.md) - Nordic golf club management system
- [TeeTime API](crm/teetime.md) - Generic golf club management system

## Weather APIs

Weather service integrations using strategy pattern:

- [Met.no Strategy](weather/met.md) - Nordic/Baltic regions weather service
- [OpenMeteo Strategy](weather/openmeteo.md) - Global weather service
- [Weather Strategy Interface](weather/strategy.md) - Base strategy implementation

## Service APIs

Internal service documentation:

- [Weather Service API](services/weather.md) - Weather data management
- [Calendar Service API](services/calendar.md) - Calendar event management
- [External Events API](services/events.md) - External event integration
- [Base API](services/base_api.md) - Base API implementation

## Guidelines

- [Error Handling](guidelines/errors.md) - Error patterns and handling
- [Strategy Pattern](guidelines/strategy.md) - Strategy implementation guide
- [Authentication](guidelines/auth.md) - Authentication strategies
- [Data Formats](guidelines/formats.md) - Common data formats
- [Caching](guidelines/caching.md) - Caching patterns
- [Performance](guidelines/performance.md) - Rate limiting and optimization 