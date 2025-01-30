from typing import List, Dict, Optional, Union, Sequence
from datetime import datetime, timedelta
from golfcal2.services.weather_types import WeatherData, WeatherResponse
from golfcal2.utils.weather_utils import get_weather_symbol

class WeatherFormatter:
    """Centralized weather formatting service."""
    
    @classmethod
    def format_forecast(cls, weather_data: Union[WeatherResponse, List[WeatherData], Sequence[WeatherData]], start_time: datetime = None, end_time: datetime = None) -> str:
        """Format weather forecast for display.
        
        Args:
            weather_data: Weather data to format
            start_time: Optional start time to filter forecasts
            end_time: Optional end time to filter forecasts
            
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
            
        # Get event timezone from first forecast
        event_tz = data_list[0].time.tzinfo if data_list else None
        
        # Convert all forecasts to event timezone and sort by time
        normalized_data = []
        for forecast in data_list:
            if event_tz and forecast.time.tzinfo != event_tz:
                forecast.time = forecast.time.astimezone(event_tz)
            normalized_data.append(forecast)
        
        normalized_data = sorted(normalized_data, key=lambda x: x.time)
        
        def get_block_end(forecasts: List[WeatherData], index: int, event_end: datetime = None) -> datetime:
            """Get the end time of a forecast block."""
            return forecasts[index + 1].time if index < len(forecasts) - 1 else forecasts[index].time + timedelta(hours=6)
        
        # Filter forecasts if time range provided
        if start_time and end_time:
            filtered_data = []
            for i, curr in enumerate(normalized_data):
                block_end = get_block_end(normalized_data, i, end_time)
                if curr.time <= end_time and block_end > start_time:
                    filtered_data.append(curr)
        else:
            filtered_data = normalized_data
            
        if not filtered_data:
            return "No forecast available for event time"
            
        formatted_lines = []
        for i, forecast in enumerate(filtered_data):
            # Get block end time
            block_end = get_block_end(filtered_data, i, end_time)
            
            # Calculate time difference in hours
            time_diff = (block_end - forecast.time).total_seconds() / 3600
            
            # Format time string based on block size
            if time_diff > 1:
                time_str = f"{forecast.time.strftime('%H:%M')}-{block_end.strftime('%H:%M')}"
            else:
                time_str = forecast.time.strftime('%H:%M')
            
            # Get weather symbol
            symbol = get_weather_symbol(forecast.weather_code.value)
            
            # Build weather line with optional precipitation and thunder probability
            parts = [time_str, symbol, f"{forecast.temperature:.1f}°C", f"{forecast.wind_speed:.1f}m/s"]
            
            if forecast.precipitation_probability is not None and forecast.precipitation_probability > 5:
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