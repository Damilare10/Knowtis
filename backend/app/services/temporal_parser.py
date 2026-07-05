"""
Temporal Parser Service
Parses relative dates and times (e.g., "tomorrow", "next Monday", "2pm")
anchored to the parent message's actual timestamp.
"""
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from app.timezone_utils import app_tz, to_naive_utc

logger = logging.getLogger(__name__)

# Regex Patterns
TIME_RE = re.compile(
    r"\b(?:at|by|before|@)?\s*(\d{1,2}):(\d{2})\s*(am|pm)?\b|"  # 10:00 am, 14:30
    r"\b(\d{1,2})\s*(am|pm)\b|"                                  # 10am, 2 pm
    r"\b(?:at|by|before|@)\s*(\d{1,2})\b",                       # at 10, @ 2
    re.IGNORECASE
)

DATE_RE_NUMERIC = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
DATE_RE_ALPHA = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})(?:,?\s*(\d{4}))?\b",
    re.IGNORECASE
)

WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6
}


class TemporalParser:
    """Helper to parse relative time mentions using a specific message anchor time."""

    @staticmethod
    def has_date_reference(text: str) -> bool:
        """Return True only when text contains an explicit date/day reference."""
        if not text:
            return False

        text_lower = text.lower()
        if any(token in text_lower for token in ["today", "tomorrow", "day after tomorrow"]):
            return True
        if DATE_RE_ALPHA.search(text) or DATE_RE_NUMERIC.search(text):
            return True
        return any(
            re.search(rf"\b(?:(?:this|next|on|by|due)\s+)?{day_name}\b", text_lower)
            for day_name in WEEKDAYS
        )

    @staticmethod
    def parse_date_time(text: str, anchor_time: Optional[datetime] = None) -> Optional[datetime]:
        """
        Parses text for date/time references relative to anchor_time (in app timezone).
        Returns a naive UTC datetime for database storage.
        """
        # 1. Resolve anchor time in the configured app timezone
        from app.timezone_utils import now_app
        if anchor_time is None:
            now = now_app()
        else:
            # If naive, assume UTC and localize to app_tz
            tz = app_tz()
            if anchor_time.tzinfo is None:
                anchor_time = anchor_time.replace(tzinfo=timezone.utc)
            now = anchor_time.astimezone(tz)

        resolved_date = None
        resolved_time = None
        text_lower = text.lower()

        # 2. Parse relative days (highest priority — explicit "today/tomorrow")
        if "today" in text_lower:
            resolved_date = now.date()
        elif "tomorrow" in text_lower:
            resolved_date = (now + timedelta(days=1)).date()
        elif "day after tomorrow" in text_lower:
            resolved_date = (now + timedelta(days=2)).date()

        # 3. Parse absolute calendar dates: June 12, 2024
        if not resolved_date:
            alpha_match = DATE_RE_ALPHA.search(text)
            if alpha_match:
                try:
                    month_name = alpha_match.group(1)[:3].lower()
                    day = int(alpha_match.group(2))
                    year = alpha_match.group(3)
                    year = int(year) if year else now.year

                    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
                    month_num = months.index(month_name) + 1
                    resolved_date = datetime(year, month_num, day).date()
                except ValueError:
                    pass

        # 4. Parse numeric dates: 12/06/2024
        if not resolved_date:
            num_match = DATE_RE_NUMERIC.search(text)
            if num_match:
                try:
                    d, m, y = int(num_match.group(1)), int(num_match.group(2)), int(num_match.group(3))
                    if y < 100:
                        y += 2000
                    resolved_date = datetime(y, m, d).date()
                except ValueError:
                    pass

        # 5. Fall back to weekday mentions (e.g. "on Friday", "by Friday")
        if not resolved_date:
            for day_name, weekday_num in WEEKDAYS.items():
                pattern = rf"\b(?:(?:this|next|on|by|due)\s+)?{day_name}\b"
                if re.search(pattern, text_lower):
                    days_ahead = weekday_num - now.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    resolved_date = (now + timedelta(days=days_ahead)).date()
                    break

        # Do not invent dates. Missing dates stay unscheduled so the review layer
        # can handle them without creating false reminders.
        if not resolved_date:
            return None

        # 6. Parse Time (e.g. 10:00 AM, 14:30, 2pm)
        time_match = TIME_RE.search(text)
        if time_match:
            try:
                groups = time_match.groups()
                hour = 9
                minute = 0
                meridian = None

                if groups[0] is not None:
                    hour = int(groups[0])
                    minute = int(groups[1])
                    meridian = groups[2]
                elif groups[3] is not None:
                    hour = int(groups[3])
                    minute = 0
                    meridian = groups[4]
                elif groups[5] is not None:
                    hour = int(groups[5])
                    minute = 0
                    meridian = None

                if meridian:
                    meridian = meridian.lower()
                    if meridian == "pm" and hour < 12:
                        hour += 12
                    elif meridian == "am" and hour == 12:
                        hour = 0
                
                if 0 <= hour < 24 and 0 <= minute < 60:
                    resolved_time = (hour, minute)
            except ValueError:
                pass

        if not resolved_time:
            # Default to 9:00 AM
            resolved_time = (9, 0)

        # 7. Construct local datetime, then convert to naive UTC for storage
        local_dt = datetime(
            resolved_date.year,
            resolved_date.month,
            resolved_date.day,
            resolved_time[0],
            resolved_time[1],
            tzinfo=now.tzinfo,
        )
        return to_naive_utc(local_dt)
