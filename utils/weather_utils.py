"""Weather utility functions."""

from typing import List, Optional
from golfcal2.services.weather_types import WeatherData

def get_weather_symbol(code: str) -> str:
    """Get weather symbol for weather code."""
    symbol_map = {
        'clearsky_day': '☀️',
        'clearsky_night': '🌙',
        'fair_day': '🌤️',
        'fair_night': '🌤️',
        'partlycloudy_day': '⛅',
        'partlycloudy_night': '⛅',
        'cloudy': '☁️',
        'lightrain': '🌦️',
        'rain': '🌧️',
        'heavyrain': '⛈️',
        'rainshowers_day': '🌦️',
        'rainshowers_night': '🌦️',
        'heavyrainshowers_day': '⛈️',
        'heavyrainshowers_night': '⛈️',
        'rainandthunder': '⛈️',
        'heavyrainandthunder': '⛈️',
        'lightsnow': '🌨️',
        'snow': '❄️',
        'heavysnow': '❄️',
        'lightsleet': '🌨️',
        'heavysleet': '🌨️',
        'fog': '🌫️'
    }
    return symbol_map.get(code, '☁️')  # Default to cloudy if code not found

def format_weather_data(weather_data: List[WeatherData]) -> str:
    """Format weather data into a human-readable string."""
    if not weather_data:
        return "No weather data available"
    
    formatted_lines = []
    for forecast in weather_data:
        time_str = forecast.elaboration_time.strftime('%H:%M')
        symbol = get_weather_symbol(forecast.symbol)
        temp = f"{forecast.temperature:.1f}°C"
        wind = f"{forecast.wind_speed:.1f}m/s"
        
        # Build weather line with optional precipitation and thunder probability
        parts = [f"{time_str}", symbol, temp, wind]
        
        if forecast.precipitation_probability is not None and forecast.precipitation_probability > 0:
            parts.append(f"💧{forecast.precipitation_probability:.1f}%")
        
        if forecast.thunder_probability is not None and forecast.thunder_probability > 0:
            parts.append(f"⚡{forecast.thunder_probability:.1f}%")
        
        formatted_lines.append(" ".join(parts))
    
    return "\n".join(formatted_lines) 