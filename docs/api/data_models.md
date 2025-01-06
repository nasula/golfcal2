# API Data Models

## Weather Models

### WeatherData

```python
@dataclass
class WeatherData:
    """Weather data model for standardized forecast information."""
    temperature: float          # Temperature in Celsius
    precipitation: float        # Precipitation amount in mm
    precipitation_probability: float  # Probability as percentage (0-100)
    wind_speed: float          # Wind speed in m/s
    wind_direction: str        # Wind direction in degrees or cardinal points
    symbol: str                # Weather symbol code
    elaboration_time: datetime # Forecast time (timezone-aware)
    thunder_probability: float = 0.0  # Thunder probability as percentage
```

### WeatherCode

```python
class WeatherCode:
    """Standard weather code definitions."""
    CLEAR_DAY = "clearsky_day"
    CLEAR_NIGHT = "clearsky_night"
    FAIR_DAY = "fair_day"
    FAIR_NIGHT = "fair_night"
    PARTLY_CLOUDY_DAY = "partlycloudy_day"
    PARTLY_CLOUDY_NIGHT = "partlycloudy_night"
    CLOUDY = "cloudy"
    LIGHT_RAIN = "lightrain"
    RAIN = "rain"
    HEAVY_RAIN = "heavyrain"
    RAIN_AND_THUNDER = "rainandthunder"
    HEAVY_RAIN_AND_THUNDER = "heavyrainandthunder"
```

## CRM Models

### Reservation

```python
@dataclass
class Reservation:
    """Standardized reservation data model."""
    datetime_start: datetime
    players: List[Player]
    course_info: Optional[CourseInfo] = None
    booking_reference: Optional[str] = None
    status: Optional[str] = None
```

### Player

```python
@dataclass
class Player:
    """Player information model."""
    first_name: str
    family_name: str
    handicap: Optional[float] = None
    club_abbreviation: Optional[str] = None
```

### CourseInfo

```python
@dataclass
class CourseInfo:
    """Golf course information model."""
    name: str
    holes: int = 18
    par: Optional[int] = None
    slope: Optional[float] = None
``` 