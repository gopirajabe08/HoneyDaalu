"""
Futures Scanner — Orchestrates OI analysis + strategy screeners + lot-based sizing.

Layer 3 from the Strategic Blueprint:
  1. Fetch OI data for all F&O stocks (Layer 1)
  2. Apply liquidity filter (min OI, min volume)
  3. Run selected strategy screeners with OI filter (Layer 2)
  4. Calculate margin-based lot sizing (Layer 3)
  5. Return ranked signals
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf
from fno_stocks import get_fno_symbols, get_lot_size
from strategies.futures_registry import FUTURES_STRATEGY_MAP, FUTURES_STRATEGY_TIMEFRAMES
from services.futures_oi_analyser import analyse_batch
from services.futures_client import calculate_position_size, get_futures_ltp
from services.market_data import fetch_stock_data
from config import (
    INTERVAL_PERIOD_MAP, FUTURES_MIN_OI, FUTURES_MIN_DAILY_VOLUME,
    FUTURES_MARGIN_PCT_INTRADAY, FUTURES_MARGIN_PCT_OVERNIGHT,
)


def _estimate_futures_brokerage(qty: int, entry: float, exit_price: float) -> float:
    """
    Estimate round-trip brokerage for a futures trade.
    Fyers charges: ₹20/order (2 orders) + STT 0.0125% on sell + exchange + GST.
    """
    if qty == 0 or entry == 0:
        return 0.0
    buy_val = entry * qty
    sell_val = exit_price * qty
    turnover = buy_val + sell_val

    brokerage = 40.0  # ₹20 × 2 legs
    stt = sell_val * 0.000125  # 0.0125% on sell side (futures)
    exchange = turnover * 0.0000190  # ~0.0019% NSE charges
    gst = (brokerage + exchange) * 0.18
    sebi = turnover * 0.000001  # ₹10 per crore
    stamp = buy_val * 0.00002  # 0.002% on buy side

    return round(brokerage + stt + exchange + gst + sebi + stamp, 2)

logger = logging.getLogger(__name__)


def _passes_liquidity_filter(oi_data: dict | None, symbol: str) -> bool:
    """Check if a futures contract has sufficient OI and volume for safe trading."""
    if not oi_data or symbol not in oi_data:
        return False  # No OI data = contract doesn't exist or not traded — SKIP

    oi_info = oi_data[symbol]
    ltp = oi_info.get("ltp", 0)
    volume = oi_info.get("volume", 0)

    # Must have non-zero LTP — confirms the contract actually trades
    if ltp <= 0:
        return False

    if volume < FUTURES_MIN_DAILY_VOLUME:
        return False

    return True


def run_futures_scan(strategy_key: str, timeframe: str, capital: float,
                     oi_data: dict | None = None, mode: str = "intraday") -> dict:
    """
    Scan F&O stocks for futures signals using a specific strategy.

    Uses spot OHLCV data from yfinance for technical analysis, but adjusts
    entry prices using futures LTP when available (accounts for basis).

    Args:
        strategy_key: e.g. "futures_volume_breakout"
        timeframe: e.g. "15m", "1h", "1d"
        capital: Trading capital for position sizing
        oi_data: Pre-fetched OI data dict {symbol: oi_dict}. If None, scans without OI filter.
    """
    strategy = FUTURES_STRATEGY_MAP.get(strategy_key)
    if not strategy:
        return {"error": f"Unknown futures strategy: {strategy_key}"}

    period = INTERVAL_PERIOD_MAP.get(timeframe, "30d")
    symbols = get_fno_symbols()

    start_time = time.time()
    signals = []
    scanned = 0
    errors = 0
    filtered_liquidity = 0

    def _scan_one(symbol: str):
        try:
            # Liquidity filter — skip illiquid contracts
            if not _passes_liquidity_filter(oi_data, symbol):
                return "FILTERED"

            df = fetch_stock_data(symbol, timeframe, period)
            if df is None or df.empty or len(df) < 10:
                return None

            symbol_oi = oi_data.get(symbol) if oi_data else None
            result = strategy.scan(df, symbol, oi_data=symbol_oi)

            if result:
                # Adjust entry price to futures LTP if available (accounts for basis)
                if oi_data and symbol in oi_data:
                    futures_ltp = oi_data[symbol].get("ltp", 0)
                    if futures_ltp > 0:
                        spot_price = result.get("entry_price", 0)
                        if spot_price > 0:
                            # Calculate basis ratio and adjust SL/target proportionally
                            basis_ratio = futures_ltp / spot_price
                            result["entry_price"] = round(futures_ltp, 2)
                            result["stop_loss"] = round(result["stop_loss"] * basis_ratio, 2)
                            result["target_1"] = round(result["target_1"] * basis_ratio, 2)
                            result["current_price"] = round(futures_ltp, 2)
                            # Recalculate risk/reward with adjusted prices
                            if result["signal_type"] == "BUY":
                                result["risk"] = round(result["entry_price"] - result["stop_loss"], 2)
                                result["reward"] = round(result["target_1"] - result["entry_price"], 2)
                            else:
                                result["risk"] = round(result["stop_loss"] - result["entry_price"], 2)
                                result["reward"] = round(result["entry_price"] - result["target_1"], 2)

            return result
        except Exception as e:
            logger.debug(f"[FuturesScanner] {symbol} error: {e}")
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_scan_one, sym): sym for sym in symbols}
        for future in as_completed(futures):
            scanned += 1
            try:
                result = future.result()
                if result == "FILTERED":
                    filtered_liquidity += 1
                    continue
                if result:
                    # Add position sizing
                    entry = result.get("entry_price", 0)
                    sl = result.get("stop_loss", 0)
                    symbol = result.get("symbol", "")
                    if entry and sl and symbol:
                        margin_pct = FUTURES_MARGIN_PCT_OVERNIGHT if mode == "swing" else FUTURES_MARGIN_PCT_INTRADAY
                        sizing = calculate_position_size(symbol, entry, sl, capital, margin_pct=margin_pct)
                        result["lot_size"] = sizing.get("lot_size", 0)
                        result["num_lots"] = sizing.get("num_lots", 0)
                        result["quantity"] = sizing.get("total_qty", 0)
                        result["margin_required"] = sizing.get("margin_required", 0)
                        result["risk_amount"] = sizing.get("risk_amount", 0)
                        result["risk_pct_actual"] = sizing.get("risk_pct_actual", 0)

                        # Estimate brokerage for this trade
                        est_target = result.get("target_1", entry)
                        est_brokerage = _estimate_futures_brokerage(
                            sizing.get("total_qty", 0), entry, est_target
                        )
                        result["est_brokerage"] = est_brokerage
                        # Net reward after brokerage
                        raw_reward = result.get("reward", 0) * sizing.get("total_qty", 0)
                        result["net_reward_after_charges"] = round(raw_reward - est_brokerage, 2)

                        # Skip signals where brokerage eats the profit
                        if est_brokerage > 0 and raw_reward > 0 and est_brokerage >= raw_reward * 0.5:
                            continue  # brokerage > 50% of reward — not worth it

                        # Add OI data to signal
                        if oi_data and symbol in oi_data:
                            oi = oi_data[symbol]
                            result["oi_sentiment"] = oi.get("sentiment", "")
                            result["oi_conviction"] = oi.get("conviction", 0)
                            result["oi_change_pct"] = oi.get("oi_change_pct", 0)

                    if result.get("quantity", 0) > 0:
                        signals.append(result)
            except Exception:
                errors += 1

    scan_time = round(time.time() - start_time, 1)

    # Sort by: OI-aligned first, then conviction, then R:R
    signals.sort(key=lambda s: (
        1 if s.get("oi_aligned", True) else 0,  # OI-aligned signals get priority
        s.get("oi_conviction", 0),
        s.get("reward", 0) / max(s.get("risk", 1), 0.01),
    ), reverse=True)

    return {
        "strategy": strategy_key,
        "timeframe": timeframe,
        "stocks_scanned": scanned,
        "signals_found": len(signals),
        "filtered_liquidity": filtered_liquidity,
        "signals": signals,
        "scan_time_seconds": scan_time,
        "errors": errors,
    }


def run_futures_scan_all(strategies: list[dict], capital: float,
                         use_oi: bool = True) -> dict:
    """
    Run multiple futures strategies with OI pre-filter.
    """
    start_time = time.time()

    oi_data = {}
    if use_oi:
        symbols = get_fno_symbols()
        oi_data = analyse_batch(symbols)
        logger.info(f"[FuturesScanner] OI data fetched for {len(oi_data)} stocks")

    all_signals = []
    total_scanned = 0

    for strat in strategies:
        key = strat.get("strategy", "")
        tf = strat.get("timeframe", "15m")
        result = run_futures_scan(key, tf, capital, oi_data=oi_data)

        if "error" in result:
            continue

        for sig in result.get("signals", []):
            sig["_strategy"] = key
            sig["_timeframe"] = tf
        all_signals.extend(result.get("signals", []))
        total_scanned = max(total_scanned, result.get("stocks_scanned", 0))

    # Deduplicate by symbol — keep best conviction + R:R
    seen = {}
    for sig in all_signals:
        sym = sig.get("symbol", "")
        score = sig.get("oi_conviction", 0) + sig.get("reward", 0) / max(sig.get("risk", 1), 0.01)
        if sym not in seen or score > seen[sym][1]:
            seen[sym] = (sig, score)

    unique_signals = [s[0] for s in sorted(seen.values(), key=lambda x: x[1], reverse=True)]

    return {
        "stocks_scanned": total_scanned,
        "oi_stocks_analysed": len(oi_data),
        "signals": unique_signals,
        "scan_time_seconds": round(time.time() - start_time, 1),
    }
