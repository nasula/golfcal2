# Architecture Overview

## System Components

### 1. Weather Services
- **WeatherManager**: Central coordinator for weather data
  - Manages multiple regional weather services
  - Handles geographic region selection
  - Coordinates timezone conversions
  - Implements caching and error handling

- **Regional Weather Services**
  - Mediterranean Weather Service
  - Iberian Weather Service
  - Met Weather Service
  - Portuguese Weather Service
  - Each service implements region-specific API integration

### 2. CRM Integration Layer
- Abstract interfaces for CRM systems
- Base implementation with common functionality
- Standardized error handling
- Authentication management
- Request retry mechanisms

### 3. Data Models
- Standardized models for cross-CRM compatibility
- Type-safe data structures
- Validation rules
- Weather data models
- Reservation models
- Course information models

### 4. External Integrations
- Multiple CRM systems
- Weather service providers
- Authentication providers
- Monitoring services

## Geographic Coverage

### Weather Service Regions
1. **Norway** (Met Weather Service)
   - Bounds: 57.0°N to 71.5°N, 4.0°E to 31.5°E

2. **Mediterranean** (Mediterranean Weather Service)
   - Bounds: 35.0°N to 45.0°N, 20.0°E to 45.0°E

3. **Portugal** (Portuguese Weather Service)
   - Bounds: 36.5°N to 42.5°N, 9.5°W to 7.5°W

4. **Spain** (Iberian Weather Service)
   - Mainland: 36.0°N to 44.0°N, 7.5°W to 3.5°E
   - Canary Islands: 27.5°N to 29.5°N, 18.5°W to 13.0°W

## Architecture Principles

### 1. Service Organization
- Clear separation of concerns
- Standard interfaces
- Geographic region-based service selection
- Centralized management through manager classes

### 2. Data Management
- Type safety throughout the system
- Standardized data models
- Validation at service boundaries
- Proper error propagation

### 3. Error Handling
- Specialized error types
- Consistent error patterns
- Proper error context
- Retry mechanisms where appropriate

### 4. Performance
- Caching strategies
- Rate limiting
- Efficient data structures
- Optimized API calls

### 5. Maintainability
- Clear documentation
- Type hints
- Unit tests
- Integration tests 