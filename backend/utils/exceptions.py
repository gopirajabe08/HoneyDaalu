"""
Custom exception hierarchy for LuckyNavi.

Provides specific exception types so callers can handle different
failure modes (auth, orders, scanning) without catching bare Exception.
"""


class TradingError(Exception):
    """Base exception for all trading-related errors."""
    pass


class AuthenticationError(TradingError):
    """Fyers authentication or token errors."""
    pass


class OrderError(TradingError):
    """Order placement, modification, or cancellation failures."""

    def __init__(self, message: str, order_id: str = "", symbol: str = ""):
        super().__init__(message)
        self.order_id = order_id
        self.symbol = symbol


class ScannerError(TradingError):
    """Market data fetch or strategy scan failures."""
    pass


class StateError(TradingError):
    """State persistence (save/load) failures."""
    pass


class MarketDataError(TradingError):
    """Market data retrieval failures (yfinance, Fyers quotes)."""
    pass
