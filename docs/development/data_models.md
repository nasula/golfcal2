# Data Models

## Overview

The application uses a comprehensive set of data models to ensure type safety and data consistency across different components. All models are implemented using Python's dataclasses with strict type hints and validation rules.

## Core Models

### 1. Reservation Models

#### Reservation

```python
@dataclass
class Reservation:
    """Core reservation model representing a golf booking."""
    datetime_start: datetime
    players: List[Player]
    course_info: Optional[CourseInfo] = None
    booking_reference: Optional[str] = None
    status: Optional[str] = None
    cart: Optional[bool] = None
    notes: Optional[str] = None
    confirmation_sent: bool = False

    def __post_init__(self):
        """Validate reservation data after initialization."""
        if not self.players:
            raise ValueError("Reservation must have at least one player")
        if self.datetime_start < datetime.now(self.datetime_start.tzinfo):
            raise ValueError("Reservation start time must be in the future")
```

#### Player

```python
@dataclass
class Player:
    """Player information model."""
    first_name: str
    family_name: str
    handicap: Optional[float] = None
    club_abbreviation: Optional[str] = None
    player_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    def __post_init__(self):
        """Validate player data after initialization."""
        if not self.first_name or not self.family_name:
            raise ValueError("Player must have both first and last name")
        if self.handicap is not None and not (-10 <= self.handicap <= 54):
            raise ValueError("Handicap must be between -10 and 54")
```

#### CourseInfo

```python
@dataclass
class CourseInfo:
    """Golf course information model."""
    name: str
    holes: int = 18
    par: Optional[int] = None
    slope: Optional[float] = None
    course_rating: Optional[float] = None
    tee_color: Optional[str] = None
    club_id: Optional[str] = None

    def __post_init__(self):
        """Validate course information after initialization."""
        if self.holes not in [9, 18]:
            raise ValueError("Course must have either 9 or 18 holes")
        if self.par is not None and not (68 <= self.par <= 74):
            raise ValueError("Par must be between 68 and 74")
```

### 2. Weather Models

#### WeatherData

```python
@dataclass
class WeatherData:
    """Weather forecast data model."""
    elaboration_time: datetime
    temperature: float  # Celsius
    precipitation_probability: float  # 0-100%
    wind_speed: float  # meters/second
    wind_direction: float  # degrees (0-360)
    weather_symbol: str
    cloud_coverage: Optional[float] = None  # 0-100%

    def __post_init__(self):
        """Validate weather data after initialization."""
        if not (-50 <= self.temperature <= 50):
            raise ValueError("Temperature must be between -50°C and 50°C")
        if not (0 <= self.precipitation_probability <= 100):
            raise ValueError("Precipitation probability must be between 0% and 100%")
        if not (0 <= self.wind_speed <= 100):
            raise ValueError("Wind speed must be between 0 and 100 m/s")
        if not (0 <= self.wind_direction <= 360):
            raise ValueError("Wind direction must be between 0° and 360°")
        if self.cloud_coverage is not None and not (0 <= self.cloud_coverage <= 100):
            raise ValueError("Cloud coverage must be between 0% and 100%")
```

#### WeatherSymbol

```python
class WeatherSymbol(str, Enum):
    """Standardized weather symbols across all weather services."""
    CLEAR = "clear"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    LIGHT_RAIN = "light_rain"
    RAIN = "rain"
    HEAVY_RAIN = "heavy_rain"
    THUNDERSTORM = "thunderstorm"
    SNOW = "snow"
    FOG = "fog"
```

### 3. Configuration Models

#### AppConfig

```python
@dataclass
class AppConfig:
    """Application configuration model."""
    environment: str
    debug: bool = False
    log_level: str = "INFO"
    timezone: str = "UTC"
    cache_duration: int = 3600  # seconds
    api_timeout: int = 30  # seconds
    retry_count: int = 3
    weather_cache_days: int = 7

    def __post_init__(self):
        """Validate configuration after initialization."""
        valid_environments = {"development", "staging", "production"}
        if self.environment not in valid_environments:
            raise ValueError(f"Environment must be one of: {valid_environments}")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Invalid log level")
```

## Validation Rules

### 1. Type Validation
- All fields must match their type hints
- Optional fields must be properly marked
- Enums must use valid values
- Date/time fields must be timezone-aware

### 2. Business Rules

#### Reservation Rules
- Start time must be in the future
- Must have at least one player
- Course info required for new bookings
- Valid booking reference format if provided
- Valid status values from predefined set

#### Player Rules
- Non-empty names required
- Valid handicap range (-10 to 54)
- Valid email format if provided
- Valid phone format if provided
- Club abbreviation must match known formats

#### Course Rules
- Must have 9 or 18 holes
- Par must be between 68 and 74 if provided
- Valid slope rating range if provided
- Valid course rating range if provided
- Known tee colors only

#### Weather Rules
- Temperature in valid range (-50°C to 50°C)
- Percentages between 0 and 100
- Wind speed between 0 and 100 m/s
- Wind direction between 0° and 360°
- Weather symbol must match enum values

## Usage Examples

### 1. Creating a Reservation

```python
# Create a basic reservation
reservation = Reservation(
    datetime_start=datetime.now(timezone.utc) + timedelta(days=1),
    players=[
        Player("John", "Doe", handicap=12.5),
        Player("Jane", "Smith", handicap=8.2)
    ],
    course_info=CourseInfo(
        name="Sample Golf Club",
        holes=18,
        par=72,
        tee_color="white"
    )
)

# Add optional details
reservation.cart = True
reservation.notes = "Prefer early start"
```

### 2. Working with Weather Data

```python
# Create weather data instance
weather = WeatherData(
    elaboration_time=datetime.now(timezone.utc),
    temperature=22.5,
    precipitation_probability=30.0,
    wind_speed=5.2,
    wind_direction=180.0,
    weather_symbol=WeatherSymbol.PARTLY_CLOUDY,
    cloud_coverage=45.0
)

# Access normalized data
print(f"Temperature: {weather.temperature}°C")
print(f"Wind: {weather.wind_speed} m/s from {weather.wind_direction}°")
```

## Best Practices

### 1. Data Integrity
- Always validate input data
- Use appropriate data types
- Handle missing data gracefully
- Maintain data consistency

### 2. Error Handling
- Use custom exceptions for validation
- Include helpful error messages
- Maintain error context
- Log validation failures

### 3. Type Safety
- Use type hints consistently
- Validate at boundaries
- Document type constraints
- Use mypy for static type checking

### 4. Performance
- Minimize object creation
- Use appropriate data structures
- Cache computed values
- Optimize validation routines
``` 