# Code Style Guide

## Python Style

We follow PEP 8 with some additional guidelines:

### 1. Formatting

- Use 4 spaces for indentation
- Maximum line length: 88 characters (Black formatter default)
- Use trailing commas in multi-line structures

```python
# Good
my_list = [
    "first_item",
    "second_item",
    "third_item",
]

# Bad
my_list = ["first_item",
           "second_item",
           "third_item"]
```

### 2. Type Hints

Always use type hints for function arguments and return values:

```python
# Good
def fetch_reservations(
    self,
    start_date: datetime,
    end_date: datetime,
) -> List[Reservation]:
    pass

# Bad
def fetch_reservations(self, start_date, end_date):
    pass
```

### 3. Documentation

Use Google-style docstrings:

```python
def parse_reservation(self, raw_data: Dict[str, Any]) -> Reservation:
    """Parse raw reservation data into standard format.
    
    Args:
        raw_data: Raw reservation data from CRM
        
    Returns:
        Standardized Reservation object
        
    Raises:
        APIResponseError: If required fields are missing
    """
    pass
```

## Project Structure

### 1. Module Organization

```
api/
  ├── __init__.py
  ├── interfaces.py
  ├── crm/
  │   ├── __init__.py
  │   ├── base.py
  │   └── implementations/
  └── weather/
      ├── __init__.py
      ├── base.py
      └── providers/
```

### 2. Import Style

```python
# Standard library imports
from typing import Dict, List, Optional
from datetime import datetime

# Third-party imports
import requests
import pandas as pd

# Local imports
from api.interfaces import CRMInterface
from api.models import Reservation
```

## Testing

### 1. Test Organization

```python
# test_wise_golf.py

class TestWiseGolfAuth:
    def test_successful_login(self):
        pass
    
    def test_invalid_credentials(self):
        pass

class TestWiseGolfReservations:
    def test_fetch_reservations(self):
        pass
```

### 2. Test Naming

- Test files: `test_<module>.py`
- Test classes: `Test<Class>` or `Test<Functionality>`
- Test methods: `test_<scenario>`

## Tools

### 1. Code Formatting

Use Black for automatic formatting:
```bash
# Format a file
black api/crm/wise_golf.py

# Format the whole project
black .
```

### 2. Type Checking

Use mypy for static type checking:
```bash
mypy api/
```

### 3. Linting

Use flake8 for linting:
```bash
flake8 api/
```

## Git Workflow

### 1. Branch Naming

- Feature branches: `feature/add-new-crm`
- Bug fixes: `fix/auth-timeout`
- Documentation: `docs/update-crm-guide`

### 2. Commit Messages

Follow conventional commits:
```
feat: add WiseGolf CRM integration
fix: handle authentication timeout
docs: update CRM integration guide
refactor: improve error handling in base CRM
```

### 3. Pull Requests

- Create descriptive titles
- Use PR template
- Include tests
- Update documentation 