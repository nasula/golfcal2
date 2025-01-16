# API Documentation

## Overview

This directory contains detailed documentation for all external and internal APIs used in GolfCal2.

## CRM APIs

Golf club management system integrations:

- [WiseGolf API](crm/wisegolf.md) - Modern and legacy WiseGolf implementations
- [NexGolf API](crm/nexgolf.md) - Nordic golf club management system
- [TeeTime API](crm/teetime.md) - Generic golf club management system

## Weather APIs

Weather service integrations:

- [MET.no API](weather/met.md) - Nordic weather service
- [OpenMeteo API](weather/openmeteo.md) - Global weather service
- [OpenWeather API](weather/openweather.md) - Global weather service with fallback
- [AEMET API](weather/aemet.md) - Spanish weather service

## Service APIs

Internal service documentation:

- [Weather Service API](services/weather.md) - Weather data management
- [Calendar Service API](services/calendar.md) - Calendar event management
- [External Events API](services/events.md) - External event integration

## Guidelines

- [Error Handling](guidelines/errors.md) - Common error patterns and handling
- [Authentication](guidelines/auth.md) - Authentication strategies
- [Data Formats](guidelines/formats.md) - Common data formats and structures
- [Performance](guidelines/performance.md) - Rate limiting and caching 