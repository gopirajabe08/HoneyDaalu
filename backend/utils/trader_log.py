"""
Structured logging for trader engines.

Provides a TraderLogger class that maintains an in-memory log buffer
(for UI display) while also writing to Python's logging system.
Replaces the identical _log() method duplicated across all 8 traders.
"""

import logging
from utils.time_utils import timestamp_ist

# Standard log levels used across all traders
TRADE_LOG_LEVELS = {
    "START", "STOP", "SCAN", "ORDER", "SQUAREOFF",
    "ALERT", "ERROR", "WARN", "SKIP", "INFO", "RESTORE",
    "REGIME", "EXPIRY",
}

# Map trade log levels to Python logging levels
_PYTHON_LOG_MAP = {
    "ERROR": logging.ERROR,
    "ALERT": logging.WARNING,
    "WARN": logging.WARNING,
    "START": logging.INFO,
    "STOP": logging.INFO,
    "ORDER": logging.INFO,
    "SQUAREOFF": logging.INFO,
    "SCAN": logging.DEBUG,
    "SKIP": logging.DEBUG,
    "INFO": logging.DEBUG,
    "RESTORE": logging.INFO,
    "REGIME": logging.INFO,
    "EXPIRY": logging.INFO,
}


class TraderLogger:
    """Structured logger for a trader engine.

    Maintains an in-memory buffer of log entries (for the frontend live log panel)
    while also writing to Python's standard logging system.

    Args:
        name: Trader identifier shown in log prefixes (e.g. 'AutoTrader', 'OptionsPaper').
        max_entries: Maximum log entries kept in memory (oldest are pruned).
    """

    def __init__(self, name: str, max_entries: int = 500):
        self.name = name
        self.max_entries = max_entries
        self._entries: list[dict] = []
        self._logger = logging.getLogger(f"trader.{name}")

    def log(self, level: str, message: str):
        """Add a structured log entry.

        Args:
            level: One of TRADE_LOG_LEVELS (START, STOP, SCAN, ORDER, etc.)
            message: Human-readable log message.
        """
        entry = {
            "timestamp": timestamp_ist(),
            "level": level,
            "message": message,
        }
        self._entries.append(entry)

        # Prune oldest entries if over limit
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]

        # Also write to Python logging
        py_level = _PYTHON_LOG_MAP.get(level, logging.INFO)
        self._logger.log(py_level, f"[{self.name}] [{level}] {message}")

    @property
    def entries(self) -> list[dict]:
        """Get all log entries (for status API response)."""
        return self._entries

    @entries.setter
    def entries(self, value: list[dict]):
        """Set log entries (for state restoration)."""
        self._entries = value

    def clear(self):
        """Clear all log entries."""
        self._entries.clear()

    def recent(self, n: int = 200) -> list[dict]:
        """Get the N most recent entries."""
        return self._entries[-n:]
