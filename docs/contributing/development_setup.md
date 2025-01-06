# Development Setup

## Initial Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/golfcal.git
cd golfcal
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
# Install all dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

## Development Tools

### 1. IDE Setup (VSCode)

settings.json:
```json
{
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "python.analysis.typeCheckingMode": "basic"
}
```

### 2. Debugging

launch.json:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "GolfCal Process",
            "type": "python",
            "request": "launch",
            "module": "golfcal",
            "args": ["--dev", "process"],
            "env": {
                "GOLFCAL_DEBUG": "1"
            }
        }
    ]
}
```

## Testing Environment

### 1. Test Configuration

Create `tests/config/test_clubs.json`:
```json
{
    "Test Club": {
        "type": "test_crm",
        "name": "Test Golf Club",
        "url": "http://localhost:8000"
    }
}
```

### 2. Mock Services

Create mock weather service:
```python
class MockWeatherService(WeatherService):
    def _fetch_forecasts(self, lat: float, lon: float) -> List[WeatherData]:
        return [
            WeatherData(
                temperature=20.0,
                precipitation=0.0,
                wind_speed=5.0,
                symbol="clearsky_day"
            )
        ]
```

### 3. Test Data

Create test fixtures in `tests/fixtures/`:
```
fixtures/
  ├── reservations/
  │   ├── wise_golf.json
  │   └── nex_golf.json
  └── weather/
      ├── aemet.json
      └── met_no.json
```

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/new-feature
```

### 2. Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_crm/test_wise_golf.py

# Run with coverage
pytest --cov=api
```

### 3. Check Code Quality

```bash
# Run all checks
./scripts/check_code.sh

# Or individually:
black .
mypy api/
flake8 api/
```

### 4. Update Documentation

- Update relevant documentation files
- Generate API documentation if needed
- Update changelog

### 5. Create Pull Request

- Fill out PR template
- Request review
- Address feedback 