"""Weather service manager."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import time
from zoneinfo import ZoneInfo

from golfcal2.utils.logging_utils import EnhancedLoggerMixin, log_execution
from golfcal2.exceptions import WeatherError, ErrorCode, handle_errors
from golfcal2.config.error_aggregator import aggregate_error
from golfcal2.services.weather_types import WeatherService, WeatherData, WeatherResponse, get_weather_symbol
from golfcal2.services.mediterranean_weather_service import MediterraneanWeatherService
from golfcal2.services.iberian_weather_service import IberianWeatherService
from golfcal2.services.portuguese_weather_service import PortugueseWeatherService
from golfcal2.services.met_weather_service import MetWeatherService
from golfcal2.services.weather_database import WeatherDatabase
from golfcal2.config.types import AppConfig


class WeatherManager(EnhancedLoggerMixin):
    """Weather service manager."""
    
    def __init__(self, local_tz: ZoneInfo, utc_tz: ZoneInfo, config: AppConfig):
        """Initialize weather services.
        
        Args:
            local_tz: Local timezone object
            utc_tz: UTC timezone object
            config: Application configuration
        """
        super().__init__()
        
        # Configure logger
        for handler in self.logger.handlers:
            handler.set_name('weather_manager')  # Ensure unique handler names
        self.logger.propagate = True  # Allow logs to propagate to root logger
        
        with handle_errors(WeatherError, "weather", "initialize services"):
            # Store timezone settings
            self.local_tz = ZoneInfo(local_tz) if isinstance(local_tz, str) else local_tz
            self.utc_tz = ZoneInfo(utc_tz) if isinstance(utc_tz, str) else utc_tz
            
            # Initialize weather data cache
            self._weather_cache: Dict[str, Any] = {}
            
            # Rate limiting configuration
            self._last_api_call = None
            self._min_call_interval = timedelta(seconds=1)
            
            # Initialize services
            self.services = {
                'mediterranean': MediterraneanWeatherService(self.local_tz, self.utc_tz, config),
                'iberian': IberianWeatherService(self.local_tz, self.utc_tz, config),
                'met': MetWeatherService(self.local_tz, self.utc_tz, config),
                'portuguese': PortugueseWeatherService(self.local_tz, self.utc_tz, config)
            }
            
            # Define service regions
            self.regions = {
                'norway': {
                    'service': 'met',
                    'bounds': (57.0, 71.5, 4.0, 31.5)  # lat_min, lat_max, lon_min, lon_max
                },
                'mediterranean': {
                    'service': 'mediterranean',
                    'bounds': (35.0, 45.0, 20.0, 45.0)
                },
                'portugal': {
                    'service': 'portuguese',  # Using PortugueseWeatherService
                    'bounds': (36.5, 42.5, -9.5, -7.5)  # Mainland Portugal
                },
                'spain_mainland': {
                    'service': 'iberian',
                    'bounds': (36.0, 44.0, -7.5, 3.5)  # Mainland Spain (AEMET)
                },
                'spain_canary': {
                    'service': 'iberian',
                    'bounds': (27.5, 29.5, -18.5, -13.0)  # Canary Islands (AEMET)
                }
            }
            
            self.set_correlation_id()  # Generate unique ID for this manager instance
    
    def _apply_rate_limit(self):
        """Apply rate limiting between API calls."""
        if hasattr(self, '_last_api_call') and self._last_api_call:
            elapsed = (datetime.now() - self._last_api_call).total_seconds()
            if elapsed < 1.0:
                sleep_time = 1.0 - elapsed
                self.debug(f"Rate limit: sleeping for {sleep_time} seconds")
                time.sleep(sleep_time)
    
    @log_execution(level='DEBUG')
    def get_weather(self, lat: float, lon: float, start_time: datetime, end_time: datetime, club: str) -> Optional[WeatherResponse]:
        """Get weather data for a location and time range."""
        try:
            # Get appropriate service for location
            service = self._get_service_for_location(lat, lon, club)
            if not service:
                return None
            
            # Get weather data from service
            weather_data = service.get_weather(lat, lon, start_time, end_time, club)
            if not weather_data:
                return None
            
            # Create response with expiry time
            now_utc = datetime.now(ZoneInfo("UTC"))
            return WeatherResponse(data=weather_data, expires=now_utc + timedelta(hours=1))
        except Exception as e:
            self.error(f"Failed to get weather data: {e}")
            return None
    
    @log_execution(level='DEBUG')
    def _get_service_for_location(self, lat: float, lon: float, club: Optional[str] = None) -> Optional[WeatherService]:
        """Get appropriate weather service for location."""
        with handle_errors(
            WeatherError,
            "weather",
            f"get service for location (lat={lat}, lon={lon})",
            lambda: None  # Fallback to None on error
        ):
            service_name = None
            
            # Select service based on coordinates
            for region, config in self.regions.items():
                lat_min, lat_max, lon_min, lon_max = config['bounds']
                if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                    self.debug(
                        "Found matching region",
                        region=region,
                        service=config['service'],
                        coordinates=f"({lat}, {lon})"
                    )
                    service_name = config['service']
                    break
            
            # Default to MET service as fallback
            if not service_name:
                self.info(
                    "No specific region found, using MET service as fallback",
                    latitude=lat,
                    longitude=lon
                )
                service_name = 'met'
            
            # Return the actual service instance
            service = self.services.get(service_name)
            if not service:
                error = WeatherError(
                    f"Weather service '{service_name}' not found",
                    ErrorCode.SERVICE_UNAVAILABLE,
                    {
                        "service": service_name,
                        "latitude": lat,
                        "longitude": lon
                    }
                )
                aggregate_error(str(error), "weather", None)
                return None
            
            return service
    
    def _get_symbol_severity(self, symbol: str) -> int:
        """Get severity level for a weather symbol for sorting."""
        severity_map = {
            'clearsky': 0,
            'fair': 1,
            'partlycloudy': 2,
            'cloudy': 3,
            'fog': 4,
            'lightrain': 5,
            'rain': 6,
            'heavyrain': 7,
            'lightsnow': 8,
            'snow': 9,
            'heavysnow': 10,
            'sleet': 11,
            'thunder': 12,
            'thunderstorm': 13
        }
        
        # Remove day/night suffix and get base symbol
        base_symbol = symbol.rstrip('_day').rstrip('_night').rstrip('_polartwilight')
        
        # Return severity or 0 if symbol not found
        return severity_map.get(base_symbol, 0)
    
    def _process_weather_data(self, forecasts: List[WeatherData], start_time: datetime, end_time: datetime) -> Optional[str]:
        """Process weather data into a human-readable string."""
        with handle_errors(
            WeatherError,
            "weather_manager",
            "process weather data",
            lambda: None  # Return None on error
        ):
            if not forecasts:
                self.debug("No forecasts to process")
                return None
            
            # Sort forecasts by time
            sorted_data = sorted(forecasts, key=lambda x: x.elaboration_time)
            
            # Get overview of data
            first_time = sorted_data[0].elaboration_time
            last_time = sorted_data[-1].elaboration_time
            now = datetime.now(first_time.tzinfo)
            hours_ahead = (first_time - now).total_seconds() / 3600
            
            self.debug(
                "Weather data overview",
                forecasts=len(sorted_data),
                hours_ahead=hours_ahead,
                first_time=first_time.isoformat(),
                last_time=last_time.isoformat(),
                timezone=str(first_time.tzinfo)
            )
            
            # Use 6-hour blocks for forecasts beyond 48 hours
            block_size = 6 if hours_ahead > 48 else 1
            self.debug(f"Using {block_size}-hour blocks from MetWeatherService")
            
            # Group forecasts by time blocks
            periods = {}
            for data in sorted_data:
                time = data.elaboration_time
                block_start = time.replace(
                    hour=(time.hour // block_size) * block_size,
                    minute=0
                )
                block_end = block_start + timedelta(hours=block_size)
                
                # Only include blocks that overlap with the event time range
                if not (block_end <= start_time or block_start >= end_time):
                    if (block_start, block_end) not in periods:
                        periods[(block_start, block_end)] = []
                    periods[(block_start, block_end)].append(data)
            
            # For 1-hour blocks, don't merge - use periods as is
            if block_size == 1:
                merged_periods = periods
            else:
                # Only merge for multi-hour blocks
                merged_periods = {}
                current_start = None
                current_forecasts = []
                
                for (start_time, end_time), forecasts in sorted(periods.items()):
                    if current_start is None:
                        current_start = start_time
                        current_forecasts = forecasts
                    else:
                        # If there's a gap between blocks or different weather conditions,
                        # save current block and start new one
                        if start_time > current_start + timedelta(hours=block_size):
                            merged_periods[(current_start, start_time)] = current_forecasts
                            current_start = start_time
                            current_forecasts = forecasts
                        else:
                            # Merge blocks if they're adjacent
                            current_forecasts.extend(forecasts)
                
                # Add the last block
                if current_start is not None and current_forecasts:
                    merged_periods[(current_start, last_time)] = current_forecasts
            
            self.debug(f"Grouped into {len(merged_periods)} merged periods")
            
            # Format output
            lines = []
            for (start_time, end_time), forecasts in sorted(merged_periods.items()):
                self.debug("Processing period", start=start_time.isoformat(), end=end_time.isoformat())
                
                # Convert to local time for display
                local_start = start_time.astimezone(self.local_tz)
                local_end = end_time.astimezone(self.local_tz)
                if block_size == 1:
                    time_str = local_start.strftime('%H:%M')
                else:
                    # For multi-hour blocks, ensure end time is correct
                    block_end = local_start + timedelta(hours=block_size)
                    time_str = f"{local_start.strftime('%H:%M')}-{block_end.strftime('%H:%M')}"
                
                # Calculate aggregated values
                avg_temp = sum(f.temperature for f in forecasts) / len(forecasts)
                avg_wind = sum(f.wind_speed for f in forecasts) / len(forecasts)
                max_prob = max((f.precipitation_probability or 0) for f in forecasts)
                total_precip = sum(f.precipitation for f in forecasts)
                max_thunder = max((f.thunder_probability or 0) for f in forecasts)
                
                self.debug(
                    "Calculated values",
                    time_str=time_str,
                    avg_temp=avg_temp,
                    avg_wind=avg_wind,
                    max_prob=max_prob,
                    total_precip=total_precip,
                    max_thunder=max_thunder
                )
                
                # Get most severe weather symbol
                symbol = max(forecasts, key=lambda f: self._get_symbol_severity(f.symbol)).symbol
                weather_symbol = get_weather_symbol(symbol)
                
                self.debug("Got weather symbol", symbol=symbol, emoji=weather_symbol)
                
                # Build parts list
                parts = [
                    time_str,
                    weather_symbol,
                    f"{avg_temp:.1f}°C",
                    f"{avg_wind:.1f}m/s"
                ]
                
                # Add wind direction if available
                wind_dirs = [f.wind_direction for f in forecasts if f.wind_direction]
                if wind_dirs:
                    # Use most common wind direction in the period
                    from collections import Counter
                    wind_dir = Counter(wind_dirs).most_common(1)[0][0]
                    # Handle calm conditions
                    if wind_dir == 'CALM':
                        parts[3] = f"{avg_wind:.1f}m/s (calm)"
                    else:
                        parts[3] = f"{avg_wind:.1f}m/s {wind_dir}"
                
                # Add precipitation info if significant
                if total_precip > 0:
                    parts.append(f"💧{max_prob:.1f}% {total_precip:.1f}mm")
                elif max_prob > 5:
                    parts.append(f"💧{max_prob:.1f}%")
                
                # Add thunder probability if significant
                if max_thunder >= 0.5:
                    parts.append(f"⚡{max_thunder:.1f}%")
                
                line = ' '.join(parts)
                self.debug(
                    "Built weather line",
                    parts=parts,
                    final_line=line
                )
                lines.append(line)
            
            result = "\n".join(lines)
            self.debug("Final weather string", result=result)
            return result