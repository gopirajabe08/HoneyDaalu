"""
Futures OI Analyser — Layer 1 from the Strategic Blueprint.

Classifies each F&O stock's Open Interest sentiment into one of four states:
  - Long Buildup:    Price UP + OI UP    (fresh longs entering)
  - Short Covering:  Price UP + OI DOWN  (shorts exiting)
  - Short Buildup:   Price DOWN + OI UP  (fresh shorts entering)
  - Long Unwinding:  Price DOWN + OI DOWN (longs exiting)

Also calculates a conviction score based on Volume/OI change magnitude.

Data source: Fyers quotes() API returns OI for futures symbols.
"""

import logging
from datetime import datetime, timezone, timedelta

from services.fyers_client import get_quotes, is_authenticated
from services.futures_client import build_futures_symbol
from fno_stocks import get_fno_symbols, get_lot_size

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


def classify_oi_sentiment(price_change_pct: float, oi_change_pct: float) -> str:
    """
    Classify OI sentiment based on price and OI change.

    Returns one of: "long_buildup", "short_covering", "short_buildup", "long_unwinding"
    """
    if price_change_pct > 0 and oi_change_pct > 0:
        return "long_buildup"
    elif price_change_pct > 0 and oi_change_pct <= 0:
        return "short_covering"
    elif price_change_pct <= 0 and oi_change_pct > 0:
        return "short_buildup"
    else:  # price down, OI down
        return "long_unwinding"


def calculate_conviction(volume: float, oi_change: float) -> float:
    """
    Calculate conviction score from volume and OI change.
    Higher volume relative to OI change = stronger conviction.
    Returns a score from 0.0 to 1.0.
    """
    if oi_change == 0:
        return 0.5  # neutral
    ratio = abs(volume / oi_change) if oi_change != 0 else 0
    # Normalize: ratio > 2 is high conviction, < 0.5 is low
    score = min(ratio / 3.0, 1.0)
    return round(score, 2)


def analyse_single_symbol(symbol: str) -> dict | None:
    """
    Fetch OI data for a single symbol and classify sentiment.
    Returns dict with sentiment, conviction, and raw data, or None on failure.
    """
    if not is_authenticated():
        return None

    fyers_symbol = build_futures_symbol(symbol)
    try:
        res = get_quotes([fyers_symbol])
        quotes = res.get("d", [])
        if not quotes:
            data = res.get("data", {})
            if isinstance(data, dict):
                quotes = data.get("d", [])

        if not quotes:
            return None

        q = quotes[0]
        v = q.get("v", {})
        if not isinstance(v, dict):
            return None

        ltp = v.get("lp", 0)
        prev_close = v.get("prev_close_price", 0)
        oi = v.get("open_interest", 0)
        prev_oi = v.get("prev_open_interest", 0)
        volume = v.get("volume", 0)

        if not ltp or not prev_close:
            return None

        price_change = ltp - prev_close
        price_change_pct = (price_change / prev_close * 100) if prev_close else 0
        oi_change = oi - prev_oi if prev_oi else 0
        oi_change_pct = (oi_change / prev_oi * 100) if prev_oi else 0

        sentiment = classify_oi_sentiment(price_change_pct, oi_change_pct)
        conviction = calculate_conviction(volume, abs(oi_change) if oi_change else 1)

        return {
            "symbol": symbol,
            "futures_symbol": fyers_symbol,
            "ltp": ltp,
            "prev_close": prev_close,
            "price_change_pct": round(price_change_pct, 2),
            "oi": oi,
            "prev_oi": prev_oi,
            "oi_change": oi_change,
            "oi_change_pct": round(oi_change_pct, 2),
            "volume": volume,
            "sentiment": sentiment,
            "conviction": conviction,
        }
    except Exception as e:
        logger.warning(f"[FuturesOI] Failed to fetch OI for {symbol}: {e}")
        return None


def analyse_batch(symbols: list[str], batch_size: int = 50) -> dict[str, dict]:
    """
    Batch-fetch OI data for multiple symbols.
    Returns {symbol: oi_data_dict} for each successfully fetched symbol.
    """
    if not is_authenticated():
        logger.warning("[FuturesOI] Fyers not authenticated — skipping OI analysis")
        return {}

    result = {}

    # Process in batches to avoid API limits
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        fyers_symbols = [build_futures_symbol(s) for s in batch]

        try:
            res = get_quotes(fyers_symbols)
            quotes = res.get("d", [])
            if not quotes:
                data = res.get("data", {})
                if isinstance(data, dict):
                    quotes = data.get("d", [])

            for q in quotes:
                try:
                    fyers_sym = q.get("n", "")
                    # Extract base symbol: NSE:RELIANCE26MARFUT -> RELIANCE
                    base = fyers_sym.replace("NSE:", "")
                    # Remove the date+FUT suffix
                    for s in batch:
                        if base.startswith(s):
                            sym = s
                            break
                    else:
                        continue

                    v = q.get("v", {})
                    if not isinstance(v, dict):
                        continue

                    ltp = v.get("lp", 0)
                    prev_close = v.get("prev_close_price", 0)
                    oi = v.get("open_interest", 0)
                    prev_oi = v.get("prev_open_interest", 0)
                    volume = v.get("volume", 0)

                    if not ltp or not prev_close:
                        continue

                    price_change_pct = ((ltp - prev_close) / prev_close * 100) if prev_close else 0
                    oi_change = oi - prev_oi if prev_oi else 0
                    oi_change_pct = (oi_change / prev_oi * 100) if prev_oi else 0

                    sentiment = classify_oi_sentiment(price_change_pct, oi_change_pct)
                    conviction = calculate_conviction(volume, abs(oi_change) if oi_change else 1)

                    result[sym] = {
                        "symbol": sym,
                        "futures_symbol": fyers_sym,
                        "ltp": ltp,
                        "prev_close": prev_close,
                        "price_change_pct": round(price_change_pct, 2),
                        "oi": oi,
                        "prev_oi": prev_oi,
                        "oi_change": oi_change,
                        "oi_change_pct": round(oi_change_pct, 2),
                        "volume": volume,
                        "sentiment": sentiment,
                        "conviction": conviction,
                    }
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"[FuturesOI] Batch fetch failed: {e}")

    return result
