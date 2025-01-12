"""Tests for the Iberian weather service implementation."""

import pytest
import requests_mock
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from golfcal2.services.iberian_weather_service import IberianWeatherService
from golfcal2.services.weather_types import WeatherData, WeatherResponse
from golfcal2.config.types import (
    AppConfig, GlobalConfig, WeatherApiConfig, ApiKeysConfig, LoggingConfig
)
from golfcal2.config.error_aggregator import init_error_aggregator, ErrorAggregationConfig

@pytest.fixture(autouse=True)
def setup_error_aggregator():
    """Initialize error aggregator for all tests."""
    error_config = ErrorAggregationConfig(
        enabled=True,
        report_interval=3600,
        error_threshold=5,
        time_threshold=300,
        categorize_by=['service', 'message', 'stack_trace']
    )
    init_error_aggregator(error_config)

@pytest.fixture
def mock_iberian_config():
    """Create a mock config for Iberian weather service."""
    global_config = {
        'timezone': 'Europe/Madrid',
        'api_keys': {
            'weather': {
                'aemet': 'test_api_key',
                'openweather': ''
            }
        }
    }
    
    users = {}  # Empty users dict for testing
    clubs = {}  # Empty clubs dict for testing
    
    return AppConfig(
        users=users,
        clubs=clubs,
        global_config=global_config,
        api_keys=global_config['api_keys'],
        timezone='Europe/Madrid',
        ics_dir='test_ics',
        config_dir='test_config',
        log_level='DEBUG',
        log_file=None
    )

@pytest.fixture
def mock_aemet_response(requests_mock):
    """
    Mock AEMET API responses, producing data structures closer to
    typical short-term vs. long-term AEMET forecasts.
    Now starts from 2024-01-14 so that 2024-01-15 is only day=1
    and still uses short-term (hourly) data.
    """

    municipality_data = [
        {
            "id": "id28079",
            "nombre": "Madrid",
            "latitud": "40.4",
            "longitud": "-3.7",
            "altitud": "667"
        },
        {
            "id": "id17233",  # PGA Catalunya
            "nombre": "Caldes de Malavella",
            "latitud": "41.8789",
            "longitud": "2.7649",
            "altitud": "84"
        }
    ]
    
    def create_forecast_url_response(data_url):
        return {
            "descripcion": "exito",
            "estado": 200,
            "datos": f"https://opendata.aemet.es/opendata/sh/{data_url}",
            "metadatos": "https://opendata.aemet.es/opendata/sh/mock_metadata"
        }

    def create_day_forecast(date_str, hour_start=0, hour_end=24, step=1):
        """Create a day forecast with hourly data."""
        # Parse the date to determine if this is the test day (2024-01-15)
        forecast_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        is_test_day = forecast_date.date() == datetime(2024, 1, 15).date()
        print(f"Creating forecast for {date_str}, is_test_day={is_test_day}")
        
        return {
            "prediccion": {
                "dia": [{
                    "fecha": date_str,
                    "temperatura": [
                        {"periodo": str(hour).zfill(2), "value": "15.5" if (is_test_day and hour == 12) else "21.5"}
                        for hour in range(hour_start, hour_end, step)
                    ],
                    "precipitacion": [
                        {"periodo": str(hour).zfill(2), "value": "0.0"}
                        for hour in range(hour_start, hour_end, step)
                    ],
                    "probPrecipitacion": [
                        {"periodo": "0006" if hour < 6 else "0612" if hour < 12 else "1218" if hour < 18 else "1824", "value": "30"}
                        for hour in range(hour_start, hour_end, step)
                    ],
                    "viento": [
                        {"periodo": str(hour).zfill(2), "velocidad": "18.72" if hour == 12 else "19.8", "direccion": "NE"}
                        for hour in range(hour_start, hour_end, step)
                    ],
                    "estadoCielo": [
                        {"periodo": str(hour).zfill(2), "value": "11n" if (hour < 6 or hour >= 20) else "11", "descripcion": "Despejado"}
                        for hour in range(hour_start, hour_end, step)
                    ],
                    "tormenta": [
                        {"periodo": str(hour).zfill(2), "probabilidad": "0"}
                        for hour in range(hour_start, hour_end, step)
                    ],
                    "orto": "07:58",
                    "ocaso": "18:28"
                }]
            }
        }

    # Shift "now" to 2024-01-14 so that 2024-01-15 is day=1 => short-term
    now = datetime(2024, 1, 14, 12, 0, tzinfo=timezone.utc)

    def create_forecast_data(municipality_id):
        # 7 days total: day=0,1 => short-term (hourly), day=2..6 => medium/long-term
        prediccion_dias = []
        for i in range(7):
            day_date = now + timedelta(days=i)
            print(f"Creating forecast for day {i}: {day_date.isoformat()}")
            # For short-term (first 48h), use hourly data
            if i < 2:
                day_data = create_day_forecast(day_date.strftime("%Y-%m-%dT%H:%M:%S"), hour_start=0, hour_end=24, step=1)
            else:
                # For medium/long-term, use 6-hour blocks
                day_data = create_day_forecast(day_date.strftime("%Y-%m-%dT%H:%M:%S"), hour_start=0, hour_end=24, step=6)
            prediccion_dias.extend(day_data["prediccion"]["dia"])

        return [{
            "elaborado": now.strftime("%Y-%m-%dT%H:00:00"),
            "nombre": "Madrid" if municipality_id == "28079" else "Caldes de Malavella",
            "provincia": "Madrid" if municipality_id == "28079" else "Girona",
            "prediccion": {
                "dia": prediccion_dias
            }
        }]

    base_url = "https://opendata.aemet.es/opendata/api"

    # Mock municipality lookup
    requests_mock.get(
        f"{base_url}/maestro/municipios",
        json=municipality_data
    )

    # For each municipality, register the "prediccion/especifica/municipio/horaria/{id}" + data
    for muni in municipality_data:
        muni_id = muni["id"][2:]  # remove "id" prefix
        forecast_url = f"mock_forecast_{muni_id}"

        requests_mock.get(
            f"{base_url}/prediccion/especifica/municipio/horaria/{muni_id}",
            json=create_forecast_url_response(forecast_url)
        )

        # Then mock the JSON data behind that "datos" link
        requests_mock.get(
            f"https://opendata.aemet.es/opendata/sh/{forecast_url}",
            json=create_forecast_data(muni_id)
        )

    return {
        "municipality": municipality_data,
        "now": now
    }

@pytest.fixture
def weather_service(mock_iberian_config, mock_aemet_response):
    """Create an Iberian weather service instance for testing."""
    return IberianWeatherService(
        local_tz=ZoneInfo("Europe/Madrid"),
        utc_tz=timezone.utc,
        config=mock_iberian_config
    )

class TestIberianWeatherService:
    """Test cases for IberianWeatherService."""

    def test_iberian_forecast_ranges(self, weather_service, mock_aemet_response):
        """
        Test forecast ranges for Iberian weather service:

        • The first 2 hours (hours 12..13) should be short-term hourly with the expected
          temperature of 15.5 at hour=12. 
        • The precipitation probability should be 30% at that hour=12 (matching mock data).
        """
        start_time = datetime(2024, 1, 15, 12, tzinfo=timezone.utc)
        end_time = start_time + timedelta(hours=2)
        print(f"\nTest requesting data from {start_time.isoformat()} to {end_time.isoformat()}")
        
        response = weather_service.get_weather(
            lat=40.4,  # Madrid
            lon=-3.7,
            start_time=start_time,
            end_time=end_time
        )

        assert isinstance(response, WeatherResponse)
        assert len(response.data) == 2, "Expect 2 hourly blocks covering 12:00..13:59"

        first_hour = response.data[0]
        print(f"First hour data: time={first_hour.elaboration_time.isoformat()}, temp={first_hour.temperature}")
        assert isinstance(first_hour, WeatherData)
        # Expect 15.5°C at hour=12 (per short-term fixture data)
        assert first_hour.temperature == pytest.approx(15.5, 0.1)

        # Expect probability_of_precipitation=30% at noon (from hourly data)
        assert first_hour.precipitation_probability == 30, (
            f"Expected 30% chance at {first_hour.elaboration_time}, got {first_hour.precipitation_probability}"
        )

        # Verify weather code mapping
        assert first_hour.symbol == "clearsky_day", (
            f"Expected 'clearsky_day', got {first_hour.symbol}"
        )

    def test_iberian_block_alignment(self, weather_service, mock_aemet_response):
        """Test block alignment for Iberian weather service."""
        start_time = datetime(2024, 1, 15, 12, 30, tzinfo=timezone.utc)  # 30 minutes past hour
        end_time = start_time + timedelta(hours=1, minutes=30)  # Spans two hours
        
        response = weather_service.get_weather(
            lat=40.4,
            lon=-3.7,
            start_time=start_time,
            end_time=end_time
        )
        
        assert len(response.data) == 2  # Should return two full hours
        
        # First block should start at the hour
        assert response.data[0].elaboration_time == datetime(2024, 1, 15, 12, tzinfo=timezone.utc)
        assert response.data[1].elaboration_time == datetime(2024, 1, 15, 13, tzinfo=timezone.utc)

    def test_iberian_mixed_intervals(self, weather_service, mock_aemet_response):
        """
        Test handling of mixed intervals. 
        • For hours < 48 from start_time, ensure hourly increments.
        • For hours >= 48, ensure 6-hour increments. 
        """
        start_time = datetime(2024, 1, 15, 12, tzinfo=timezone.utc)
        end_time = start_time + timedelta(days=3)  # 72 hours total

        response = weather_service.get_weather(
            lat=40.4,
            lon=-3.7,
            start_time=start_time,
            end_time=end_time
        )

        # Up to 48h from start_time => hourly
        max_hourly_index = min(48, len(response.data) - 1)
        for i in range(max_hourly_index - 1):
            diff = response.data[i+1].elaboration_time - response.data[i].elaboration_time
            msg = f"Expected hourly increments for first 48 hours, got {diff} at index={i}"
            assert diff == timedelta(hours=1), msg

        # After 48h => 6-hour blocks (if the fixture provides them).
        if len(response.data) > 48:
            for i in range(48, len(response.data) - 1):
                diff = response.data[i+1].elaboration_time - response.data[i].elaboration_time
                msg = f"Expected 6-hour increments after 48 hours, got {diff} at index={i}"
                assert diff == timedelta(hours=6), msg

    def test_iberian_timezone_handling(self, weather_service, mock_aemet_response):
        """
        Verify that the local time is used properly. For 14:00–16:00 local Madrid time,
        we expect 'clearsky_day' since it's daytime.
        """
        madrid_tz = ZoneInfo("Europe/Madrid")
        local_start = datetime(2024, 1, 15, 14, tzinfo=madrid_tz)
        local_end = local_start + timedelta(hours=2)

        response = weather_service.get_weather(
            lat=40.4,
            lon=-3.7,
            start_time=local_start,
            end_time=local_end
        )

        # Convert times to local
        local_times = [data.elaboration_time.astimezone(madrid_tz) for data in response.data]
        assert local_times[0].hour == 14
        assert local_times[-1].hour == 15

        for data in response.data:
            assert data.symbol == "clearsky_day", (
                f"Expected 'clearsky_day' at {data.elaboration_time}, got {data.symbol}"
            )

    def test_iberian_event_time_ranges(self, weather_service, mock_aemet_response):
        """Test weather data for different event time ranges."""
        test_ranges = [
            (timedelta(hours=1), 1),     # 1-hour event
            (timedelta(hours=3), 3),     # 3-hour event
            (timedelta(hours=6), 6),     # 6-hour event
            (timedelta(days=1), 24),     # 1-day event
        ]
        
        start_time = datetime(2024, 1, 15, 12, tzinfo=timezone.utc)
        
        for duration, expected_blocks in test_ranges:
            end_time = start_time + duration
            response = weather_service.get_weather(
                lat=40.4,
                lon=-3.7,
                start_time=start_time,
                end_time=end_time
            )
            
            assert len(response.data) == expected_blocks
            
            # Verify time progression
            for i in range(len(response.data)-1):
                time_diff = response.data[i+1].elaboration_time - response.data[i].elaboration_time
                assert time_diff == timedelta(hours=1)  # Hourly blocks for all ranges

    def test_iberian_partial_hour_alignment(self, weather_service, mock_aemet_response):
        """Test handling of partial hour alignments."""
        # Test with 15-minute offsets
        offsets = [15, 30, 45]
        
        for minutes in offsets:
            start_time = datetime(2024, 1, 15, 12, minutes, tzinfo=timezone.utc)
            end_time = start_time + timedelta(hours=1)
            
            response = weather_service.get_weather(
                lat=40.4,
                lon=-3.7,
                start_time=start_time,
                end_time=end_time
            )
            
            # Should always align to full hours
            assert response.data[0].elaboration_time.minute == 0
            assert len(response.data) == 2  # Should return two hours to cover the range

    def test_iberian_cross_day_event(self, weather_service, mock_aemet_response):
        """
        Verify that an event from 23:00–01:00 uses correct day/night weather codes.
        At 23:00 and 00:00 in January, both should be night conditions.
        """
        start_time = datetime(2024, 1, 15, 23, tzinfo=timezone.utc)
        end_time = start_time + timedelta(hours=2)

        response = weather_service.get_weather(
            lat=40.4,
            lon=-3.7,
            start_time=start_time,
            end_time=end_time
        )

        assert len(response.data) == 2
        # First hour => 23:00
        assert response.data[0].elaboration_time.hour == 23
        # Next hour => 00:00 next day
        assert response.data[1].elaboration_time.day == 16
        assert response.data[1].elaboration_time.hour == 0

        # Both hours should be night conditions in January
        assert response.data[0].symbol == "clearsky_night", (
            f"At 23:00, expected 'clearsky_night', got {response.data[0].symbol}"
        )
        assert response.data[1].symbol == "clearsky_night", (
            f"At 00:00, expected 'clearsky_night', got {response.data[1].symbol}"
        ) 