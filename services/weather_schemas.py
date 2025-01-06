"""Database schemas for weather services."""

# Common weather table columns
WEATHER_COLUMNS = [
    'id INTEGER PRIMARY KEY AUTOINCREMENT',
    'location TEXT NOT NULL',
    'time TEXT NOT NULL',
    'data_type TEXT NOT NULL DEFAULT "next_1_hours"',
    'air_temperature REAL',
    'precipitation_amount REAL',
    'precipitation_max REAL',
    'precipitation_min REAL',
    'precipitation_rate REAL',
    'precipitation_intensity REAL',
    'wind_speed REAL',
    'wind_from_direction REAL',
    'wind_speed_gust REAL',
    'probability_of_precipitation REAL',
    'probability_of_thunder REAL',
    'air_pressure REAL',
    'cloud_area_fraction REAL',
    'fog_area_fraction REAL',
    'relative_humidity REAL',
    'ultraviolet_index REAL',
    'dew_point_temperature REAL',
    'temperature_max REAL',
    'temperature_min REAL',
    'summary_code TEXT',
    'expires TEXT',
    'last_modified TEXT',
    'UNIQUE(location, time, data_type)'
]

# MET.no schema
MET_SCHEMA = {
    'weather': WEATHER_COLUMNS
}

# AEMET/IPMA schema
IBERIAN_SCHEMA = {
    'weather': WEATHER_COLUMNS,
    'weather_stations': [
        'id TEXT PRIMARY KEY',
        'latitude REAL',
        'longitude REAL',
        'name TEXT',
        'province TEXT',
        'municipality_code TEXT',
        'last_updated TIMESTAMP'
    ]
}

# Portuguese schema
PORTUGUESE_SCHEMA = {
    'weather': WEATHER_COLUMNS
}

# OpenWeather schema
MEDITERRANEAN_SCHEMA = {
    'weather': WEATHER_COLUMNS
} 