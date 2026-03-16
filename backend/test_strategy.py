"""
Strategy Backtest — Simulates a full trading day for ANY strategy.

Usage:
  python test_strategy.py <strategy_key> [timeframe] [capital]

Examples:
  python test_strategy.py play3_vwap_pullback 5m 100000
  python test_strategy.py play1_ema_crossover 15m 200000
  python test_strategy.py play4_supertrend 5m
  python test_strategy.py play5_bb_squeeze 15m

Available strategies:
  play1_ema_crossover   — EMA-EMA Crossover (15m, 1h, 1d)
  play2_triple_ma       — Triple MA Trend Filter (15m, 1h, 1d)
  play3_vwap_pullback   — VWAP Trend-Pullback (3m, 5m)
  play4_supertrend      — Supertrend Power Trend (5m, 15m)
  play5_bb_squeeze      — BB Squeeze Breakout (15m, 30m, 1d)
  play6_bb_contra       — BB Mean Reversion (5m, 15m, 1d)
"""

import sys, os, warnings, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Suppress noisy yfinance/urllib3 output
warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("peewee").setLevel(logging.CRITICAL)

import time
import math
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf

from nifty500 import get_nifty500_symbols, get_yfinance_symbol
from strategies import STRATEGY_MAP
from config import STRATEGY_TIMEFRAMES, INTERVAL_PERIOD_MAP

IST = timezone(timedelta(hours=5, minutes=30))

RISK_PCT = 0.02
MAX_POSITIONS = 3

# ── Helpers ────────────────────────────────────────────────────────────────

def calc_quantity(capital, entry, risk_per_share):
    risk_amount = capital * RISK_PCT
    if risk_per_share <= 0:
        return 0
    qty = math.floor(risk_amount / risk_per_share)
    max_qty = math.floor(capital / entry) if entry > 0 else 0
    return min(qty, max_qty)


def find_last_trading_day(use_today=False):
    """Find the most recent completed weekday (Mon-Fri)."""
    now = datetime.now(IST)
    if use_today and now.weekday() < 5:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def is_intraday_timeframe(tf):
    return tf in {"3m", "5m", "15m", "30m", "1h"}


def fetch_data(symbol, interval, period):
    """Fetch data from yfinance."""
    yf_sym = get_yfinance_symbol(symbol)
    try:
        ticker = yf.Ticker(yf_sym)
        df = ticker.history(period=period, interval=interval)
        if df is None or df.empty:
            return None
        required = ["Open", "High", "Low", "Close", "Volume"]
        for col in required:
            if col not in df.columns:
                return None
        df = df[required].copy()
        df.dropna(inplace=True)
        return df if len(df) >= 5 else None
    except Exception:
        return None


def filter_to_date(df, target_date):
    """Filter DataFrame to only candles from target_date (for intraday)."""
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    # Convert to IST for consistent comparison
    try:
        df.index = df.index.tz_convert(IST)
    except Exception:
        pass  # already in a compatible timezone
    mask = df.index.date == target_date.date()
    day_df = df[mask].copy()
    return day_df if len(day_df) >= 5 else None


def simulate_trade_intraday(day_df, entry_idx, entry_price, stop_loss, target, signal_type):
    """Simulate intraday trade: walk forward from entry candle."""
    future = day_df.iloc[entry_idx + 1:]
    is_buy = signal_type == "BUY"

    for i, (_, candle) in enumerate(future.iterrows()):
        if is_buy:
            if candle["Low"] <= stop_loss:
                return _result("SL_HIT", stop_loss, entry_price, is_buy, i + 1, candle)
            if candle["High"] >= target:
                return _result("TARGET_HIT", target, entry_price, is_buy, i + 1, candle)
        else:  # SELL
            if candle["High"] >= stop_loss:
                return _result("SL_HIT", stop_loss, entry_price, is_buy, i + 1, candle)
            if candle["Low"] <= target:
                return _result("TARGET_HIT", target, entry_price, is_buy, i + 1, candle)

    # EOD square-off
    last_price = future.iloc[-1]["Close"] if len(future) > 0 else entry_price
    pnl = (last_price - entry_price) if is_buy else (entry_price - last_price)
    return {
        "outcome": "EOD_SQUAREOFF",
        "exit_price": round(last_price, 2),
        "pnl_per_share": round(pnl, 2),
        "candles_held": len(future),
        "exit_time": future.iloc[-1].name.strftime("%H:%M") if len(future) > 0 else "15:15",
    }


def simulate_trade_daily(df, entry_idx, entry_price, stop_loss, target, signal_type, hold_days=5):
    """Simulate daily trade: walk forward up to hold_days."""
    future = df.iloc[entry_idx + 1: entry_idx + 1 + hold_days]
    is_buy = signal_type == "BUY"

    for i, (_, candle) in enumerate(future.iterrows()):
        if is_buy:
            if candle["Low"] <= stop_loss:
                return _result("SL_HIT", stop_loss, entry_price, is_buy, i + 1, candle)
            if candle["High"] >= target:
                return _result("TARGET_HIT", target, entry_price, is_buy, i + 1, candle)
        else:
            if candle["High"] >= stop_loss:
                return _result("SL_HIT", stop_loss, entry_price, is_buy, i + 1, candle)
            if candle["Low"] <= target:
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


# ── Main Backtest ──────────────────────────────────────────────────────────

def run_backtest(strategy_key, timeframe, capital, use_today=False):
    if strategy_key not in STRATEGY_MAP:
        print(f"\n  ERROR: Unknown strategy '{strategy_key}'")
        print(f"  Available: {', '.join(STRATEGY_MAP.keys())}")
        sys.exit(1)

    valid_tfs = STRATEGY_TIMEFRAMES.get(strategy_key, [])
    if timeframe not in valid_tfs:
        print(f"\n  ERROR: Invalid timeframe '{timeframe}' for {strategy_key}")
        print(f"  Valid timeframes: {valid_tfs}")
        sys.exit(1)

    strategy = STRATEGY_MAP[strategy_key]
    info = strategy.info()
    intraday = is_intraday_timeframe(timeframe)
    target_date = find_last_trading_day(use_today=use_today)
    period = INTERVAL_PERIOD_MAP.get(timeframe, "30d")

    print("=" * 80)
    print(f"  STRATEGY BACKTEST — {info['name']}")
    print(f"  Strategy  : {strategy_key}")
    print(f"  Date      : {target_date.strftime('%A, %d %B %Y')}")
    print(f"  Timeframe : {timeframe} ({'Intraday' if intraday else 'Daily'})")
    print(f"  Capital   : ₹{capital:,} | Risk: {RISK_PCT*100}% per trade | Max Positions: {MAX_POSITIONS}")
    print(f"  Indicators: {', '.join(info['indicators'])}")
    print("=" * 80)

    # Scan windows
    if intraday:
        scan_times = []
        t = target_date.replace(hour=9, minute=30, second=0)
        cutoff = target_date.replace(hour=14, minute=0, second=0)
        while t < cutoff:
            scan_times.append(t)
            t += timedelta(minutes=15)
        print(f"\n  Scan windows: {len(scan_times)} (9:30 AM → 1:45 PM, every 15 min)")
        print(f"  Order cutoff: 2:00 PM | Square-off: 3:15 PM")
    else:
        scan_times = [target_date]  # single scan for daily
        print(f"\n  Mode: End-of-day scan (daily candles)")
    print()

    # Step 1: Fetch data
    symbols = get_nifty500_symbols()
    print(f"  Fetching {timeframe} data for {len(symbols)} Nifty 500 stocks...")
    start_fetch = time.time()

    all_data = {}   # symbol -> full DataFrame
    day_data = {}   # symbol -> filtered day data (intraday only)

    def fetch_one(sym):
        df = fetch_data(sym, timeframe, period)
        if df is None:
            return sym, None, None
        if intraday:
            day_df = filter_to_date(df, target_date)
            return sym, df, day_df
        else:
            return sym, df, df

    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(fetch_one, s): s for s in symbols}
        done = 0
        for future in as_completed(futures):
            done += 1
            if done % 50 == 0:
                print(f"    ... fetched {done}/{len(symbols)}")
            sym, full_df, working_df = future.result()
            if full_df is not None and working_df is not None:
                all_data[sym] = full_df
                day_data[sym] = working_df

    fetch_time = time.time() - start_fetch
    print(f"  Data fetched: {len(day_data)} stocks with valid data ({fetch_time:.1f}s)")
    print()

    if not day_data:
        print("  No data available for this date. Possible reasons:")
        print("    - Market was closed (holiday)")
        print("    - Data not yet available from yfinance")
        return

    # Step 2: Replay scans
    all_trades = []
    open_positions = set()
    total_signals_found = 0

    for scan_time in scan_times:
        if intraday:
            scan_label = scan_time.strftime("%H:%M")
        else:
            scan_label = scan_time.strftime("%Y-%m-%d")

        # Free up positions that have closed before this scan
        if intraday:
            current_ts = scan_time.replace(tzinfo=IST) if scan_time.tzinfo is None else scan_time
            for t in all_trades:
                if t["symbol"] in open_positions and t["outcome"] in ("SL_HIT", "TARGET_HIT"):
                    exit_time_str = t["exit_time"]
                    try:
                        exit_dt = target_date.replace(
                            hour=int(exit_time_str.split(":")[0]),
                            minute=int(exit_time_str.split(":")[1]),
                            second=0, tzinfo=IST
                        )
                        if exit_dt <= current_ts:
                            open_positions.discard(t["symbol"])
                    except Exception:
                        pass

        print(f"  ┌─ SCAN @ {scan_label} {'─' * (60 - len(scan_label))}")

        if len(open_positions) >= MAX_POSITIONS:
            print(f"  │  Max positions ({MAX_POSITIONS}) reached — skipping")
            print(f"  └{'─' * 70}")
            print()
            continue

        slots = MAX_POSITIONS - len(open_positions)
        signals = []

        for sym in day_data:
            if sym in open_positions:
                continue

            # Use full multi-day history for scanning (indicators need history)
            # but simulate trades only on today's candles
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

        total_signals_found += len(signals)

        if not signals:
            print(f"  │  No signals found")
            print(f"  └{'─' * 70}")
            print()
            continue

        signals.sort(key=lambda s: s.get("reward", 0) / max(s.get("risk", 1), 0.01), reverse=True)
        print(f"  │  {len(signals)} signal(s) found:")

        orders_placed = 0
        for sig in signals:
            if orders_placed >= slots:
                break

            sym = sig["symbol"]
            if sym in open_positions:
                continue

            entry = sig["entry_price"]
            sl = sig["stop_loss"]
            target = sig.get("target_1", sig.get("target", entry))
            risk = sig.get("risk", abs(entry - sl))
            signal_type = sig.get("signal_type", "BUY")
            qty = calc_quantity(capital, entry, risk)

            if qty <= 0:
                continue

            rr_val = sig.get("reward", abs(target - entry)) / max(risk, 0.01)
            rr = f"1:{rr_val:.1f}"

            working_df = day_data[sym]
            if intraday:
                scan_ts = pd.Timestamp(scan_time)
                if scan_ts.tzinfo is None:
                    scan_ts = scan_ts.tz_localize(IST)
                entry_idx = len(working_df[working_df.index <= scan_ts]) - 1
                if entry_idx < 0:
                    continue
                result = simulate_trade_intraday(working_df, entry_idx, entry, sl, target, signal_type)
            else:
                # For daily, find the index of the signal candle
                entry_idx = len(working_df) - 1
                result = simulate_trade_daily(working_df, entry_idx, entry, sl, target, signal_type)

            pnl_total = result["pnl_per_share"] * qty
            cap_used = qty * entry

            trade = {
                "symbol": sym,
                "signal_type": signal_type,
                "scan_time": scan_label,
                "entry_price": entry,
                "stop_loss": sl,
                "target": target,
                "risk_reward": rr,
                "qty": qty,
                "capital_used": round(cap_used, 2),
                **result,
                "total_pnl": round(pnl_total, 2),
            }
            all_trades.append(trade)
            open_positions.add(sym)
            orders_placed += 1

            icon = "+" if result["outcome"] == "TARGET_HIT" else "-" if result["outcome"] == "SL_HIT" else "~"
            print(f"  │  {icon} {signal_type:>4s} {sym:>12s} | Entry ₹{entry:>8.2f} | SL ₹{sl:>8.2f} | Tgt ₹{target:>8.2f} | Qty {qty:>3} | {rr:>5s} | Exit ₹{result['exit_price']:>8.2f} ({result['exit_time']}) | P&L ₹{pnl_total:>+9.2f}")

        remaining = len(signals) - orders_placed
        if remaining > 0:
            print(f"  │  ... {remaining} more signal(s) not traded (max positions)")

        print(f"  └{'─' * 70}")
        print()

    # ── Summary ──
    print()
    print("=" * 80)
    print(f"  BACKTEST RESULTS — {info['name']} ({timeframe})")
    print("=" * 80)

    if not all_trades:
        print(f"\n  No trades were executed on {target_date.strftime('%d %b %Y')}.")
        print(f"  Total signals found across all scans: {total_signals_found}")
        if total_signals_found == 0:
            print(f"\n  Possible reasons:")
            print(f"    - No stocks matched the {info['name']} pattern on this day")
            print(f"    - Market conditions didn't suit this strategy")
            print(f"    - Insufficient candle history for indicators")
        print()
        return

    total_pnl = sum(t["total_pnl"] for t in all_trades)
    wins = [t for t in all_trades if t["total_pnl"] > 0]
    losses = [t for t in all_trades if t["total_pnl"] < 0]
    even = [t for t in all_trades if t["total_pnl"] == 0]

    print(f"\n  Trades Executed : {len(all_trades)}")
    print(f"  Signals Found   : {total_signals_found}")
    print(f"  Winners         : {len(wins)}")
    print(f"  Losers          : {len(losses)}")
    print(f"  Breakeven       : {len(even)}")
    print(f"  Win Rate        : {len(wins)/len(all_trades)*100:.0f}%")
    print()

    hdr = f"  {'Symbol':<12s} {'Type':>4s} {'Scan':>8s} {'Entry':>9s} {'SL':>9s} {'Target':>9s} {'Exit':>9s} {'Outcome':<14s} {'Qty':>4s} {'P&L':>11s}"
    print(f"  {'─' * (len(hdr) - 2)}")
    print(hdr)
    print(f"  {'─' * (len(hdr) - 2)}")
    for t in all_trades:
        outcome_str = t['outcome'].replace('_', ' ')
        pnl_str = f"₹{t['total_pnl']:>+,.2f}"
        print(f"  {t['symbol']:<12s} {t['signal_type']:>4s} {t['scan_time']:>8s} {t['entry_price']:>9.2f} {t['stop_loss']:>9.2f} {t['target']:>9.2f} {t['exit_price']:>9.2f} {outcome_str:<14s} {t['qty']:>4d} {pnl_str:>11s}")
    print(f"  {'─' * (len(hdr) - 2)}")

    total_capital_used = sum(t["capital_used"] for t in all_trades)
    roi = (total_pnl / capital * 100) if capital > 0 else 0
    gross_win = sum(t["total_pnl"] for t in wins) if wins else 0
    gross_loss = sum(t["total_pnl"] for t in losses) if losses else 0

    print(f"\n  Total P&L       : ₹{total_pnl:>+,.2f}")
    print(f"  ROI on Capital  : {roi:>+.2f}%")
    print(f"  Gross Profit    : ₹{gross_win:>+,.2f}")
    print(f"  Gross Loss      : ₹{gross_loss:>+,.2f}")
    print(f"  Capital Used    : ₹{total_capital_used:>,.2f} (of ₹{capital:,})")
    print(f"  Avg Trade P&L   : ₹{total_pnl/len(all_trades):>+,.2f}")
    if losses and gross_loss != 0:
        print(f"  Profit Factor   : {abs(gross_win/gross_loss):.2f}")
    print()


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("  Available strategies:")
        for key, strat in STRATEGY_MAP.items():
            tfs = STRATEGY_TIMEFRAMES.get(key, [])
            print(f"    {key:<25s} — {strat.name} ({', '.join(tfs)})")
        print()
        sys.exit(0)

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_today = "--today" in sys.argv

    strat_key = args[0]
    tf = args[1] if len(args) > 1 else STRATEGY_TIMEFRAMES.get(strat_key, ["15m"])[0]
    cap = float(args[2]) if len(args) > 2 else 100000

    run_backtest(strat_key, tf, cap, use_today=use_today)
