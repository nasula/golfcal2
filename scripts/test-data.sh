#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Track progress
STEPS_TOTAL=4
CURRENT_STEP=0

progress() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "\n${YELLOW}[$CURRENT_STEP/$STEPS_TOTAL] $1${NC}"
}

handle_error() {
    echo -e "${RED}Error: $1${NC}"
    exit 1
}

echo -e "${GREEN}Starting test data generation...${NC}"

# Ensure we're in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    handle_error "Virtual environment not activated. Please run: source venv/bin/activate"
fi

# Create test database
progress "Creating test database..."
python -m golfcal2.db.init --test || handle_error "Failed to initialize test database"

# Generate test weather data
progress "Generating weather test data..."
python -m golfcal2.tests.generate_weather_data || handle_error "Failed to generate weather data"

# Generate test reservations
progress "Generating test reservations..."
python -m golfcal2.tests.generate_reservations || handle_error "Failed to generate reservations"

# Generate test calendar events
progress "Generating test calendar events..."
python -m golfcal2.tests.generate_calendar_events || handle_error "Failed to generate calendar events"

echo -e "\n${GREEN}✨ Test data generation complete!${NC}"
echo -e "You can now run: ${YELLOW}./scripts/check.sh${NC} to verify everything works" 