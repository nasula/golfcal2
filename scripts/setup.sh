#!/bin/bash

# Exit on error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check for required commands
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}Error: $1 is required but not installed.${NC}"
        exit 1
    fi
}

check_command python3
check_command pip
check_command git

echo -e "${GREEN}Setting up GolfCal2 development environment...${NC}"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv || { echo -e "${RED}Failed to create virtual environment${NC}"; exit 1; }
fi

# Activate virtual environment
source venv/bin/activate || { echo -e "${RED}Failed to activate virtual environment${NC}"; exit 1; }

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip || { echo -e "${RED}Failed to upgrade pip${NC}"; exit 1; }

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt || { echo -e "${RED}Failed to install requirements.txt${NC}"; exit 1; }
if [ -f "requirements-dev.txt" ]; then
    pip install -r requirements-dev.txt || { echo -e "${RED}Failed to install requirements-dev.txt${NC}"; exit 1; }
fi

# Create necessary directories
echo -e "${YELLOW}Creating necessary directories...${NC}"
mkdir -p data/cache logs

# Copy example configs if they don't exist
if [ ! -f "config.yaml" ] && [ -f "config.example.yaml" ]; then
    echo -e "${YELLOW}Copying example configuration...${NC}"
    cp config.example.yaml config.yaml
    echo -e "${GREEN}Created config.yaml - please edit it with your settings${NC}"
fi

# Initialize database
echo -e "${YELLOW}Initializing database...${NC}"
python -m golfcal2.db.init || { echo -e "${RED}Failed to initialize database${NC}"; exit 1; }

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
python -m golfcal2.db.migrate || { echo -e "${RED}Failed to run migrations${NC}"; exit 1; }

echo -e "${GREEN}Setup complete! To get started:${NC}"
echo -e "1. ${YELLOW}source venv/bin/activate${NC}"
echo -e "2. Edit config.yaml with your settings"
echo -e "3. Run ${YELLOW}./scripts/check.sh${NC} to verify everything works" 