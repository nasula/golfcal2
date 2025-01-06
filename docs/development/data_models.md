# Data Models

## Overview

The application uses dataclasses for type-safe data handling across different CRM systems.

## Core Models

### Reservation Model

```python
@dataclass
class Reservation:
    datetime_start: datetime
    players: List[Player]
    course_info: Optional[CourseInfo] = None
    booking_reference: Optional[str] = None
    status: Optional[str] = None
```

### Player Model

```python
@dataclass
class Player:
    first_name: str
    family_name: str
    handicap: Optional[float] = None
    club_abbreviation: Optional[str] = None
```

### Course Information

```python
@dataclass
class CourseInfo:
    name: str
    holes: int = 18
    par: Optional[int] = None
    slope: Optional[float] = None
```

## Usage Guidelines

1. **Type Safety**
   - Always use type hints
   - Validate data at boundaries
   - Handle optional fields appropriately

2. **Data Validation**
   - Validate data during construction
   - Handle missing fields gracefully
   - Convert types as needed

3. **Error Handling**
   - Use appropriate error types
   - Include context in error messages
   - Handle edge cases 