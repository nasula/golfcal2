"""
Event model for calendar events.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from icalendar import Event as ICalEvent

@dataclass
class Event:
    """Calendar event."""
    summary: str
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    description: Optional[str] = None
    uid: Optional[str] = None
    
    def to_ical(self) -> ICalEvent:
        """Convert to iCalendar event."""
        event = ICalEvent()
        
        # Required fields
        event.add('summary', self.summary)
        event.add('dtstart', self.start_time)
        event.add('dtend', self.end_time)
        event.add('dtstamp', datetime.now(ZoneInfo('UTC')))
        
        # Optional fields
        if self.location:
            event.add('location', self.location)
        if self.description:
            event.add('description', self.description)
        if self.uid:
            event.add('uid', self.uid)
        else:
            # Generate unique ID if not provided
            unique_id = f"{self.summary}_{self.start_time.strftime('%Y%m%d%H%M')}"
            event.add('uid', unique_id)
        
        return event 