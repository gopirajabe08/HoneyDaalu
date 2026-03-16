"""
Backtest service — runs strategy backtests and returns structured JSON results.
Refactored from test_strategy.py for API use.
"""

import time
import math
import warnings
import logging
import pandas as pd
from datetime import datetime, timezone, timedelta

warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("peewee").setLevel(logging.CRITICAL)

import yfinance as yf

from nifty500 import get_nifty500_symbols, get_yfinance_symbol
from strategies import STRATEGY_MAP
from config import STRATEGY_TIMEFRAMES, INTERVAL_PERIOD_MAP
from services.market_data import get_nifty_trend

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

RISK_PCT = 0.02
MAX_POSITIONS = 3
SLIPPAGE_PCT = 0.001  # 0.1% slippage on entry to simulate realistic fills

# In-memory cache: (timeframe, period) -> {symbol: DataFrame}
_data_cache = {}
_cache_ts = {}
CACHE_TTL = 600  # 10 minutes


def _calc_quantity(capital, entry, risk_per_share):
    risk_amount = capital * RISK_PCT
    if risk_per_share <= 0:
        return 0
    qty = math.floor(risk_amount / risk_per_share)
    max_qty = math.floor(capital / entry) if entry > 0 else 0
    return min(qty, max_qty)


def _find_trading_day(date_str=None):
    """Parse date string or find last trading day."""
    if date_str:
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=IST)
            return day
        except ValueError:
            return None
    now = datetime.now(IST)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _is_intraday(tf):
    return tf in {"3m", "5m", "15m", "30m", "1h"}


def _fetch_all_batch(symbols, interval, period):
    """Fetch data for all symbols using yf.download() batch API — much faster than individual calls."""
    cache_key = (interval, period)
    now = time.time()

    # Check cache
    if cache_key in _data_cache and (now - _cache_ts.get(cache_key, 0)) < CACHE_TTL:
        logger.info(f"[Backtester] Using cached data for {interval}/{period}")
        return _data_cache[cache_key]

    yf_symbols = [get_yfinance_symbol(s) for s in symbols]
    sym_map = {get_yfinance_symbol(s): s for s in symbols}  # RELIANCE.NS -> RELIANCE

    try:
        # Batch download — single HTTP request for all tickers
        raw = yf.download(
            tickers=yf_symbols,
            period=period,
            interval=interval,
            group_by="ticker",
            threads=True,
            progress=False,
        )
    except Exception as e:
        logger.error(f"[Backtester] Batch download failed: {e}")
        return {}

    result = {}
    required = ["Open", "High", "Low", "Close", "Volume"]

    for yf_sym, nse_sym in sym_map.items():
        try:
            if len(yf_symbols) == 1:
                df = raw  # single ticker returns flat DataFrame
            else:
                df = raw[yf_sym] if yf_sym in raw.columns.get_level_values(0) else None

            if df is None or df.empty:
                continue

            # Handle both old and new yfinance column formats
            cols = df.columns.tolist()
            col_map = {}
            for col in cols:
                col_str = str(col).lower().replace(" ", "")
                if "open" in col_str:
                    col_map[col] = "Open"
                elif "high" in col_str:
                    col_map[col] = "High"
                elif "low" in col_str:
                    col_map[col] = "Low"
                elif "close" in col_str and "adj" not in col_str:
                    col_map[col] = "Close"
                elif "volume" in col_str:
                    col_map[col] = "Volume"

            if col_map:
                df = df.rename(columns=col_map)

            missing = [c for c in required if c not in df.columns]
            if missing:
                continue

            df = df[required].copy()
            df.dropna(inplace=True)
            if len(df) >= 5:
                result[nse_sym] = df
        except Exception:
            continue

    # Update cache
    _data_cache[cache_key] = result
    _cache_ts[cache_key] = now
    logger.info(f"[Backtester] Fetched {len(result)} stocks via batch download ({interval}/{period})")

    return result


def _filter_to_date(df, target_date):
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    try:
        df.index = df.index.tz_convert(IST)
    except Exception:
        pass
    mask = df.index.date == target_date.date()
    day_df = df[mask].copy()
    return day_df if len(day_df) >= 5 else None


def _sim_trade_intraday(day_df, entry_idx, entry_price, stop_loss, target, signal_type):
    future = day_df.iloc[entry_idx + 1:]
    is_buy = signal_type == "BUY"

    for i, (_, candle) in enumerate(future.iterrows()):
        sl_hit = (candle["Low"] <= stop_loss) if is_buy else (candle["High"] >= stop_loss)
        tgt_hit = (candle["High"] >= target) if is_buy else (candle["Low"] <= target)

        if sl_hit and tgt_hit:
            # Both hit in same candle — use open price heuristic:
            # If candle opened in a favorable direction, assume target hit first
            if is_buy:
                if candle["Open"] >= entry_price:
                    return _result("TARGET_HIT", target, entry_price, is_buy, i + 1, candle)
                else:
                    return _result("SL_HIT", stop_loss, entry_price, is_buy, i + 1, candle)
            else:
                if candle["Open"] <= entry_price:
                    return _result("TARGET_HIT", target, entry_price, is_buy, i + 1, candle)
                else:
                    return _result("SL_HIT", stop_loss, entry_price, is_buy, i + 1, candle)
        elif sl_hit:
            return _result("SL_HIT", stop_loss, entry_price, is_buy, i + 1, candle)
        elif tgt_hit:
            return _result("TARGET_HIT", target, entry_price, is_buy, i + 1, candle)

    last_price = future.iloc[-1]["Close"] if len(future) > 0 else entry_price
    pnl = (last_price - entry_price) if is_buy else (entry_price - last_price)
    return {
        "outcome": "EOD_SQUAREOFF",
        "exit_price": round(last_price, 2),
        "pnl_per_share": round(pnl, 2),
        "candles_held": len(future),
        "exit_time": future.iloc[-1].name.strftime("%H:%M") if len(future) > 0 else "15:15",
    }


def _sim_trade_daily(df, entry_idx, entry_price, stop_loss, target, signal_type, hold_days=5):
    future = df.iloc[entry_idx + 1: entry_idx + 1 + hold_days]
    is_buy = signal_type == "BUY"

    for i, (_, candle) in enumerate(future.iterrows()):
        sl_hit = (candle["Low"] <= stop_loss) if is_buy else (candle["High"] >= stop_loss)
        tgt_hit = (candle["High"] >= target) if is_buy else (candle["Low"] <= target)

        if sl_hit and tgt_hit:
            if is_buy:
                if candle["Open"] >= entry_price:
                    return _result("TARGET_HIT", target, entry_price, is_buy, i + 1, candle)
                else:
                    return _result("SL_HIT", stop_loss, entry_price, is_buy, i + 1, candle)
            else:
                if candle["Open"] <= entry_price:
                    return _result("TARGET_HIT", target, entry_price, is_buy, i + 1, candle)
                else:
                    return _result("SL_HIT", stop_loss, entry_price, is_buy, i + 1, candle)
        elif sl_hit:
            return _result("SL_HIT", stop_loss, entry_price, is_buy, i + 1, candle)
        elif tgt_hit:
            return _result("TARGET_HIT", target, entry_price, is_buy, i + 1, candle)

    last_price = future.iloc[-1]["Close"] if len(future) > 0 else entry_price
    pnl = (last_price - entry_price) if is_buy else (entry_price - last_price)
    date_str = future.iloc[-1].name.strftime("%Y-%m-%d") if len(future) > 0 else "N/A"
    return {
        "outcome": f"EXIT_{hold_days}D",
        "exit_price": round(last_price, 2),
        "pnl_per_share": round(pnl, 2),
        "candles_held": len(future),
        "exit_time": date_str,
    }


def _result(outcome, exit_price, entry_price, is_buy, candles, candle):
    pnl = (exit_price - entry_price) if is_buy else (entry_price - exit_price)
    try:
        exit_time = candle.name.strftime("%H:%M")
    except Exception:
        try:
            exit_time = candle.name.strftime("%Y-%m-%d")
        except Exception:
            exit_time = "N/A"
    return {
        "outcome": outcome,
        "exit_price": round(exit_price, 2),
        "pnl_per_share": round(pnl, 2),
        "candles_held": candles,
        "exit_time": exit_time,
    }


# ── Main API ──────────────────────────────────────────────────────────────

def run_backtest_api(strategy_key: str, timeframe: str, capital: float = 100000, date: str = None) -> dict:
    """
    Run a backtest and return structured JSON results.

    Args:
        strategy_key: e.g. "play3_vwap_pullback"
        timeframe: e.g. "5m", "15m", "1d"
        capital: trading capital
        date: "YYYY-MM-DD" or None for last trading day
    """
    if strategy_key not in STRATEGY_MAP:
        return {"error": f"Unknown strategy '{strategy_key}'", "available": list(STRATEGY_MAP.keys())}

    valid_tfs = STRATEGY_TIMEFRAMES.get(strategy_key, [])
    if timeframe not in valid_tfs:
        return {"error": f"Invalid timeframe '{timeframe}' for {strategy_key}", "valid_timeframes": valid_tfs}

    strategy = STRATEGY_MAP[strategy_key]
    info = strategy.info()
    intraday = _is_intraday(timeframe)
    target_date = _find_trading_day(date)

    if target_date is None:
        return {"error": f"Invalid date format: '{date}'. Use YYYY-MM-DD."}

    if target_date.weekday() >= 5:
        return {"error": f"{target_date.strftime('%Y-%m-%d')} is a weekend. Choose a weekday."}

    period = INTERVAL_PERIOD_MAP.get(timeframe, "30d")

    # Build scan windows
    if intraday:
        scan_times = []
        t = target_date.replace(hour=9, minute=30, second=0)
        cutoff = target_date.replace(hour=14, minute=0, second=0)
        while t < cutoff:
            scan_times.append(t)
            t += timedelta(minutes=15)
    else:
        scan_times = [target_date]

    # Fetch data (batch download — single request for all 500 stocks)
    symbols = get_nifty500_symbols()
    start_fetch = time.time()

    all_data = _fetch_all_batch(symbols, timeframe, period)
    day_data = {}

    if intraday:
        for sym, df in all_data.items():
            day_df = _filter_to_date(df, target_date)
            if day_df is not None:
                day_data[sym] = day_df
    else:
        day_data = {sym: df for sym, df in all_data.items()}

    fetch_time = round(time.time() - start_fetch, 1)

    if not day_data:
        return {
            "strategy": strategy_key,
            "strategy_name": info["name"],
            "timeframe": timeframe,
            "date": target_date.strftime("%Y-%m-%d"),
            "error": "No data available for this date (market holiday or data not available)",
            "stocks_fetched": 0,
            "fetch_time": fetch_time,
        }

    # Replay scans
    all_trades = []
    open_positions = set()
    total_signals = 0
    scan_log = []

    for scan_time in scan_times:
        scan_label = scan_time.strftime("%H:%M") if intraday else scan_time.strftime("%Y-%m-%d")

        # Free positions that closed before this scan
        if intraday:
            current_ts = scan_time.replace(tzinfo=IST) if scan_time.tzinfo is None else scan_time
            for t in all_trades:
                if t["symbol"] in open_positions and t["outcome"] in ("SL_HIT", "TARGET_HIT"):
                    try:
                        exit_dt = target_date.replace(
                            hour=int(t["exit_time"].split(":")[0]),
                            minute=int(t["exit_time"].split(":")[1]),
                            second=0, tzinfo=IST
                        )
                        if exit_dt <= current_ts:
                            open_positions.discard(t["symbol"])
                    except Exception:
                        pass

        if len(open_positions) >= MAX_POSITIONS:
            scan_log.append({"time": scan_label, "signals": 0, "trades": 0, "note": "Max positions reached"})
            continue

        slots = MAX_POSITIONS - len(open_positions)
        signals = []

        for sym in day_data:
            if sym in open_positions:
                continue

            full_df = all_data.get(sym)
            if full_df is None:
                continue

            if intraday:
                scan_ts = pd.Timestamp(scan_time)
                if scan_ts.tzinfo is None:
                    scan_ts = scan_ts.tz_localize(IST)
                candles = full_df[full_df.index <= scan_ts]
            else:
                candles = full_df

            if len(candles) < 5:
                continue

            signal = strategy.scan(candles, sym)
            if signal is not None:
                signals.append(signal)

        total_signals += len(signals)

        if not signals:
            scan_log.append({"time": scan_label, "signals": 0, "trades": 0})
            continue

        # ── Nifty trend filter: block counter-trend trades ──
        nifty_trend = get_nifty_trend(timeframe)
        if nifty_trend == "BULLISH":
            signals = [s for s in signals if s.get("signal_type") != "SELL"]
        elif nifty_trend == "BEARISH":
            signals = [s for s in signals if s.get("signal_type") != "BUY"]

        if not signals:
            scan_log.append({"time": scan_label, "signals": 0, "trades": 0, "note": f"All filtered by Nifty trend ({nifty_trend})"})
            continue

        signals.sort(key=lambda s: s.get("reward", 0) / max(s.get("risk", 1), 0.01), reverse=True)

        trades_this_scan = 0
        for sig in signals:
            if trades_this_scan >= slots:
                break

            sym = sig["symbol"]
            if sym in open_positions:
                continue

            raw_entry = sig["entry_price"]
            sl = sig["stop_loss"]
            target = sig.get("target_1", sig.get("target", raw_entry))
            signal_type = sig.get("signal_type", "BUY")

            # Apply slippage to simulate realistic fills (next-candle-open effect)
            if signal_type == "BUY":
                entry = round(raw_entry * (1 + SLIPPAGE_PCT), 2)
            else:
                entry = round(raw_entry * (1 - SLIPPAGE_PCT), 2)

            risk = sig.get("risk", abs(entry - sl))
            qty = _calc_quantity(capital, entry, risk)

            if qty <= 0:
                continue

            rr_val = sig.get("reward", abs(target - entry)) / max(risk, 0.01)

            working_df = day_data[sym]
            if intraday:
                scan_ts = pd.Timestamp(scan_time)
                if scan_ts.tzinfo is None:
                    scan_ts = scan_ts.tz_localize(IST)
                entry_idx = len(working_df[working_df.index <= scan_ts]) - 1
                if entry_idx < 0:
                    continue
                result = _sim_trade_intraday(working_df, entry_idx, entry, sl, target, signal_type)
            else:
                entry_idx = len(working_df) - 1
                result = _sim_trade_daily(working_df, entry_idx, entry, sl, target, signal_type)

            pnl_total = round(result["pnl_per_share"] * qty, 2)
            cap_used = round(qty * entry, 2)

            trade = {
                "symbol": sym,
                "signal_type": signal_type,
                "scan_time": scan_label,
                "entry_price": entry,
                "stop_loss": round(sl, 2),
                "target": round(target, 2),
                "risk_reward": f"1:{rr_val:.1f}",
                "qty": qty,
                "capital_used": cap_used,
                "outcome": result["outcome"],
                "exit_price": result["exit_price"],
                "exit_time": result["exit_time"],
                "candles_held": result["candles_held"],
                "pnl_per_share": result["pnl_per_share"],
                "total_pnl": pnl_total,
            }
            all_trades.append(trade)
            open_positions.add(sym)
            trades_this_scan += 1

        scan_log.append({"time": scan_label, "signals": len(signals), "trades": trades_this_scan})

    # Summary
    total_pnl = sum(t["total_pnl"] for t in all_trades)
    wins = [t for t in all_trades if t["total_pnl"] > 0]
    losses = [t for t in all_trades if t["total_pnl"] < 0]
    gross_win = sum(t["total_pnl"] for t in wins) if wins else 0
    gross_loss = sum(t["total_pnl"] for t in losses) if losses else 0
    profit_factor = round(abs(gross_win / gross_loss), 2) if gross_loss != 0 else 0

    return {
        "strategy": strategy_key,
        "strategy_name": info["name"],
        "timeframe": timeframe,
        "date": target_date.strftime("%Y-%m-%d"),
        "date_display": target_date.strftime("%A, %d %B %Y"),
        "mode": "Intraday" if intraday else "Daily",
        "capital": capital,
        "stocks_fetched": len(day_data),
        "fetch_time": fetch_time,
        "total_signals": total_signals,
        "scan_windows": len(scan_times),
        "scan_log": scan_log,
        "trades": all_trades,
        "summary": {
            "total_trades": len(all_trades),
            "winners": len(wins),
            "losers": len(losses),
            "breakeven": len(all_trades) - len(wins) - len(losses),
            "win_rate": round(len(wins) / len(all_trades) * 100, 1) if all_trades else 0,
            "total_pnl": round(total_pnl, 2),
            "roi": round(total_pnl / capital * 100, 2) if capital > 0 else 0,
            "gross_profit": round(gross_win, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": profit_factor,
            "avg_trade_pnl": round(total_pnl / len(all_trades), 2) if all_trades else 0,
            "total_capital_used": round(sum(t["capital_used"] for t in all_trades), 2),
        },
    }
