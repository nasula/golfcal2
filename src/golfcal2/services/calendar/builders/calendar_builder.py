"""
Calendar builder for golf calendar application.
"""

from pathlib import Path
from zoneinfo import ZoneInfo

from icalendar import Calendar
from icalendar import vText

from golfcal2.models.user import User
from golfcal2.utils.logging_utils import LoggerMixin


class CalendarBuilder(LoggerMixin):
    """Builder for calendar objects."""
    
    def __init__(self, local_tz: ZoneInfo):
        """Initialize calendar builder."""
        super().__init__()
        self.local_tz = local_tz
    
    def build_base_calendar(self, user: User) -> Calendar:
        """Create base calendar with metadata."""
        calendar = Calendar()
        calendar.add('prodid', vText('-//Golf Calendar//EN'))
        calendar.add('version', vText('2.0'))
        calendar.add('calscale', vText('GREGORIAN'))
        calendar.add('method', vText('PUBLISH'))
        calendar.add('x-wr-calname', vText(f'Golf Reservations - {user.name}'))
        calendar.add('x-wr-timezone', vText(str(self.local_tz)))
        return calendar
    
    def write_calendar(self, calendar: Calendar, file_path: Path, dev_mode: bool = False) -> None:
        """Write calendar to file."""
        try:
            # Modify path for dev mode if needed
            if dev_mode:
                stem = file_path.stem
                file_path = file_path.with_name(f"{stem}-dev{file_path.suffix}")
            
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write calendar to file
            event_count = len(calendar.walk('vevent'))
            self.logger.debug(f"Writing calendar with {event_count} events to {file_path}")
            
            with open(file_path, 'wb') as f:
                calendar_data = calendar.to_ical()
                f.write(calendar_data)
                self.logger.debug(f"Wrote {len(calendar_data)} bytes to calendar file")
            
            self.logger.info(f"Created calendar file: {file_path}")
            
        except OSError as e:
            self.logger.error(f"Failed to write calendar file: {e}")
            raise 