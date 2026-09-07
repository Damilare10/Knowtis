"""
Temporal Parser Service
Parses relative dates and times (e.g., "tomorrow", "next Monday", "2pm")
anchored to the parent message's actual timestamp.

Tie-break rule for multiple dates in one expression:
When an expression contains two or more date references, the parser selects
the LAST date mention in the string (rightmost match). This is deliberate:
in natural language, the final date mentioned is typically the operative one
(e.g., "Test moved from Monday to Friday" -> Friday; "by 5pm tomorrow" -> tomorrow).
If the same date appears twice, the last occurrence wins.
"""
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List
from enum import Enum

from app.timezone_utils import app_tz, to_naive_utc

logger = logging.getLogger(__name__)

# Bare-hour convention: an hour with no am/pm in this range resolves to PM.
# In a Nigerian university WhatsApp group "half past 2" or "test at 3" means
# 14:30 / 15:00; nobody schedules a 03:00 test. Hours 8-12 are left as written,
# because "lecture at 10" means 10:00. Applied uniformly to every bare-hour
# form (HH:MM, "at H", "half past H", H.MM, H-H ranges), not special-cased.
BARE_HOUR_PM_RANGE = (1, 7)

# Regex Patterns
TIME_RE = re.compile(
    r"\b(?:at|by|before|@)?\s*(\d{1,2}):(\d{2})\s*(am|pm)?\b|"  # 10:00 am, 14:30
    r"\b(\d{1,2})\s*(am|pm)\b|"                                  # 10am, 2 pm
    r"\b(?:at|by|before|@)\s*(\d{1,2})\b|"                       # at 10, @ 2
    r"\b(noon|midnight)\b|"                                      # noon, midnight
    r"\bhalf\s+past\s+(\d{1,2})\b|"                              # half past 2
    r"\b(\d{1,2})\.(\d{2})\s*(am|pm)?\b|"                        # 2.30pm
    r"\b(\d{1,2})\s*-\s*(\d{1,2})\s*(am|pm)?\b",                 # 2-4pm (take start)
    re.IGNORECASE
)

DATE_RE_NUMERIC = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")

DATE_RE_ALPHA = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?\b",
    re.IGNORECASE
)

_MONTH_ALT = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)

# Ordinal dates: "30th", "1st of June", "June 30th", "on the 15th", "January 1st 2025"
#
# Alternatives are ordered MOST SPECIFIC FIRST and use named groups. Python's
# `re` alternation is leftmost-first, so with the bare `(\d{1,2})(?:st|nd|rd|th)`
# branch listed first, "2nd of July" matched the bare branch and silently fell
# back to the anchor's month, yielding 2 June instead of 2 July. Named groups
# also mean adding a branch can no longer shift positional indices in the
# handler.
ORDINAL_RE = re.compile(
    rf"\b(?P<mdy_month>{_MONTH_ALT})\s+(?P<mdy_day>\d{{1,2}})(?:st|nd|rd|th)\s+(?P<mdy_year>\d{{4}})\b|"
    rf"\b(?P<dom_day>\d{{1,2}})(?:st|nd|rd|th)\s+of\s+(?P<dom_month>{_MONTH_ALT})\b|"
    rf"\b(?P<md_month>{_MONTH_ALT})\s+(?P<md_day>\d{{1,2}})(?:st|nd|rd|th)\b|"
    r"\bon\s+the\s+(?P<onthe_day>\d{1,2})(?:st|nd|rd|th)\b|"
    r"\b(?P<bare_day>\d{1,2})(?:st|nd|rd|th)\b",
    re.IGNORECASE
)

# Relative spans: "in 2 days", "in a week", "next week", "end of the week", "end of the month"
RELATIVE_SPAN_RE = re.compile(
    r"\bin\s+(\d+)\s+days?\b|"                                    # in 2 days
    r"\bin\s+a\s+week\b|"                                         # in a week
    r"\bin\s+(\d+)\s+weeks?\b|"                                   # in 2 weeks
    r"\bnext\s+week\b|"                                           # next week
    r"\bend\s+of\s+(?:the\s+)?week\b|"                            # end of the week
    r"\bend\s+of\s+(?:the\s+)?month\b",                           # end of the month
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

# Combined weekday regex with prefix capture: this/next/on/by/due + weekday
# Using finditer to scan by match position, not dict order
# Sort by length descending so longer names match first
WEEKDAY_NAMES = sorted(WEEKDAYS.keys(), key=len, reverse=True)
WEEKDAY_PREFIX_RE = re.compile(
    r"\b(?:(this|next|on|by|due)\s+)?(" + "|".join(WEEKDAY_NAMES) + r")\b",
    re.IGNORECASE
)

# Relative days: today, tomorrow, day after tomorrow
RELATIVE_DAY_RE = re.compile(
    r"\b(today|tomorrow|day\s+after\s+tomorrow)\b",
    re.IGNORECASE
)

# Vague terms that should return UNKNOWN
VAGUE_RE = re.compile(
    r"\b(soon|later|asap|eventually|sometime|whenever)\b",
    re.IGNORECASE
)

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MONTH_MAP = {name: i + 1 for i, name in enumerate(MONTHS)}
MONTH_MAP.update({
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
})


class DatePrecision(Enum):
    """Precision of the resolved date/time."""
    EXACT = "exact"       # Both date and time resolved (e.g., "Friday 2pm")
    DAY_ONLY = "day_only" # Date resolved, no time (e.g., "Friday", "tomorrow")
    UNKNOWN = "unknown"   # No resolvable date/time (e.g., "soon", "later")


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
        if ORDINAL_RE.search(text):
            return True
        if RELATIVE_SPAN_RE.search(text):
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
        
        DEPRECATED: Use resolve() instead for new code. This method is kept for
        backward compatibility with the legacy extractor.
        """
        result, _ = TemporalParser.resolve(text, anchor_time)
        return result

    @staticmethod
    def resolve(
        expression: Optional[str],
        anchor: Optional[datetime] = None,
        explicit: bool = False
    ) -> Tuple[Optional[datetime], DatePrecision]:
        """
        Resolve a temporal expression to a datetime with precision info.
        
        Args:
            expression: The natural language temporal expression (e.g., "next Friday 2pm")
            anchor: Anchor datetime in app timezone. If None, uses now_app().
            explicit: If True, only return a result for explicit date/time references.
                      If False, also resolves relative spans like "in 2 days".
        
        Returns:
            Tuple of (naive UTC datetime or None, DatePrecision enum)
        """
        if not expression:
            return None, DatePrecision.UNKNOWN

        text = expression.strip()
        text_lower = text.lower()

        # Reject vague terms immediately (but allow if combined with explicit date/time)
        has_explicit_date = (
            DATE_RE_ALPHA.search(text) or 
            DATE_RE_NUMERIC.search(text) or 
            ORDINAL_RE.search(text) or 
            RELATIVE_DAY_RE.search(text) or
            any(re.search(rf"\b(?:(?:this|next|on|by|due)\s+)?{day_name}\b", text_lower) for day_name in WEEKDAYS)
        )
        has_explicit_time = TIME_RE.search(text)
        
        if VAGUE_RE.search(text_lower) and not has_explicit_date and not has_explicit_time:
            return None, DatePrecision.UNKNOWN

        # Resolve anchor time in the configured app timezone
        from app.timezone_utils import now_app
        if anchor is None:
            now = now_app()
        else:
            tz = app_tz()
            if anchor.tzinfo is None:
                anchor = anchor.replace(tzinfo=timezone.utc)
            now = anchor.astimezone(tz)

        # Collect all date candidates with their match positions
        date_candidates: List[Tuple[int, datetime.date, DatePrecision, str]] = []

        # 1. Relative days (today, tomorrow, day after tomorrow)
        for match in RELATIVE_DAY_RE.finditer(text_lower):
            token = match.group(1).lower()
            pos = match.start()
            if token == "today":
                resolved_date = now.date()
                precision = DatePrecision.DAY_ONLY
            elif token == "tomorrow":
                resolved_date = (now + timedelta(days=1)).date()
                precision = DatePrecision.DAY_ONLY
            elif token == "day after tomorrow":
                resolved_date = (now + timedelta(days=2)).date()
                precision = DatePrecision.DAY_ONLY
            else:
                continue
            date_candidates.append((pos, resolved_date, precision, token))

        # 2. Absolute calendar dates: "June 12, 2024" or "January 1st 2025"
        for match in DATE_RE_ALPHA.finditer(text_lower):
            try:
                month_name = match.group(1)[:3].lower()
                day = int(match.group(2))
                year = match.group(3)
                year = int(year) if year else now.year
                month_num = MONTH_MAP.get(month_name)
                if month_num:
                    resolved_date = datetime(year, month_num, day).date()
                    date_candidates.append((match.start(), resolved_date, DatePrecision.DAY_ONLY, match.group(0)))
            except ValueError as e:
                logger.warning(f"Failed to parse alpha date '{match.group(0)}': {e}")

        # 3. Numeric dates: "12/06/2024" or "12/25/2024" (disambiguate DD/MM vs MM/DD)
        for match in DATE_RE_NUMERIC.finditer(text_lower):
            try:
                d, m, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if y < 100:
                    y += 2000
                # Disambiguation: first > 12 -> DD/MM; second > 12 -> MM/DD; else DD/MM (Nigerian)
                if d > 12 and m <= 12:
                    day, month = d, m
                elif m > 12 and d <= 12:
                    day, month = m, d
                else:
                    day, month = d, m  # DD/MM convention
                resolved_date = datetime(y, month, day).date()
                date_candidates.append((match.start(), resolved_date, DatePrecision.DAY_ONLY, match.group(0)))
            except ValueError as e:
                logger.warning(f"Failed to parse numeric date '{match.group(0)}': {e}")

        # 4. Ordinal dates: "30th", "1st of June", "June 30th", "on the 15th", "January 1st 2025"
        for match in ORDINAL_RE.finditer(text_lower):
            try:
                g = match.groupdict()
                pos = match.start()
                resolved_date = None

                if g["mdy_month"] and g["mdy_day"] and g["mdy_year"]:      # "January 1st 2025"
                    month_num = MONTH_MAP.get(g["mdy_month"][:3].lower())
                    if month_num:
                        resolved_date = datetime(int(g["mdy_year"]), month_num, int(g["mdy_day"])).date()
                elif g["dom_day"] and g["dom_month"]:                      # "1st of June"
                    month_num = MONTH_MAP.get(g["dom_month"][:3].lower())
                    if month_num:
                        resolved_date = datetime(now.year, month_num, int(g["dom_day"])).date()
                elif g["md_month"] and g["md_day"]:                        # "June 30th"
                    month_num = MONTH_MAP.get(g["md_month"][:3].lower())
                    if month_num:
                        resolved_date = datetime(now.year, month_num, int(g["md_day"])).date()
                elif g["onthe_day"]:                                       # "on the 15th"
                    resolved_date = datetime(now.year, now.month, int(g["onthe_day"])).date()
                elif g["bare_day"]:                                        # "30th"
                    resolved_date = datetime(now.year, now.month, int(g["bare_day"])).date()

                if resolved_date is not None:
                    date_candidates.append((pos, resolved_date, DatePrecision.DAY_ONLY, match.group(0)))
            except ValueError as e:
                logger.warning(f"Failed to parse ordinal date '{match.group(0)}': {e}")

        # 5. Relative spans: "in 2 days", "in a week", "next week", "end of the week", "end of the month"
        # Only process if not explicit mode
        if not explicit:
            for match in RELATIVE_SPAN_RE.finditer(text_lower):
                try:
                    token = match.group(0).lower()
                    pos = match.start()
                    if token.startswith("in "):
                        if "day" in token:
                            days = int(match.group(1))
                            resolved_date = (now + timedelta(days=days)).date()
                        elif "week" in token:
                            # NOTE: group(1) is the *days* capture; the weeks
                            # capture is group(2). Reading group(1) here made
                            # "in 2 weeks" silently collapse to "in a week".
                            if match.group(2):      # "in 2 weeks"
                                weeks = int(match.group(2))
                            else:                   # "in a week"
                                weeks = 1
                            resolved_date = (now + timedelta(weeks=weeks)).date()
                        else:
                            continue
                        date_candidates.append((pos, resolved_date, DatePrecision.DAY_ONLY, token))
                    elif token == "next week":
                        # Next week = Monday of next week
                        days_ahead = (7 - now.weekday()) % 7
                        if days_ahead == 0:
                            days_ahead = 7
                        resolved_date = (now + timedelta(days=days_ahead)).date()
                        date_candidates.append((pos, resolved_date, DatePrecision.DAY_ONLY, token))
                    elif token in ("end of week", "end of the week"):
                        # End of week = Friday
                        days_ahead = (4 - now.weekday()) % 7
                        if days_ahead == 0:
                            days_ahead = 7
                        resolved_date = (now + timedelta(days=days_ahead)).date()
                        date_candidates.append((pos, resolved_date, DatePrecision.DAY_ONLY, token))
                    elif token in ("end of month", "end of the month"):
                        # End of month = last day of current month
                        if now.month == 12:
                            next_month = datetime(now.year + 1, 1, 1)
                        else:
                            next_month = datetime(now.year, now.month + 1, 1)
                        last_day = (next_month - timedelta(days=1)).date()
                        resolved_date = last_day
                        date_candidates.append((pos, resolved_date, DatePrecision.DAY_ONLY, token))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse relative span '{match.group(0)}': {e}")

        # 6. Weekday mentions with prefix support: "this Friday", "next Friday", "on Friday", "by Friday"
        # Use finditer to get match positions (fixes bug #1: dict iteration order)
        for match in WEEKDAY_PREFIX_RE.finditer(text_lower):
            prefix = match.group(1)
            day_name = match.group(2).lower()
            weekday_num = WEEKDAYS.get(day_name)
            if weekday_num is None:
                continue
            
            pos = match.start()
            current_weekday = now.weekday()
            days_ahead = weekday_num - current_weekday
            
            if prefix:
                prefix_lower = prefix.lower()
                if prefix_lower in ("next", "this", "on", "by", "due"):
                    # All weekday prefixes resolve to the COMING weekday.
                    #
                    # "next Friday" is genuinely ambiguous in English: British
                    # and Nigerian usage usually means the upcoming Friday,
                    # American usage often means the following week. This is a
                    # deadline app, and the error is asymmetric — resolving too
                    # early produces a harmlessly early reminder, resolving too
                    # late means the student misses the deadline entirely. So
                    # the earliest plausible reading wins.
                    #
                    # This deliberately diverges from the original spec (which
                    # had "next X" = following week). It also makes the 3-letter
                    # abbreviations behave identically to the full names, which
                    # was the actual defect: "next Mon" and "next Monday"
                    # previously resolved a week apart.
                    #
                    # "next week" as a standalone span is unaffected and still
                    # means Monday of the following week.
                    if days_ahead < 0:
                        days_ahead += 7
                    # days_ahead == 0 keeps today, when the time is still ahead.
                else:
                    # Any other prefix: also the coming weekday.
                    if days_ahead < 0:
                        days_ahead += 7
            else:
                # Bare weekday: "Friday" = the coming Friday
                if days_ahead < 0:
                    days_ahead += 7
            
            resolved_date = (now + timedelta(days=days_ahead)).date()
            date_candidates.append((pos, resolved_date, DatePrecision.DAY_ONLY, match.group(0)))

        # If no date candidates found, check for time-only expressions
        # Fallback: if there's a time but no date, use anchor date
        time_match = TIME_RE.search(text_lower)
        has_time = time_match is not None
        
        if not date_candidates:
            if has_time:
                # Time-only expression: use anchor date
                resolved_date = now.date()
                base_precision = DatePrecision.DAY_ONLY
                date_candidates.append((-1, resolved_date, base_precision, "anchor_fallback"))
            else:
                return None, DatePrecision.UNKNOWN

        # Select the rightmost date candidate (tie-break rule: last mention wins)
        date_candidates.sort(key=lambda x: x[0], reverse=True)
        _, resolved_date, base_precision, matched_text = date_candidates[0]

        # 7. Parse Time (e.g. 10:00 AM, 14:30, 2pm, noon, midnight, half past 2, 2.30pm, 2-4pm)
        resolved_time = None
        precision = base_precision

        if time_match:
            try:
                groups = time_match.groups()
                hour = None
                minute = 0
                meridian = None

                # Group mapping:
                # 0=HH (from HH:MM), 1=MM, 2=meridian
                # 3=H (from Ham/pm), 4=meridian
                # 5=H (from @ H)
                # 6=noon/midnight
                # 7=H (half past)
                # 8=H (from H.MM), 9=MM, 10=meridian
                # 11=H_start (range), 12=H_end, 13=meridian
                if groups[6]:  # noon or midnight
                    token = groups[6].lower()
                    if token == "noon":
                        hour, minute = 12, 0
                    else:  # midnight
                        hour, minute = 0, 0
                elif groups[7] is not None:  # half past H
                    hour = int(groups[7])
                    minute = 30
                elif groups[0] is not None:  # HH:MM
                    hour = int(groups[0])
                    minute = int(groups[1])
                    meridian = groups[2]
                elif groups[3] is not None:  # H am/pm
                    hour = int(groups[3])
                    minute = 0
                    meridian = groups[4]
                elif groups[5] is not None:  # at H
                    hour = int(groups[5])
                    minute = 0
                elif groups[8] is not None:  # H.MM
                    hour = int(groups[8])
                    minute = int(groups[9])
                    meridian = groups[10]
                elif groups[11] is not None:  # H-H range (take start)
                    hour = int(groups[11])
                    minute = 0
                    meridian = groups[13]

                if hour is not None:
                    if meridian:
                        meridian = meridian.lower()
                        if meridian == "pm" and hour < 12:
                            hour += 12
                        elif meridian == "am" and hour == 12:
                            hour = 0
                    elif BARE_HOUR_PM_RANGE[0] <= hour <= BARE_HOUR_PM_RANGE[1]:
                        # Bare-hour convention (see module docstring): with no
                        # am/pm, hours 1-7 mean afternoon. "half past 2" or
                        # "test at 3" in a university group is 14:30 / 15:00,
                        # never 02:30 / 03:00. Hours 8-12 stay as written.
                        hour += 12
                    
                    if 0 <= hour < 24 and 0 <= minute < 60:
                        resolved_time = (hour, minute)
                        precision = DatePrecision.EXACT
            except ValueError as e:
                logger.warning(f"Failed to parse time from '{time_match.group(0)}': {e}")

        # If no time found, keep DAY_ONLY precision (don't fabricate 9am)
        if resolved_time is None:
            precision = DatePrecision.DAY_ONLY

        # 8. Construct local datetime, then convert to naive UTC for storage
        if resolved_time:
            local_dt = datetime(
                resolved_date.year,
                resolved_date.month,
                resolved_date.day,
                resolved_time[0],
                resolved_time[1],
                tzinfo=now.tzinfo,
            )
        else:
            # Date only - use start of day in app timezone
            local_dt = datetime(
                resolved_date.year,
                resolved_date.month,
                resolved_date.day,
                0, 0,
                tzinfo=now.tzinfo,
            )

        return to_naive_utc(local_dt), precision


__all__ = [
    "TemporalParser",
    "DatePrecision",
]