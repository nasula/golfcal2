    def _add_weather_to_event(self, event: Event, club: str, start_time: datetime, weather_service: WeatherManager) -> None:
        """Add weather information to event description."""
        try:
            # Get club coordinates from config
            club_config = self.config.clubs.get(club)
            if not club_config or 'coordinates' not in club_config:
                self.logger.warning(f"No coordinates found for club {club}")
                return
            
            # Get event duration and calculate end time
            duration = event.get('duration')
            if not duration:
                self.logger.warning(f"No duration found for event {event.get('uid')}")
                return
            
            # Convert vCalendar duration to timedelta if needed
            if not isinstance(duration, timedelta):
                # Get the end time directly from the event instead
                end_time = event.get('dtend').dt
                if not end_time:
                    self.logger.warning(f"No end time found for event {event.get('uid')}")
                    return
            else:
                end_time = start_time + duration
            
            # Get weather data
            weather_data = weather_service.get_weather(
                lat=club_config['coordinates']['lat'],
                lon=club_config['coordinates']['lon'],
                start_time=start_time,
                end_time=end_time,
                club=club
            )
            
            if not weather_data:
                self.logger.warning(f"No weather data found for club {club}")
                return
            
            # Update event description with weather data
            description = event.get('description', '')
            if description:
                description = description + "\n\nWeather:\n"
            else:
                description = "Weather:\n"
            
            # Format weather data
            for forecast in weather_data:
                description += (
                    f"{forecast.time.strftime('%H:%M')} - "
                    f"{forecast.temperature}°C, "
                    f"{forecast.wind_speed}m/s"
                )
                if forecast.precipitation_probability is not None:
                    description += f", {forecast.precipitation_probability}% rain"
                description += "\n"
            
            event['description'] = description
            
        except Exception as e:
            self.logger.error(f"Failed to add weather to event: {e}")
            return 