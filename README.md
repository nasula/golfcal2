# GolfCal2

A Python application for managing golf calendar and tee time reservations.

## Requirements

- Python 3.12 or higher
- Git

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/golfcal2.git
cd golfcal2
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Unix/macOS
# OR
.venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -e ".[dev]"
```

## Running Tests

Run tests with coverage:
```bash
pytest
```

## Code Quality

Run type checking:
```bash
mypy src/golfcal2
```

Run linting:
```bash
ruff check src/golfcal2
```

## Project Structure

```
golfcal2/
├── .github/
│   └── workflows/        # CI/CD workflows
├── src/
│   └── golfcal2/        # Main package
│       ├── api/         # API integration
│       │   └── crm/     # CRM implementations
│       └── ...
├── tests/               # Test files
├── .gitignore          # Git ignore rules
├── pyproject.toml      # Project configuration
└── README.md           # This file
```

## License

MIT License 