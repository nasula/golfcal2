#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Track if any check failed
FAILED=0

echo -e "${GREEN}Running code quality checks...${NC}"

# Ensure we're in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${RED}Error: Virtual environment not activated. Please run:${NC}"
    echo -e "${YELLOW}source venv/bin/activate${NC}"
    exit 1
fi

# Run black check
echo -e "\n${YELLOW}Checking code formatting with black...${NC}"
if ! black --check .; then
    echo -e "${RED}❌ Black check failed${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ Black check passed${NC}"
fi

# Run flake8
echo -e "\n${YELLOW}Running flake8 linting...${NC}"
if ! flake8 .; then
    echo -e "${RED}❌ Flake8 check failed${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ Flake8 check passed${NC}"
fi

# Run mypy type checking
echo -e "\n${YELLOW}Running type checks with mypy...${NC}"
if ! mypy golfcal2; then
    echo -e "${RED}❌ Type check failed${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ Type check passed${NC}"
fi

# Run tests with coverage
echo -e "\n${YELLOW}Running tests with coverage...${NC}"
if ! pytest --cov=golfcal2 --cov-report=term-missing; then
    echo -e "${RED}❌ Tests failed${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ Tests passed${NC}"
fi

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}✨ All checks completed successfully!${NC}"
    exit 0
else
    echo -e "\n${RED}❌ Some checks failed. Please fix the issues and try again.${NC}"
    exit 1
fi 