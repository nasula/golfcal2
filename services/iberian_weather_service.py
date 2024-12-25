"""Iberian weather service implementation."""

import os
import json
import time
import sqlite3
import pytz
import yaml
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

import requests
import math

from golfcal2.utils.logging_utils import LoggerMixin
from golfcal2.services.weather_service import WeatherService, WeatherCode, get_weather_symbol

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
        self.ipma_endpoint = 'https://api.ipma.pt/open-data'
        self.ipma_headers = {
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
        
        # Set up database path
        self.db_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        self.db_file = os.path.join(self.db_dir, 'iberian_weather.db')
        os.makedirs(self.db_dir, exist_ok=True)
        
        # Initialize database
        self._init_db()
    
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
            config_path = Path(__file__).parent.parent / 'config' / 'api_keys.yaml'
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    if config and 'weather' in config and 'aemet' in config['weather']:
                        api_key = config['weather']['aemet']
                        if api_key:  # Check if it's not empty
                            return api_key
            
            self.logger.error("AEMET API key not configured in environment or config file")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to load AEMET API key: {e}")
            return None
    
    def get_weather(
        self,
        lat: float,
        lon: float,
        date: datetime,
        duration_minutes: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get weather data for given coordinates and date."""
        try:
            self.logger.info(f"Weather: Starting Iberian weather fetch for {lat},{lon} at {date}")
            
            # Skip past dates
            if date < datetime.now(self.utc_tz):
                self.logger.debug(f"Weather: Skipping past date {date}")
                return None
            
            # Calculate event duration and end time
            event_duration = duration_minutes or 180  # Default to 3 hours
            event_end = date + timedelta(minutes=event_duration)
            
            # Create a list of target hours we want forecasts for
            target_hours = []
            current_time = date
            while current_time <= event_end:
                target_hours.append(current_time.replace(minute=0))
                current_time += timedelta(hours=1)
            
            # Determine country based on coordinates
            if -9.5 <= lon <= -6.2:  # Portugal
                weather_data = self._get_ipma_weather('', date, {'lat': lat, 'lon': lon}, duration_minutes)
            else:  # Spain
                weather_data = self._get_aemet_weather('', date, {'lat': lat, 'lon': lon}, duration_minutes)
            
            if not weather_data:
                return None
            
            # Convert weather_data dict to list of forecasts
            forecasts = []
            for target_time in target_hours:
                # Find the closest forecast for this target hour
                closest_time = min(
                    weather_data.keys(),
                    key=lambda x: abs(
                        datetime.fromisoformat(x.replace('Z', '+00:00')).astimezone(date.tzinfo) - target_time
                    )
                )
                data = weather_data[closest_time]
                
                forecast = {
                    'time': target_time,
                    'data_type': 'next_1_hours',
                    'symbol_code': data['summary_code'],
                    'air_temperature': round(data['air_temperature'], 1),
                    'precipitation_amount': data['precipitation_amount'],
                    'wind_speed': data['wind_speed'],
                    'wind_from_direction': data['wind_from_direction'],
                    'probability_of_precipitation': data.get('probability_of_precipitation', 0.0),
                    'probability_of_thunder': data.get('probability_of_thunder', 0.0)
                }
                forecasts.append(forecast)
            
            if not forecasts:
                return None
            
            # Return first forecast's data as the main weather data
            first_forecast = forecasts[0]
            return {
                'forecasts': forecasts,
                'symbol_code': first_forecast['symbol_code'],
                'air_temperature': round(first_forecast['air_temperature'], 1),
                'precipitation_amount': first_forecast['precipitation_amount'],
                'wind_speed': first_forecast['wind_speed'],
                'wind_from_direction': first_forecast['wind_from_direction'],
                'probability_of_precipitation': first_forecast['probability_of_precipitation'],
                'probability_of_thunder': first_forecast['probability_of_thunder']
            }
            
        except Exception as e:
            self.logger.error(f"Weather: Failed to get Iberian weather for {lat},{lon}: {e}", exc_info=True)
            return None
    
    def _get_municipality_code(self, lat: float, lon: float) -> Optional[str]:
        """Get municipality code for given coordinates."""
        try:
            # Find the nearest station from the database
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                
                # Check if we need to refresh the stations
                cursor.execute('SELECT COUNT(*), MIN(last_updated) FROM weather_stations')
                count, last_updated = cursor.fetchone()
                
                if count == 0 or (last_updated and 
                    datetime.fromisoformat(last_updated) < datetime.now() - timedelta(days=30)):
                    self._refresh_stations()
                
                # Find the nearest station using SQLite's math functions
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

    def _refresh_stations(self) -> None:
        """Refresh the weather stations in the database."""
        try:
            # Get the list of weather stations
            url = f"{self.aemet_endpoint}/valores/climatologicos/inventarioestaciones/todasestaciones"
            headers = {
                'Accept': 'application/json',
                'api_key': self.aemet_api_key
            }
            
            self.logger.debug(f"Fetching weather stations from AEMET: {url}")
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                self.logger.error(f"Failed to fetch weather stations: {response.status_code}")
                self.logger.debug(f"Response content: {response.text}")
                return
            
            # AEMET uses a two-step process - first get the data URL
            data_url = response.json().get('datos')
            if not data_url:
                self.logger.error("No data URL in station response")
                return
            
            # Get the actual station data
            station_response = requests.get(data_url, headers=headers)
            if station_response.status_code != 200:
                self.logger.error(f"Failed to fetch station data: {station_response.status_code}")
                self.logger.debug(f"Response content: {station_response.text}")
                return
            
            # Parse the response
            stations = station_response.json()
            
            if not stations:
                self.logger.error("Empty station list received")
                return
            
            # Update database
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                # Start a transaction
                cursor.execute('BEGIN TRANSACTION')
                
                try:
                    # Clear existing stations
                    cursor.execute('DELETE FROM weather_stations')
                    
                    # Insert new stations
                    for station in stations:
                        try:
                            if 'latitud' in station and 'longitud' in station and 'indicativo' in station:
                                # Convert DMS coordinates to decimal degrees
                                lat = self._dms_to_decimal(station['latitud'])
                                lon = self._dms_to_decimal(station['longitud'])
                                
                                cursor.execute('''
                                    INSERT INTO weather_stations 
                                    (id, latitude, longitude, name, province, municipality_code, last_updated)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    station['indicativo'],
                                    lat,
                                    lon,
                                    station.get('nombre', ''),
                                    station.get('provincia', ''),
                                    None,  # municipality_code will be updated later if needed
                                    now
                                ))
                                
                        except (ValueError, KeyError) as e:
                            self.logger.warning(f"Skipping invalid station data: {e}")
                            continue
                    
                    # Commit the transaction
                    conn.commit()
                    self.logger.info(f"Updated weather stations in database")
                    
                except Exception as e:
                    conn.rollback()
                    self.logger.error(f"Failed to update stations in database: {e}")
                    raise
            
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