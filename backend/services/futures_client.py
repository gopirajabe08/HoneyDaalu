"""
Futures Client — broker API wrapper for futures-specific operations.

Handles:
  - Futures symbol formatting (NSE:SYMBOL26MARFUT)
  - Expiry date calculation (last Thursday of month)
  - Futures order placement (market, limit, SL-M)
  - LTP fetching for futures contracts
"""

import logging
from datetime import datetime, timezone, timedelta, date
from calendar import monthrange

from services.broker_client import (
    place_order as _broker_place_order,
    get_quotes as _broker_get_quotes,
    is_authenticated,
)
from fno_stocks import get_lot_size
from config import NSE_HOLIDAYS

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


def get_current_expiry() -> date:
    """
    Get the current month's futures expiry date (last Thursday, adjusted for holidays).
    If past this month's expiry, returns next month's expiry.
    """
    today = datetime.now(IST).date()
    expiry = _last_trading_thursday(today.year, today.month)

    # If past this month's expiry, use next month
    if today > expiry:
        if today.month == 12:
            expiry = _last_trading_thursday(today.year + 1, 1)
        else:
            expiry = _last_trading_thursday(today.year, today.month + 1)

    return expiry


def get_next_expiry() -> date:
    """Get the next month's futures expiry (for rollover)."""
    current = get_current_expiry()
    if current.month == 12:
        return _last_trading_thursday(current.year + 1, 1)
    return _last_trading_thursday(current.year, current.month + 1)


def _last_thursday(year: int, month: int) -> date:
    """Find the last Thursday of a given month."""
    _, last_day = monthrange(year, month)
    d = date(year, month, last_day)
    while d.weekday() != 3:  # Thursday = 3
        d -= timedelta(days=1)
    return d


def _last_trading_thursday(year: int, month: int) -> date:
    """
    Find the last Thursday of a month, adjusted for NSE holidays.
    If the last Thursday is a holiday, expiry moves to Wednesday before it.
    """
    d = _last_thursday(year, month)
    # If last Thursday is a holiday, move to previous trading day
    while d.strftime("%Y-%m-%d") in NSE_HOLIDAYS:
        d -= timedelta(days=1)
        # Skip weekends
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d


def days_to_expiry() -> int:
    """Days remaining to current expiry."""
    today = datetime.now(IST).date()
    return (get_current_expiry() - today).days


def build_futures_symbol(symbol: str, expiry: date | None = None) -> str:
    """
    Build broker futures symbol.
    Format: NSE:SYMBOL26MARFUT
    """
    if expiry is None:
        expiry = get_current_expiry()
    year_short = expiry.strftime("%y")
    month_abbr = expiry.strftime("%b").upper()
    return f"NSE:{symbol}{year_short}{month_abbr}FUT"


def get_futures_ltp(symbol: str) -> float:
    """Get last traded price for a futures contract."""
    if not is_authenticated():
        return 0
    try:
        broker_sym = build_futures_symbol(symbol)
        res = _broker_get_quotes([broker_sym])
        quotes = res.get("d", [])
        if not quotes:
            data = res.get("data", {})
            if isinstance(data, dict):
                quotes = data.get("d", [])
        for q in quotes:
            if q.get("n", "") == broker_sym:
                return q.get("v", {}).get("lp", 0)
        return 0
    except Exception:
        return 0


def get_futures_ltp_batch(symbols: list[str]) -> dict[str, float]:
    """Get LTP for multiple futures contracts. Returns {symbol: ltp}."""
    if not symbols or not is_authenticated():
        return {}

    broker_symbols = [build_futures_symbol(s) for s in symbols]
    ltp_map = {}
    try:
        res = _broker_get_quotes(broker_symbols)
        quotes = res.get("d", [])
        if not quotes:
            data = res.get("data", {})
            if isinstance(data, dict):
                quotes = data.get("d", [])

        for q in quotes:
            broker_sym = q.get("n", "")
            ltp = q.get("v", {}).get("lp", 0)
            if broker_sym and ltp:
                # Map back to base symbol
                for sym in symbols:
                    expected = build_futures_symbol(sym)
                    if broker_sym == expected:
                        ltp_map[sym] = ltp
                        break
    except Exception as e:
        logger.warning(f"[FuturesClient] Batch LTP fetch failed: {e}")

    return ltp_map


def place_futures_order(symbol: str, qty: int, side: int,
                        order_type: int = 2, product_type: str = "INTRADAY",
                        limit_price: float = 0, stop_price: float = 0) -> dict:
    """
    Place a futures order via broker.

    Args:
        symbol: Base symbol (e.g. "RELIANCE")
        qty: Number of shares (must be multiple of lot size)
        side: 1=Buy, -1=Sell
        order_type: 1=Limit, 2=Market, 3=SL, 4=SL-M
        product_type: "INTRADAY" or "MARGIN"
        limit_price: For limit orders
        stop_price: For SL/SL-M orders
    """
    broker_symbol = build_futures_symbol(symbol)

    return _broker_place_order(
        symbol=broker_symbol,
        qty=qty,
        side=side,
        order_type=order_type,
        product_type=product_type,
        limit_price=limit_price,
        stop_price=stop_price,
    )


def calculate_margin_per_lot(price: float, lot_size: int, margin_pct: float = 0.10) -> float:
    """
    Estimate margin required per lot.
    Intraday: ~10% (brokers offer reduced margin for MIS/INTRADAY)
    Overnight: ~20% (SPAN + exposure for MARGIN product)
    """
    return price * lot_size * margin_pct


def calculate_position_size(symbol: str, entry_price: float, stop_loss: float,
                            capital: float, risk_pct: float = None,
                            margin_pct: float = 0.10) -> dict:
    """
    Calculate futures position size using margin-based lot sizing with 2% risk cap.

    Returns:
        dict with num_lots, total_qty, margin_required, risk_amount
    """
    from config import FUTURES_RISK_PER_TRADE_PCT
    if risk_pct is None:
        risk_pct = FUTURES_RISK_PER_TRADE_PCT

    lot_size = get_lot_size(symbol)
    if lot_size == 0:
        return {"num_lots": 0, "total_qty": 0, "margin_required": 0, "risk_amount": 0}

    sl_distance = abs(entry_price - stop_loss)
    if sl_distance == 0:
        return {"num_lots": 0, "total_qty": 0, "margin_required": 0, "risk_amount": 0}

    # Margin-based constraint
    margin_per_lot = calculate_margin_per_lot(entry_price, lot_size, margin_pct)
    max_lots_by_margin = int(capital / margin_per_lot) if margin_per_lot > 0 else 0

    # Risk-based constraint (2% of capital)
    max_risk = capital * risk_pct
    risk_per_lot = sl_distance * lot_size
    max_lots_by_risk = int(max_risk / risk_per_lot) if risk_per_lot > 0 else 0

    # Most conservative wins — never exceed 2% risk cap
    num_lots = max(min(max_lots_by_margin, max_lots_by_risk), 0)

    # If risk cap says 0 lots, do NOT override — capital insufficient for this stock
    # This enforces the 2% risk limit strictly

    total_qty = num_lots * lot_size
    margin_required = num_lots * margin_per_lot
    risk_amount = num_lots * risk_per_lot

    return {
        "num_lots": num_lots,
        "lot_size": lot_size,
        "total_qty": total_qty,
        "margin_required": round(margin_required, 2),
        "risk_amount": round(risk_amount, 2),
        "risk_pct_actual": round((risk_amount / capital) * 100, 2) if capital > 0 else 0,
    }
