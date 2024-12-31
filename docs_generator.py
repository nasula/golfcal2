from diagrams import Diagram, Cluster
from diagrams.programming.language import Python
from diagrams.programming.framework import Flask
from diagrams.generic.storage import Storage
from diagrams.onprem.network import Internet
from diagrams.generic.database import SQL
from diagrams.saas.chat import Teams
from diagrams.programming.flowchart import Document
from datetime import datetime
import os
from fpdf import FPDF
import graphviz

# Create diagrams directory if it doesn't exist
os.makedirs("docs/diagrams", exist_ok=True)

# Configuration Files Diagram (more compact layout)
with Diagram("Configuration Files Structure", 
            filename="docs/diagrams/config_structure",
            show=False,
            direction="TB",  # Top to bottom direction
            graph_attr={
                "ratio": "0.7",
                "fontsize": "12",
                "ranksep": "0.5",
                "nodesep": "0.4",
                "splines": "ortho"
            }):
    with Cluster("Configuration Files"):
        config = Document("config.yaml")
        users = Document("users.json")
        clubs = Document("clubs.json")
        weather = Document("weather.json")
        external_events = Document("external_events.yaml")
        test_events = Document("test_events.yaml")
        
        with Cluster("Club Configs"):
            clubs >> Document("WiseGolf")
            clubs >> Document("NexGolf")
            clubs >> Document("TeeTime")
        
        with Cluster("User Configs"):
            users >> Document("Memberships")
            users >> Document("Preferences")
            users >> Document("Auth")
        
        with Cluster("Global Settings"):
            config >> Document("Directories")
            config >> Document("API Keys")
            config >> Document("Logging")

# 1. System Architecture Diagram
with Diagram("Golf Calendar System Architecture", filename="docs/diagrams/architecture", show=False):
    with Cluster("External Services"):
        apis = [Internet("WiseGolf API"), Internet("NexGolf API"), Internet("TeeTime API")]
        weather = Internet("Weather Service")
        events = Internet("External Events")
    
    with Cluster("Core Application"):
        app = Python("GolfCalendarApp")
        services = Python("Services")
        models = Python("Models")
    
    with Cluster("Storage"):
        config = Storage("Config Files")
        calendar = Storage("ICS Files")
        weather_cache = Storage("Weather Cache")
        event_cache = Storage("Event Cache")
    
    for api in apis:
        api >> app
    weather >> app
    events >> app
    app >> services
    services >> models
    models >> config
    services >> calendar
    services >> weather_cache
    services >> event_cache

# 2. API Layer Diagram
with Diagram("API Layer Structure", filename="docs/diagrams/api_layer", show=False, direction="TB", graph_attr={
    "ratio": "0.6",
    "fontsize": "11",
    "ranksep": "0.4",
    "nodesep": "0.3"
}):
    with Cluster("API Implementations"):
        base = Python("BaseAPI")
        wise = Python("WiseGolfAPI")
        nex = Python("NexGolfAPI")
        tee = Python("TeeTimeAPI")
        weather_api = Python("WeatherAPI")
        event_api = Python("EventAPI")
        
        base >> wise
        base >> nex
        base >> tee
        base >> weather_api
        base >> event_api

# 3. Service Layer Diagram
with Diagram("Service Layer", filename="docs/diagrams/service_layer", show=False, direction="LR", graph_attr={
    "ratio": "0.5",
    "fontsize": "11",
    "ranksep": "0.4",
    "nodesep": "0.3"
}):
    with Cluster("Services"):
        cal = Python("CalendarService")
        res = Python("ReservationService")
        weather = Python("WeatherService")
        event = Python("EventService")
        
        cal >> res
        weather >> res
        event >> res
        weather >> cal
        event >> cal

# 4. Data Model Diagram
with Diagram("Data Models", filename="docs/diagrams/data_models", show=False, direction="TB", graph_attr={
    "ratio": "0.6",
    "fontsize": "11",
    "ranksep": "0.4",
    "nodesep": "0.3"
}):
    with Cluster("Core Models"):
        user = Python("User")
        club = Python("GolfClub")
        res = Python("Reservation")
        player = Python("Player")
        event = Python("Event")
        weather_data = Python("WeatherData")
        ext_event = Python("ExternalEvent")
        
        user >> res
        club >> res
        player >> res
        res >> event
        weather_data >> event
        ext_event >> event

# New API Data Structures Diagram
with Diagram("API Data Structures", filename="docs/diagrams/api_data_structures", show=False):
    with Cluster("WiseGolf Data"):
        wise_res = Document("Reservation")
        wise_player = Document("Player")
        wise_course = Document("Course")
        
        wise_res >> wise_player
        wise_res >> wise_course
    
    with Cluster("NexGolf Data"):
        nex_res = Document("Booking")
        nex_member = Document("Member")
        nex_facility = Document("Facility")
        
        nex_res >> nex_member
        nex_res >> nex_facility
    
    with Cluster("TeeTime Data"):
        tee_res = Document("Tee Time")
        tee_user = Document("User")
        tee_venue = Document("Venue")
        
        tee_res >> tee_user
        tee_res >> tee_venue
    
    with Cluster("Weather Data"):
        weather_current = Document("Current")
        weather_forecast = Document("Forecast")
        weather_alerts = Document("Alerts")
        
        weather_forecast >> weather_current
        weather_forecast >> weather_alerts
    
    with Cluster("External Events"):
        event_data = Document("Event")
        event_location = Document("Location")
        event_participants = Document("Participants")
        
        event_data >> event_location
        event_data >> event_participants

# Create PDF Documentation
class PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf', uni=True)
        self.add_font('DejaVu', 'B', '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf', uni=True)
        self.set_auto_page_break(auto=True, margin=15)
        self.accent_color = (0, 102, 204)
        
    def header(self):
        self.set_font('DejaVu', 'B', 12)
        self.set_text_color(*self.accent_color)
        self.cell(0, 8, 'Golf Calendar Documentation', 0, 1, 'C')
        self.set_text_color(0, 0, 0)
        self.line(10, 20, 200, 20)
        self.ln(12)

    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', '', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('DejaVu', 'B', 12)
        self.set_text_color(*self.accent_color)
        self.cell(0, 8, title, 0, 1, 'L')
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_text_color(0, 0, 0)
        self.ln(8)

    def sub_title(self, title):
        self.set_font('DejaVu', 'B', 10)
        self.set_text_color(51, 51, 51)
        self.cell(0, 6, title, 0, 1, 'L')
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('DejaVu', '', 9)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 5, body)
        self.ln(4)

    def add_image(self, image_path, w=None):
        """Add image with automatic sizing."""
        if w is None:
            w = 170  # Default width for most diagrams
        
        # Get image size
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                img_w, img_h = img.size
                ratio = img_h / img_w
                
                # Calculate new height based on width while maintaining aspect ratio
                new_h = w * ratio
                
                # If height is too large, scale down
                if new_h > 220:  # Maximum height
                    w = w * (220 / new_h)
                
                # Center the image
                x = (210 - w) / 2
                self.image(image_path, x=x, w=w)
        except:
            # Fallback to simple centered image
            self.image(image_path, x=20, w=170)
        
        self.ln(8)

    def get_image_size(self, image_path):
        """Get image dimensions."""
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                return img.size
        except:
            return (1000, 1000)  # Default size if can't read image

    def add_attribute_table(self, attributes):
        self.set_fill_color(240, 240, 240)
        self.set_font('DejaVu', 'B', 9)
        
        # Table header
        self.cell(50, 6, 'Attribute', 1, 0, 'L', True)
        self.cell(50, 6, 'Type', 1, 0, 'L', True)
        self.cell(90, 6, 'Description', 1, 1, 'L', True)
        
        # Table content
        self.set_font('DejaVu', '', 9)
        for attr in attributes:
            # Calculate required height based on description length
            lines = len(attr['description']) // 50 + 1
            height = max(5 * lines, 6)
            
            self.cell(50, height, attr['name'], 1, 0, 'L')
            self.cell(50, height, attr['type'], 1, 0, 'L')
            
            # Handle multi-line description
            current_x = self.get_x()
            current_y = self.get_y()
            self.multi_cell(90, 5, attr['description'], 1, 'L')
            self.set_xy(10, current_y + height)

pdf = PDF()
pdf.add_page()

# Title Page
pdf.set_font('DejaVu', 'B', 24)
pdf.cell(0, 60, 'Golf Calendar', 0, 1, 'C')
pdf.set_font('DejaVu', '', 16)
pdf.cell(0, 10, 'Technical Documentation', 0, 1, 'C')
pdf.cell(0, 10, f'Generated: {datetime.now().strftime("%Y-%m-%d")}', 0, 1, 'C')

# Table of Contents
pdf.add_page()
pdf.chapter_title('Table of Contents')
sections = [
    '1. System Architecture',
    '2. API Layer Analysis',
    '3. Service Layer Details',
    '4. Data Models',
    '5. Configuration System',
    '6. API Data Structures',
    '7. Configuration File Structures',
    '8. Reservation Processing'
]
for section in sections:
    pdf.cell(0, 10, section, 0, 1, 'L')

# 1. System Architecture
pdf.add_page()
pdf.chapter_title('1. System Architecture')
pdf.chapter_body('The Golf Calendar application follows a modular architecture with clear separation of concerns. The system is composed of several key components that work together to provide golf reservation management and calendar generation capabilities. The architecture includes integration with weather services and external event systems, with dedicated caching mechanisms for optimal performance.')
pdf.add_image('docs/diagrams/architecture.png')

# 2. API Layer
pdf.add_page()
pdf.chapter_title('2. API Layer Analysis')
pdf.chapter_body('The API layer implements adapters for different golf booking systems, weather services, and external event providers. It follows the adapter pattern with a base API class that defines the common interface. The WeatherAPI provides forecast data integration, while the EventAPI handles external event synchronization.')
pdf.add_image('docs/diagrams/api_layer.png')

# 3. Service Layer
pdf.add_page()
pdf.chapter_title('3. Service Layer Details')
pdf.chapter_body('The service layer contains the core business logic of the application. The WeatherService manages weather data retrieval and caching, while the EventService handles external event integration. These services work together with the ReservationService and CalendarService to provide comprehensive event information.')
pdf.add_image('docs/diagrams/service_layer.png')

# 4. Data Models
pdf.add_page()
pdf.chapter_title('4. Data Models')
pdf.chapter_body('The data models represent the core domain entities of the application. The WeatherData model stores temperature, precipitation, and wind information, while the ExternalEvent model handles additional event data. These models integrate with the core Reservation and Event models to provide comprehensive calendar entries.')
pdf.add_image('docs/diagrams/data_models.png')

# 5. Configuration System
pdf.add_page()
pdf.chapter_title('5. Configuration System')
pdf.chapter_body('The configuration system uses JSON files to store user and club configurations, as well as weather service API keys and external event source settings. It supports flexible configuration of multiple golf clubs, users, authentication methods, and integration points.')

# 6. API Data Structures
pdf.add_page()
pdf.chapter_title('6. API Data Structures')
pdf.chapter_body('The Golf Calendar system interacts with various external APIs, each with its own data structures and formats. Below are the key data structures for each API:')

# WiseGolf API
pdf.chapter_title('WiseGolf API Data Structures')
pdf.chapter_body('''
• Reservation:
  - id: Unique reservation identifier
  - datetime: Tee time date and time
  - duration: Duration in minutes
  - course_id: Reference to course
  - players: Array of player references
  - status: Booking status

• Player:
  - id: Player identifier
  - name: Full name
  - handicap: Current handicap
  - membership: Membership details
  - preferences: Player preferences

• Course:
  - id: Course identifier
  - name: Course name
  - holes: Number of holes
  - par: Course par
  - facilities: Available facilities
''')

# NexGolf API
pdf.chapter_title('NexGolf API Data Structures')
pdf.chapter_body('''
• Booking:
  - booking_id: Unique booking reference
  - time_slot: Reserved time slot
  - member_ids: List of participating members
  - facility_id: Golf facility reference
  - booking_type: Type of reservation

• Member:
  - member_id: Member identifier
  - details: Personal information
  - membership_level: Level of membership
  - active_status: Current status

• Facility:
  - facility_id: Facility identifier
  - location: Geographic location
  - amenities: Available services
  - operating_hours: Business hours
''')

# TeeTime API
pdf.chapter_title('TeeTime API Data Structures')
pdf.chapter_body('''
• Tee Time:
  - slot_id: Time slot identifier
  - start_time: Start time
  - end_time: End time
  - venue_id: Golf venue reference
  - player_count: Number of players
  - booking_status: Current status

• User:
  - user_id: User identifier
  - profile: User profile data
  - booking_history: Past bookings
  - preferences: User preferences

• Venue:
  - venue_id: Venue identifier
  - details: Venue information
  - availability: Time slot availability
  - pricing: Rate information
''')

# Weather API
pdf.chapter_title('Weather API Data Structures')
pdf.chapter_body('''
• Current Weather:
  - temperature: Current temperature
  - precipitation: Precipitation probability
  - wind_speed: Wind speed
  - wind_direction: Wind direction
  - humidity: Humidity percentage

• Forecast:
  - hourly: Hourly forecast data
  - daily: Daily forecast summary
  - alerts: Weather warnings
  - location: Forecast location

• Alerts:
  - type: Alert type
  - severity: Alert severity
  - description: Alert details
  - valid_period: Validity timeframe
''')

# External Events API
pdf.chapter_title('External Events API Data Structures')
pdf.chapter_body('''
• Event:
  - event_id: Unique event identifier
  - title: Event title
  - description: Event description
  - start_time: Event start time
  - end_time: Event end time
  - type: Event type

• Location:
  - coordinates: Geographic coordinates
  - address: Physical address
  - venue_name: Location name
  - accessibility: Access information

• Participants:
  - capacity: Maximum participants
  - current_count: Current participant count
  - registration_status: Registration state
  - waiting_list: Waiting list status
''')

pdf.add_image('docs/diagrams/api_data_structures.png')

# 7. Configuration File Structures
pdf.add_page()
pdf.chapter_title('7. Configuration File Structures')
pdf.chapter_body('The Golf Calendar system uses several JSON configuration files to manage different aspects of the application. Each configuration file has a specific structure and purpose:')

pdf.add_image('docs/diagrams/config_structure.png')

# users.json
pdf.chapter_title('users.json')
pdf.chapter_body('''
Structure:
{
    "user_name": {
        "email": "user@example.com",
        "memberships": [
            {
                "club": "CLUB_CODE",
                "duration": {
                    "hours": 2,
                    "minutes": 0
                },
                "auth_details": {
                    "token": "auth_token",
                    "cookie": "session_cookie",
                    "username": "login_username",
                    "password": "encrypted_password"
                }
            }
        ],
        "preferences": {
            "default_duration": 120,
            "notification_email": "notifications@example.com",
            "calendar_file": "user_calendar.ics",
            "time_zone": "Europe/Helsinki"
        }
    }
}

Description:
- user_name: Unique identifier for each user
- email: Primary contact email
- memberships: Array of club memberships
  - club: Reference to club configuration
  - duration: Default booking duration
  - auth_details: Authentication credentials
- preferences: User-specific settings
''')

# clubs.json
pdf.chapter_title('clubs.json')
pdf.chapter_body('''
Structure:
{
    "CLUB_CODE": {
        "type": "wisegolf|nexgolf|teetime",
        "url": "https://api.club.com/endpoint",
        "public_url": "https://club.com/api/public",
        "cookie_name": "session_cookie",
        "auth_type": "token|cookie|basic",
        "crm": "system_type",
        "address": "Club physical address",
        "clubAbbreviation": "SHG",
        "product_ids": {
            "53": {
                "description": "18 holes",
                "group": "A"
            }
        },
        "coordinates": {
            "latitude": 60.123,
            "longitude": 24.456
        },
        "facilities": ["restaurant", "pro_shop", "driving_range"],
        "operating_hours": {
            "weekday": "06:00-22:00",
            "weekend": "07:00-21:00"
        }
    }
}

Description:
- CLUB_CODE: Unique identifier for each club
- type: Booking system type
- url: API endpoint URL
- auth_type: Authentication method
- product_ids: Available booking types
- coordinates: Location for weather data
- facilities: Available services
''')

# weather.json
pdf.chapter_title('weather.json')
pdf.chapter_body('''
Structure:
{
    "api_key": "weather_service_api_key",
    "providers": {
        "primary": {
            "name": "openweathermap",
            "url": "https://api.openweathermap.org/data/2.5",
            "update_interval": 3600,
            "units": "metric"
        },
        "fallback": {
            "name": "weatherapi",
            "url": "https://api.weatherapi.com/v1",
            "update_interval": 7200
        }
    },
    "cache": {
        "enabled": true,
        "duration": 3600,
        "file": "weather_cache.json"
    },
    "alerts": {
        "enabled": true,
        "threshold": {
            "wind_speed": 10,
            "precipitation": 70
        }
    }
}

Description:
- api_key: Weather service authentication
- providers: Available weather services
- cache: Caching configuration
- alerts: Weather alert settings
''')

# events.json
pdf.chapter_title('external_events.yaml')
pdf.chapter_body('''
Structure:
events:
  - name: "Event Name"
    location: "Golf Club Name"
    coordinates:
      lat: 60.2859
      lon: 24.8427
    users:
      - "User1"
      - "User2"
    start: "2024-11-13T18:00:00"
    end: "2024-11-13T21:00:00"
    timezone: "Europe/Helsinki"
    address: "Club Address"
    repeat:
      frequency: "weekly"    # weekly or monthly
      until: "2025-04-02"   # end date for recurring events

Description:
- name: Event display name
- location: Golf club or venue name
- coordinates: Geographic coordinates for weather data
- users: List of users to include in the event
- start/end: ISO format datetime strings
- timezone: IANA timezone identifier
- address: Full venue address
- repeat: Optional recurring event settings
  - frequency: weekly/monthly
  - until: End date for recurrence
''')

# Add test_events.yaml documentation
pdf.chapter_title('test_events.yaml')
pdf.chapter_body('''
Structure:
- name: "Test Event Name"
  location: "Test Golf Club"
  coordinates:
    lat: 59.8940
    lon: 10.8282
  users:
    - "User1"
  start_time: "tomorrow 10:00"
  end_time: "tomorrow 14:00"
  timezone: "Europe/Oslo"
  address: "Test Club Address"

Description:
- name: Test event identifier
- location: Test venue name
- coordinates: Location for weather testing
- users: Test users to include
- start_time/end_time: Supports dynamic time formats:
  - "tomorrow HH:MM"
  - "N days HH:MM"
  - "today HH:MM"
- timezone: IANA timezone for testing
- address: Full test venue address

Used for testing different scenarios:
1. Time ranges: tomorrow, 3 days, 7 days
2. Times of day: morning, afternoon, evening
3. Regions: Nordic, Spain, Portugal, Mediterranean
''')

# Add attribute documentation for each configuration file
def document_config_attributes(pdf):
    pdf.add_page()
    pdf.chapter_title('Configuration File Attributes')
    pdf.chapter_body('Detailed documentation of all available configuration attributes and their purposes.')

    # users.json attributes
    pdf.sub_title('users.json Attributes')
    user_attributes = [
        {
            'name': 'email',
            'type': 'string',
            'description': 'Primary email address for user notifications and identification'
        },
        {
            'name': 'memberships',
            'type': 'array',
            'description': 'List of club memberships with authentication and booking preferences'
        },
        {
            'name': 'preferences',
            'type': 'object',
            'description': 'User-specific settings including default duration, timezone, and notification preferences'
        },
        {
            'name': 'default_duration',
            'type': 'integer',
            'description': 'Default booking duration in minutes (typical values: 120 for 18 holes, 60 for 9 holes)'
        },
        {
            'name': 'time_zone',
            'type': 'string',
            'description': 'User\'s timezone in IANA format (e.g., "Europe/Helsinki")'
        }
    ]
    pdf.add_attribute_table(user_attributes)

    # clubs.json attributes
    pdf.add_page()
    pdf.sub_title('clubs.json Attributes')
    club_attributes = [
        {
            'name': 'type',
            'type': 'string',
            'description': 'Booking system type (wisegolf, nexgolf, teetime). Determines API integration method'
        },
        {
            'name': 'url',
            'type': 'string',
            'description': 'Primary API endpoint URL for the booking system'
        },
        {
            'name': 'auth_type',
            'type': 'string',
            'description': 'Authentication method (token, cookie, basic). Each type requires specific auth_details'
        },
        {
            'name': 'product_ids',
            'type': 'object',
            'description': 'Mapping of booking types to internal IDs with descriptions and grouping'
        },
        {
            'name': 'coordinates',
            'type': 'object',
            'description': 'Geographic coordinates for weather data retrieval and distance calculations'
        },
        {
            'name': 'operating_hours',
            'type': 'object',
            'description': 'Business hours for different days, affects booking time validation'
        }
    ]
    pdf.add_attribute_table(club_attributes)

    # weather.json attributes
    pdf.add_page()
    pdf.sub_title('weather.json Attributes')
    weather_attributes = [
        {
            'name': 'api_key',
            'type': 'string',
            'description': 'Authentication key for weather service API access'
        },
        {
            'name': 'providers',
            'type': 'object',
            'description': 'Configuration for primary and fallback weather data providers'
        },
        {
            'name': 'update_interval',
            'type': 'integer',
            'description': 'Time in seconds between weather data updates (typical: 3600-7200)'
        },
        {
            'name': 'cache',
            'type': 'object',
            'description': 'Weather data caching settings to minimize API calls and improve performance'
        },
        {
            'name': 'alerts',
            'type': 'object',
            'description': 'Weather alert thresholds and notification settings'
        }
    ]
    pdf.add_attribute_table(weather_attributes)

    # events.json attributes
    pdf.add_page()
    pdf.sub_title('events.json Attributes')
    event_attributes = [
        {
            'name': 'sources',
            'type': 'object',
            'description': 'External event data sources with authentication and update settings'
        },
        {
            'name': 'filters',
            'type': 'object',
            'description': 'Event filtering rules based on type, priority, and other criteria'
        },
        {
            'name': 'sync',
            'type': 'object',
            'description': 'Synchronization settings including frequency and future event horizon'
        },
        {
            'name': 'categories',
            'type': 'array',
            'description': 'List of supported event categories for filtering and display'
        }
    ]
    pdf.add_attribute_table(event_attributes)

    # logging.json attributes
    pdf.add_page()
    pdf.sub_title('logging.json Attributes')
    logging_attributes = [
        {
            'name': 'formatters',
            'type': 'object',
            'description': 'Log message format configurations for different output types'
        },
        {
            'name': 'handlers',
            'type': 'object',
            'description': 'Log output handlers for file and console with rotation settings'
        },
        {
            'name': 'loggers',
            'type': 'object',
            'description': 'Logger configurations for different components with log levels'
        },
        {
            'name': 'maxBytes',
            'type': 'integer',
            'description': 'Maximum log file size before rotation (default: 10MB)'
        },
        {
            'name': 'backupCount',
            'type': 'integer',
            'description': 'Number of rotated log files to keep (default: 5)'
        }
    ]
    pdf.add_attribute_table(logging_attributes)

# Add the attribute documentation
document_config_attributes(pdf)

# Add config.yaml documentation
pdf.chapter_title('config.yaml')
pdf.chapter_body('''
Structure:
# Global configuration parameters
timezone: "Europe/Helsinki"

# Directory paths
directories:
  ics: "ics"
  config: "config"
  logs: "logs"

# ICS file paths (override default naming)
ics_files:
  User1: "ics/User1_golf_reservations.ics"
  User2: "ics/User2_golf_reservations.ics"

# API Keys
api_keys:
  weather:
    # Spanish Meteorological Agency (AEMET)
    aemet: "your-aemet-api-key"
    # OpenWeather API (Mediterranean region)
    openweather: "your-openweather-api-key"

# Logging configuration
logging:
  dev_level: "DEBUG"
  verbose_level: "INFO"
  default_level: "WARNING"

Description:
- timezone: Default timezone for the application
- directories: Path configurations
  - ics: Calendar file storage location
  - config: Configuration files location
  - logs: Log files location
- ics_files: Custom calendar file paths per user
- api_keys: External service API keys
  - weather: Weather service authentication
    - aemet: Spanish weather service
    - openweather: OpenWeather API
- logging: Log level configurations
  - dev_level: Development mode logging
  - verbose_level: Verbose mode logging
  - default_level: Default logging level
''')

# Add config.yaml attributes to the configuration attributes section
pdf.add_page()
pdf.sub_title('config.yaml Attributes')
config_attributes = [
    {
        'name': 'timezone',
        'type': 'string',
        'description': 'Default application timezone in IANA format (e.g., "Europe/Helsinki"). Used when no user-specific timezone is set.'
    },
    {
        'name': 'directories',
        'type': 'object',
        'description': 'Path configurations for different file types. Supports relative and absolute paths.'
    },
    {
        'name': 'ics_files',
        'type': 'object',
        'description': 'Custom calendar file path mappings per user. Overrides default naming convention.'
    },
    {
        'name': 'api_keys.weather',
        'type': 'object',
        'description': 'Weather service API keys. Supports multiple providers with region-specific configurations.'
    },
    {
        'name': 'logging',
        'type': 'object',
        'description': 'Logging configuration with different levels for development, verbose, and default modes.'
    }
]
pdf.add_attribute_table(config_attributes)

# Add YAML files attributes section
pdf.add_page()
pdf.chapter_title('YAML Configuration Files')
pdf.chapter_body('The application uses YAML format for configuration files that require more structured and readable formats. Below are the detailed attributes for each YAML file:')

# config.yaml attributes
pdf.sub_title('config.yaml (Primary Configuration)')
config_yaml_attributes = [
    {
        'name': 'timezone',
        'type': 'string',
        'description': 'Default application timezone (e.g., "Europe/Helsinki"). Required. Used as fallback when user timezone is not set.'
    },
    {
        'name': 'directories.ics',
        'type': 'string',
        'description': 'Calendar files directory path. Default: "ics". Can be relative or absolute path.'
    },
    {
        'name': 'directories.config',
        'type': 'string',
        'description': 'Configuration files directory path. Default: "config". Can be relative or absolute path.'
    },
    {
        'name': 'directories.logs',
        'type': 'string',
        'description': 'Log files directory path. Default: "logs". Can be relative or absolute path.'
    },
    {
        'name': 'ics_files',
        'type': 'map<string,string>',
        'description': 'Map of username to custom calendar file path. Optional. Overrides default "{username}_golf_reservations.ics" naming.'
    },
    {
        'name': 'api_keys.weather.aemet',
        'type': 'string',
        'description': 'Spanish Meteorological Agency API key. Required for Spanish weather data. Get from: https://opendata.aemet.es/'
    },
    {
        'name': 'api_keys.weather.openweather',
        'type': 'string',
        'description': 'OpenWeather API key. Required for Mediterranean region. Default key provided but can be overridden.'
    },
    {
        'name': 'logging.dev_level',
        'type': 'string',
        'description': 'Development mode log level. Default: "DEBUG". Options: DEBUG, INFO, WARNING, ERROR, CRITICAL'
    },
    {
        'name': 'logging.verbose_level',
        'type': 'string',
        'description': 'Verbose mode log level. Default: "INFO". Options: DEBUG, INFO, WARNING, ERROR, CRITICAL'
    },
    {
        'name': 'logging.default_level',
        'type': 'string',
        'description': 'Default log level. Default: "WARNING". Options: DEBUG, INFO, WARNING, ERROR, CRITICAL'
    }
]
pdf.add_attribute_table(config_yaml_attributes)

# external_events.yaml attributes
pdf.add_page()
pdf.sub_title('external_events.yaml (External Events)')
external_events_attributes = [
    {
        'name': 'events[].name',
        'type': 'string',
        'description': 'Event display name. Required. Used in calendar entries and logs.'
    },
    {
        'name': 'events[].location',
        'type': 'string',
        'description': 'Golf club or venue name. Required. Used for location display and weather lookup.'
    },
    {
        'name': 'events[].coordinates.lat',
        'type': 'float',
        'description': 'Venue latitude. Required. Used for weather data retrieval. Range: -90 to 90.'
    },
    {
        'name': 'events[].coordinates.lon',
        'type': 'float',
        'description': 'Venue longitude. Required. Used for weather data retrieval. Range: -180 to 180.'
    },
    {
        'name': 'events[].users',
        'type': 'string[]',
        'description': 'List of usernames to include in event. Required. Must match user configuration names.'
    },
    {
        'name': 'events[].start',
        'type': 'datetime',
        'description': 'Event start time in ISO format (YYYY-MM-DDTHH:MM:SS). Required. Must be in specified timezone.'
    },
    {
        'name': 'events[].end',
        'type': 'datetime',
        'description': 'Event end time in ISO format (YYYY-MM-DDTHH:MM:SS). Required. Must be after start time.'
    },
    {
        'name': 'events[].timezone',
        'type': 'string',
        'description': 'IANA timezone identifier. Required. Used for time conversions and weather data.'
    },
    {
        'name': 'events[].address',
        'type': 'string',
        'description': 'Full venue address. Optional. Used in calendar location field.'
    },
    {
        'name': 'events[].repeat.frequency',
        'type': 'string',
        'description': 'Recurrence frequency. Optional. Values: "weekly" or "monthly". Creates recurring events.'
    },
    {
        'name': 'events[].repeat.until',
        'type': 'date',
        'description': 'Recurrence end date in ISO format (YYYY-MM-DD). Required if repeat is set. Last instance date.'
    }
]
pdf.add_attribute_table(external_events_attributes)

# test_events.yaml attributes
pdf.add_page()
pdf.sub_title('test_events.yaml (Test Configuration)')
test_events_attributes = [
    {
        'name': 'name',
        'type': 'string',
        'description': 'Test event identifier. Required. Used to identify test case purpose.'
    },
    {
        'name': 'location',
        'type': 'string',
        'description': 'Test venue name. Required. Used to test location handling.'
    },
    {
        'name': 'coordinates',
        'type': 'object',
        'description': 'Geographic coordinates for weather testing. Required. Tests different weather service regions.'
    },
    {
        'name': 'users',
        'type': 'string[]',
        'description': 'Test user list. Required. Must exist in user configuration.'
    },
    {
        'name': 'start_time',
        'type': 'string',
        'description': 'Dynamic start time. Required. Formats: "tomorrow HH:MM", "N days HH:MM", "today HH:MM".'
    },
    {
        'name': 'end_time',
        'type': 'string',
        'description': 'Dynamic end time. Required. Same format as start_time. Must be after start_time.'
    },
    {
        'name': 'timezone',
        'type': 'string',
        'description': 'IANA timezone. Required. Tests timezone handling and conversions.'
    },
    {
        'name': 'address',
        'type': 'string',
        'description': 'Test venue address. Optional. Tests address formatting and display.'
    }
]
pdf.add_attribute_table(test_events_attributes)

# Add section about the top 3 most important configuration files
pdf.add_page()
pdf.chapter_title('Core Configuration Files')
pdf.chapter_body('''The application relies primarily on three key configuration files that must be properly configured for basic functionality:

1. config.yaml - Global Application Settings
   - Contains essential application-wide settings
   - Defines directory structures and paths
   - Manages API keys and authentication
   - Controls logging behavior
   - Required for application startup

2. users.json - User Management
   - Stores user profiles and credentials
   - Manages club memberships
   - Defines user preferences
   - Handles authentication details
   - Required for booking functionality

3. clubs.json - Golf Club Configuration
   - Defines supported golf clubs
   - Contains API endpoints and authentication
   - Manages booking types and products
   - Stores facility information
   - Required for reservation system

These files form the core configuration backbone and must be present and properly formatted for the application to function correctly.''')

# Add configuration relationships diagram
with Diagram("Configuration Dependencies", filename="docs/diagrams/config_dependencies", show=False, direction="LR", graph_attr={
    "ratio": "0.6",
    "fontsize": "11",
    "ranksep": "0.4",
    "nodesep": "0.3",
    "splines": "polyline"
}):
    with Cluster("Core Configuration"):
        config = Document("config.yaml")
        users = Document("users.json")
        clubs = Document("clubs.json")
    
    with Cluster("Extended Configuration"):
        weather = Document("weather.json")
        ext_events = Document("external_events.yaml")
        test_events = Document("test_events.yaml")
    
    config >> users
    config >> clubs
    config >> weather
    clubs >> ext_events
    clubs >> test_events
    users >> ext_events
    users >> test_events

pdf.add_image('docs/diagrams/config_dependencies.png')

# Add Weather APIs section
pdf.add_page()
pdf.chapter_title('Weather Service APIs')
pdf.chapter_body('''The application uses multiple weather service APIs based on geographic location. Each service has its own request format, response structure, and specific features.''')

# Weather Service Selection
pdf.sub_title('Weather Service Selection')
pdf.chapter_body('''The appropriate weather service is selected based on coordinates:

• Nordic Region (55°N-72°N, 3°E-32°E):
  - Service: MET Norway (met.no) 
  - Coverage: Norway, Sweden, Finland
  - Free service, no API key required
  - Hourly forecasts up to 48 hours

• Portugal (-9.5°W to -6.2°W):
  - Service: IPMA (Portuguese Institute for Sea and Atmosphere)
  - Coverage: Portugal mainland and islands
  - Free service, no API key required
  - Daily forecasts with 3-hour resolution

• Spain (-7°W to 5°E):
  - Service: AEMET (Spanish State Meteorological Agency)
  - Coverage: Spain mainland and islands
  - Requires API key from opendata.aemet.es
  - Hourly and daily forecasts

• Mediterranean Region (Other locations):
  - Service: OpenWeather API
  - Global coverage as fallback
  - Requires API key
  - Various forecast products''')

# MET Norway API
pdf.sub_title('MET Norway (met.no)')
pdf.chapter_body('''
Request Format:
GET https://api.met.no/weatherapi/locationforecast/2.0/complete
Parameters:
- lat: Latitude (-90 to 90)
- lon: Longitude (-180 to 180)
- altitude: Optional elevation in meters

Headers Required:
- User-Agent: Application identifier (required)
- Accept: application/json

Example Response:
{
    "type": "Feature",
    "geometry": {
        "type": "Point",
        "coordinates": [24.8427, 60.2859, 15]
    },
    "properties": {
        "timeseries": [
            {
                "time": "2024-01-26T12:00:00Z",
                "data": {
                    "instant": {
                        "details": {
                            "air_temperature": -2.3,
                            "wind_speed": 4.2,
                            "wind_from_direction": 180,
                            "relative_humidity": 85.0
                        }
                    },
                    "next_1_hours": {
                        "summary": {
                            "symbol_code": "cloudy"
                        },
                        "details": {
                            "precipitation_amount": 0.2
                        }
                    }
                }
            }
        ]
    }
}

Key Attributes:
- time: ISO 8601 timestamp
- air_temperature: Celsius
- wind_speed: meters/second
- wind_from_direction: degrees (0-360)
- precipitation_amount: millimeters
- symbol_code: Weather condition code
- relative_humidity: percentage''')

# IPMA API
pdf.sub_title('IPMA (Portuguese Weather Service)')
pdf.chapter_body('''
Request Format:
GET https://api.ipma.pt/open-data/forecast/meteorology/cities/daily/{city_id}.json

Parameters:
- city_id: IPMA location identifier

Example Response:
{
    "data": [
        {
            "precipitaProb": 85.0,
            "tMin": 12.4,
            "tMax": 18.7,
            "predWindDir": "S",
            "idWeatherType": 6,
            "classWindSpeed": 2,
            "forecastDate": "2024-01-26"
        }
    ],
    "globalIdLocal": 1110600,
    "dataUpdate": "2024-01-26T09:32:51"
}

Key Attributes:
- precipitaProb: Precipitation probability (0-100)
- tMin/tMax: Temperature range in Celsius
- predWindDir: Wind direction (N,S,E,W,NE,SE,SW,NW)
- idWeatherType: Weather condition code
- classWindSpeed: Wind speed class (1-9)
- forecastDate: YYYY-MM-DD format''')

# AEMET API
pdf.sub_title('AEMET (Spanish Weather Service)')
pdf.chapter_body('''
Request Format:
1. Get Data URL:
GET https://opendata.aemet.es/opendata/api/prediccion/especifica/municipio/horaria/{municipality_id}
Headers:
- api_key: Your AEMET API key

2. Fetch Forecast:
GET {data_url} (from step 1 response)

Example Response:
{
    "elaborado": "2024-01-26T09:00:00",
    "prediccion": {
        "dia": [
            {
                "fecha": "2024-01-26",
                "temperatura": {
                    "dato": [
                        {
                            "hora": 6,
                            "valor": 15.4
                        }
                    ]
                },
                "precipitacion": {
                    "dato": [
                        {
                            "hora": 6,
                            "valor": 0.0
                        }
                    ]
                },
                "viento": [
                    {
                        "direccion": "S",
                        "velocidad": 15
                    }
                ]
            }
        ]
    }
}

Key Attributes:
- elaborado: Forecast generation time
- fecha: Date YYYY-MM-DD
- hora: Hour (0-23)
- temperatura.valor: Celsius
- precipitacion.valor: mm/hour
- viento.velocidad: km/h
- viento.direccion: Wind direction''')

# OpenWeather API
pdf.sub_title('OpenWeather API (Mediterranean/Fallback)')
pdf.chapter_body('''
Request Format:
GET https://api.openweathermap.org/data/2.5/onecall
Parameters:
- lat: Latitude
- lon: Longitude
- appid: API key
- units: metric
- exclude: Optional parts to exclude

Example Response:
{
    "lat": 36.7584,
    "lon": 31.5876,
    "timezone": "Europe/Istanbul",
    "current": {
        "dt": 1706277600,
        "temp": 18.2,
        "feels_like": 17.8,
        "humidity": 65,
        "wind_speed": 3.6,
        "wind_deg": 180,
        "weather": [
            {
                "id": 800,
                "main": "Clear",
                "description": "clear sky"
            }
        ]
    },
    "hourly": [
        {
            "dt": 1706281200,
            "temp": 18.5,
            "pop": 0.2,
            "weather": [{"id": 800, "main": "Clear"}]
        }
    ]
}

Key Attributes:
- dt: Unix timestamp
- temp: Temperature in Celsius
- feels_like: Apparent temperature
- humidity: Relative humidity %
- wind_speed: meters/second
- wind_deg: degrees (meteorological)
- pop: Probability of precipitation
- weather.id: Condition code
- weather.description: Human readable description''')

# Weather Data Processing
pdf.sub_title('Weather Data Processing')
pdf.chapter_body('''The application processes weather data uniformly regardless of the source:

1. Data Retrieval:
   - Select appropriate service based on coordinates
   - Fetch data with error handling and retries
   - Cache responses to minimize API calls

2. Data Normalization:
   - Convert all temperatures to Celsius
   - Standardize wind speeds to m/s
   - Normalize precipitation to mm
   - Convert timestamps to local timezone

3. Forecast Assembly:
   - Combine data points for event duration
   - Calculate averages and extremes
   - Generate human-readable summary
   - Add weather alerts if applicable

4. Cache Management:
   - Store processed data
   - Update based on configured intervals
   - Separate caches per region
   - Automatic cache invalidation''')

# Add an enhanced weather service regions diagram
with Diagram("Weather Service Regions", 
            filename="docs/diagrams/weather_regions",
            show=False,
            direction="TB",
            graph_attr={
                "ratio": "0.7",
                "fontsize": "11",
                "ranksep": "0.6",
                "nodesep": "0.4",
                "splines": "ortho"
            }):
    
    with Cluster("Regional Weather Services"):
        with Cluster("Nordic Region\n55°N-72°N, 3°E-32°E"):
            met = Internet("MET Norway")
            met_info = Document("• Free service\n• No API key\n• 48h forecasts\n• 1h resolution")
            met - met_info
        
        with Cluster("Portugal\n-9.5°W to -6.2°W"):
            ipma = Internet("IPMA")
            ipma_info = Document("• Free service\n• No API key\n• Daily forecasts\n• 3h resolution")
            ipma - ipma_info
        
        with Cluster("Spain\n-7°W to 5°E"):
            aemet = Internet("AEMET")
            aemet_info = Document("• API key required\n• Hourly data\n• Municipality based\n• Two-step auth")
            aemet - aemet_info
        
        with Cluster("Mediterranean\n& Global Fallback"):
            openweather = Internet("OpenWeather")
            ow_info = Document("• API key required\n• Global coverage\n• Multiple products\n• Primary fallback")
            openweather - ow_info
    
    with Cluster("Data Processing Pipeline"):
        coords = Python("Coordinate\nValidator")
        selector = Python("Region\nDetector")
        processor = Python("Data\nNormalizer")
        cache = Storage("Regional\nCache")
        
        coords >> selector
        selector >> met
        selector >> ipma
        selector >> aemet
        selector >> openweather
        
        met >> processor
        ipma >> processor
        aemet >> processor
        openweather >> processor
        
        processor >> cache

pdf.add_image('docs/diagrams/weather_regions.png')

# Add Error Handling and Fallback Strategies section
pdf.add_page()
pdf.chapter_title('Weather Service Error Handling')
pdf.chapter_body('''The application implements comprehensive error handling and fallback strategies for weather data retrieval:''')

# Error Handling
pdf.sub_title('Error Handling by Service')
pdf.chapter_body('''
1. MET Norway (met.no):
   - Rate Limiting: Exponential backoff with max 3 retries
   - Invalid Coordinates: Fallback to nearest valid point
   - Service Outage: Switch to OpenWeather API
   - Response Validation:
     • Missing data points: Interpolate from surrounding times
     • Invalid values: Use reasonable defaults
     • Timezone issues: Convert all to UTC then local

2. IPMA (Portugal):
   - City ID Not Found: Use nearest city based on coordinates
   - Missing Daily Data: Fall back to 3-hour forecasts
   - Authentication Issues: Retry with delay
   - Data Quality:
     • Temperature range validation
     • Wind speed class conversion
     • Precipitation probability normalization

3. AEMET (Spain):
   - Two-Step Request Handling:
     • Step 1: Get data URL with retry on failure
     • Step 2: Fetch actual data with separate retry logic
   - API Key Issues:
     • Validate key before requests
     • Auto-refresh if expired
     • Fall back to OpenWeather if key invalid
   - Municipality Lookup:
     • Cache municipality IDs
     • Use nearest if exact match not found
     • Fall back to provincial forecast

4. OpenWeather (Mediterranean/Fallback):
   - Primary Fallback Service:
     • Used when regional services fail
     • Provides consistent data format
     • Global coverage
   - API Key Management:
     • Rotate between multiple keys if available
     • Monitor usage limits
     • Implement rate limiting''')

# Fallback Strategies
pdf.sub_title('Fallback Strategy Implementation')
pdf.chapter_body('''
1. Service Selection Fallbacks:
   • Primary: Region-specific service (MET/IPMA/AEMET)
   • Secondary: OpenWeather API
   • Tertiary: Cached historical data
   • Last Resort: Default weather parameters

2. Data Quality Assurance:
   • Validate all incoming data
   • Check value ranges and units
   • Ensure timestamp consistency
   • Verify coordinate boundaries

3. Cache Management:
   • Store successful responses
   • Implement sliding expiration
   • Separate caches per region
   • Progressive data refresh

4. Recovery Mechanisms:
   • Automatic service switching
   • Graceful degradation
   • Partial data handling
   • User notification''')

# Add a weather service fallback diagram
with Diagram("Weather Service Fallbacks", 
            filename="docs/diagrams/weather_fallbacks",
            show=False,
            direction="LR",
            graph_attr={
                "ratio": "0.6",
                "fontsize": "11",
                "ranksep": "0.4",
                "nodesep": "0.3",
                "splines": "ortho"
            }):
    with Cluster("Primary Services"):
        met = Internet("MET Norway")
        ipma = Internet("IPMA")
        aemet = Internet("AEMET")
    
    with Cluster("Fallback Chain"):
        openweather = Internet("OpenWeather")
        cache = Storage("Cache")
        defaults = Storage("Defaults")
    
    with Cluster("Error Handling"):
        validator = Python("Validator")
        retry = Python("Retry Logic")
        fallback = Python("Fallback Manager")
    
    # Primary flow
    validator >> met
    validator >> ipma
    validator >> aemet
    
    # Error handling
    met >> retry
    ipma >> retry
    aemet >> retry
    retry >> fallback
    
    # Fallback flow
    fallback >> openweather
    fallback >> cache
    fallback >> defaults

pdf.add_image('docs/diagrams/weather_fallbacks.png')

# Add error codes and handling table
pdf.add_page()
pdf.sub_title('Weather Service Error Codes and Handling')
error_codes = [
    {
        'name': 'Rate Limit Exceeded',
        'type': 'HTTP 429',
        'description': 'Implement exponential backoff, retry after specified delay, switch to fallback if persistent.'
    },
    {
        'name': 'Invalid API Key',
        'type': 'HTTP 401/403',
        'description': 'Validate key, attempt refresh if possible, switch to fallback service if unresolvable.'
    },
    {
        'name': 'Service Unavailable',
        'type': 'HTTP 503',
        'description': 'Retry with backoff, switch to fallback service after max retries, use cached data if available.'
    },
    {
        'name': 'Invalid Coordinates',
        'type': 'HTTP 400',
        'description': 'Validate coordinates before request, use nearest valid point, fall back to regional defaults.'
    },
    {
        'name': 'Timeout',
        'type': 'Network',
        'description': 'Implement request timeout, retry with increased timeout, switch to fallback after max attempts.'
    },
    {
        'name': 'Malformed Response',
        'type': 'Parse Error',
        'description': 'Validate response schema, attempt partial data extraction, use cached data if parsing fails.'
    },
    {
        'name': 'Missing Data Points',
        'type': 'Data Quality',
        'description': 'Interpolate from available data, use historical averages, fall back to conservative estimates.'
    },
    {
        'name': 'Invalid Values',
        'type': 'Data Quality',
        'description': 'Apply range validation, use nearest valid value, fall back to regional averages if necessary.'
    }
]
pdf.add_attribute_table(error_codes)

# Add CRM API Documentation
pdf.add_page()
pdf.chapter_title('CRM API Documentation')
pdf.chapter_body('''The Golf Calendar system integrates with multiple CRM systems for golf club booking management. Each system has its own API structure, authentication methods, and data formats.''')

# WiseGolf API
pdf.sub_title('WiseGolf API')
pdf.chapter_body('''
Base URL: https://api.wisegolf.club/v2

Authentication:
- Type: Bearer Token
- Header: Authorization: Bearer <token>
- Token Validity: 24 hours
- Refresh: POST /auth/refresh with refresh_token

Key Endpoints:

1. Authentication
   POST /auth/login
   {
     "username": "user@example.com",
     "password": "encrypted_password"
   }
   Response:
   {
     "access_token": "jwt_token",
     "refresh_token": "refresh_token",
     "expires_in": 86400
   }

2. Tee Time Search
   GET /tee-times/search
   Parameters:
   - date: YYYY-MM-DD
   - course_id: integer
   - players: integer (1-4)
   - start_time: HH:MM
   - end_time: HH:MM
   
   Response:
   {
     "available_times": [
       {
         "id": "12345",
         "course_id": 1,
         "datetime": "2024-01-26T10:00:00Z",
         "available_slots": 4,
         "price_category": "member",
         "duration_minutes": 120,
         "booking_restrictions": {
           "min_players": 1,
           "max_players": 4,
           "member_only": true
         }
       }
     ],
     "course_info": {
       "name": "Main Course",
       "holes": 18,
       "walking_time": 120
     }
   }

3. Reservation Creation
   POST /reservations
   Body:
   {
     "tee_time_id": "12345",
     "players": [
       {
         "member_id": "M123",
         "name": "John Doe",
         "handicap": 15.4,
         "guest": false
       }
     ],
     "special_requests": {
       "cart": true,
       "rental_clubs": false
     }
   }
   
   Response:
   {
     "reservation_id": "R789",
     "confirmation_code": "WG2024123",
     "status": "confirmed",
     "payment_required": false,
     "calendar_entry": {
       "start": "2024-01-26T10:00:00Z",
       "end": "2024-01-26T12:00:00Z",
       "location": {
         "name": "Golf Club Name",
         "address": "Club Address",
         "coordinates": {
           "lat": 60.2859,
           "lon": 24.8427
         }
       }
     }
   }

4. Member Profile
   GET /clubs/{club_id}/members/{member_id}
   Response:
   {
     "member_id": "M123",
     "status": "active",
     "membership_type": "full",
     "handicap": 15.4,
     "booking_privileges": {
       "max_advance_days": 14,
       "max_active_bookings": 3,
       "guest_allowed": true
     },
     "preferences": {
       "preferred_tee_times": ["morning", "afternoon"],
       "notifications": {
         "email": true,
         "sms": false
       }
     }
   }

Key Attributes:
- member_id: Unique member identifier
- handicap: Current playing handicap
- booking_privileges: Member-specific booking rules
- tee_time_id: Unique identifier for available time slot
- confirmation_code: Booking reference number
- status: Reservation status (confirmed, pending, cancelled)''')

# NexGolf API
pdf.sub_title('NexGolf API')
pdf.chapter_body('''
Base URL: https://nexgolf.fi/api/v3

Authentication:
- Type: Cookie-based Session
- Login Endpoint: POST /auth/session
- Session Duration: 12 hours
- CSRF Token Required: X-CSRF-Token header

Key Endpoints:

1. Session Creation
   POST /auth/session
   {
     "club_id": "NGF123",
     "username": "member_id",
     "password": "encrypted_password"
   }
   Response:
   {
     "session_id": "sess_12345",
     "csrf_token": "csrf_token_value",
     "valid_until": "2024-01-27T12:00:00Z"
   }

2. Available Times
   GET /clubs/{club_id}/times
   Parameters:
   - date: YYYY-MM-DD
   - course: integer
   - group_size: integer
   
   Response:
   {
     "times": [
       {
         "slot_id": "NG789",
         "time": "2024-01-26T09:00:00+02:00",
         "course": {
           "id": 1,
           "name": "Pääkenttä",
           "type": "18-hole"
         },
         "availability": {
           "total": 4,
           "booked": 1,
           "minimum_players": 2
         },
         "restrictions": {
           "members_only": true,
           "competition": false
         }
       }
     ],
     "day_info": {
       "sunrise": "08:15",
       "sunset": "16:45",
       "maintenance": []
     }
   }

3. Booking Creation
   POST /clubs/{club_id}/bookings
   Body:
   {
     "slot_id": "NG789",
     "players": [
       {
         "id": "NGM456",
         "type": "member",
         "extras": {
           "cart": true
         }
       }
     ],
     "notes": "Cart requested"
   }
   
   Response:
   {
     "booking_id": "NGB123",
     "reference": "NG20240126-123",
     "status": "confirmed",
     "details": {
       "start_time": "2024-01-26T09:00:00+02:00",
       "course": "Pääkenttä",
       "player_count": 1,
       "extras": {
         "cart": {
           "confirmed": true,
           "number": "Cart-7"
         }
       }
     }
   }

4. Member Details
   GET /clubs/{club_id}/members/{member_id}
   Response:
   {
     "id": "NGM456",
     "membership": {
       "type": "full",
       "valid_until": "2024-12-31",
       "home_club": true
     },
     "playing_rights": {
       "advance_booking_days": 7,
       "booking_quota": {
         "active_limit": 3,
         "current_count": 1
       }
     },
     "handicap_info": {
       "exact": 12.4,
       "playing": 12,
       "last_updated": "2024-01-20"
     }
   }

Key Attributes:
- slot_id: Unique time slot identifier
- booking_id: Unique reservation identifier
- reference: Human-readable booking reference
- player_count: Number of players in booking
- handicap_info: Current handicap details''')

# TeeTime API
pdf.sub_title('TeeTime API')
pdf.chapter_body('''
Base URL: https://teetimeapi.golf/v1

Authentication:
- Type: API Key
- Header: X-Api-Key: <key>
- Additional: Club-specific credentials in request body

Key Endpoints:

1. Club Authentication
   POST /clubs/auth
   {
     "club_id": "TT123",
     "api_key": "club_specific_key",
     "user_credentials": {
       "member_number": "12345",
       "pin": "encrypted_pin"
     }
   }
   Response:
   {
     "auth_token": "tt_session_token",
     "permissions": ["view", "book", "modify"],
     "expires_at": "2024-01-27T00:00:00Z"
   }

2. Time Slots
   GET /clubs/{club_id}/slots
   Parameters:
   - date: YYYY-MM-DD
   - players: integer
   - time_range: morning|afternoon|evening
   
   Response:
   {
     "date": "2024-01-26",
     "slots": [
       {
         "id": "TTS456",
         "start": "2024-01-26T08:30:00+02:00",
         "product": {
           "id": "18H",
           "name": "18 Holes",
           "duration": 120
         },
         "capacity": {
           "total": 4,
           "available": 3
         },
         "pricing": {
           "member": 0,
           "guest": 65
         },
         "booking_window": {
           "opens": "2024-01-12T00:00:00Z",
           "closes": "2024-01-26T07:30:00Z"
         }
       }
     ],
     "weather_advisory": null
   }

3. Create Booking
   POST /clubs/{club_id}/bookings
   Body:
   {
     "slot_id": "TTS456",
     "booking": {
       "players": [
         {
           "member_number": "12345",
           "type": "member",
           "rental_set": null
         }
       ],
       "preferences": {
         "starting_tee": 1,
         "cart_required": false
       }
     }
   }
   
   Response:
   {
     "booking": {
       "id": "TTB789",
       "reference": "TT-20240126-789",
       "status": "confirmed",
       "slot": {
         "date": "2024-01-26",
         "time": "08:30",
         "course": "Main Course"
       },
       "players": [
         {
           "member_number": "12345",
           "checked_in": false,
           "rental_equipment": []
         }
       ],
       "payment_status": "not_required",
       "cancellation_policy": {
         "deadline": "2024-01-25T16:00:00Z",
         "fee_applies": true
       }
     }
   }

4. Player Profile
   GET /clubs/{club_id}/players/{member_number}
   Response:
   {
     "member": {
       "number": "12345",
       "category": "full_member",
       "status": "active"
     },
     "playing_rights": {
       "booking_horizon": 14,
       "concurrent_bookings": 3,
       "guest_privileges": true
     },
     "statistics": {
       "rounds_played": 45,
       "no_shows": 0,
       "average_pace": 118
     },
     "equipment": {
       "own_cart": false,
       "rental_preferences": {
         "club_set": "right-handed",
         "cart": "single"
       }
     }
   }

Key Attributes:
- slot_id: Unique time slot identifier
- booking.id: Unique booking reference
- member_number: Player identification
- status: Booking confirmation status
- cancellation_policy: Rules for cancellation''')

# Add API Integration Diagram
with Diagram("CRM API Integration", 
            filename="docs/diagrams/crm_api_integration",
            show=False,
            direction="TB",
            graph_attr={
                "ratio": "0.7",
                "fontsize": "11",
                "ranksep": "0.6",
                "nodesep": "0.4",
                "splines": "ortho"
            }):
    
    with Cluster("Golf Calendar System"):
        app = Python("Core Application")
        auth = Python("Auth Manager")
        booking = Python("Booking Service")
        cache = Storage("Response Cache")
    
    with Cluster("CRM Systems"):
        with Cluster("WiseGolf"):
            wise = Internet("WiseGolf API")
            wise_auth = Document("Bearer Token")
            wise_endpoints = Document("• /tee-times\n• /reservations\n• /members")
            wise - wise_auth
            wise - wise_endpoints
        
        with Cluster("NexGolf"):
            nex = Internet("NexGolf API")
            nex_auth = Document("Cookie Session")
            nex_endpoints = Document("• /times\n• /bookings\n• /members")
            nex - nex_auth
            nex - nex_endpoints
        
        with Cluster("TeeTime"):
            tee = Internet("TeeTime API")
            tee_auth = Document("API Key + Token")
            tee_endpoints = Document("• /slots\n• /bookings\n• /players")
            tee - tee_auth
            tee - tee_endpoints
    
    app >> auth
    auth >> wise
    auth >> nex
    auth >> tee
    
    app >> booking
    booking >> wise
    booking >> nex
    booking >> tee
    
    wise >> cache
    nex >> cache
    tee >> cache

pdf.add_image('docs/diagrams/crm_api_integration.png')

# Add API Authentication Flow Diagram
with Diagram("CRM Authentication Flows", 
            filename="docs/diagrams/crm_auth_flows",
            show=False,
            direction="LR",
            graph_attr={
                "ratio": "0.6",
                "fontsize": "11",
                "ranksep": "0.5",
                "nodesep": "0.4",
                "splines": "ortho"
            }):
    
    with Cluster("Client"):
        auth = Python("Auth Manager")
        cache = Storage("Token Cache")
    
    with Cluster("WiseGolf"):
        wise_login = Internet("POST /auth/login")
        wise_token = Document("JWT Token")
        wise_refresh = Internet("POST /auth/refresh")
    
    with Cluster("NexGolf"):
        nex_login = Internet("POST /auth/session")
        nex_cookie = Document("Session Cookie")
        nex_csrf = Document("CSRF Token")
    
    with Cluster("TeeTime"):
        tee_auth = Internet("POST /clubs/auth")
        tee_key = Document("API Key")
        tee_token = Document("Session Token")
    
    # WiseGolf flow
    auth >> wise_login
    wise_login >> wise_token
    wise_token >> cache
    cache >> wise_refresh
    wise_refresh >> wise_token
    
    # NexGolf flow
    auth >> nex_login
    nex_login >> nex_cookie
    nex_login >> nex_csrf
    nex_cookie >> cache
    nex_csrf >> cache
    
    # TeeTime flow
    auth >> tee_auth
    tee_key >> tee_auth
    tee_auth >> tee_token
    tee_token >> cache

pdf.add_image('docs/diagrams/crm_auth_flows.png')

# Add API Response Handling section
pdf.add_page()
pdf.chapter_title('CRM API Response Handling')
pdf.chapter_body('''The Golf Calendar system implements comprehensive response handling for each CRM API:''')

# Response Processing
pdf.sub_title('Response Processing by System')
pdf.chapter_body('''
1. WiseGolf:
   - Response Format: JSON with snake_case
   - Date Format: ISO 8601 with UTC
   - Error Handling:
     • HTTP 401: Token refresh required
     • HTTP 429: Rate limiting (exponential backoff)
     • HTTP 409: Booking conflict resolution
   - Data Validation:
     • Schema validation for all responses
     • Handicap range checks
     • Time slot availability confirmation

2. NexGolf:
   - Response Format: JSON with camelCase
   - Date Format: ISO 8601 with local timezone
   - Session Management:
     • Cookie renewal
     • CSRF token validation
     • Session expiry handling
   - Booking Validation:
     • Member status verification
     • Booking quota checks
     • Time slot locking

3. TeeTime:
   - Response Format: JSON with mixed case
   - Date Format: YYYY-MM-DD + HH:mm
   - Authentication:
     • API key validation
     • Club-specific credentials
     • Token refresh management
   - Response Processing:
     • Time zone conversions
     • Price calculation
     • Availability updates''')

# Add API Error Codes table
pdf.add_page()
pdf.sub_title('CRM API Error Codes and Handling')
error_codes = [
    {
        'name': 'Authentication Failed',
        'type': 'HTTP 401',
        'description': 'Refresh authentication token or prompt for new credentials.'
    },
    {
        'name': 'Rate Limit Exceeded',
        'type': 'HTTP 429',
        'description': 'Implement backoff strategy, cache responses, retry with exponential delay.'
    },
    {
        'name': 'Booking Conflict',
        'type': 'HTTP 409',
        'description': 'Check availability again, offer alternative slots, handle concurrent bookings.'
    },
    {
        'name': 'Invalid Request',
        'type': 'HTTP 400',
        'description': 'Validate request parameters, check time formats, verify member status.'
    },
    {
        'name': 'Resource Not Found',
        'type': 'HTTP 404',
        'description': 'Verify club/course IDs, check member numbers, validate time slot existence.'
    },
    {
        'name': 'Quota Exceeded',
        'type': 'Business Logic',
        'description': 'Check booking limits, verify member privileges, handle waiting lists.'
    },
    {
        'name': 'Time Slot Locked',
        'type': 'Business Logic',
        'description': 'Implement retry mechanism, check alternative slots, handle concurrent access.'
    },
    {
        'name': 'Invalid Member Status',
        'type': 'Business Logic',
        'description': 'Verify membership status, check playing rights, validate handicap requirements.'
    }
]
pdf.add_attribute_table(error_codes)

# Add Authentication Strategies section
pdf.add_page()
pdf.chapter_title('Authentication Strategies')
pdf.chapter_body('''The Golf Calendar system implements multiple authentication strategies to handle different CRM systems:''')

# Authentication Types
pdf.sub_title('Authentication Types')
pdf.chapter_body('''
1. Token App Authentication (token_appauth):
   - Used by: WiseGolf, TeeTime
   - Flow:
     • Initial token request with credentials
     • Token stored in auth_details
     • Token included in Authorization header
     • Automatic token refresh when expired
   - Headers:
     • Authorization: Bearer <token>
     • Content-Type: application/json

2. Cookie Authentication (cookie):
   - Used by: NexGolf
   - Flow:
     • Session creation with credentials
     • Cookie stored in auth_details
     • Cookie included in subsequent requests
     • CSRF token handling where required
   - Headers:
     • Cookie: <session_cookie>
     • X-CSRF-Token: <csrf_token>

3. Query Authentication (query):
   - Used by: Legacy systems
   - Flow:
     • Credentials included as URL parameters
     • Session maintained through query params
     • Less secure, used only for legacy support
   - URL Format:
     • https://api.example.com/endpoint?token=<token>

4. Authentication Strategy Selection:
   - Based on club configuration
   - Fallback to unsupported strategy
   - Automatic strategy switching on failure
   - Credential refresh handling''')

# Add Authentication Flow Diagram
with Diagram("Authentication Strategy Flow", 
            filename="docs/diagrams/auth_strategy_flow",
            show=False,
            direction="TB",
            graph_attr={
                "ratio": "0.7",
                "fontsize": "11",
                "ranksep": "0.6",
                "nodesep": "0.4",
                "splines": "ortho"
            }):
    
    with Cluster("Auth Service"):
        auth = Python("Auth Service")
        strategy = Python("Strategy Selector")
        cache = Storage("Token Cache")
    
    with Cluster("Strategies"):
        with Cluster("Token Auth"):
            token = Python("Token Strategy")
            token_flow = Document("• Bearer Token\n• JWT\n• Auto Refresh")
            token - token_flow
        
        with Cluster("Cookie Auth"):
            cookie = Python("Cookie Strategy")
            cookie_flow = Document("• Session Cookie\n• CSRF Token\n• Session Renewal")
            cookie - cookie_flow
        
        with Cluster("Query Auth"):
            query = Python("Query Strategy")
            query_flow = Document("• URL Parameters\n• Session ID\n• Legacy Support")
            query - query_flow
    
    with Cluster("CRM Systems"):
        wise = Internet("WiseGolf")
        nex = Internet("NexGolf")
        tee = Internet("TeeTime")
    
    # Flow
    auth >> strategy
    strategy >> token
    strategy >> cookie
    strategy >> query
    
    token >> wise
    token >> tee
    cookie >> nex
    query >> wise

pdf.add_image('docs/diagrams/auth_strategy_flow.png')

# Add Authentication Error Handling
pdf.add_page()
pdf.sub_title('Authentication Error Handling')
auth_errors = [
    {
        'name': 'Token Expired',
        'type': 'Auth Error',
        'description': 'Attempt token refresh, if fails request new credentials, fall back to alternative auth method.'
    },
    {
        'name': 'Invalid Credentials',
        'type': 'Auth Error',
        'description': 'Clear stored credentials, prompt for new credentials, verify club configuration.'
    },
    {
        'name': 'Session Expired',
        'type': 'Auth Error',
        'description': 'Create new session, handle CSRF token refresh, maintain cookie jar.'
    },
    {
        'name': 'Missing CSRF Token',
        'type': 'Auth Error',
        'description': 'Request new CSRF token, update session cookies, retry request with new token.'
    },
    {
        'name': 'Rate Limited',
        'type': 'API Error',
        'description': 'Implement exponential backoff, rotate credentials if available, cache successful tokens.'
    },
    {
        'name': 'Invalid Token Format',
        'type': 'Auth Error',
        'description': 'Validate token format, check auth strategy compatibility, verify API version.'
    },
    {
        'name': 'Permission Denied',
        'type': 'Auth Error',
        'description': 'Verify membership status, check booking privileges, validate club access rights.'
    },
    {
        'name': 'Connection Failed',
        'type': 'Network Error',
        'description': 'Retry with backoff, check API endpoint availability, verify network connectivity.'
    }
]
pdf.add_attribute_table(auth_errors)

# Add Authentication Implementation
pdf.sub_title('Authentication Implementation')
pdf.chapter_body('''
1. Strategy Pattern Implementation:
   ```python
   class AuthStrategy:
       def create_headers(self, cookie_name: str, auth_details: Dict[str, str]) -> Dict[str, str]:
           """Create request headers based on auth type."""
           pass

       def build_full_url(self, club_details: Dict[str, Any], membership: Membership) -> str:
           """Build authenticated URL if required."""
           pass
   ```

2. Token Management:
   - Token Storage:
     • Secure storage in auth_details
     • Encrypted when at rest
     • Memory-only during runtime
   
   - Token Refresh:
     • Automatic refresh before expiry
     • Refresh token rotation
     • Failure recovery

3. Session Management:
   - Cookie Handling:
     • Secure cookie storage
     • Session expiry tracking
     • Automatic session renewal
   
   - CSRF Protection:
     • Token validation
     • Header inclusion
     • Token refresh

4. Security Considerations:
   - Credential Encryption:
     • Sensitive data encryption
     • Secure credential storage
     • Memory cleanup
   
   - Rate Limiting:
     • Request throttling
     • Exponential backoff
     • API key rotation''')

# Add Authentication Configuration
pdf.sub_title('Authentication Configuration')
auth_config = [
    {
        'name': 'auth_type',
        'type': 'string',
        'description': 'Authentication strategy type (token_appauth, cookie, query). Required. Determines auth flow.'
    },
    {
        'name': 'auth_details.token',
        'type': 'string',
        'description': 'Authentication token for token-based auth. Required for token_appauth.'
    },
    {
        'name': 'auth_details.refresh_token',
        'type': 'string',
        'description': 'Token for refreshing expired auth tokens. Optional for token_appauth.'
    },
    {
        'name': 'auth_details.cookie',
        'type': 'string',
        'description': 'Session cookie for cookie-based auth. Required for cookie auth type.'
    },
    {
        'name': 'auth_details.csrf_token',
        'type': 'string',
        'description': 'CSRF token for cookie-based auth. Required if CSRF protection enabled.'
    },
    {
        'name': 'cookie_name',
        'type': 'string',
        'description': 'Name of session cookie for cookie-based auth. Required for cookie auth type.'
    },
    {
        'name': 'token_expiry',
        'type': 'integer',
        'description': 'Token expiration time in seconds. Optional. Default varies by CRM.'
    },
    {
        'name': 'retry_limit',
        'type': 'integer',
        'description': 'Maximum number of auth retry attempts. Optional. Default: 3.'
    }
]
pdf.add_attribute_table(auth_config)

# Add Golf Club Factory section
pdf.add_page()
pdf.chapter_title('Golf Club Factory and Club Types')
pdf.chapter_body('''The Golf Calendar system uses a factory pattern to create and manage different types of golf club integrations. Each club type has its own specific implementation and requirements.''')

# Club Types
pdf.sub_title('Golf Club Types')
pdf.chapter_body('''
1. WiseGolf Club:
   - Modern REST API implementation
   - JWT-based authentication
   - Features:
     • Real-time availability
     • Member pricing
     • Advanced booking rules
     • Equipment rental
   - Configuration:
     • Requires ajaxUrl
     • Bearer token auth
     • Product IDs for booking types

2. WiseGolf0 Club (Legacy):
   - Original WiseGolf implementation
   - Cookie-based authentication
   - Features:
     • Basic availability checking
     • Simple booking flow
     • Limited member features
   - Configuration:
     • Requires shopURL
     • Session cookie auth
     • Basic product mapping

3. NexGolf Club:
   - Nordic golf club system
   - Session-based authentication
   - Features:
     • Competition support
     • Member management
     • Facility booking
     • Equipment tracking
   - Configuration:
     • Standard URL endpoint
     • CSRF protection
     • Club-specific settings

4. TeeTime Club:
   - Modern booking platform
   - API key authentication
   - Features:
     • Dynamic pricing
     • Guest booking
     • Weather integration
     • Mobile check-in
   - Configuration:
     • API endpoint URL
     • API key required
     • Product configuration''')

# Add Club Factory Diagram
with Diagram("Golf Club Factory", 
            filename="docs/diagrams/club_factory",
            show=False,
            direction="TB",
            graph_attr={
                "ratio": "0.7",
                "fontsize": "11",
                "ranksep": "0.6",
                "nodesep": "0.4",
                "splines": "ortho"
            }):
    
    with Cluster("Factory"):
        factory = Python("GolfClubFactory")
        base = Python("BaseGolfClub")
    
    with Cluster("Club Types"):
        with Cluster("WiseGolf"):
            wise = Python("WiseGolfClub")
            wise_config = Document("• ajaxUrl\n• Bearer Token\n• Product IDs")
            wise - wise_config
        
        with Cluster("WiseGolf0"):
            wise0 = Python("WiseGolf0Club")
            wise0_config = Document("• shopURL\n• Cookie Auth\n• Basic Products")
            wise0 - wise0_config
        
        with Cluster("NexGolf"):
            nex = Python("NexGolfClub")
            nex_config = Document("• Standard URL\n• CSRF Token\n• Club Settings")
            nex - nex_config
        
        with Cluster("TeeTime"):
            tee = Python("TeeTimeClub")
            tee_config = Document("• API Endpoint\n• API Key\n• Products")
            tee - tee_config
    
    # Factory pattern
    factory >> base
    base >> wise
    base >> wise0
    base >> nex
    base >> tee

pdf.add_image('docs/diagrams/club_factory.png')

# Club Configuration
pdf.add_page()
pdf.sub_title('Club Configuration Attributes')
club_config = [
    {
        'name': 'type',
        'type': 'string',
        'description': 'Club system type (wisegolf, wisegolf0, nexgolf, teetime). Required. Determines factory creation.'
    },
    {
        'name': 'url',
        'type': 'string',
        'description': 'Base API endpoint URL. Required for nexgolf and teetime.'
    },
    {
        'name': 'ajaxUrl',
        'type': 'string',
        'description': 'AJAX endpoint URL. Required for wisegolf type.'
    },
    {
        'name': 'shopURL',
        'type': 'string',
        'description': 'Shop system URL. Required for wisegolf0 type.'
    },
    {
        'name': 'variant',
        'type': 'string',
        'description': 'System variant for special handling. Optional.'
    },
    {
        'name': 'product',
        'type': 'object',
        'description': 'Product configuration for bookings. Required for some club types.'
    },
    {
        'name': 'address',
        'type': 'string',
        'description': 'Physical club address. Optional. Used for weather and calendar entries.'
    },
    {
        'name': 'timezone',
        'type': 'string',
        'description': 'Club timezone. Optional. Defaults to Europe/Helsinki.'
    }
]
pdf.add_attribute_table(club_config)

# Club Implementation
pdf.sub_title('Club Implementation')
pdf.chapter_body('''
1. Base Golf Club:
   ```python
   class BaseGolfClub(GolfClub, ABC):
       def __init__(self, name: str, auth_details: Dict[str, Any], 
                   club_details: Dict[str, Any], membership: Dict[str, Any]):
           self.auth_service = AuthService()
           self.club_details = club_details
           self.membership = membership
       
       @abstractmethod
       def get_reservations(self, user: User) -> List[Reservation]:
           """Get reservations for user."""
           pass
   ```

2. Factory Implementation:
   ```python
   class GolfClubFactory:
       @staticmethod
       def create_club(club_details: Dict[str, Any],
                      membership: Membership,
                      auth_service: AuthService) -> Optional[GolfClub]:
           club_type = club_details["type"]
           club_class = club_classes.get(club_type)
           return club_class(
               name=club_details.get("name"),
               url=club_details.get("url"),
               auth_service=auth_service,
               club_details=club_details
           )
   ```

3. Club Type Specifics:
   - WiseGolf Implementation:
     • Modern REST endpoints
     • JWT authentication
     • Real-time availability
   
   - WiseGolf0 Implementation:
     • Legacy endpoints
     • Cookie-based auth
     • Basic functionality
   
   - NexGolf Implementation:
     • Nordic system integration
     • Session management
     • Competition support
   
   - TeeTime Implementation:
     • API key authentication
     • Dynamic pricing
     • Weather integration

4. Common Features:
   - Reservation Management:
     • Fetch user reservations
     • Create new bookings
     • Cancel existing bookings
   
   - Member Handling:
     • Validate membership
     • Check booking rights
     • Handle guest players
   
   - Error Management:
     • Connection issues
     • Authentication errors
     • Booking conflicts''')

# Add Club Error Handling
pdf.add_page()
pdf.sub_title('Club System Error Handling')
club_errors = [
    {
        'name': 'Invalid Club Type',
        'type': 'Configuration',
        'description': 'Verify club type in configuration, check supported types, ensure factory implementation.'
    },
    {
        'name': 'Missing URL',
        'type': 'Configuration',
        'description': 'Check required URL configuration for club type, verify endpoint accessibility.'
    },
    {
        'name': 'Product Configuration',
        'type': 'Configuration',
        'description': 'Validate product IDs and mapping, check booking type configuration.'
    },
    {
        'name': 'Booking Failed',
        'type': 'Operation',
        'description': 'Verify availability, check member privileges, validate booking parameters.'
    },
    {
        'name': 'Reservation Fetch Failed',
        'type': 'Operation',
        'description': 'Check authentication, verify membership status, handle partial data.'
    },
    {
        'name': 'Invalid Response Format',
        'type': 'Data',
        'description': 'Validate API response format, handle schema changes, check API version.'
    },
    {
        'name': 'Member Validation Failed',
        'type': 'Authentication',
        'description': 'Verify membership details, check club access rights, validate credentials.'
    },
    {
        'name': 'System Unavailable',
        'type': 'Connection',
        'description': 'Implement retry logic, check system status, handle maintenance windows.'
    }
]
pdf.add_attribute_table(club_errors)

# Add Reservation Processing section
pdf.add_page()
pdf.chapter_title('Reservation Processing')
pdf.chapter_body('''The Golf Calendar system implements comprehensive reservation processing to handle bookings from multiple CRM systems and integrate them into user calendars.''')

# Reservation Flow
pdf.sub_title('Reservation Processing Flow')
pdf.chapter_body('''
1. Reservation Retrieval:
   - Fetch from multiple clubs
   - Handle different formats
   - Process past/future bookings
   - Deduplication handling

2. Data Normalization:
   - Standardize timestamps
   - Convert time zones
   - Normalize durations
   - Format descriptions

3. Calendar Integration:
   - Create calendar entries
   - Add weather information
   - Include location details
   - Set reminders

4. Optimization:
   - Cache responses
   - Batch processing
   - Incremental updates
   - Memory management''')

# Add Reservation Processing Diagram
with Diagram("Reservation Processing Flow", 
            filename="docs/diagrams/reservation_flow",
            show=False,
            direction="LR",
            graph_attr={
                "ratio": "0.7",
                "fontsize": "11",
                "ranksep": "0.6",
                "nodesep": "0.4",
                "splines": "ortho"
            }):
    
    with Cluster("Data Sources"):
        with Cluster("Golf Clubs"):
            wise = Internet("WiseGolf")
            nex = Internet("NexGolf")
            tee = Internet("TeeTime")
        
        with Cluster("External Data"):
            weather = Internet("Weather API")
            events = Internet("External Events")
    
    with Cluster("Processing Pipeline"):
        fetch = Python("Data Fetcher")
        normalize = Python("Normalizer")
        dedupe = Python("Deduplicator")
        enrich = Python("Data Enricher")
        calendar = Python("Calendar Generator")
    
    with Cluster("Output"):
        ics = Storage("ICS Files")
        cache = Storage("Cache")
    
    # Flow
    wise >> fetch
    nex >> fetch
    tee >> fetch
    
    fetch >> normalize
    normalize >> dedupe
    dedupe >> enrich
    
    weather >> enrich
    events >> enrich
    
    enrich >> calendar
    calendar >> ics
    calendar >> cache

pdf.add_image('docs/diagrams/reservation_flow.png')

# Reservation Processing Details
pdf.add_page()
pdf.sub_title('Reservation Processing Implementation')
pdf.chapter_body('''
1. Reservation Service:
   ```python
   class ReservationService:
       def process_user(self, user_name: str, user_config: Dict[str, Any],
                       past_days: int = 7) -> Tuple[Calendar, List[Reservation]]:
           """Process reservations for user."""
           cal = Calendar()
           all_reservations = []
           
           for membership in user_config.memberships:
               club = GolfClubFactory.create_club(club_details, membership)
               raw_reservations = club.fetch_reservations(membership)
               
               for raw_reservation in raw_reservations:
                   reservation = self._create_reservation(raw_reservation, club)
                   if self._should_include_reservation(reservation):
                       all_reservations.append(reservation)
                       self._add_to_calendar(reservation, cal)
           
           return cal, all_reservations
   ```

2. Reservation Processing:
   - Time Window Handling:
     • Skip past dates beyond window
     • Process future bookings
     • Handle recurring events
   
   - Deduplication:
     • Track seen UIDs
     • Compare key fields
     • Handle modifications
   
   - Data Enrichment:
     • Add weather forecasts
     • Include club details
     • Set location info

3. Calendar Integration:
   - Event Creation:
     • Set start/end times
     • Add location details
     • Include weather data
   
   - File Management:
     • Create ICS files
     • Handle file paths
     • Manage backups

4. Error Recovery:
   - Partial Processing:
     • Continue on club errors
     • Skip invalid entries
     • Log issues
   
   - Data Validation:
     • Check required fields
     • Validate formats
     • Handle missing data''')

# Add Reservation Attributes
pdf.sub_title('Reservation Attributes')
reservation_attrs = [
    {
        'name': 'start_time',
        'type': 'datetime',
        'description': 'Reservation start time in local timezone. Required. Must be valid datetime.'
    },
    {
        'name': 'end_time',
        'type': 'datetime',
        'description': 'Reservation end time in local timezone. Required. Must be after start_time.'
    },
    {
        'name': 'club',
        'type': 'GolfClub',
        'description': 'Reference to golf club. Required. Must be valid club instance.'
    },
    {
        'name': 'user',
        'type': 'User',
        'description': 'Reference to booking user. Required. Must be valid user instance.'
    },
    {
        'name': 'membership',
        'type': 'Membership',
        'description': 'User\'s club membership details. Required for member validation.'
    },
    {
        'name': 'players',
        'type': 'List[Player]',
        'description': 'List of players in booking. Optional. Includes guests and members.'
    },
    {
        'name': 'weather',
        'type': 'Dict[str, Any]',
        'description': 'Weather forecast data. Optional. Added during processing.'
    },
    {
        'name': 'external_id',
        'type': 'string',
        'description': 'CRM system booking ID. Required. Used for deduplication.'
    }
]
pdf.add_attribute_table(reservation_attrs)

# Add Calendar Integration Details
pdf.add_page()
pdf.sub_title('Calendar Integration')
pdf.chapter_body('''
1. Calendar Entry Creation:
   - Event Properties:
     • Summary: Club and time
     • Description: Players and weather
     • Location: Club address
     • Duration: Based on holes
   
   - Special Handling:
     • Timezone conversion
     • All-day events
     • Recurring bookings
     • Competition events

2. File Management:
   - ICS File Handling:
     • Create per user
     • Append new events
     • Remove old events
     • Handle conflicts
   
   - Path Resolution:
     • Support absolute paths
     • Handle relative paths
     • Create directories
     • Manage permissions

3. Calendar Features:
   - Event Details:
     • Rich descriptions
     • Location mapping
     • Weather forecasts
     • Player information
   
   - Integration:
     • iCal format
     • Google Calendar
     • Outlook support
     • Mobile sync

4. Update Management:
   - Change Detection:
     • Track modifications
     • Handle cancellations
     • Process updates
     • Maintain history
   
   - Sync Strategy:
     • Incremental updates
     • Full refresh option
     • Error recovery
     • Version control''')

# Add Calendar Configuration
pdf.sub_title('Calendar Configuration')
calendar_config = [
    {
        'name': 'ics_dir',
        'type': 'string',
        'description': 'Directory for ICS files. Required. Can be absolute or relative path.'
    },
    {
        'name': 'ics_files',
        'type': 'Dict[str, str]',
        'description': 'Custom file paths per user. Optional. Overrides default naming.'
    },
    {
        'name': 'past_days',
        'type': 'integer',
        'description': 'Days of past reservations to include. Optional. Default: 7.'
    },
    {
        'name': 'future_days',
        'type': 'integer',
        'description': 'Days of future reservations to include. Optional. Default: 90.'
    },
    {
        'name': 'timezone',
        'type': 'string',
        'description': 'Default timezone for calendar. Required. IANA timezone format.'
    },
    {
        'name': 'refresh_interval',
        'type': 'integer',
        'description': 'Minutes between calendar updates. Optional. Default: 60.'
    },
    {
        'name': 'backup_count',
        'type': 'integer',
        'description': 'Number of backup files to keep. Optional. Default: 3.'
    },
    {
        'name': 'file_permissions',
        'type': 'string',
        'description': 'Unix-style permissions for files. Optional. Default: 0o644.'
    }
]
pdf.add_attribute_table(calendar_config)

# Save the PDF
pdf.output('docs/GolfCalendar_Documentation.pdf') 