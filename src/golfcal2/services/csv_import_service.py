"""
CSV import service for golf calendar application.
"""

import json
import re
from collections import defaultdict
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from golfcal2.models.golf_club import ExternalGolfClub
from golfcal2.models.reservation import Reservation
from golfcal2.models.user import Membership, User
from golfcal2.utils.logging_utils import get_logger
from golfcal2.utils.timezone_utils import TimezoneManager

logger = get_logger(__name__)

class CSVImportService:
    """Service for importing calendar events from CSV files."""

    def __init__(self, timezone: str = "Europe/Helsinki"):
        """Initialize service."""
        self.timezone = timezone
        self.tz_manager = TimezoneManager()

    def _parse_datetime(self, date_str: str, time_str: str, timezone: str | None = None) -> datetime:
        """
        Parse date and time strings into datetime object.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            time_str: Time string in HH:MM:SS format
            timezone: Optional timezone name (e.g. 'Europe/Helsinki')
            
        Returns:
            Timezone-aware datetime object
        """
        try:
            # Handle time format with or without seconds
            if len(time_str.split(':')) == 2:
                time_str = f"{time_str}:00"
                
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
            
            # Use provided timezone or default
            tz = ZoneInfo(timezone or self.timezone)
            return dt.replace(tzinfo=tz)
            
        except ValueError as e:
            logger.error(f"Error parsing datetime: {e}")
            raise

    def _create_recurrence_rule(self, start_date: datetime, end_date: datetime, description: str, location: str, start_time: time) -> dict[str, Any] | None:
        """Create a recurrence rule for weekly events if they match certain patterns."""
        # Extract course name and level from description
        course_match = re.search(r';\s*([^;]+);\s*([A-Z0-9]+)\s+([^;\n]+)', description)
        if not course_match:
            return None
        
        teacher, course_code, course_name = course_match.groups()
        
        # Check if this is a recurring course by looking at the course code and name
        is_recurring = bool(re.search(r'A\d{5}|IL\d{4}', course_code))  # Match course codes like A14903 or IL0002
        
        if not is_recurring:
            return None
        
        # Create weekly recurrence
        rrule = {
            'FREQ': 'WEEKLY',
            'UNTIL': end_date,
            'INTERVAL': 1,
            'BYDAY': [start_date.strftime('%A')[:2].upper()],  # Convert day name to 2-letter code (e.g., 'Monday' -> 'MO')
            'WKST': 'MO'  # Week starts on Monday
        }
        
        return rrule

    def _parse_csv_row(self, row: list[str]) -> dict[str, str]:
        """
        Parse a CSV row into a dictionary with proper column mapping.
        
        Args:
            row: List of values from CSV row
            
        Returns:
            Dictionary with mapped column values
        """
        # Expected columns in order
        columns = ['START DATE', 'START TIME', 'END DATE', 'END TIME', 'LOCATION', 'DESCRIPTION', 'SUBJECT']
        
        # Create a dictionary with known columns
        data = {}
        for i, col in enumerate(columns):
            if i < len(row):
                data[col] = row[i]
            else:
                data[col] = ''
                
        # Combine additional fields into description
        if len(row) > len(columns):
            extra_info = '; '.join(row[len(columns):])
            if data['DESCRIPTION']:
                data['DESCRIPTION'] = f"{data['DESCRIPTION']}; {extra_info}"
            else:
                data['DESCRIPTION'] = extra_info
                
        return data

    def _get_event_key(self, start_time: datetime, location: str, description: str) -> tuple[int, str, str, str]:
        """
        Get a key for grouping recurring events.
        
        Args:
            start_time: Event start time
            location: Event location
            description: Event description
            
        Returns:
            Tuple of (weekday, time, location, course_code) for grouping
        """
        # Extract course code from description
        course_match = re.search(r';\s*[^;]+;\s*([A-Z0-9]+)', description)
        course_code = course_match.group(1) if course_match else ''
        
        return (
            start_time.weekday(),
            start_time.strftime('%H:%M'),
            location,
            course_code
        )

    def _get_event_summary(self, description: str) -> str:
        """
        Get a summary for the event based on the description.
        
        Args:
            description: Event description
            
        Returns:
            Event summary string
        """
        # Extract course name and details from description
        course_match = re.search(r'([^;]+);\s*([^;]+);\s*([A-Z0-9]+)\s+([^;\n]+)', description)
        if course_match:
            course_name, teacher, course_code, course_title = course_match.groups()
            if "Level" in course_title:
                # For language courses, include the level
                return f"{course_title}"
            else:
                # For other courses, use the course name
                return f"{course_name} - {course_title}"
        return description

    def import_from_csv(
        self,
        file_path: str,
        user: User,
        recurring_until: datetime | None = None,
        recurrence_end: datetime | None = None,
        timezone: str | None = None,
        delimiter: str = ";"
    ) -> list[Reservation]:
        """
        Import reservations from a CSV file.
        """
        logger.info(f"Importing reservations from {file_path}")
        reservations = []
        event_groups = defaultdict(list)  # For grouping potential recurring events

        # Use provided timezone or default
        event_timezone = timezone or self.timezone
        logger.info(f"Using timezone: {event_timezone}")

        try:
            with open(file_path, encoding='utf-8') as f:
                # Skip header line
                next(f)
                
                # First pass: Read all events and group them
                for line in f:
                    try:
                        # Split line and clean values
                        row = [val.strip() for val in line.split(delimiter)]
                        if not row or not row[0]:  # Skip empty lines
                            continue
                            
                        # Parse row into proper column mapping
                        data = self._parse_csv_row(row)
                        
                        # Parse start and end times with specified timezone
                        start_time = self._parse_datetime(
                            data['START DATE'], 
                            data['START TIME'],
                            event_timezone
                        )
                        end_time = self._parse_datetime(
                            data['END DATE'], 
                            data['END TIME'],
                            event_timezone
                        )

                        # Extract course code from description
                        course_match = re.search(r';\s*[^;]+;\s*([A-Z0-9]+)', data['DESCRIPTION'])
                        if course_match:
                            course_code = course_match.group(1)
                            # Create a pattern key for recurring events
                            pattern_key = (
                                data['LOCATION'],
                                start_time.time(),
                                start_time.weekday(),
                                course_code
                            )
                            
                            # Group events by weekday, time, location, and course code
                            event_groups[pattern_key].append((data, start_time, end_time))
                        else:
                            # Handle non-course events individually
                            club = ExternalGolfClub(
                                name=data['LOCATION'],
                                url="",
                                coordinates=None,
                                timezone=event_timezone,
                                address=data['LOCATION']
                            )

                            membership = Membership(
                                club=club.name,
                                club_abbreviation="EXT",  # External event marker
                                duration={"hours": 0, "minutes": 0},  # Duration will be calculated from event times
                                auth_details={}  # External events don't need auth details
                            )

                            raw_data = {
                                'description': data['DESCRIPTION'],
                                'subject': data['SUBJECT'],
                                'location': data['LOCATION'],
                                'summary': self._get_event_summary(data['DESCRIPTION'])
                            }

                            reservation = Reservation(
                                club=club,
                                user=user,
                                membership=membership,
                                start_time=start_time,
                                end_time=end_time,
                                players=[],
                                raw_data=raw_data
                            )
                            reservations.append(reservation)
                    except (KeyError, ValueError) as e:
                        logger.error(f"Error processing row: {e}")
                        continue

                # Second pass: Create recurring events
                for _pattern_key, events in event_groups.items():
                    try:
                        # Sort events by date
                        events.sort(key=lambda x: x[1])
                        
                        # Get the first event as the base
                        data, start_time, end_time = events[0]
                        
                        # Create external golf club for the event
                        club = ExternalGolfClub(
                            name=data['LOCATION'],
                            url="",
                            coordinates=None,
                            timezone=event_timezone,
                            address=data['LOCATION']
                        )

                        # Create a pseudo-membership for the external event
                        membership = Membership(
                            club=club.name,
                            club_abbreviation="EXT",  # External event marker
                            duration={"hours": 0, "minutes": 0},  # Duration will be calculated from event times
                            auth_details={}  # External events don't need auth details
                        )

                        # Calculate recurrence end date
                        series_end = events[-1][1]  # Last event in the series
                        if recurring_until:
                            series_end = min(series_end, recurring_until)
                        if recurrence_end:
                            series_end = min(series_end, recurrence_end)

                        # Create RRULE for weekly recurrence
                        rrule = {
                            'FREQ': 'WEEKLY',
                            'UNTIL': series_end,
                            'INTERVAL': 1,
                            'BYDAY': [start_time.strftime('%A')[:2].upper()],  # Convert day name to 2-letter code
                            'WKST': 'MO'  # Week starts on Monday
                        }

                        # Create the base reservation with recurrence rule
                        raw_data = {
                            'description': data['DESCRIPTION'],
                            'subject': data['SUBJECT'],
                            'location': data['LOCATION'],
                            'rrule': json.dumps(rrule),
                            'summary': self._get_event_summary(data['DESCRIPTION'])
                        }

                        reservation = Reservation(
                            club=club,
                            user=user,
                            membership=membership,
                            start_time=start_time,
                            end_time=end_time,
                            players=[],
                            raw_data=raw_data
                        )
                        reservations.append(reservation)
                    except Exception as e:
                        logger.error(f"Error creating recurring event: {e}")
                        continue

                logger.info(f"Imported {len(reservations)} reservations")
                return reservations

        except Exception as e:
            logger.error(f"Error importing from CSV: {e}")
            raise 