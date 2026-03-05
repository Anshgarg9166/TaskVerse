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


# ── Date/Time Helpers ─────────────────────────────────────────────────────────

def now_local() -> datetime:
    """Return current datetime in the configured timezone (aware)."""
    return datetime.now(TZ)


def parse_natural_date(text: str) -> Optional[datetime]:
    """
    Attempt to parse a natural-language date string.
    Always returns a timezone-aware datetime.
    """
    text = text.lower().strip()
    now = now_local()

    # Simple heuristics first
    if "today" in text:
        base = now
    elif "tomorrow" in text:
        base = now + timedelta(days=1)
    else:
        try:
            parsed = dateutil_parser.parse(text, default=now.replace(tzinfo=None))
            # Make it timezone-aware
            if parsed.tzinfo is None:
                base = TZ.localize(parsed)
            else:
                base = parsed.astimezone(TZ)
        except (ValueError, OverflowError):
            return None

    # Time-of-day hints
    if "morning" in text:
        base = base.replace(hour=8, minute=0, second=0, microsecond=0)
    elif "afternoon" in text:
        base = base.replace(hour=14, minute=0, second=0, microsecond=0)
    elif "evening" in text:
        base = base.replace(hour=18, minute=0, second=0, microsecond=0)
    elif "night" in text:
        base = base.replace(hour=21, minute=0, second=0, microsecond=0)
    else:
        # Check if a specific time was parsed (hour not midnight)
        if base.hour == 0 and base.minute == 0:
            base = base.replace(hour=9, minute=0, second=0, microsecond=0)

    return base


def humanise_delta(dt: datetime) -> str:
    """Return a human-friendly relative time string."""
    now = now_local()
    # Ensure dt is timezone-aware
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


# ── String Helpers ────────────────────────────────────────────────────────────

def sanitise_text(text: str) -> str:
    """Strip excessive whitespace and control characters."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate(text: str, max_len: int = 200) -> str:
    """Truncate text to max_len characters, appending '…' if cut."""
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


def extract_telegram_user_id(update_dict: dict) -> Optional[int]:
    """Safely extract Telegram user_id from an Update dict."""
    try:
        return update_dict["message"]["from"]["id"]
    except (KeyError, TypeError):
        return None