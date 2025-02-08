# Contributing to GolfCal2

Thank you for your interest in contributing to GolfCal2! This document provides guidelines and instructions for contributing.

## Development Setup

1. Fork and clone the repository:
```bash
git clone https://github.com/your-username/golfcal2.git
cd golfcal2
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install development dependencies:
```bash
pip install -e ".[dev]"
```

4. Install pre-commit hooks:
```bash
pre-commit install
```

## Development Workflow

1. Create a new branch for your feature or bugfix:
```bash
git checkout -b feature/your-feature-name
```

2. Make your changes, following our coding standards:
   - Use type hints for all function parameters and return values
   - Follow Google docstring format
   - Keep line length to 88 characters
   - Use meaningful variable names
   - Add tests for new functionality

3. Run tests and checks:
```bash
# Run tests
pytest

# Run type checking
mypy src/golfcal2

# Run linting
ruff check .
```

4. Commit your changes:
```bash
git add .
git commit -m "feat: Add your feature description"
```

Follow [Conventional Commits](https://www.conventionalcommits.org/) format:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `test:` for test changes
- `refactor:` for code refactoring
- `style:` for code style changes
- `chore:` for other changes

5. Push your changes and create a pull request:
```bash
git push origin feature/your-feature-name
```

## Code Style

- We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting
- Configuration is in `ruff.toml`
- Key style points:
  - 88 character line length
  - Use type hints
  - Follow Google docstring format
  - Use meaningful variable names
  - Keep functions focused and small
  - Add tests for new functionality

## Testing

- Write tests for all new functionality
- Place tests in the `tests/` directory
- Follow existing test structure and naming conventions
- Use pytest fixtures where appropriate
- Aim for high test coverage

## Documentation

- Update documentation for any changed functionality
- Add docstrings for new functions and classes
- Keep README.md up to date
- Update CHANGELOG.md for notable changes

## Pull Request Process

1. Update documentation
2. Add tests for new functionality
3. Ensure all tests pass
4. Update CHANGELOG.md
5. Request review from maintainers

## Getting Help

- Open an issue for questions
- Join our community discussions
- Contact maintainers directly for security issues

## Code of Conduct

Please note that this project is released with a [Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.

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