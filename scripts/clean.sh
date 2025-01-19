#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Safety check - ensure we're in the right directory
if [ ! -f "setup.py" ] || [ ! -d "golfcal2" ]; then
    echo -e "${RED}Error: This script must be run from the project root directory${NC}"
    exit 1
fi

echo -e "${GREEN}Starting cleanup...${NC}"

# Ask for confirmation
read -p "$(echo -e ${YELLOW}This will remove all temporary files and caches. Continue? [y/N]${NC} )" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Cleanup cancelled${NC}"
    exit 1
fi

# Function to safely remove files
safe_remove() {
    if [ -e "$1" ]; then
        echo -e "${YELLOW}Removing $1...${NC}"
        rm -rf "$1"
    fi
}

# Function to safely clean directory
clean_dir() {
    if [ -d "$1" ]; then
        echo -e "${YELLOW}Cleaning $1...${NC}"
        rm -rf "$1"/*
        touch "$1/.gitkeep"
    else
        echo -e "${RED}Warning: Directory $1 not found${NC}"
    fi
}

echo -e "\n${YELLOW}Removing Python cache files...${NC}"
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete
find . -type f -name "*.pyd" -delete

echo -e "\n${YELLOW}Removing test cache...${NC}"
safe_remove .pytest_cache
safe_remove .coverage
safe_remove htmlcov
safe_remove .mypy_cache

echo -e "\n${YELLOW}Removing build artifacts...${NC}"
safe_remove build
safe_remove dist
safe_remove *.egg-info

echo -e "\n${YELLOW}Cleaning cache directories...${NC}"
clean_dir "data/cache"
clean_dir "logs"

echo -e "\n${GREEN}✨ Cleanup complete!${NC}" 