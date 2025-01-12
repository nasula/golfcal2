from typing import List, Optional
from datetime import datetime

class WeatherManager:
    def get_weather(
        self,
        lat: float,
        lon: float,
        start_time: datetime,
        end_time: datetime,
        club: Optional[str] = None
    ) -> Optional[WeatherResponse]:
        """Get weather data for a location."""
        try:
            # Validate input
            if not (-90 <= lat <= 90):
                raise ValueError(f"Invalid latitude: {lat}")
            if not (-180 <= lon <= 180):
                raise ValueError(f"Invalid longitude: {lon}")
            
            # Convert times to UTC
            start_time = start_time.astimezone(self.utc_tz)
            end_time = end_time.astimezone(self.utc_tz)
            
            # Validate time range
            if start_time > end_time:
                raise ValueError("Start time must be before end time")
            
            # Get services that cover this location
            services = self._get_services_for_location(lat, lon)
            if not services:
                self.warning(
                    "No weather services available for location",
                    latitude=lat,
                    longitude=lon
                )
                return None
            
            # Try each service in order
            for service in services:
                try:
                    self.debug(
                        "Trying weather service",
                        service=service.__class__.__name__,
                        coords=(lat, lon),
                        time_range=f"{start_time.isoformat()} to {end_time.isoformat()}"
                    )
                    
                    response = service.get_weather(lat, lon, start_time, end_time, club)
                    if response and response.data:
                        self.info(
                            "Got weather data",
                            service=service.__class__.__name__,
                            coords=(lat, lon),
                            time_range=f"{start_time.isoformat()} to {end_time.isoformat()}",
                            forecast_count=len(response.data)
                        )
                        return response
                    
                    self.debug(
                        "Service returned no data",
                        service=service.__class__.__name__
                    )
                    
                except Exception as e:
                    self.warning(
                        "Weather service failed",
                        exc_info=e,
                        service=service.__class__.__name__
                    )
                    continue
            
            self.warning(
                "All weather services failed",
                coords=(lat, lon),
                time_range=f"{start_time.isoformat()} to {end_time.isoformat()}"
            )
            return None
            
        except Exception as e:
            self.error("Failed to get weather data", exc_info=e)
            return None

    def _get_services_for_location(
        self,
        lat: float,
        lon: float
    ) -> List[WeatherService]:
        """Get list of weather services that cover a location."""
        try:
            services = []
            for service in self.services:
                try:
                    if service.covers_location(lat, lon):
                        services.append(service)
                except Exception as e:
                    self.warning(
                        "Failed to check service coverage",
                        exc_info=e,
                        service=service.__class__.__name__
                    )
                    continue
            
            if services:
                self.debug(
                    "Found weather services for location",
                    latitude=lat,
                    longitude=lon,
                    services=[s.__class__.__name__ for s in services]
                )
            else:
                self.warning(
                    "No weather services found for location",
                    latitude=lat,
                    longitude=lon
                )
                
            return services
            
        except Exception as e:
            self.error("Failed to get services for location", exc_info=e)
            return [] 