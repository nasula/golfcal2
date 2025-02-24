"""Pushover notification service for golf calendar application."""

import http.client
import urllib
from dataclasses import dataclass

from golfcal2.config.settings import AppConfig
from golfcal2.utils.logging_utils import LoggerMixin


@dataclass
class PushoverConfig:
    """Pushover configuration."""
    user_key: str
    app_token: str
    device: str | None = None
    priority: int = 0
    sound: str | None = None

class PushoverService(LoggerMixin):
    """Service for sending notifications via Pushover."""
    
    def __init__(self, config: AppConfig):
        """Initialize Pushover service."""
        super().__init__()
        self.config = config
        
        # Get Pushover configuration from global config
        pushover_config = config.global_config.get('global', {}).get('pushover', {})
        self.pushover_config = PushoverConfig(
            user_key=pushover_config.get('user_key', ''),
            app_token=pushover_config.get('app_token', ''),
            device=pushover_config.get('device'),
            priority=int(pushover_config.get('priority', 0)),
            sound=pushover_config.get('sound')
        )
        
        if not self.pushover_config.user_key or not self.pushover_config.app_token:
            self.logger.warning("Pushover not configured - notifications will be disabled")
    
    def is_enabled(self) -> bool:
        """Check if Pushover is properly configured."""
        return bool(self.pushover_config.user_key and self.pushover_config.app_token)
    
    def send_notification(
        self,
        title: str,
        message: str,
        priority: int | None = None,
        sound: str | None = None,
        url: str | None = None,
        url_title: str | None = None
    ) -> bool:
        """Send a notification via Pushover.
        
        Args:
            title: Notification title
            message: Notification message
            priority: Message priority (-2 to 2, default from config)
            sound: Notification sound (default from config)
            url: Optional URL to include
            url_title: Title for the URL
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self.is_enabled():
            self.logger.warning("Pushover not configured - notification not sent")
            return False
        
        try:
            # Prepare notification data
            data = {
                "token": self.pushover_config.app_token,
                "user": self.pushover_config.user_key,
                "title": title,
                "message": message,
                "priority": priority if priority is not None else self.pushover_config.priority,
                "sound": sound if sound is not None else self.pushover_config.sound
            }
            
            # Add optional parameters
            if self.pushover_config.device:
                data["device"] = self.pushover_config.device
            if url:
                data["url"] = url
            if url_title:
                data["url_title"] = url_title
            
            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}
            
            # Send notification
            conn = http.client.HTTPSConnection("api.pushover.net:443")
            conn.request(
                "POST",
                "/1/messages.json",
                urllib.parse.urlencode(data),
                {"Content-type": "application/x-www-form-urlencoded"}
            )
            
            # Check response
            response = conn.getresponse()
            if response.status == 200:
                self.logger.info("Pushover notification sent successfully")
                return True
            else:
                self.logger.error(f"Failed to send Pushover notification: {response.status} {response.reason}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending Pushover notification: {e}")
            return False 