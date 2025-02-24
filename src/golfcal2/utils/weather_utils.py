"""Weather utility functions."""


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
        'fog': '🌫️',
        'LIGHTRAIN': '🌦️',
        'RAIN': '🌧️',
        'HEAVYRAIN': '⛈️',
        'RAINSHOWERS_DAY': '🌦️',
        'RAINSHOWERS_NIGHT': '🌦️',
        'HEAVYRAINSHOWERS_DAY': '⛈️',
        'HEAVYRAINSHOWERS_NIGHT': '⛈️',
        'RAINANDTHUNDER': '⛈️',
        'HEAVYRAINANDTHUNDER': '⛈️',
        'THUNDERSTORM': '⛈️'
    }
    return symbol_map.get(code.lower(), '☁️')  # Default to cloudy if code not found, convert to lowercase for matching

def _get_symbol_severity(symbol: str) -> int:
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