"""
Schedule parser for natural language time expressions.
Supports Hebrew and English input.
"""

import re
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ParsedSchedule:
    """Represents a parsed schedule."""
    times: List[datetime]  # List of scheduled times
    recurrence: Optional[str]  # 'daily', 'weekly', or None
    recurrence_day: Optional[int]  # 0=Monday, 6=Sunday


# Day name mappings (Hebrew and English)
DAY_NAMES = {
    # Hebrew
    'ראשון': 6, 'א': 6,  # Sunday
    'שני': 0, 'ב': 0,     # Monday
    'שלישי': 1, 'ג': 1,   # Tuesday
    'רביעי': 2, 'ד': 2,   # Wednesday
    'חמישי': 3, 'ה': 3,   # Thursday
    'שישי': 4, 'ו': 4,    # Friday
    'שבת': 5,             # Saturday
    # English
    'sunday': 6, 'sun': 6,
    'monday': 0, 'mon': 0,
    'tuesday': 1, 'tue': 1,
    'wednesday': 2, 'wed': 2,
    'thursday': 3, 'thu': 3,
    'friday': 4, 'fri': 4,
    'saturday': 5, 'sat': 5,
}

# Relative day mappings
RELATIVE_DAYS = {
    'today': 0, 'היום': 0,
    'tomorrow': 1, 'מחר': 1,
}


def parse_time(time_str: str) -> Tuple[int, int]:
    """Parse a time string like '18:00' or '6pm' into (hour, minute)."""
    time_str = time_str.strip().lower()
    
    # Handle 24-hour format (18:00)
    match = re.match(r'^(\d{1,2}):(\d{2})$', time_str)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # Handle 12-hour format (6pm, 6:30pm)
    match = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$', time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        if match.group(3) == 'pm' and hour != 12:
            hour += 12
        elif match.group(3) == 'am' and hour == 12:
            hour = 0
        return hour, minute
    
    # Handle just hour (18, 6)
    match = re.match(r'^(\d{1,2})$', time_str)
    if match:
        return int(match.group(1)), 0
    
    raise ValueError(f"Could not parse time: {time_str}")


def parse_date(date_str: str) -> datetime:
    """Parse a date string like '15/02' or '15/02/2025'."""
    date_str = date_str.strip()
    now = datetime.now()
    
    # DD/MM format
    match = re.match(r'^(\d{1,2})[/\-.](\d{1,2})$', date_str)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        result = now.replace(day=day, month=month, hour=0, minute=0, second=0, microsecond=0)
        # If the date is in the past, assume next year
        if result < now:
            result = result.replace(year=result.year + 1)
        return result
    
    # DD/MM/YYYY format
    match = re.match(r'^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$', date_str)
    if match:
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if year < 100:
            year += 2000
        return datetime(year, month, day)
    
    raise ValueError(f"Could not parse date: {date_str}")


def get_next_weekday(target_day: int, time_hour: int, time_minute: int) -> datetime:
    """Get the next occurrence of a specific weekday."""
    now = datetime.now()
    current_day = now.weekday()
    days_ahead = target_day - current_day
    
    if days_ahead < 0:  # Target day already passed this week
        days_ahead += 7
    elif days_ahead == 0:  # Same day - check if time passed
        target_time = now.replace(hour=time_hour, minute=time_minute, second=0, microsecond=0)
        if now >= target_time:
            days_ahead = 7
    
    next_date = now + timedelta(days=days_ahead)
    return next_date.replace(hour=time_hour, minute=time_minute, second=0, microsecond=0)


def distribute_times_this_week(count: int, prefer_evening: bool = True) -> List[datetime]:
    """Distribute N uploads evenly across the remaining week."""
    now = datetime.now()
    end_of_week = now + timedelta(days=(6 - now.weekday()))  # Until Sunday
    
    # Calculate available days
    remaining_days = (end_of_week - now).days + 1
    
    if count > remaining_days:
        # More uploads than days - some days get multiple
        times_per_day = count // remaining_days
        extra = count % remaining_days
    else:
        times_per_day = 1
        extra = 0
    
    result = []
    base_hour = 18 if prefer_evening else 12  # Default to 18:00 or 12:00
    current_date = now
    
    for i in range(min(count, remaining_days)):
        upload_time = current_date.replace(
            hour=base_hour + (i % 4),  # Vary the hour slightly
            minute=0,
            second=0,
            microsecond=0
        )
        if upload_time <= now:
            upload_time += timedelta(days=1)
        result.append(upload_time)
        current_date += timedelta(days=max(1, remaining_days // count))
    
    return result[:count]


def parse_schedule(text: str) -> ParsedSchedule:
    """
    Parse a natural language schedule expression.
    
    Supported formats:
    - "today 18:00" / "היום 18:00"
    - "tomorrow 10:00" / "מחר 10:00"
    - "sunday 18:00" / "ראשון 18:00"
    - "every sunday 18:00" / "כל ראשון 18:00"
    - "every day 09:00" / "כל יום 09:00"
    - "3 times this week" / "3 פעמים השבוע"
    - "15/02 20:00" (specific date)
    """
    text = text.strip().lower()
    now = datetime.now()
    
    # Pattern: "X times this week"
    match = re.search(r'(\d+)\s*(?:times?|פעמים?)\s*(?:this\s*week|השבוע)', text)
    if match:
        count = int(match.group(1))
        times = distribute_times_this_week(count)
        return ParsedSchedule(times=times, recurrence=None, recurrence_day=None)
    
    # Pattern: "every day HH:MM"
    match = re.search(r'(?:every\s*day|כל\s*יום)\s+(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?)', text)
    if match:
        hour, minute = parse_time(match.group(1))
        next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_time <= now:
            next_time += timedelta(days=1)
        return ParsedSchedule(times=[next_time], recurrence='daily', recurrence_day=None)
    
    # Pattern: "every [day_name] HH:MM"
    for day_name, day_num in DAY_NAMES.items():
        pattern = rf'(?:every|כל)\s*{re.escape(day_name)}\s+(\d{{1,2}}(?::\d{{2}})?(?:\s*(?:am|pm))?)'
        match = re.search(pattern, text)
        if match:
            hour, minute = parse_time(match.group(1))
            next_time = get_next_weekday(day_num, hour, minute)
            return ParsedSchedule(times=[next_time], recurrence='weekly', recurrence_day=day_num)
    
    # Pattern: "today/tomorrow HH:MM"
    for rel_name, days_ahead in RELATIVE_DAYS.items():
        pattern = rf'{re.escape(rel_name)}\s+(\d{{1,2}}(?::\d{{2}})?(?:\s*(?:am|pm))?)'
        match = re.search(pattern, text)
        if match:
            hour, minute = parse_time(match.group(1))
            target_date = now + timedelta(days=days_ahead)
            target_time = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target_time <= now:
                target_time += timedelta(days=1)
            return ParsedSchedule(times=[target_time], recurrence=None, recurrence_day=None)
    
    # Pattern: "[day_name] HH:MM" (specific day this/next week)
    for day_name, day_num in DAY_NAMES.items():
        pattern = rf'^{re.escape(day_name)}\s+(\d{{1,2}}(?::\d{{2}})?(?:\s*(?:am|pm))?)'
        match = re.search(pattern, text)
        if match:
            hour, minute = parse_time(match.group(1))
            next_time = get_next_weekday(day_num, hour, minute)
            return ParsedSchedule(times=[next_time], recurrence=None, recurrence_day=None)
    
    # Pattern: "DD/MM HH:MM"
    match = re.search(r'(\d{1,2}[/\-\.]\d{1,2}(?:[/\-\.]\d{2,4})?)\s+(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?)', text)
    if match:
        target_date = parse_date(match.group(1))
        hour, minute = parse_time(match.group(2))
        target_time = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return ParsedSchedule(times=[target_time], recurrence=None, recurrence_day=None)
    
    # Pattern: Just time "HH:MM" - assume today or tomorrow
    match = re.search(r'^(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?)$', text)
    if match:
        hour, minute = parse_time(match.group(1))
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target_time <= now:
            target_time += timedelta(days=1)
        return ParsedSchedule(times=[target_time], recurrence=None, recurrence_day=None)
    
    raise ValueError(
        f"לא הצלחתי להבין את התזמון: '{text}'\n\n"
        "דוגמאות:\n"
        "• היום 18:00\n"
        "• מחר 10:00\n"
        "• ראשון 20:00\n"
        "• כל ראשון 18:00\n"
        "• כל יום 09:00\n"
        "• 3 פעמים השבוע\n"
        "• 15/02 20:00"
    )


def format_schedule_summary(schedule: ParsedSchedule) -> str:
    """Format a schedule for display to the user."""
    lines = []
    
    for time in schedule.times:
        day_names_he = ['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון']
        day_name = day_names_he[time.weekday()]
        lines.append(f"📅 יום {day_name} {time.strftime('%d/%m')} בשעה {time.strftime('%H:%M')}")
    
    if schedule.recurrence == 'daily':
        lines.append("\n🔄 חוזר: כל יום")
    elif schedule.recurrence == 'weekly':
        day_names_he = ['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון']
        lines.append(f"\n🔄 חוזר: כל יום {day_names_he[schedule.recurrence_day]}")
    
    return "\n".join(lines)
