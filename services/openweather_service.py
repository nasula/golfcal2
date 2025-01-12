def get_weather(
    self,
    lat: float,
    lon: float,
    start_time: datetime,
    end_time: datetime,
    club: Optional[str] = None
) -> Optional[WeatherResponse]:
    """Get weather data from OpenWeather API."""
    try:
        # Calculate time range for fetching data
        now = datetime.now(self.utc_tz)
        hours_ahead = (end_time - now).total_seconds() / 3600
        interval = self.get_block_size(hours_ahead)
        
        # Align start and end times to block boundaries
        base_time = start_time.replace(minute=0, second=0, microsecond=0)
        fetch_end_time = end_time.replace(minute=0, second=0, microsecond=0)
        if end_time.minute > 0 or end_time.second > 0:
            fetch_end_time += timedelta(hours=1)
        
        self.debug(
            "Using forecast interval",
            hours_ahead=hours_ahead,
            interval=interval,
            aligned_start=base_time.isoformat(),
            aligned_end=fetch_end_time.isoformat()
        )
        
        # Check cache for response
        cached_response = self.cache.get_response(
            service_type='openweather',
            latitude=lat,
            longitude=lon,
            start_time=base_time,
            end_time=fetch_end_time
        )
        
        if cached_response:
            self.info(
                "Using cached response",
                location=cached_response['location'],
                time_range=f"{base_time.isoformat()} to {fetch_end_time.isoformat()}",
                interval=interval
            )
            return self._parse_response(cached_response['response'], base_time, fetch_end_time, interval)
        
        # If not in cache, fetch from API
        self.info(
            "Fetching new data from API",
            coords=(lat, lon),
            time_range=f"{base_time.isoformat()} to {fetch_end_time.isoformat()}",
            interval=interval
        )
        
        # Fetch data for the full forecast range
        response_data = self._fetch_forecasts(lat, lon, base_time, fetch_end_time)
        if not response_data:
            self.warning("No forecasts found for requested time range")
            return None
        
        # Store the full response in cache
        self.cache.store_response(
            service_type='openweather',
            latitude=lat,
            longitude=lon,
            response_data=response_data,
            forecast_start=base_time,
            forecast_end=fetch_end_time,
            expires=datetime.now(self.utc_tz) + timedelta(hours=1)
        )
        
        # Parse and return just the requested time range
        return self._parse_response(response_data, base_time, fetch_end_time, interval)
        
    except Exception as e:
        self.error("Failed to get weather data", exc_info=e)
        return None

def _fetch_forecasts(
    self,
    lat: float,
    lon: float,
    start_time: datetime,
    end_time: datetime
) -> Optional[Dict[str, Any]]:
    """Fetch forecast data from OpenWeather API."""
    try:
        # Get forecast data
        forecast_url = f"{self.BASE_URL}/data/2.5/forecast"
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric'
        }
        
        self.debug(
            "Getting forecast data",
            url=forecast_url,
            params=params
        )
        
        forecast_response = requests.get(
            forecast_url,
            params=params,
            timeout=10
        )
        
        self.debug(
            "Got forecast response",
            status=forecast_response.status_code,
            content_type=forecast_response.headers.get('content-type'),
            content_length=len(forecast_response.content)
        )
        
        if forecast_response.status_code != 200:
            error = APIResponseError(
                f"OpenWeather forecast request failed with status {forecast_response.status_code}",
                response=forecast_response
            )
            aggregate_error(str(error), "openweather", None)
            return None

        forecast_data = forecast_response.json()
        if not forecast_data or 'list' not in forecast_data:
            error = WeatherError(
                "Invalid forecast data format from OpenWeather API",
                ErrorCode.INVALID_RESPONSE,
                {"response": forecast_data}
            )
            aggregate_error(str(error), "openweather", None)
            return None

        self.debug(
            "Received forecast data",
            data=json.dumps(forecast_data, indent=2),
            data_type=type(forecast_data).__name__,
            has_data=bool(forecast_data.get('list')),
            data_length=len(forecast_data.get('list', [])),
            first_period=forecast_data.get('list', [{}])[0] if forecast_data.get('list') else None
        )

        return forecast_data

    except Exception as e:
        self.error("Error fetching forecasts", exc_info=e)
        return None

def _parse_response(
    self,
    response_data: Dict[str, Any],
    start_time: datetime,
    end_time: datetime,
    interval: int
) -> Optional[WeatherResponse]:
    """Parse raw API response into WeatherData objects."""
    try:
        forecasts = []
        for period in response_data.get('list', []):
            try:
                # Parse forecast time
                forecast_time = datetime.fromtimestamp(period['dt'], tz=self.utc_tz)
                
                # Skip forecasts outside requested range
                if forecast_time < start_time or forecast_time > end_time:
                    continue
                
                # Extract weather data
                main = period.get('main', {})
                weather = period.get('weather', [{}])[0]
                wind = period.get('wind', {})
                rain = period.get('rain', {})
                snow = period.get('snow', {})
                
                # Calculate precipitation (rain + snow)
                precip = rain.get('3h', 0) + snow.get('3h', 0)
                
                # Create WeatherData object
                forecast = WeatherData(
                    elaboration_time=forecast_time,
                    block_duration=timedelta(hours=interval),
                    temperature=float(main.get('temp', 0)),
                    temperature_min=float(main.get('temp_min', 0)),
                    temperature_max=float(main.get('temp_max', 0)),
                    precipitation=float(precip),
                    precipitation_probability=float(period.get('pop', 0)) * 100,
                    wind_speed=float(wind.get('speed', 0)),
                    wind_direction=float(wind.get('deg', 0)),
                    weather_code=str(weather.get('id', 0)),
                    weather_description=weather.get('description', ''),
                    thunder_probability=0,  # OpenWeather doesn't provide this
                    metadata={
                        'humidity': main.get('humidity'),
                        'pressure': main.get('pressure'),
                        'clouds': period.get('clouds', {}).get('all'),
                        'visibility': period.get('visibility'),
                        'wind_gust': wind.get('gust'),
                        'rain_3h': rain.get('3h'),
                        'snow_3h': snow.get('3h')
                    }
                )
                forecasts.append(forecast)
            except (KeyError, ValueError) as e:
                self.warning(
                    "Failed to parse forecast period",
                    exc_info=e,
                    period=period
                )
                continue
        
        if not forecasts:
            self.warning("No valid forecasts found in response")
            return None
        
        # Sort forecasts by time
        forecasts.sort(key=lambda x: x.elaboration_time)
        
        return WeatherResponse(
            data=forecasts,
            expires=datetime.now(self.utc_tz) + timedelta(hours=1)
        )
        
    except Exception as e:
        self.error("Failed to parse response", exc_info=e)
        return None 