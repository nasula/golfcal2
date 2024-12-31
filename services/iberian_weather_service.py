"""Iberian weather service implementation."""

import os
import json
import time
import pytz
import yaml
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

import requests
import math

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.services.weather_service import WeatherService, WeatherCode, get_weather_symbol
from golfcal2.services.weather_database import WeatherDatabase
from golfcal2.services.weather_schemas import IBERIAN_SCHEMA

class IberianWeatherService(WeatherService, LoggerMixin):
    """Weather service using AEMET (Spain) and IPMA (Portugal) APIs."""
    
    def __init__(self, local_tz, utc_tz):
        """Initialize service with API endpoints and credentials."""
        WeatherService.__init__(self)
        LoggerMixin.__init__(self)
        
        # Load API keys from config
        self.aemet_api_key = self._load_aemet_api_key()
        
        # AEMET API (Spain)
        self.aemet_endpoint = 'https://opendata.aemet.es/opendata/api'
        self.aemet_headers = {
            'api_key': self.aemet_api_key,
            'Accept': 'application/json',
            'User-Agent': 'GolfCal/1.0 github.com/jahonen/golfcal jarkko.ahonen@iki.fi',
        }
        
        # IPMA API (Portugal)
        self.ipma_endpoint = 'https://api.ipma.pt/open-data/observation/meteorology/stations'
        self.ipma_headers = {
            'Accept': 'application/json',
            'User-Agent': 'GolfCal/1.0 github.com/jahonen/golfcal jarkko.ahonen@iki.fi',
        }
        
        # Timezone settings
        self.utc_tz = utc_tz
        self.local_tz = local_tz
        self.spain_tz = pytz.timezone('Europe/Madrid')
        self.portugal_tz = pytz.timezone('Europe/Lisbon')
        
        # Track API calls
        self._last_api_call = None
        self._min_call_interval = timedelta(seconds=1)
        
        # Initialize database
        self.db = WeatherDatabase('iberian_weather', IBERIAN_SCHEMA)

    def get_weather(self, lat: float, lon: float, date: datetime, duration_minutes: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get weather data for location and time."""
        try:
            # Calculate time range
            start_time = date.replace(minute=0, second=0, microsecond=0)
            if duration_minutes:
                end_time = start_time + timedelta(minutes=duration_minutes)
            else:
                end_time = start_time + timedelta(hours=4)  # Default to 4 hours

            # Generate list of target hours
            target_hours = []
            current = start_time
            while current <= end_time:
                target_hours.append(current)
                current += timedelta(hours=1)

            # Define fields we want to retrieve
            fields = [
                'air_temperature',
                'precipitation_amount',
                'wind_speed',
                'wind_from_direction',
                'probability_of_precipitation',
                'probability_of_thunder',
                'summary_code'
            ]

            # Check cache first
            cached_data = {}
            for target_time in target_hours:
                time_str = target_time.strftime('%Y-%m-%dT%H:%M:%SZ')
                cached = self.db.get_weather_data(
                    f"{lat},{lon}",      # location
                    [time_str],          # times (as a list)
                    'next_1_hours',      # data_type
                    fields              # fields
                )
                if cached and time_str in cached:
                    cached_data[time_str] = {
                        'data_type': 'next_1_hours',
                        'air_temperature': cached[time_str]['air_temperature'],
                        'precipitation_amount': cached[time_str]['precipitation_amount'],
                        'wind_speed': cached[time_str]['wind_speed'],
                        'wind_from_direction': cached[time_str]['wind_from_direction'],
                        'probability_of_precipitation': cached[time_str]['probability_of_precipitation'],
             'probability_of_thunder': cached[time_str]['probability_of_thunder'],
            'symbol_code': cached[time_str]['summary_code']  # Map summary_code to symbol_code
        }

            # If we have all data in cache, use it
            if len(cached_data) == len(target_hours):
                self.logger.debug("Using cached weather data")
                weather_data = cached_data
            else:
                # Determine if we're in Portugal or Spain based on coordinates
                is_portugal = -9.5 <= lon <= -6.2
                
                if is_portugal:
                    # IPMA API (Portugal)
                    api_data = self._fetch_ipma_data(lat, lon)
                    if not api_data:
                        return None
                    
                    # Parse and store in cache
                    parsed_data = self._parse_ipma_data(api_data, start_time, duration_minutes)
                    if not parsed_data:
                        return None
                    
                    # Calculate expiry based on IPMA update schedule
                    expires = self._calculate_ipma_expiry(datetime.now(self.utc_tz))
                else:
                    # AEMET API (Spain)
                    municipality_code = self._get_municipality_code(lat, lon)
                    if not municipality_code:
                        return None
                    
                    # Fetch from API if not in cache
                    api_data = self._fetch_aemet_data(municipality_code)
                    if not api_data or not isinstance(api_data, list) or len(api_data) == 0:
                        return None
                    
                    # Parse and store in cache
                    parsed_data = self._parse_aemet_data(api_data, start_time, duration_minutes)
                    if not parsed_data:
                        return None
                    
                    # Calculate expiry based on AEMET elaboration date
                    elaboration_date = api_data[0].get('elaborado', '') if api_data else ''
                    expires = self._calculate_aemet_expiry(elaboration_date)
                
                # Convert to database format and store
                db_entries = []
                for time_str, data in parsed_data.items():
                    entry = {
                        'location': f"{lat},{lon}",
                        'time': time_str,
                        'data_type': 'next_1_hours',
                        'air_temperature': data['air_temperature'],
                        'precipitation_amount': data['precipitation_amount'],
                        'wind_speed': data['wind_speed'],
                        'wind_from_direction': data['wind_from_direction'],
                        'probability_of_precipitation': data['probability_of_precipitation'],
                        'probability_of_thunder': data['probability_of_thunder'],
                        'summary_code': data.get('symbol_code')
                    }
                    db_entries.append(entry)
                
                # Store in cache with appropriate expiry
                self.db.store_weather_data(db_entries, expires=expires)
                
                weather_data = parsed_data

            # Convert cached data to forecast format
            forecasts = []
            for target_time in target_hours:
                time_str = target_time.strftime('%Y-%m-%dT%H:%M:%SZ')
                if time_str in weather_data:
                    data = weather_data[time_str]
                    forecast = {
                        'time': target_time,
                        'data_type': data['data_type'],
                        'symbol_code': data['symbol_code'],
                        'air_temperature': data['air_temperature'],
                        'precipitation_amount': data['precipitation_amount'],
                        'wind_speed': data['wind_speed'],
                        'wind_from_direction': data['wind_from_direction'],
                        'probability_of_precipitation': data['probability_of_precipitation'],
                        'probability_of_thunder': data['probability_of_thunder']
                    }
                    forecasts.append(forecast)

            if not forecasts:
                return None

            # Return first forecast's data as the main weather data
            first_forecast = forecasts[0]
            return {
                'forecasts': forecasts,  # Include all forecasts for time block formatting
                'time': first_forecast['time'],  # Add time field
                'data_type': first_forecast['data_type'],
                'symbol_code': first_forecast['symbol_code'],
                'air_temperature': first_forecast['air_temperature'],
                'precipitation_amount': first_forecast['precipitation_amount'],
                'wind_speed': first_forecast['wind_speed'],
                'wind_from_direction': first_forecast['wind_from_direction'],
                'probability_of_precipitation': first_forecast['probability_of_precipitation'],
                'probability_of_thunder': first_forecast['probability_of_thunder']
        }


        except Exception as e:
            self.logger.error(f"Failed to get Iberian weather for {lat},{lon}: {e}", exc_info=True)
            return None
        
    def _init_db(self):
        """Initialize the database tables."""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Create weather stations table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS weather_stations (
                        id TEXT PRIMARY KEY,
                        latitude REAL,
                        longitude REAL,
                        name TEXT,
                        province TEXT,
                        municipality_code TEXT,
                        last_updated TIMESTAMP
                    )
                ''')
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _load_aemet_api_key(self) -> Optional[str]:
        """Load AEMET API key from config file."""
        try:
            # Try environment variable first
            api_key = os.getenv('AEMET_API_KEY')
            if api_key:
                return api_key

            # Try config file
            config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    if config and 'api_keys' in config and 'weather' in config['api_keys'] and 'aemet' in config['api_keys']['weather']:
                        api_key = config['api_keys']['weather']['aemet']
                        if api_key:  # Check if it's not empty
                            return api_key
            
            self.logger.error("AEMET API key not configured in environment or config file")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to load AEMET API key: {e}")
            return None

    def _fetch_aemet_data(self, municipality_code: str) -> Optional[Dict[str, Any]]:
        """Fetch weather data from AEMET API."""
        try:
            # Rate limiting
            if self._last_api_call:
                elapsed = datetime.now() - self._last_api_call
                if elapsed < self._min_call_interval:
                    sleep_time = (self._min_call_interval - elapsed).total_seconds()
                    self.logger.debug(f"Rate limit: sleeping for {sleep_time} seconds")
                    time.sleep(sleep_time)
            
            # First request to get data URL
            url = f"{self.aemet_endpoint}/prediccion/especifica/municipio/horaria/{municipality_code}"
            self.logger.debug(f"AEMET URL: {url}")
            
            response = requests.get(url, headers=self.aemet_headers)
            response.raise_for_status()
            
            # Parse response to get data URL
            response_data = response.json()
            if not isinstance(response_data, dict) or 'datos' not in response_data:
                self.logger.error(f"Invalid response format: {response_data}")
                return None
            
            # Get actual data from the provided URL
            data_url = response_data['datos']
            self.logger.debug(f"AEMET data URL: {data_url}")
            
            data_response = requests.get(data_url, headers=self.aemet_headers)
            data_response.raise_for_status()
            
            self._last_api_call = datetime.now()
            return data_response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"AEMET API request failed: {e}", exc_info=True)
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse AEMET response: {e}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"Failed to fetch AEMET data: {e}", exc_info=True)
            return None
    
    def _get_municipality_code(self, lat: float, lon: float) -> Optional[str]:
        """Get municipality code for given coordinates."""
        try:
            # Find the nearest station from the database
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if we need to refresh the stations
                cursor.execute('SELECT COUNT(*), MIN(last_updated) FROM weather_stations')
                count, last_updated = cursor.fetchone()
                
                # Make timezone-aware comparison
                now = datetime.now(self.utc_tz)
                needs_refresh = True
                if count > 0 and last_updated:
                    try:
                        last_updated_dt = datetime.fromisoformat(last_updated)
                        if not last_updated_dt.tzinfo:
                            last_updated_dt = last_updated_dt.replace(tzinfo=self.utc_tz)
                        needs_refresh = last_updated_dt < now - timedelta(days=30)
                    except ValueError:
                        self.logger.warning(f"Invalid last_updated timestamp: {last_updated}")
                        needs_refresh = True
                
                if needs_refresh:
                    self._refresh_stations()
                
                # Rest of the method remains unchanged...
                cursor.execute('''
                    SELECT id, name, latitude, longitude, municipality_code,
                        (latitude - ?)*(latitude - ?) + (longitude - ?)*(longitude - ?) as distance
                    FROM weather_stations
                    ORDER BY distance ASC
                    LIMIT 1
                ''', (lat, lat, lon, lon))
                
                result = cursor.fetchone()
                if result:
                    station_id, name, station_lat, station_lon, muni_code, distance = result
                    self.logger.debug(
                        f"Found nearest station: {name} ({station_lat}, {station_lon}) "
                        f"distance: {math.sqrt(distance)}"
                    )
                    return muni_code or "17001"  # Default to Girona if no specific code
                
                self.logger.error(f"No station found near coordinates {lat},{lon}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get municipality code: {e}", exc_info=True)
            return None

    def _dms_to_decimal(self, dms_str: str) -> float:
        """Convert DMS (Degrees Minutes Seconds) coordinate string to decimal degrees.
        
        Examples:
            "411458N" -> 41.24944 (41°14'58"N)
            "035749W" -> -3.96361 (3°57'49"W)
        """
        try:
            if not dms_str or len(dms_str) < 7:
                raise ValueError(f"Invalid DMS format: {dms_str}")
            
            direction = dms_str[-1].upper()
            if direction not in 'NSEW':
                raise ValueError(f"Invalid direction: {direction}")
            
            # Extract degrees, minutes, seconds
            nums = dms_str[:-1]
            if len(nums) == 6:
                degrees = int(nums[0:2])
                minutes = int(nums[2:4])
                seconds = int(nums[4:6])
            else:
                degrees = int(nums[0:3])
                minutes = int(nums[3:5])
                seconds = int(nums[5:7])
            
            # Convert to decimal degrees
            decimal = degrees + minutes/60 + seconds/3600
            
            # Make negative for West/South
            if direction in 'WS':
                decimal = -decimal
            
            return decimal
            
        except Exception as e:
            raise ValueError(f"Failed to parse DMS coordinate '{dms_str}': {e}")

    def _refresh_stations(self):
        """Refresh weather stations from AEMET API."""
        try:
            # Rate limiting
            if self._last_api_call:
                elapsed = datetime.now() - self._last_api_call
                if elapsed < self._min_call_interval:
                    sleep_time = (self._min_call_interval - elapsed).total_seconds()
                    self.logger.debug(f"Rate limit: sleeping for {sleep_time} seconds")
                    time.sleep(sleep_time)
            
            # First request to get data URL
            url = f"{self.aemet_endpoint}/maestro/municipios"
            self.logger.debug(f"AEMET stations URL: {url}")
            
            response = requests.get(url, headers=self.aemet_headers)
            response.raise_for_status()
            
            # Parse response to get data URL
            response_data = response.json()
            if not isinstance(response_data, dict) or 'datos' not in response_data:
                self.logger.error(f"Invalid response format: {response_data}")
                return
            
            # Get actual data from the provided URL
            data_url = response_data['datos']
            self.logger.debug(f"AEMET data URL: {data_url}")
            
            data_response = requests.get(data_url, headers=self.aemet_headers)
            data_response.raise_for_status()
            
            municipalities = data_response.json()
            if not isinstance(municipalities, list):
                self.logger.error(f"Invalid municipalities data format: {municipalities}")
                return
            
            # Store in database
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Clear existing stations
                cursor.execute('DELETE FROM weather_stations')
                
                # Insert new stations
                for muni in municipalities:
                    try:
                        cursor.execute('''
                            INSERT INTO weather_stations (
                                id, latitude, longitude, name, province,
                                municipality_code, last_updated
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            muni.get('id', muni.get('municipio', '')),
                            float(muni.get('latitud_dec', 0)),
                            float(muni.get('longitud_dec', 0)),
                            muni.get('nombre', ''),
                            muni.get('provincia', ''),
                            muni.get('municipio', ''),
                            datetime.now(self.utc_tz).isoformat()
                        ))
                    except (ValueError, KeyError) as e:
                        self.logger.warning(f"Failed to process municipality: {e}")
                        continue
                
                conn.commit()
            
            self._last_api_call = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Failed to refresh stations: {e}", exc_info=True)
            raise
    
    def _get_aemet_weather(
        self, 
        club: str, 
        teetime: datetime, 
        coordinates: Dict[str, float], 
        duration_minutes: Optional[int] = None
    ) -> Optional[str]:
        """Get weather data from AEMET (Spain)."""
        if not self.aemet_api_key:
            self.logger.error("AEMET API key not configured")
            return None
            
        try:
            # Respect rate limits
            now = datetime.now()
            if self._last_api_call and (now - self._last_api_call) < self._min_call_interval:
                sleep_time = (self._min_call_interval - (now - self._last_api_call)).total_seconds()
                time.sleep(sleep_time)
            
            # Get municipality code for the coordinates
            station_code = self._get_municipality_code(coordinates['lat'], coordinates['lon'])
            if not station_code:
                self.logger.error(f"No station code found for coordinates: {coordinates}")
                return None
            
            # Map station to municipality code
            # PGA Catalunya and Girona Airport are in Caldes de Malavella
            municipality_code = "17033"  # Caldes de Malavella
            
            # Choose endpoint based on forecast date
            days_ahead = (teetime.date() - datetime.now().date()).days
            if days_ahead <= 2:
                endpoint = "prediccion/especifica/municipio/horaria"
            else:
                endpoint = "prediccion/especifica/municipio/diaria"
            
            # Get forecast for municipality
            url = f"{self.aemet_endpoint}/{endpoint}/{municipality_code}"
            headers = {
                'Accept': 'application/json',
                'api_key': self.aemet_api_key,
                'User-Agent': 'GolfCal/1.0 github.com/jahonen/golfcal jarkko.ahonen@iki.fi',
                'Cache-Control': 'no-cache'
            }
            
            self.logger.debug(f"Using AEMET endpoint for {days_ahead} days ahead: {endpoint}")
            
            # Try up to 3 times with increasing delays
            max_retries = 3
            retry_delay = 1
            
            for attempt in range(max_retries):
                try:
                    self.logger.debug(f"AEMET URL (attempt {attempt + 1}/{max_retries}): {url}")
                    response = requests.get(url, headers=headers, timeout=10)
                    self._last_api_call = datetime.now()
                    
                    if response.status_code == 200:
                        break
                    elif response.status_code == 429:  # Too Many Requests
                        if attempt < max_retries - 1:
                            sleep_time = retry_delay * (2 ** attempt)
                            self.logger.warning(f"Rate limited, waiting {sleep_time}s before retry")
                            time.sleep(sleep_time)
                            continue
                    else:
                        self.logger.error(f"AEMET API request failed: {response.status_code}")
                        self.logger.debug(f"Response content: {response.text}")
                        return None
                        
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    if attempt < max_retries - 1:
                        sleep_time = retry_delay * (2 ** attempt)
                        self.logger.warning(f"Request failed, retrying in {sleep_time}s: {e}")
                        time.sleep(sleep_time)
                        continue
                    raise
            
            if response.status_code != 200:
                self.logger.error(f"All AEMET API attempts failed")
                return None
                
            # AEMET uses a two-step process - first get the data URL
            data_url = response.json().get('datos')
            if not data_url:
                self.logger.error("No data URL in AEMET response")
                return None
                
            # Get actual weather data with the same headers
            weather_response = requests.get(data_url, headers=headers, timeout=10)
            if weather_response.status_code != 200:
                self.logger.error(f"AEMET weather data request failed: {weather_response.status_code}")
                self.logger.debug(f"Response content: {weather_response.text}")
                return None
            
            # Parse and format weather data
            if days_ahead <= 2:
                weather_data = self._parse_aemet_data(weather_response.json(), teetime, duration_minutes)
            else:
                weather_data = self._parse_aemet_daily_data(weather_response.json(), teetime, duration_minutes)
            
            return weather_data
            
        except Exception as e:
            self.logger.error(f"Failed to get AEMET weather: {e}")
            return None
    
    def _get_ipma_weather(
        self, 
        club: str, 
        teetime: datetime, 
        coordinates: Dict[str, float], 
        duration_minutes: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get weather data from IPMA (Portugal)."""
        try:
            # Respect rate limits
            now = datetime.now()
            if self._last_api_call and (now - self._last_api_call) < self._min_call_interval:
                sleep_time = (self._min_call_interval - (now - self._last_api_call)).total_seconds()
                time.sleep(sleep_time)
            
            # First get the list of locations
            locations_url = f"{self.ipma_endpoint}/distrits-islands"
            self.logger.debug(f"IPMA locations URL: {locations_url}")
            locations_response = requests.get(
                locations_url,
                headers=self.ipma_headers
            )
            self._last_api_call = datetime.now()
            
            if locations_response.status_code != 200:
                self.logger.error(f"IPMA locations API request failed: {locations_response.status_code}")
                return None
            
            # Find the nearest location
            locations_data = locations_response.json()
            locations = locations_data['data']  # Access the 'data' field
            nearest_location = None
            min_distance = float('inf')
            
            for location in locations:
                dist = self._haversine_distance(
                    coordinates['lat'], coordinates['lon'],
                    float(location['latitude']), float(location['longitude'])
                )
                if dist < min_distance:
                    min_distance = dist
                    nearest_location = location
            
            if not nearest_location:
                self.logger.error("No IPMA location found")
                return None
            
            # Get forecast for the nearest location
            location_id = nearest_location['globalIdLocal']
            url = f"{self.ipma_endpoint}/forecast/meteorology/cities/daily/{location_id}"
            self.logger.debug(f"IPMA forecast URL: {url}")
            response = requests.get(
                url,
                headers=self.ipma_headers
            )
            self._last_api_call = datetime.now()
            
            if response.status_code != 200:
                self.logger.error(f"IPMA forecast API request failed: {response.status_code}, URL: {response.url}")
                return None
                
            # Parse and format weather data
            weather_data = self._parse_ipma_data(response.json(), teetime, duration_minutes)
            return weather_data
            
        except Exception as e:
            self.logger.error(f"Failed to get IPMA weather: {e}")
            return None
    
    def _parse_aemet_data(
        self, 
        data: List[Dict[str, Any]], 
        teetime: datetime, 
        duration_minutes: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Parse AEMET weather data."""
        try:
            parsed_data = {}
            event_duration = duration_minutes or 180  # Default to 3 hours
            end_time = teetime + timedelta(minutes=event_duration)
            
            self.logger.debug(f"Parsing AEMET data for time range: {teetime} to {end_time}")
            
            if not data or not isinstance(data, list) or len(data) == 0:
                self.logger.error(f"Invalid AEMET data format: {data}")
                return None
                
            prediccion = data[0].get('prediccion', {})
            if not prediccion:
                self.logger.error("No 'prediccion' data in AEMET response")
                return None
                
            dias = prediccion.get('dia', [])
            if not dias:
                self.logger.error("No 'dia' data in AEMET prediccion")
                return None
                
            self.logger.debug(f"Found {len(dias)} days in forecast")
            
            # AEMET returns hourly data
            for forecast in dias:
                # Get the date (handle full timestamp format)
                date_str = forecast['fecha']
                if 'T' in date_str:  # Handle "YYYY-MM-DDT00:00:00" format
                    date_str = date_str.split('T')[0]
                date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=self.spain_tz)
                
                self.logger.debug(f"Processing forecast for date: {date}")
                
                # Process hourly data
                temperatura = forecast.get('temperatura', [])
                precipitacion = forecast.get('precipitacion', [])
                viento = forecast.get('viento', [])
                estadoCielo = forecast.get('estadoCielo', [])
                
                self.logger.debug(
                    f"Found data points: "
                    f"temperatura={len(temperatura)}, "
                    f"precipitacion={len(precipitacion)}, "
                    f"viento={len(viento)}, "
                    f"estadoCielo={len(estadoCielo)}"
                )
                
                for hour_data in temperatura:
                    try:
                        # Get hour and create datetime
                        hour = int(hour_data['periodo'])
                        forecast_time = date.replace(hour=hour, minute=0)
                        
                        self.logger.debug(f"Processing hour {hour} -> {forecast_time}")
                        
                        # Only include forecasts within event timeframe
                        if teetime <= forecast_time <= end_time:
                            # Find matching data for this hour
                            precip = next((x for x in precipitacion if x['periodo'] == hour_data['periodo']), {})
                            wind = next((x for x in viento if x['periodo'] == hour_data['periodo']), {})
                            sky = next((x for x in estadoCielo if x['periodo'] == hour_data['periodo']), {})
                            
                            parsed_data[forecast_time.isoformat()] = {
                                'air_temperature': float(hour_data.get('value', 0)),
                                'precipitation_amount': float(precip.get('value', 0)),
                                'wind_speed': float(wind.get('velocidad', 0)),
                                'wind_from_direction': float(wind.get('direccion', 0)),
                                'probability_of_precipitation': float(precip.get('probabilidad', 0)),
                                'probability_of_thunder': 0.0,  # AEMET doesn't provide this
                                'summary_code': self._convert_aemet_code(sky.get('value', ''))
                            }
                            
                            self.logger.debug(
                                f"Added forecast for {forecast_time.isoformat()}: "
                                f"temp={hour_data.get('value')}°C, "
                                f"precip={precip.get('value')}mm ({precip.get('probabilidad')}%), "
                                f"wind={wind.get('velocidad')}m/s, "
                                f"sky={sky.get('value')}"
                            )
                            
                    except (ValueError, KeyError) as e:
                        self.logger.warning(f"Failed to parse hour data: {e}")
                        continue
            
            if not parsed_data:
                self.logger.warning(f"No forecasts found between {teetime} and {end_time}")
            else:
                self.logger.info(f"Found {len(parsed_data)} forecasts")
            
            return parsed_data
            
        except Exception as e:
            self.logger.error(f"Failed to parse AEMET data: {e}")
            return None
    
    def _parse_ipma_data(
        self, 
        response_data: Dict[str, Any], 
        teetime: datetime, 
        duration_minutes: Optional[int] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Parse IPMA weather data into standard format."""
        weather_data = {}
        
        for forecast in response_data['data']:
            # Parse the forecast date
            forecast_date = datetime.strptime(forecast['forecastDate'], '%Y-%m-%d').replace(
                hour=teetime.hour,
                minute=teetime.minute,
                tzinfo=self.portugal_tz
            )
            
            # Skip if not the date we're looking for
            if forecast_date.date() != teetime.astimezone(self.portugal_tz).date():
                continue
                
            weather_data[forecast_date.isoformat()] = {
                'summary_code': self._convert_ipma_code(forecast['idWeatherType']),
                'air_temperature': (float(forecast['tMin']) + float(forecast['tMax'])) / 2,  # Use average of min and max
                'precipitation_amount': 0.0,  # No precipitation class in this response
                'wind_speed': self._convert_ipma_wind_class(forecast['classWindSpeed']),
                'wind_from_direction': self._convert_ipma_wind_direction(forecast['predWindDir']),
                'probability_of_precipitation': float(forecast['precipitaProb']) / 100 if 'precipitaProb' in forecast else 0.0,
            }
            
        return weather_data
    
    def _convert_aemet_code(self, aemet_code: str) -> str:
        """Convert AEMET weather codes to standard codes."""
        code_map = {
            '11': WeatherCode.CLEAR_DAY,
            '11n': WeatherCode.CLEAR_NIGHT,
            '12': WeatherCode.FAIR_DAY,
            '12n': WeatherCode.FAIR_NIGHT,
            '13': WeatherCode.PARTLY_CLOUDY_DAY,
            '13n': WeatherCode.PARTLY_CLOUDY_NIGHT,
            '14': WeatherCode.CLOUDY,
            '15': WeatherCode.LIGHT_RAIN,
            '16': WeatherCode.RAIN,
            '17': WeatherCode.HEAVY_RAIN,
            '23': WeatherCode.RAIN_AND_THUNDER,
            '24': WeatherCode.HEAVY_RAIN_AND_THUNDER,
            '33': WeatherCode.LIGHT_SNOW,
            '34': WeatherCode.SNOW,
            '35': WeatherCode.HEAVY_SNOW,
            '36': WeatherCode.LIGHT_SLEET,
            '37': WeatherCode.HEAVY_SLEET,
            '43': WeatherCode.FOG,
            '44': WeatherCode.FOG,
            '45': WeatherCode.FOG
        }
        return code_map.get(aemet_code, WeatherCode.CLOUDY)
    
    def _convert_ipma_code(self, ipma_code: int) -> str:
        """Convert IPMA weather codes to standard codes."""
        code_map = {
            1: WeatherCode.CLEAR_DAY,
            2: WeatherCode.FAIR_DAY,
            3: WeatherCode.PARTLY_CLOUDY_DAY,
            4: WeatherCode.CLOUDY,
            5: WeatherCode.LIGHT_RAIN,
            6: WeatherCode.RAIN,
            7: WeatherCode.HEAVY_RAIN,
            8: WeatherCode.RAIN_AND_THUNDER,
            9: WeatherCode.HEAVY_RAIN_AND_THUNDER,
            10: WeatherCode.LIGHT_SNOW,
            11: WeatherCode.SNOW,
            12: WeatherCode.HEAVY_SNOW,
            13: WeatherCode.LIGHT_SLEET,
            14: WeatherCode.HEAVY_SLEET,
            15: WeatherCode.FOG
        }
        return code_map.get(ipma_code, WeatherCode.CLOUDY)
    
    def _format_weather_summary(self, weather_data: Dict[str, Dict[str, Any]], teetime: Optional[datetime] = None) -> str:
        """Format weather data into a human-readable summary."""
        return format_weather_summary(weather_data, 1, teetime)
    
    def _fetch_weather_data(self, lat: float, lon: float, times: List[str], interval: int) -> Dict[str, Dict[str, Any]]:
        """Fetch weather data from AEMET/IPMA APIs."""
        # Determine country based on coordinates
        if -9.5 <= lon <= -6.2:  # Portugal
            return self._get_ipma_weather(times, lat, lon, interval)
        else:  # Spain
            return self._get_aemet_weather(times, lat, lon, interval)
    
    def _convert_ipma_wind_class(self, wind_class: int) -> float:
        """Convert IPMA wind class to m/s."""
        # Wind classes (Beaufort scale):
        # 1: 0-5 km/h (0-1.4 m/s)
        # 2: 6-15 km/h (1.7-4.2 m/s)
        # 3: 16-35 km/h (4.4-9.7 m/s)
        # 4: >35 km/h (>9.7 m/s)
        wind_map = {
            1: 0.7,   # Average of 0-1.4
            2: 3.0,   # Average of 1.7-4.2
            3: 7.0,   # Average of 4.4-9.7
            4: 11.0   # Above 9.7
        }
        return wind_map.get(wind_class, 0.0)

    def _convert_ipma_wind_direction(self, direction: str) -> float:
        """Convert IPMA wind direction to degrees."""
        direction_map = {
            'N': 0.0,
            'NE': 45.0,
            'E': 90.0,
            'SE': 135.0,
            'S': 180.0,
            'SW': 225.0,
            'W': 270.0,
            'NW': 315.0
        }
        return direction_map.get(direction, 0.0)

    def _convert_ipma_precip_class(self, precip_class: int) -> float:
        """Convert IPMA precipitation class to mm."""
        # Precipitation classes:
        # 1: 0.1-1 mm/h
        # 2: 1-5 mm/h
        # 3: 5-10 mm/h
        # 4: >10 mm/h
        precip_map = {
            0: 0.0,   # No precipitation
            1: 0.5,   # Average of 0.1-1
            2: 3.0,   # Average of 1-5
            3: 7.5,   # Average of 5-10
            4: 12.0   # Above 10
        }
        return precip_map.get(precip_class, 0.0)

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the great circle distance between two points on Earth."""
        R = 6371  # Earth's radius in kilometers

        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c  # Distance in kilometers

    def _parse_aemet_daily_data(
        self, 
        data: List[Dict[str, Any]], 
        teetime: datetime, 
        duration_minutes: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Parse AEMET daily forecast data."""
        try:
            parsed_data = {}
            event_duration = duration_minutes or 180  # Default to 3 hours
            end_time = teetime + timedelta(minutes=event_duration)
            
            self.logger.debug(f"Parsing AEMET daily data for time range: {teetime} to {end_time}")
            
            if not data or not isinstance(data, list) or len(data) == 0:
                self.logger.error(f"Invalid AEMET data format: {data}")
                return None
                
            prediccion = data[0].get('prediccion', {})
            if not prediccion:
                self.logger.error("No 'prediccion' data in AEMET response")
                return None
                
            dias = prediccion.get('dia', [])
            if not dias:
                self.logger.error("No 'dia' data in AEMET prediccion")
                return None
                
            self.logger.debug(f"Found {len(dias)} days in forecast")
            
            # Find the forecast for our target date
            target_date = teetime.date()
            for forecast in dias:
                date_str = forecast['fecha']
                if 'T' in date_str:
                    date_str = date_str.split('T')[0]
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                if date == target_date:
                    self.logger.debug(f"Found forecast for target date: {date}")
                    
                    # Get temperature for morning/afternoon
                    temp_data = forecast.get('temperatura', {})
                    morning_temp = float(temp_data.get('manana', 0))
                    afternoon_temp = float(temp_data.get('tarde', 0))
                    
                    # Get precipitation data
                    precip_data = forecast.get('precipitacion', {})
                    prob_precip = float(precip_data.get('probabilidad', 0))
                    
                    # Get wind data
                    wind_data = forecast.get('viento', {})
                    wind_speed = float(wind_data.get('velocidad', 0))
                    wind_direction = float(wind_data.get('direccion', 0))
                    
                    # Get sky condition
                    sky_data = forecast.get('estadoCielo', {})
                    sky_code = sky_data.get('descripcion', '')
                    
                    # Create hourly forecasts for the event duration
                    current_hour = teetime
                    while current_hour <= end_time:
                        # Use morning temp before 14:00, afternoon temp after
                        temp = morning_temp if current_hour.hour < 14 else afternoon_temp
                        
                        parsed_data[current_hour.isoformat()] = {
                            'air_temperature': temp,
                            'precipitation_amount': 0.0,  # No hourly data available
                            'wind_speed': wind_speed,
                            'wind_from_direction': wind_direction,
                            'probability_of_precipitation': prob_precip,
                            'probability_of_thunder': 0.0,
                            'summary_code': self._convert_aemet_code(sky_code)
                        }
                        
                        self.logger.debug(
                            f"Added daily forecast for {current_hour.isoformat()}: "
                            f"temp={temp}°C, "
                            f"precip_prob={prob_precip}%, "
                            f"wind={wind_speed}m/s, "
                            f"sky={sky_code}"
                        )
                        
                        current_hour += timedelta(hours=1)
                    
                    break
            
            if not parsed_data:
                self.logger.warning(f"No forecasts found between {teetime} and {end_time}")
            else:
                self.logger.info(f"Found {len(parsed_data)} forecasts")
            
            return parsed_data
            
        except Exception as e:
            self.logger.error(f"Failed to parse AEMET daily data: {e}")
            return None

    def _calculate_ipma_expiry(self, current_time: datetime) -> str:
        """Calculate expiry time for IPMA data based on their update schedule.
        
        IPMA updates data twice daily:
        - 00 UTC run available at 10:00 UTC
        - 12 UTC run available at 20:00 UTC
        """
        current_utc = current_time.astimezone(pytz.UTC)
        
        # If current time is between 00:00-20:00, data expires at 20:00
        if current_utc.hour < 20:
            expires = current_utc.replace(hour=20, minute=0, second=0, microsecond=0)
        # If current time is between 20:00-00:00, data expires at 10:00 next day
        else:
            expires = (current_utc + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        
        return expires.strftime('%Y-%m-%dT%H:%M:%SZ')

    def _calculate_aemet_expiry(self, elaboration_date: Optional[str] = None) -> str:
        """Calculate expiry time for AEMET data based on elaboration date.
        
        AEMET uses ECMWF model data which updates twice daily.
        If elaboration date is provided, we'll use that to calculate expiry.
        Otherwise, we'll use a conservative 3-hour window.
        """
        if elaboration_date:
            try:
                # Parse elaboration date (usually in format "YYYY-MM-DD HH:mm:ss")
                elab_time = datetime.strptime(elaboration_date, "%Y-%m-%d %H:%M:%S")
                elab_time = pytz.UTC.localize(elab_time)
                
                # AEMET typically updates forecasts at 00:00 and 12:00 UTC
                # Add 12 hours to elaboration time to get expiry
                expires = elab_time + timedelta(hours=12)
                
                # If expiry is in the past, use a shorter window
                if expires < datetime.now(pytz.UTC):
                    expires = datetime.now(pytz.UTC) + timedelta(hours=3)
                
                return expires.strftime('%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                self.logger.warning(f"Failed to parse AEMET elaboration date: {elaboration_date}")
        
        # Default to 3-hour expiry if no elaboration date or parsing failed
        return (datetime.utcnow() + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M:%SZ')

    def _fetch_ipma_data(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Fetch weather data from IPMA API."""
        try:
            # Rate limiting
            if self._last_api_call:
                elapsed = datetime.now() - self._last_api_call
                if elapsed < self._min_call_interval:
                    sleep_time = (self._min_call_interval - elapsed).total_seconds()
                    self.logger.debug(f"Rate limit: sleeping for {sleep_time} seconds")
                    time.sleep(sleep_time)
            
            # Find nearest weather station
            stations_url = f"{self.ipma_endpoint}/stations.json"
            self.logger.debug(f"IPMA stations URL: {stations_url}")
            
            response = requests.get(stations_url, headers=self.ipma_headers)
            response.raise_for_status()
            stations = response.json()
            
            # Find nearest station
            nearest = None
            min_distance = float('inf')
            for station in stations:
                try:
                    station_lat = float(station.get('latitude', 0))
                    station_lon = float(station.get('longitude', 0))
                    if station_lat == 0 or station_lon == 0:
                        continue
                    
                    distance = (lat - station_lat) ** 2 + (lon - station_lon) ** 2
                    if distance < min_distance:
                        min_distance = distance
                        nearest = station
                except (ValueError, KeyError) as e:
                    self.logger.warning(f"Failed to process station: {e}")
                    continue
            
            if not nearest:
                self.logger.error("No IPMA stations found")
                return None
            
            # Get forecast for nearest station
            station_id = nearest.get('globalIdLocal')
            if not station_id:
                self.logger.error("No station ID found")
                return None
            
            forecast_url = f"{self.ipma_endpoint}/observations/{station_id}.json"
            self.logger.debug(f"IPMA forecast URL: {forecast_url}")
            
            response = requests.get(forecast_url, headers=self.ipma_headers)
            response.raise_for_status()
            
            self._last_api_call = datetime.now()
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Failed to fetch IPMA data: {e}", exc_info=True)
            return None