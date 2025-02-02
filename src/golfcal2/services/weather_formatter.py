from typing import List, Dict, Optional, Union, Sequence
from datetime import datetime, timedelta, timezone
from golfcal2.services.weather_types import WeatherData, WeatherResponse
from golfcal2.utils.weather_utils import get_weather_symbol

class WeatherFormatter:
    """Centralized weather formatting service."""
    
    @classmethod
    def format_forecast(cls, weather_data: Union[WeatherResponse, List[WeatherData], Sequence[WeatherData]], start_time: datetime = None, end_time: datetime = None) -> str:
        """Format weather forecast for display.
        
        Args:
            weather_data: Weather data to format (timestamps in UTC)
            start_time: Optional start time to filter forecasts (in event timezone)
            end_time: Optional end time to filter forecasts (in event timezone)
            
        Returns:
            Formatted weather forecast string
        """
        # Convert input to list of WeatherData
        if isinstance(weather_data, list) or isinstance(weather_data, Sequence):
            data_list = weather_data
        else:
            data_list = weather_data.data if weather_data else []
            
        if not data_list:
            return "No forecast available"
            
        # Get event timezone from start_time
        event_tz = start_time.tzinfo if start_time else None
        if not event_tz:
            return "No timezone information available"
            
        # Convert event times to UTC for comparison with forecast times
        utc = timezone.utc
        if start_time:
            start_time_utc = start_time.astimezone(utc)
        if end_time:
            end_time_utc = end_time.astimezone(utc)
        
        filtered = []
        for forecast in data_list:
            # Ensure forecast time is UTC
            forecast_time = forecast.time
            if forecast_time.tzinfo is None:
                forecast_time = forecast_time.replace(tzinfo=utc)
            else:
                forecast_time = forecast_time.astimezone(utc)
            
            # Calculate block end time in UTC
            forecast_end = forecast_time + forecast.block_duration
            
            # Check overlap with event time window
            if start_time_utc and forecast_end <= start_time_utc:
                continue
            if end_time_utc and forecast_time >= end_time_utc:
                continue
            
            filtered.append(forecast)
        
        if not filtered:
            return "No forecast available for event time"
            
        # Sort forecasts by time (still in UTC)
        filtered_data = sorted(filtered, key=lambda x: x.time)
        
        # Format forecasts in event timezone
        formatted_lines = []
        for i, forecast in enumerate(filtered_data):
            # Convert forecast time to event timezone for display
            local_time = forecast.time.astimezone(event_tz)
            
            # Calculate block end time
            block_end = local_time + forecast.block_duration
            
            # Format time string based on block size
            time_diff = forecast.block_duration.total_seconds() / 3600
            if time_diff > 1:
                # If block end is on the next day, include the date
                if block_end.date() > local_time.date():
                    time_str = f"{local_time.strftime('%H:%M')}-{block_end.strftime('%H:%M')} (+1)"
                else:
                    time_str = f"{local_time.strftime('%H:%M')}-{block_end.strftime('%H:%M')}"
            else:
                # Even for 1-hour blocks, show the end time for consistency
                time_str = f"{local_time.strftime('%H:%M')}-{block_end.strftime('%H:%M')}"
            
            # Get weather symbol
            symbol = get_weather_symbol(forecast.weather_code.value)
            
            # Build weather line with optional precipitation and thunder probability
            parts = [time_str, symbol, f"{forecast.temperature:.1f}°C", f"{forecast.wind_speed:.1f}m/s"]
            
            # Show precipitation info if available
            if hasattr(forecast, 'precipitation_probability'):
                if forecast.precipitation and forecast.precipitation > 0:
                    parts.append(f"💧{forecast.precipitation_probability:.0f}% {forecast.precipitation:.1f}mm")
                else:
                    parts.append(f"💧{forecast.precipitation_probability:.0f}%")
            
            if hasattr(forecast, 'thunder_probability') and forecast.thunder_probability is not None and forecast.thunder_probability > 0:
                parts.append(f"⚡{forecast.thunder_probability:.0f}%")
            
            line = " ".join(parts)
            formatted_lines.append(line)
        
        return "\n".join(formatted_lines)
    
    @classmethod
    def format_for_calendar(cls, forecast: Optional[WeatherData]) -> Dict:
        """Format weather data for calendar events."""
        if not forecast:
            return {
                'temperature': None,
                'precipitation': None,
                'summary': 'No weather data'
            }
            
        summary_parts = [
            f"{forecast.temperature:.1f}°C",
            f"{forecast.wind_speed:.1f}m/s"
        ]
        
        if forecast.precipitation_probability is not None and forecast.precipitation_probability > 5:
            if forecast.precipitation and forecast.precipitation > 0:
                summary_parts.append(f"{forecast.precipitation_probability:.0f}% {forecast.precipitation:.1f}mm rain")
            else:
                summary_parts.append(f"{forecast.precipitation_probability:.0f}% chance of rain")
        
        if forecast.thunder_probability is not None and forecast.thunder_probability > 0:
            summary_parts.append(f"{forecast.thunder_probability:.0f}% thunder")
            
        return {
            'temperature': forecast.temperature,
            'precipitation': forecast.precipitation,
            'summary': ", ".join(summary_parts)
        }
    
    @classmethod
    def get_weather_summary(cls, weather: Optional[Union[WeatherData, WeatherResponse]]) -> str:
        """Get a concise weather summary."""
        if not weather:
            return "Weather data unavailable"
            
        # If we got a WeatherResponse, use the first data point
        if isinstance(weather, WeatherResponse):
            if not weather.data:
                return "Weather data unavailable"
            forecast = weather.data[0]
        else:
            forecast = weather
            
        try:
            summary_parts = []
            
            # Add temperature if available
            if hasattr(forecast, 'temperature') and forecast.temperature is not None:
                summary_parts.append(f"{forecast.temperature:.1f}°C")
            
            # Add wind speed if available
            if hasattr(forecast, 'wind_speed') and forecast.wind_speed is not None:
                summary_parts.append(f"{forecast.wind_speed:.1f}m/s")
            
            # Add precipitation info if available
            if (hasattr(forecast, 'precipitation_probability') and 
                forecast.precipitation_probability is not None and 
                forecast.precipitation_probability > 5):
                if (hasattr(forecast, 'precipitation') and 
                    forecast.precipitation is not None and 
                    forecast.precipitation > 0):
                    summary_parts.append(
                        f"{forecast.precipitation_probability:.0f}% {forecast.precipitation:.1f}mm rain"
                    )
                else:
                    summary_parts.append(f"{forecast.precipitation_probability:.0f}% chance of rain")
            
            # Add thunder probability if available
            if (hasattr(forecast, 'thunder_probability') and 
                forecast.thunder_probability is not None and 
                forecast.thunder_probability > 0):
                summary_parts.append(f"{forecast.thunder_probability:.0f}% thunder")
            
            return ", ".join(summary_parts) if summary_parts else "Weather data unavailable"
            
        except Exception as e:
            return f"Error formatting weather: {str(e)}" 