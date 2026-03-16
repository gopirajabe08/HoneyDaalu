"""
IST timezone handling and market time window checks.

Used by all 8 trader engines to avoid duplicating timezone logic.
"""

from datetime import datetime, timezone, timedelta

# Indian Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Get current time in IST."""
    return datetime.now(IST)


def is_before_time(hour: int, minute: int = 0) -> bool:
    """True if current IST time is before the given hour:minute."""
    now = now_ist()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now < target


def is_past_time(hour: int, minute: int = 0) -> bool:
    """True if current IST time is at or past the given hour:minute."""
    now = now_ist()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now >= target


def today_ist_str() -> str:
    """Get today's date as YYYY-MM-DD string in IST."""
    return now_ist().strftime("%Y-%m-%d")


def timestamp_ist() -> str:
    """Get current IST time as HH:MM:SS string for log entries."""
    return now_ist().strftime("%H:%M:%S")
