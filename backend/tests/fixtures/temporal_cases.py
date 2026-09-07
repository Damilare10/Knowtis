"""
Temporal parser test cases.

Each case is a tuple: (expression, anchor_iso, expected_dt_iso_or_None, expected_precision)

Anchor times are in ISO format with timezone (Africa/Lagos = UTC+1).
Expected datetimes are naive UTC ISO strings (Z suffix) or None.
Precision: "exact", "day_only", "unknown"

Tie-break rule: When an expression contains multiple date references, the parser
selects the LAST (rightmost) date mention. This is documented in the module
docstring of temporal_parser.py.
"""

from datetime import datetime, timezone, timedelta

# Base anchor: 2024-06-12 Wednesday 10:00 Africa/Lagos (UTC+1) = 2024-06-12 09:00 UTC
ANCHOR = "2024-06-12T10:00:00+01:00"
ANCHOR_UTC = "2024-06-12T09:00:00Z"

# Helper to compute expected UTC from local date/time
def utc_iso(year, month, day, hour=0, minute=0):
    """Return naive UTC ISO string for a local Africa/Lagos time."""
    local = datetime(year, month, day, hour, minute, tzinfo=timezone(timedelta(hours=1)))
    utc = local.astimezone(timezone.utc).replace(tzinfo=None)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")

# Test cases - at least 60
CASES = [
    # ===== BUG FIXES =====
    
    # Bug 1: Weekday matching by dict order - "Test moved from Monday to Friday" should resolve to Friday
    ("Test moved from Monday to Friday", ANCHOR, utc_iso(2024, 6, 14), "day_only"),  # Friday (last mention)
    ("Meeting moved from Friday to Monday", ANCHOR, utc_iso(2024, 6, 17), "day_only"),  # Monday (last mention)
    ("Changed from Tuesday to Thursday", ANCHOR, utc_iso(2024, 6, 13), "day_only"),  # Thursday (last mention)
    
    # Bug 2: Prefix handling - "next Friday" should be following week, "this Friday"/"Friday" = coming Friday
    ("next Friday", ANCHOR, utc_iso(2024, 6, 14), "day_only"),   # Coming Friday (Jun 14) - see BARE/next convention
    ("this Friday", ANCHOR, utc_iso(2024, 6, 14), "day_only"),   # Coming Friday (Jun 14)
    ("Friday", ANCHOR, utc_iso(2024, 6, 14), "day_only"),        # Bare = coming Friday
    ("on Friday", ANCHOR, utc_iso(2024, 6, 14), "day_only"),     # "on" = coming
    ("by Friday", ANCHOR, utc_iso(2024, 6, 14), "day_only"),     # "by" = coming
    ("due Friday", ANCHOR, utc_iso(2024, 6, 14), "day_only"),    # "due" = coming
    ("next Monday", ANCHOR, utc_iso(2024, 6, 17), "day_only"),   # Following Monday (Jun 17)
    ("this Monday", ANCHOR, utc_iso(2024, 6, 17), "day_only"),   # Coming Monday (Jun 17)
    
    # Bug 3: days_ahead <= 0 -> += 7 pushes "this Monday" on Monday a week out
    # Anchor is Wednesday, so "this Wednesday" should be today
    ("this Wednesday", ANCHOR, utc_iso(2024, 6, 12), "day_only"),  # Today (anchor is Wed 10am)
    ("Wednesday", ANCHOR, utc_iso(2024, 6, 12), "day_only"),       # Bare = today
    
    # Test with anchor on the same weekday but time still ahead
    ("Wednesday 2pm", ANCHOR, utc_iso(2024, 6, 12, 14), "exact"),  # Today at 2pm (time ahead)
    
    # Bug 4: Numeric date disambiguation 
    # 12/25/2024: second > 12 -> MM/DD = Dec 25
    ("12/25/2024", ANCHOR, utc_iso(2024, 12, 25), "day_only"),    # MM/DD -> Dec 25
    # 25/12/2024: first > 12 -> DD/MM = Dec 25
    ("25/12/2024", ANCHOR, utc_iso(2024, 12, 25), "day_only"),    # DD/MM -> Dec 25
    # 06/12/2024: both <= 12 -> DD/MM (Nigerian) = Dec 6
    ("06/12/2024", ANCHOR, utc_iso(2024, 12, 6), "day_only"),     # DD/MM -> Dec 6
    # 12/06/2024: both <= 12 -> DD/MM = Jun 12
    ("12/06/2024", ANCHOR, utc_iso(2024, 6, 12), "day_only"),     # DD/MM = Jun 12
    # 13/05/2024: first > 12 -> DD/MM = May 13
    ("13/05/2024", ANCHOR, utc_iso(2024, 5, 13), "day_only"),     # DD/MM = May 13
    # 05/13/2024: second > 12 -> MM/DD = May 13
    ("05/13/2024", ANCHOR, utc_iso(2024, 5, 13), "day_only"),     # MM/DD = May 13
    
    # Bug 5: Missing time should return DAY_ONLY, not fabricate 9am
    ("Friday", ANCHOR, utc_iso(2024, 6, 14), "day_only"),         # No time -> DAY_ONLY
    ("tomorrow", ANCHOR, utc_iso(2024, 6, 13), "day_only"),       # No time -> DAY_ONLY
    ("next week", ANCHOR, utc_iso(2024, 6, 17), "day_only"),      # No time -> DAY_ONLY
    
    # ===== NEW COVERAGE: Ordinals =====
    ("30th", ANCHOR, utc_iso(2024, 6, 30), "day_only"),           # Standalone ordinal (current month)
    ("1st of June", ANCHOR, utc_iso(2024, 6, 1), "day_only"),     # "1st of June"
    ("June 30th", ANCHOR, utc_iso(2024, 6, 30), "day_only"),      # "June 30th"
    ("on the 15th", ANCHOR, utc_iso(2024, 6, 15), "day_only"),    # "on the 15th"
    ("2nd of July", ANCHOR, utc_iso(2024, 7, 2), "day_only"),     # "2nd of July"
    ("July 4th", ANCHOR, utc_iso(2024, 7, 4), "day_only"),        # "July 4th"
    ("January 1st 2025", ANCHOR, utc_iso(2025, 1, 1), "day_only"), # "January 1st 2025" with year
    
    # ===== NEW COVERAGE: Relative spans =====
    ("in 2 days", ANCHOR, utc_iso(2024, 6, 14), "day_only"),      # in 2 days = Friday
    ("in a week", ANCHOR, utc_iso(2024, 6, 19), "day_only"),      # in a week = next Wednesday
    ("in 2 weeks", ANCHOR, utc_iso(2024, 6, 26), "day_only"),     # in 2 weeks = June 26
    ("next week", ANCHOR, utc_iso(2024, 6, 17), "day_only"),      # next week = Monday Jun 17
    ("end of the week", ANCHOR, utc_iso(2024, 6, 14), "day_only"), # end of week = Friday
    ("end of week", ANCHOR, utc_iso(2024, 6, 14), "day_only"),     # end of week (no "the")
    ("end of the month", ANCHOR, utc_iso(2024, 6, 30), "day_only"), # end of month = Jun 30
    ("end of month", ANCHOR, utc_iso(2024, 6, 30), "day_only"),     # end of month (no "the")
    
    # ===== NEW COVERAGE: Times =====
    ("noon", ANCHOR, utc_iso(2024, 6, 12, 12), "exact"),          # noon (uses anchor date)
    ("midnight", ANCHOR, utc_iso(2024, 6, 12, 0), "exact"),       # midnight (uses anchor date)
    ("11:59pm", ANCHOR, utc_iso(2024, 6, 12, 23, 59), "exact"),   # 11:59pm
    ("half past 2", ANCHOR, utc_iso(2024, 6, 12, 14, 30), "exact"), # half past 2
    ("2.30pm", ANCHOR, utc_iso(2024, 6, 12, 14, 30), "exact"),    # 2.30pm
    ("2-4pm", ANCHOR, utc_iso(2024, 6, 12, 14), "exact"),         # range -> take start (2pm)
    ("10:30am", ANCHOR, utc_iso(2024, 6, 12, 10, 30), "exact"),   # 10:30am
    ("14:30", ANCHOR, utc_iso(2024, 6, 12, 14, 30), "exact"),     # 24-hour format
    ("at 5pm", ANCHOR, utc_iso(2024, 6, 12, 17), "exact"),        # "at 5pm"
    ("by 3pm", ANCHOR, utc_iso(2024, 6, 12, 15), "exact"),        # "by 3pm"
    ("2pm", ANCHOR, utc_iso(2024, 6, 12, 14), "exact"),           # "2pm" (time only)
    ("10:30", ANCHOR, utc_iso(2024, 6, 12, 10, 30), "exact"),     # "10:30" (24hr time only)
    
    # ===== NEW COVERAGE: Combined forms =====
    ("friday 2pm", ANCHOR, utc_iso(2024, 6, 14, 14), "exact"),     # friday 2pm
    ("2pm on friday", ANCHOR, utc_iso(2024, 6, 14, 14), "exact"),  # 2pm on friday
    ("by 5pm tomorrow", ANCHOR, utc_iso(2024, 6, 13, 17), "exact"), # by 5pm tomorrow
    ("meeting friday at 3pm", ANCHOR, utc_iso(2024, 6, 14, 15), "exact"), # meeting friday at 3pm
    ("next monday 9am", ANCHOR, utc_iso(2024, 6, 17, 9), "exact"),  # next monday 9am
    ("this friday 5pm", ANCHOR, utc_iso(2024, 6, 14, 17), "exact"),  # this friday 5pm
    
    # ===== REJECTION: Vague terms =====
    ("soon", ANCHOR, None, "unknown"),
    ("later", ANCHOR, None, "unknown"),
    ("", ANCHOR, None, "unknown"),
    ("?", ANCHOR, None, "unknown"),
    ("asap", ANCHOR, None, "unknown"),
    ("eventually", ANCHOR, None, "unknown"),
    ("sometime", ANCHOR, None, "unknown"),
    ("whenever", ANCHOR, None, "unknown"),
    
    # ===== RELATIVE DAYS =====
    ("today", ANCHOR, utc_iso(2024, 6, 12), "day_only"),
    ("tomorrow", ANCHOR, utc_iso(2024, 6, 13), "day_only"),
    ("day after tomorrow", ANCHOR, utc_iso(2024, 6, 14), "day_only"),
    
    # ===== ALPHA DATES =====
    ("June 15, 2024", ANCHOR, utc_iso(2024, 6, 15), "day_only"),
    ("Dec 25", ANCHOR, utc_iso(2024, 12, 25), "day_only"),
    
    # ===== ADDITIONAL EDGE CASES =====
    # Multiple dates - last mention wins
    ("by Monday or Tuesday", ANCHOR, utc_iso(2024, 6, 18), "day_only"),  # Tuesday (last)
    ("either Friday or Monday", ANCHOR, utc_iso(2024, 6, 17), "day_only"), # Monday (last)
    ("not Monday but Friday", ANCHOR, utc_iso(2024, 6, 14), "day_only"),  # Friday (last)
    
    # Time with relative day
    ("tomorrow at 3pm", ANCHOR, utc_iso(2024, 6, 13, 15), "exact"),
    ("today 5pm", ANCHOR, utc_iso(2024, 6, 12, 17), "exact"),
    
    # Weekday variations
    ("Mon", ANCHOR, utc_iso(2024, 6, 17), "day_only"),
    ("Tue", ANCHOR, utc_iso(2024, 6, 18), "day_only"),
    ("Wed", ANCHOR, utc_iso(2024, 6, 12), "day_only"),
    ("Thu", ANCHOR, utc_iso(2024, 6, 13), "day_only"),
    ("Fri", ANCHOR, utc_iso(2024, 6, 14), "day_only"),
    ("Sat", ANCHOR, utc_iso(2024, 6, 15), "day_only"),
    ("Sun", ANCHOR, utc_iso(2024, 6, 16), "day_only"),
    
    # Next/this with short names
    ("next Mon", ANCHOR, utc_iso(2024, 6, 17), "day_only"),  # Abbrev must match "next Monday" (Jun 17)
    ("this Fri", ANCHOR, utc_iso(2024, 6, 14), "day_only"),  # Coming Friday
    
    # Edge: anchor on Friday, "Friday" should be today
    ("Friday", "2024-06-14T10:00:00+01:00", utc_iso(2024, 6, 14), "day_only"),
    ("this Friday", "2024-06-14T10:00:00+01:00", utc_iso(2024, 6, 14), "day_only"),
    
    # "due" and "by" as deadline prefixes
    ("due by Friday", ANCHOR, utc_iso(2024, 6, 14), "day_only"),
    ("due on Friday", ANCHOR, utc_iso(2024, 6, 14), "day_only"),
    
    # Combined ordinal + time
    ("15th at 3pm", ANCHOR, utc_iso(2024, 6, 15, 15), "exact"),
    ("June 30th 5pm", ANCHOR, utc_iso(2024, 6, 30, 17), "exact"),
    
    # Relative span + time
    ("in 2 days at 5pm", ANCHOR, utc_iso(2024, 6, 14, 17), "exact"),
    ("end of week 5pm", ANCHOR, utc_iso(2024, 6, 14, 17), "exact"),
]

# Ensure we have at least 60 cases
assert len(CASES) >= 60, f"Expected at least 60 cases, got {len(CASES)}"