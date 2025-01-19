# Contributing to GolfCal2

Thank you for considering contributing to GolfCal2! This document provides guidelines and instructions for development.

## Development Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install development dependencies:
```bash
pip install -r requirements-dev.txt
```

3. Install pre-commit hooks:
```bash
pre-commit install
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints for all new code
- Write docstrings for functions and classes
- Keep functions focused and small
- Use meaningful variable names

## Testing

- Write tests for new features
- Maintain or improve test coverage
- Run tests before committing:
```bash
pytest
```

## Commit Guidelines

- Use clear, descriptive commit messages
- One logical change per commit
- Reference issue numbers when applicable

## Pull Request Process

1. Create a feature branch
2. Add tests for new functionality
3. Ensure all tests pass
4. Update documentation if needed
5. Submit PR with description of changes

## Release Process

1. Update version in `setup.py`
2. Update CHANGELOG.md
3. Create a new release tag
4. Build and test distribution
5. Update documentation if needed

## Code Review Guidelines

- Review for functionality
- Check for test coverage
- Verify documentation updates
- Look for security implications
- Consider performance impact 