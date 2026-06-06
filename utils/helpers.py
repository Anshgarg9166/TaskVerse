# ─────────────────────────────────────────────
#  Taskverse – Generic Helper Utilities
# ─────────────────────────────────────────────
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

import pytz
from dateutil import parser as dateutil_parser

from backend.config import get_settings

settings = get_settings()
TZ = pytz.timezone(settings.timezone)

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2,
    "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
}


def now_local() -> datetime:
    """Return current datetime in the configured timezone (aware)."""
    return datetime.now(TZ)


def _next_weekday(weekday_index: int) -> datetime:
    """Return the next occurrence of a weekday (always in the future)."""
    now = now_local()
    days_ahead = weekday_index - now.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return now + timedelta(days=days_ahead)


def parse_natural_date(text: str) -> Optional[datetime]:
    """
    Parse a natural-language date string.
    Always returns a timezone-aware datetime.
    """
    text_lower = text.lower().strip()
    now = now_local()

    # ── Relative time: "in 2 minutes", "in 1 hour", "in 3 hours" ─────────────
    relative_match = re.search(
        r'(?:in|after)\s+(\d+)\s+(minute|minutes|min|mins|hour|hours|hr|hrs|day|days)',
        text_lower
    )
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)
        if unit in ("minute", "minutes", "min", "mins"):
            return now + timedelta(minutes=amount)
        elif unit in ("hour", "hours", "hr", "hrs"):
            return now + timedelta(hours=amount)
        elif unit in ("day", "days"):
            return now + timedelta(days=amount)

    # ── Relative day keywords ─────────────────────────────────────────────────
    if "today" in text_lower:
        base = now
    elif "tomorrow" in text_lower:
        base = now + timedelta(days=1)
    else:
        # ── Weekday names ──────────────────────────────────────────────────────
        matched_weekday = None
        for name, idx in WEEKDAYS.items():
            if name in text_lower:
                matched_weekday = idx
                break

        if matched_weekday is not None:
            base = _next_weekday(matched_weekday)
        else:
            # ── Fallback: dateutil parser ──────────────────────────────────────
            try:
                parsed = dateutil_parser.parse(
                    text, default=now.replace(tzinfo=None)
                )
                if parsed.tzinfo is None:
                    base = TZ.localize(parsed)
                else:
                    base = parsed.astimezone(TZ)
            except (ValueError, OverflowError):
                return None

    # ── Time-of-day hints ─────────────────────────────────────────────────────
    if "morning" in text_lower:
        base = base.replace(hour=8, minute=0, second=0, microsecond=0)
    elif "afternoon" in text_lower:
        base = base.replace(hour=14, minute=0, second=0, microsecond=0)
    elif "evening" in text_lower:
        base = base.replace(hour=18, minute=0, second=0, microsecond=0)
    elif "night" in text_lower:
        base = base.replace(hour=21, minute=0, second=0, microsecond=0)
    else:
        # Parse explicit times like "9pm", "5:30pm", "17:00"
        time_match = re.search(
            r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text_lower
        )
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            meridiem = time_match.group(3)
            if meridiem == "pm" and hour != 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0
            if 0 <= hour <= 23:
                base = base.replace(hour=hour, minute=minute,
                                    second=0, microsecond=0)
        else:
            if base.hour == 0 and base.minute == 0:
                base = base.replace(hour=9, minute=0, second=0, microsecond=0)

    return base


def humanise_delta(dt: datetime) -> str:
    """Return a human-friendly relative time string."""
    now = now_local()
    if dt.tzinfo is None:
        dt = TZ.localize(dt)
    delta = dt - now
    seconds = int(delta.total_seconds())

    if seconds < 0:
        return "overdue"
    if seconds < 60:
        return "in less than a minute"
    if seconds < 3600:
        return f"in {seconds // 60} minutes"
    if seconds < 86400:
        return f"in {seconds // 3600} hours"
    return f"in {delta.days} days"


def sanitise_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate(text: str, max_len: int = 200) -> str:
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


def extract_telegram_user_id(update_dict: dict) -> Optional[int]:
    try:
        return update_dict["message"]["from"]["id"]
    except (KeyError, TypeError):
        return None