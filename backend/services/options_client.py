"""
Options Client — wraps Fyers API for options-specific operations.
Handles option chain fetching, symbol building, Greeks/OI, and India VIX.
"""

import time
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional

import yfinance as yf

from services.fyers_client import get_fyers, get_quotes, is_authenticated
from config import (
    OPTIONS_LOT_SIZES, OPTIONS_SYMBOL_PREFIX, OPTIONS_INDEX_SYMBOLS,
    OPTIONS_STRIKE_INTERVAL, OPTIONS_UNDERLYINGS,
)

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# ── VIX Cache (refresh every 15 min) ──────────────────────────────────────

_vix_cache = {"value": None, "ts": 0}
VIX_CACHE_TTL = 900  # 15 minutes


def get_india_vix() -> float:
    """Fetch India VIX via yfinance, cached for 15 minutes."""
    now = time.time()
    if _vix_cache["value"] is not None and now - _vix_cache["ts"] < VIX_CACHE_TTL:
        return _vix_cache["value"]
    try:
        ticker = yf.Ticker("^INDIAVIX")
        hist = ticker.history(period="5d", interval="1d")
        if hist is not None and len(hist) > 0:
            vix = float(hist["Close"].iloc[-1])
            _vix_cache["value"] = vix
            _vix_cache["ts"] = now
            return vix
    except Exception as e:
        logger.warning(f"[OptionsClient] Failed to fetch India VIX: {e}")
    return _vix_cache.get("value", 15.0)  # default to 15 if never fetched


# ── Spot Price ─────────────────────────────────────────────────────────────

def get_spot_price(underlying: str) -> float:
    """Get current spot price for NIFTY or BANKNIFTY. Fyers first, yfinance fallback."""
    # Try Fyers API first (real-time LTP)
    fyers = get_fyers()
    if fyers is not None:
        symbol = OPTIONS_INDEX_SYMBOLS.get(underlying, "")
        if symbol:
            try:
                res = fyers.quotes(data={"symbols": symbol})
                quotes = res.get("d", [])
                for q in quotes:
                    v = q.get("v", {})
                    if isinstance(v, dict):
                        lp = v.get("lp", 0) or v.get("close_price", 0)
                        if lp:
                            return float(lp)
            except Exception as e:
                logger.warning(f"[OptionsClient] Fyers spot price failed for {underlying}: {e}")

    # Fallback to yfinance (delayed but reliable)
    yf_symbols = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK"}
    yf_sym = yf_symbols.get(underlying)
    if yf_sym:
        try:
            ticker = yf.Ticker(yf_sym)
            hist = ticker.history(period="1d", interval="5m")
            if hist is not None and len(hist) > 0:
                price = float(hist["Close"].iloc[-1])
                if price > 0:
                    logger.info(f"[OptionsClient] Spot price via yfinance fallback: {underlying}={price}")
                    return price
        except Exception as e:
            logger.warning(f"[OptionsClient] yfinance fallback failed for {underlying}: {e}")

    logger.error(f"[OptionsClient] Could not get spot price for {underlying} from any source")
    return 0.0


# ── ATM Strike ─────────────────────────────────────────────────────────────

def get_atm_strike(underlying: str, spot_price: float = 0) -> int:
    """Find ATM strike from spot price, rounded to nearest strike interval."""
    if spot_price <= 0:
        spot_price = get_spot_price(underlying)
    if spot_price <= 0:
        return 0
    interval = OPTIONS_STRIKE_INTERVAL.get(underlying, 50)
    return int(round(spot_price / interval) * interval)


# ── Option Symbol Builder ─────────────────────────────────────────────────

def get_nearest_expiry(underlying: str, preference: str = "weekly") -> tuple[str, date]:
    """
    Get nearest expiry date string in YYMMDD format.
    For weekly: next Thursday. For monthly: last Thursday of month.
    """
    today = datetime.now(IST).date()

    if preference == "weekly":
        # Find next Thursday (weekday=3)
        days_ahead = 3 - today.weekday()  # Thursday
        if days_ahead < 0:
            days_ahead += 7
        if days_ahead == 0:
            # Today is Thursday — use today if market is open, else next week
            now = datetime.now(IST)
            if now.hour >= 15:
                days_ahead = 7
        expiry_date = today + timedelta(days=days_ahead)
    else:
        # Monthly: last Thursday of current or next month
        import calendar
        year, month = today.year, today.month
        # Find last Thursday of this month
        cal = calendar.monthcalendar(year, month)
        last_thursday = None
        for week in reversed(cal):
            if week[3] != 0:  # Thursday
                last_thursday = date(year, month, week[3])
                break
        # If past this month's expiry, go to next month
        if last_thursday is None or last_thursday < today:
            month += 1
            if month > 12:
                month = 1
                year += 1
            cal = calendar.monthcalendar(year, month)
            for week in reversed(cal):
                if week[3] != 0:
                    last_thursday = date(year, month, week[3])
                    break
        expiry_date = last_thursday

    # Fyers uses YYMON format (e.g., 26MAR), no day in symbol
    return expiry_date.strftime("%y") + expiry_date.strftime("%b").upper(), expiry_date


def build_option_symbol(underlying: str, expiry: str, strike: int, option_type: str) -> str:
    """
    Build Fyers option symbol.
    Format: NSE:NIFTY2503222500CE
    Args:
        underlying: "NIFTY" or "BANKNIFTY"
        expiry: "YYMMDD" format string
        strike: strike price as integer
        option_type: "CE" or "PE"
    """
    prefix = OPTIONS_SYMBOL_PREFIX.get(underlying, f"NSE:{underlying}")
    return f"{prefix}{expiry}{strike}{option_type}"


# ── Option Chain ───────────────────────────────────────────────────────────

def get_option_chain(underlying: str, expiry_preference: str = "weekly") -> dict:
    """
    Fetch option chain data for an underlying.
    Returns dict with: strikes, expiry, spot_price, atm_strike, chain data.
    """
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}

    spot = get_spot_price(underlying)
    if spot <= 0:
        return {"error": f"Could not get spot price for {underlying}"}

    atm = get_atm_strike(underlying, spot)
    expiry_str, expiry_date = get_nearest_expiry(underlying, expiry_preference)
    interval = OPTIONS_STRIKE_INTERVAL.get(underlying, 50)

    # Generate strikes around ATM (10 strikes each side)
    num_strikes = 10
    strikes = [atm + (i * interval) for i in range(-num_strikes, num_strikes + 1)]

    # Build option symbols for all strikes
    chain = {}
    all_symbols = []

    for strike in strikes:
        ce_sym = build_option_symbol(underlying, expiry_str, strike, "CE")
        pe_sym = build_option_symbol(underlying, expiry_str, strike, "PE")
        all_symbols.extend([ce_sym, pe_sym])
        chain[strike] = {"strike": strike, "ce_symbol": ce_sym, "pe_symbol": pe_sym}

    # Fetch quotes for all option symbols in batches
    batch_size = 50
    for i in range(0, len(all_symbols), batch_size):
        batch = all_symbols[i:i + batch_size]
        try:
            res = fyers.quotes(data={"symbols": ",".join(batch)})
            quotes = res.get("d", [])
            for q in quotes:
                sym = q.get("n", "") or q.get("symbol", "")
                v = q.get("v", {})
                if not isinstance(v, dict):
                    continue
                ltp = v.get("lp", 0) or v.get("close_price", 0)
                bid = v.get("bid", 0)
                ask = v.get("ask", 0)
                oi = v.get("open_interest", 0)
                volume = v.get("volume", 0)

                # Match to chain entry
                for strike_val, entry in chain.items():
                    if sym == entry.get("ce_symbol"):
                        entry["ce_ltp"] = ltp
                        entry["ce_bid"] = bid
                        entry["ce_ask"] = ask
                        entry["ce_oi"] = oi
                        entry["ce_volume"] = volume
                    elif sym == entry.get("pe_symbol"):
                        entry["pe_ltp"] = ltp
                        entry["pe_bid"] = bid
                        entry["pe_ask"] = ask
                        entry["pe_oi"] = oi
                        entry["pe_volume"] = volume
        except Exception as e:
            logger.warning(f"[OptionsClient] Error fetching option quotes batch: {e}")

    return {
        "underlying": underlying,
        "spot_price": spot,
        "atm_strike": atm,
        "expiry": expiry_str,
        "expiry_date": expiry_date.isoformat(),
        "days_to_expiry": (expiry_date - datetime.now(IST).date()).days,
        "strike_interval": interval,
        "lot_size": OPTIONS_LOT_SIZES.get(underlying, 75),
        "chain": chain,
    }


def get_ltp(symbol: str) -> float:
    """Get LTP for a specific option symbol via Fyers quotes API."""
    fyers = get_fyers()
    if fyers is None:
        return 0.0
    try:
        res = fyers.quotes(data={"symbols": symbol})
        quotes = res.get("d", [])
        for q in quotes:
            v = q.get("v", {})
            if isinstance(v, dict):
                return float(v.get("lp", 0) or v.get("close_price", 0))
    except Exception as e:
        logger.warning(f"[OptionsClient] Failed to get LTP for {symbol}: {e}")
    return 0.0


def get_ltp_batch(symbols: list[str]) -> dict[str, float]:
    """Get LTP for multiple option symbols in a single Fyers API call.

    Args:
        symbols: List of Fyers option symbols (e.g. ["NSE:NIFTY2503222500CE", "NSE:NIFTY2503222400PE"])

    Returns:
        Dict mapping symbol -> LTP (only includes symbols with valid prices)
    """
    if not symbols:
        return {}
    fyers = get_fyers()
    if fyers is None:
        return {}

    result = {}
    # Fyers quotes API supports up to 50 symbols per call
    batch_size = 50
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        try:
            res = fyers.quotes(data={"symbols": ",".join(batch)})
            quotes = res.get("d", [])
            for q in quotes:
                sym = q.get("n", "") or q.get("symbol", "")
                v = q.get("v", {})
                if isinstance(v, dict):
                    ltp = float(v.get("lp", 0) or v.get("close_price", 0))
                    if ltp > 0:
                        result[sym] = ltp
        except Exception as e:
            logger.warning(f"[OptionsClient] Batch LTP error: {e}")

    return result


def calculate_pcr(chain_data: dict) -> float:
    """Calculate Put-Call Ratio from option chain data."""
    chain = chain_data.get("chain", {})
    total_put_oi = 0
    total_call_oi = 0
    for strike, data in chain.items():
        total_call_oi += data.get("ce_oi", 0)
        total_put_oi += data.get("pe_oi", 0)
    if total_call_oi == 0:
        return 1.0
    return round(total_put_oi / total_call_oi, 2)


def get_lot_size(underlying: str) -> int:
    """Get lot size for an underlying."""
    return OPTIONS_LOT_SIZES.get(underlying, 75)


def place_option_order(
    symbol: str,
    qty: int,
    side: int,  # 1=Buy, -1=Sell
    order_type: int = 2,  # 2=Market
    product_type: str = "INTRADAY",
    limit_price: float = 0,
) -> dict:
    """Place an order for an option contract via Fyers."""
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}

    data = {
        "symbol": symbol,  # Already in Fyers format: NSE:NIFTY2503222500CE
        "qty": qty,
        "type": order_type,
        "side": side,
        "productType": product_type,
        "limitPrice": round(limit_price, 2) if limit_price else 0,
        "stopPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
    }

    try:
        response = fyers.place_order(data=data)
        if response.get("s") == "ok" or "id" in response:
            return response
        return {"error": response.get("message", str(response))}
    except Exception as e:
        return {"error": str(e)}


def place_spread_orders(legs: list[dict], product_type: str = "INTRADAY", use_limit: bool = True) -> dict:
    """
    Place orders for all legs of a spread.
    Each leg: {"symbol": str, "qty": int, "side": int (1=Buy, -1=Sell), "price": float (optional)}
    Returns combined result with all order IDs.

    CRITICAL: BUY legs are placed FIRST, then SELL legs.
    This ensures Fyers recognizes the spread and applies spread margin (~₹20K)
    instead of naked option margin (~₹1.13L). Without this ordering,
    SELL legs get rejected for margin shortfall.

    If a leg fails after previous legs succeeded, attempts to rollback
    (reverse) the already-placed legs to avoid unhedged exposure.
    """
    # Reorder: BUY legs first (side=1), then SELL legs (side=-1)
    # This is critical for spread margin recognition on Fyers
    ordered_legs = sorted(legs, key=lambda l: l.get("side", 0), reverse=True)

    results = []
    succeeded_legs = []

    for i, leg in enumerate(ordered_legs):
        # Use limit order when price is available and use_limit is True
        leg_price = leg.get("price", 0)
        if use_limit and leg_price and leg_price > 0:
            order_type = 1  # Limit
            limit_price = leg_price
        else:
            order_type = 2  # Market
            limit_price = 0

        # Before SELL leg: verify margin is available (BUY leg should have established spread)
        if leg["side"] == -1 and succeeded_legs:
            try:
                from services.fyers_client import get_funds
                funds = get_funds()
                avail = 0
                for f_item in funds.get("fund_limit", []):
                    if f_item.get("id") == 10:
                        avail = f_item.get("equityAmount", 0)
                if avail < 5000:  # Minimum margin buffer
                    logger.warning(f"[OptionsClient] Margin too low (₹{avail:,.0f}) for SELL leg — aborting spread")
                    # Rollback BUY legs
                    for prev_leg in succeeded_legs:
                        reverse_side = -1 if prev_leg["side"] == 1 else 1
                        place_option_order(symbol=prev_leg["symbol"], qty=prev_leg["qty"],
                                           side=reverse_side, product_type=product_type)
                    return {"error": f"Margin insufficient for SELL leg (₹{avail:,.0f} available)", "results": results}
            except Exception:
                pass  # Proceed if funds check fails

        import time as _time
        # Small delay between legs to let Fyers recognize the spread
        if i > 0:
            _time.sleep(2)

        result = place_option_order(
            symbol=leg["symbol"],
            qty=leg["qty"],
            side=leg["side"],
            order_type=order_type,
            product_type=product_type,
            limit_price=limit_price,
        )

        leg_result = {
            "symbol": leg["symbol"],
            "side": leg["side"],
            "qty": leg["qty"],
            "order_id": result.get("id", result.get("order_id", "")),
            "error": result.get("error"),
            "status": "FAILED" if "error" in result else "OK",
        }
        results.append(leg_result)

        if "error" in result:
            # This leg failed — attempt rollback of previously succeeded legs
            if succeeded_legs:
                logger.warning(f"[OptionsClient] Leg {i+1}/{len(legs)} failed ({leg['symbol']}): {result.get('error')}. "
                               f"Rolling back {len(succeeded_legs)} succeeded leg(s)...")
                rollback_results = []
                for prev_leg in succeeded_legs:
                    reverse_side = -1 if prev_leg["side"] == 1 else 1
                    rollback = place_option_order(
                        symbol=prev_leg["symbol"],
                        qty=prev_leg["qty"],
                        side=reverse_side,
                        product_type=product_type,
                    )
                    rb_ok = "error" not in rollback
                    rollback_results.append({
                        "symbol": prev_leg["symbol"],
                        "reverse_order_id": rollback.get("id", rollback.get("order_id", "")),
                        "rollback_ok": rb_ok,
                        "error": rollback.get("error") if not rb_ok else None,
                    })
                    if not rb_ok:
                        logger.error(f"[OptionsClient] ROLLBACK FAILED for {prev_leg['symbol']}: {rollback.get('error')}. MANUAL CLOSE REQUIRED!")

                all_rolled_back = all(r["rollback_ok"] for r in rollback_results)
                return {
                    "error": f"Leg {i+1} failed: {result.get('error')}. "
                             f"Rollback {'succeeded' if all_rolled_back else 'PARTIALLY FAILED — MANUAL INTERVENTION REQUIRED'}.",
                    "failed_leg": i,
                    "legs": results,
                    "rollback": rollback_results,
                    "rollback_ok": all_rolled_back,
                    "all_filled": False,
                }
            else:
                # First leg failed — nothing to rollback
                return {
                    "error": f"First leg failed: {result.get('error')}",
                    "failed_leg": i,
                    "legs": results,
                    "all_filled": False,
                }
        else:
            succeeded_legs.append(leg)

    # All legs succeeded
    order_ids = [r["order_id"] for r in results if r.get("order_id")]
    return {
        "s": "ok",
        "legs": results,
        "order_ids": order_ids,
        "all_filled": True,
    }
