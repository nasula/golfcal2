# Testing Guide

## Weather Service Tests

### Test Events Configuration

Test events are defined in `test_events.yaml` to cover different scenarios:

1. Different time ranges:
   - Tomorrow (hourly forecasts)
   - 3 days ahead (daily forecasts)
   - 7 days ahead (long-range)

2. Different times of day:
   - Morning (sunrise handling)
   - Afternoon (peak temperatures)
   - Evening (sunset handling)

3. Different regions:
   - Nordic (Oslo GC)
   - Spain mainland (PGA Catalunya)
   - Canary Islands (Costa Adeje)
   - Portugal (Praia D'El Rey)
   - Mediterranean (Lykia Links)

### Running Weather Tests

```bash
# Basic test with all events
python -m golfcal --dev process

# Verbose mode for debugging
python -m golfcal --dev -v process

# Test specific user's events
python -m golfcal --dev -u Jarkko process
```

## CRM Integration Tests

### Test Setup

1. Create test configuration in `clubs.json`:
```json
{
    "Test Club": {
        "type": "test_crm",
        "name": "Test Golf Club",
        "url": "http://localhost:8000"
    }
}
```

2. Create test data fixtures:
```python
@pytest.fixture
def test_reservation():
    return {
        "dateTimeStart": "2024-01-01 10:00:00",
        "players": [
            {
                "firstName": "Test",
                "familyName": "User",
                "handicap": 15.4
            }
        ]
    }
```

### Running CRM Tests

```bash
# Run all CRM tests
pytest tests/test_crm/

# Run specific CRM implementation tests
pytest tests/test_crm/test_wise_golf.py

# Run with coverage
pytest --cov=api.crm tests/test_crm/
```

### Test Cases

1. Authentication:
   - Successful login
   - Invalid credentials
   - Token expiry/refresh
   - Rate limiting

2. Reservation Fetching:
   - Basic reservation list
   - Empty response
   - Pagination handling
   - Error responses

3. Data Parsing:
   - Complete reservation data
   - Missing optional fields
   - Invalid data formats
   - Timezone handling 