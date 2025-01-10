# Development Setup Guide

## Prerequisites

- Python 3.10 or higher
- pip (Python package installer)
- git
- SQLite3

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/golfcal2.git
cd golfcal2
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies
```

## Configuration

1. Create a configuration file:
```bash
cp config.example.yaml config.yaml
```

2. Edit `config.yaml` with your settings:
```yaml
weather:
  met:
    user_agent: "YourApp/1.0"
  openweather:
    api_key: "your-api-key"
  aemet:
    api_key: "your-api-key"
  ipma:
    enabled: true

database:
  path: "data/golfcal2.db"

logging:
  level: "DEBUG"
  file: "logs/golfcal2.log"
```

## Database Setup

1. Initialize the database:
```bash
python -m golfcal2.db.init
```

2. Run migrations:
```bash
python -m golfcal2.db.migrate
```

## Development Tools

### Code Formatting

We use `black` for code formatting:
```bash
# Format all Python files
black .

# Check formatting without making changes
black --check .
```

### Linting

We use `flake8` for linting:
```bash
# Run linter
flake8

# Run with specific config
flake8 --config=.flake8
```

### Type Checking

We use `mypy` for type checking:
```bash
# Run type checker
mypy golfcal2

# Run with specific config
mypy --config-file mypy.ini golfcal2
```

## Running Tests

1. Run all tests:
```bash
pytest
```

2. Run with coverage:
```bash
pytest --cov=golfcal2
```

3. Generate coverage report:
```bash
pytest --cov=golfcal2 --cov-report=html
```

## Development Workflow

1. Create a new branch:
```bash
git checkout -b feature/your-feature-name
```

2. Make changes and commit:
```bash
git add .
git commit -m "Description of changes"
```

3. Run tests and checks:
```bash
# Run all checks
./scripts/check.sh

# Or run individually:
black --check .
flake8
mypy golfcal2
pytest
```

4. Push changes:
```bash
git push origin feature/your-feature-name
```

## Project Structure

```
golfcal2/
├── docs/
│   ├── api/
│   ├── architecture/
│   └── development/
├── golfcal2/
│   ├── services/
│   │   ├── calendar/
│   │   ├── weather/
│   │   └── reservation/
│   ├── models/
│   ├── utils/
│   └── cli.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/
├── config.example.yaml
├── requirements.txt
└── requirements-dev.txt
```

## IDE Setup

### VSCode

1. Install recommended extensions:
   - Python
   - Pylance
   - Python Test Explorer
   - Python Docstring Generator

2. Configure settings:
```json
{
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "python.testing.pytestEnabled": true
}
```

### PyCharm

1. Configure interpreter:
   - Set project interpreter to virtual environment
   - Enable pytest as test runner

2. Configure code style:
   - Set Black as formatter
   - Enable format on save

## Debugging

1. Configure launch.json for VSCode:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "GolfCal2 CLI",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/golfcal2/cli.py",
            "args": ["list", "reservations"],
            "console": "integratedTerminal"
        }
    ]
}
```

2. Set up logging:
```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Common Issues

1. **Database Initialization**
   - Ensure SQLite3 is installed
   - Check database path in config
   - Verify write permissions

2. **Weather API**
   - Validate API keys
   - Check rate limits
   - Verify network connectivity

3. **Virtual Environment**
   - Ensure activation
   - Check Python version
   - Verify package installation

## Related Documentation

- [Testing Guide](testing.md)
- [Contributing Guidelines](contributing.md)
- [API Documentation](../api/README.md)
``` 