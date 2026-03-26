"""
Paper Trading Engine for IntraTrading.

Mirrors the Auto-Trader exactly but uses virtual positions instead of real Fyers orders.
Same rules: on-demand scan (initial + slot-open), max 10 positions, 2% risk, order cutoff 2 PM, square-off 3:15 PM.
"""

import threading
import logging
import time
from datetime import datetime
from typing import Optional

from services.scanner import run_scan, is_market_open, _calc_conviction
from services.market_data import get_nifty_trend
from services.trade_logger import log_trade, log_trades_batch
from services.fyers_client import get_quotes, is_authenticated
from utils.time_utils import now_ist, is_past_time, is_before_time
from utils.state_manager import get_state_path, save_state, load_state
from utils.trader_log import TraderLogger
from config import (
    INTRADAY_ORDER_START_HOUR, INTRADAY_ORDER_START_MIN,
    INTRADAY_ORDER_CUTOFF_HOUR, INTRADAY_ORDER_CUTOFF_MIN,
    INTRADAY_SQUAREOFF_HOUR, INTRADAY_SQUAREOFF_MIN,
    INTRADAY_PAPER_MAX_POSITIONS, INTRADAY_POSITION_CHECK_INTERVAL,
)

logger = logging.getLogger(__name__)

# Basic sector mapping for concentration limit
SECTOR_MAP = {
    'HDFCBANK': 'banking', 'ICICIBANK': 'banking', 'SBIN': 'banking', 'AXISBANK': 'banking',
    'KOTAKBANK': 'banking', 'BANKBARODA': 'banking', 'PNB': 'banking', 'INDUSINDBK': 'banking',
    'FEDERALBNK': 'banking', 'IDFCFIRSTB': 'banking', 'BANDHANBNK': 'banking', 'CANBK': 'banking',
    'TCS': 'it', 'INFY': 'it', 'WIPRO': 'it', 'HCLTECH': 'it', 'TECHM': 'it', 'LTIM': 'it',
    'RELIANCE': 'energy', 'ONGC': 'energy', 'IOC': 'energy', 'BPCL': 'energy', 'NTPC': 'energy',
    'POWERGRID': 'energy', 'ADANIGREEN': 'energy', 'ADANIPORTS': 'infra',
    'TATAMOTORS': 'auto', 'MARUTI': 'auto', 'BAJAJ-AUTO': 'auto', 'HEROMOTOCO': 'auto', 'M&M': 'auto',
    'HDFCLIFE': 'insurance', 'SBILIFE': 'insurance', 'ICICIPRULI': 'insurance',
    'BAJFINANCE': 'nbfc', 'BAJAJFINSV': 'nbfc', 'CHOLAFIN': 'nbfc', 'SHRIRAMFIN': 'nbfc',
}
MAX_PER_SECTOR = 2

STATE_FILE = get_state_path(".paper_trader_state.json")


def _is_past_order_cutoff() -> bool:
    return is_past_time(INTRADAY_ORDER_CUTOFF_HOUR, INTRADAY_ORDER_CUTOFF_MIN)


def _is_squareoff_time() -> bool:
    return is_past_time(INTRADAY_SQUAREOFF_HOUR, INTRADAY_SQUAREOFF_MIN)


class PaperTrader:
    """
    Virtual auto-trading engine.
    Same logic as AutoTrader but no real orders — tracks virtual positions
    and uses Fyers quotes for live LTP.
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._strategy_keys: list[str] = []
        self._timeframes: dict[str, str] = {}
        self._capital: float = 0.0

        self._active_trades: list[dict] = []
        self._trade_history: list[dict] = []
        self._total_pnl: float = 0.0
        self._daily_realized_pnl: float = 0.0
        self._daily_loss_limit_hit: bool = False
        self._scan_count: int = 0
        self._order_count: int = 0
        self._started_at: Optional[str] = None
        self._squared_off: bool = False
        self._next_scan_at: Optional[str] = None
        self._next_order_id: int = 1

        # Shared utilities
        self._logger = TraderLogger("PaperTrader")

        self._load_state()

    @property
    def is_running(self) -> bool:
        return self._running

    # ── State Persistence ──────────────────────────────────────────────────

    def _save_state(self):
        state = {
            "date": now_ist().strftime("%Y-%m-%d"),
            "running": self._running,
            "strategy_keys": self._strategy_keys,
            "timeframes": self._timeframes,
            "capital": self._capital,
            "active_trades": self._active_trades,
            "trade_history": self._trade_history,
            "total_pnl": self._total_pnl,
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "started_at": self._started_at,
            "squared_off": self._squared_off,
            "next_order_id": self._next_order_id,
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "PaperTrader")

    def _load_state(self):
        try:
            state = load_state(STATE_FILE, "PaperTrader")
            if not state:
                return

            today = now_ist().strftime("%Y-%m-%d")
            if state.get("date") != today:
                logger.info(f"[PaperTrader] State file is from {state.get('date')}, not today ({today}) — ignoring")
                return

            self._strategy_keys = state.get("strategy_keys", [])
            self._timeframes = state.get("timeframes", {})
            self._capital = state.get("capital", 0.0)
            self._active_trades = state.get("active_trades", [])
            self._trade_history = state.get("trade_history", [])
            self._total_pnl = state.get("total_pnl", 0.0)
            self._scan_count = state.get("scan_count", 0)
            self._order_count = state.get("order_count", 0)
            self._started_at = state.get("started_at")
            self._squared_off = state.get("squared_off", False)
            self._logger.entries = state.get("logs", [])
            self._next_order_id = state.get("next_order_id", 1)

            was_running = state.get("running", False)

            if self._strategy_keys:
                strat_names = ", ".join(f"{k}({self._timeframes.get(k, '')})" for k in self._strategy_keys)
                self._log("RESTORE", f"Restored today's state — {len(self._strategy_keys)} strategies: {strat_names} | "
                          f"Scans: {self._scan_count} | Orders: {self._order_count} | P&L: ₹{self._total_pnl:,.2f} | "
                          f"Trades: {len(self._trade_history)} completed, {len(self._active_trades)} active")

                if was_running and not self._squared_off and is_market_open() and not _is_past_order_cutoff():
                    self._log("RESTORE", "Paper trader was running before restart — auto-resuming...")
                    self._running = True
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif was_running and not self._squared_off and is_market_open():
                    self._log("RESTORE", "Paper trader was running but past order cutoff — monitoring positions only")
                    self._running = True
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif was_running:
                    self._log("RESTORE", "Paper trader was running but market is now closed — state preserved")

        except Exception as e:
            logger.warning(f"[PaperTrader] Failed to load state: {e}")

    # ── Controls ──────────────────────────────────────────────────────────

    def start(self, strategies: list[dict], capital: float) -> dict:
        with self._lock:
            if self._running:
                return {"error": "Paper trader is already running"}

            if not is_market_open():
                now = now_ist()
                if now.weekday() >= 5:
                    return {"error": "Market is closed (Weekend). Paper trading runs during market hours (Mon-Fri 9:15 AM - 3:30 PM IST)."}
                return {"error": "Market is closed. Paper trading runs during market hours (9:15 AM - 3:30 PM IST)."}

            if _is_past_order_cutoff():
                return {"error": "Cannot start after 2:00 PM IST. No new virtual orders after 2:00 PM."}

            if not strategies:
                return {"error": "At least one strategy must be selected."}

            self._strategy_keys = []
            self._timeframes = {}
            for s in strategies:
                key = s.get("strategy", "")
                tf = s.get("timeframe", "")
                if key and tf:
                    self._strategy_keys.append(key)
                    self._timeframes[key] = tf

            if not self._strategy_keys:
                return {"error": "No valid strategies provided."}

            self._capital = capital
            self._running = True
            self._active_trades = []
            self._trade_history = []
            self._logger.clear()
            self._total_pnl = 0.0
            self._scan_count = 0
            self._order_count = 0
            self._squared_off = False
            self._started_at = now_ist().isoformat()
            self._next_scan_at = None
            self._next_order_id = 1

            strat_names = ", ".join(f"{k}({self._timeframes[k]})" for k in self._strategy_keys)
            self._log("START", f"Paper trader STARTED — {len(self._strategy_keys)} strateg{'y' if len(self._strategy_keys) == 1 else 'ies'}: {strat_names} | Capital=₹{capital:,.0f}")
            self._log("INFO", f"Virtual trading — NO real orders | Order cutoff: 2:00 PM | Square-off: 3:15 PM | Max positions: {INTRADAY_PAPER_MAX_POSITIONS}")

            self._save_state()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

            return {
                "status": "started",
                "strategies": [{"strategy": k, "timeframe": self._timeframes[k]} for k in self._strategy_keys],
                "capital": capital,
                "started_at": self._started_at,
            }

    def stop(self) -> dict:
        with self._lock:
            if not self._running:
                return {"status": "already_stopped", "message": "Paper trader is not running"}

            self._running = False
            self._log("STOP", "Paper trader STOPPED by user")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._save_state()

        return {
            "status": "stopped",
            "total_scans": self._scan_count,
            "total_orders": self._order_count,
            "total_pnl": round(self._total_pnl, 2),
        }

    def status(self) -> dict:
        return {
            "is_running": self._running,
            "strategies": [{"strategy": k, "timeframe": self._timeframes.get(k, "")} for k in self._strategy_keys],
            "capital": self._capital,
            "started_at": self._started_at,
            "next_scan_at": self._next_scan_at,
            "scan_mode": "on-demand",
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "total_pnl": round(self._total_pnl, 2),
            "active_trades": self._active_trades,
            "trade_history": self._trade_history[-20:],
            "squared_off": self._squared_off,
            "order_cutoff_passed": _is_past_order_cutoff(),
            "logs": self._logger.recent(100),
        }

    # ── Main Loop ─────────────────────────────────────────────────────────

    def _run_loop(self):
        """Background loop: scan-on-demand, monitor positions, square off.

        Strategy:
          1. Run ONE full scan immediately to fill all slots.
          2. Monitor positions every 60s.  When a position closes and a slot
             opens up (before 2:00 PM cutoff), trigger an immediate scan.
          3. After 2:00 PM — monitor only, no new scans.
          4. At 3:15 PM — square off everything.
        """
        self._log("INFO", "Background thread started")
        self._log("INFO", "Scan mode: ON-DEMAND — scan at 10:30 AM, then re-scan only when a slot opens")

        # ── Wait for 10:30 AM order window ──
        while self._running and is_before_time(INTRADAY_ORDER_START_HOUR, INTRADAY_ORDER_START_MIN):
            self._log("INFO", "Waiting for 10:30 AM order window...")
            for _ in range(60):
                if not self._running or not is_before_time(INTRADAY_ORDER_START_HOUR, INTRADAY_ORDER_START_MIN):
                    break
                time.sleep(1)

        # ── Initial full scan ──
        if not _is_past_order_cutoff() and is_market_open() and self._running:
            self._log("SCAN", "10:30 AM — initial scan to fill all slots")
            self._execute_scan_cycle()
        elif not is_market_open():
            self._log("INFO", "Market closed — stopping paper trader")
            self._running = False
            self._log("INFO", "Background thread exited")
            self._save_state()
            return

        # ── Monitor loop — check positions every 60s, scan on slot open ──
        prev_open_count = len(self._active_trades)
        self._next_scan_at = None  # no scheduled scan — on-demand only
        _monitor_tick = 0  # counter for periodic health checks

        while self._running:
            # Square-off check
            if _is_squareoff_time() and not self._squared_off:
                self._log("ALERT", "3:15 PM IST reached — initiating virtual square-off")
                self._square_off_all()
                self._squared_off = True
                self._log("STOP", "Paper trader stopping after square-off")
                self._running = False
                break

            # Sleep 60s in 1-second ticks for responsiveness
            for _ in range(INTRADAY_POSITION_CHECK_INTERVAL):
                if not self._running:
                    break
                time.sleep(1)
                if _is_squareoff_time() and not self._squared_off:
                    break

            if not self._running:
                break
            if _is_squareoff_time() and not self._squared_off:
                continue  # will hit square-off at top of loop

            # ── Monitor positions: detect SL/target hits, update P&L ──
            self._update_position_pnl()
            _monitor_tick += 1

            # Fyers health check every ~5 minutes (every 5th tick at 60s intervals)
            if _monitor_tick % 5 == 0:
                try:
                    if not is_authenticated():
                        self._log("WARN", "Fyers disconnected — using delayed yfinance data. Reconnect via UI.")
                except Exception:
                    pass

            current_open_count = len(self._active_trades)

            # Did a slot open up?
            if current_open_count < prev_open_count:
                slots_freed = prev_open_count - current_open_count
                self._log("INFO", f"{slots_freed} position(s) closed — {current_open_count}/{INTRADAY_PAPER_MAX_POSITIONS} slots used")

                # Scan to refill if before cutoff and slots available
                if current_open_count < INTRADAY_PAPER_MAX_POSITIONS and not _is_past_order_cutoff():
                    if is_market_open():
                        self._log("SCAN", f"Slot available — triggering scan to fill {INTRADAY_PAPER_MAX_POSITIONS - current_open_count} open slot(s)")
                        self._execute_scan_cycle()
                        current_open_count = len(self._active_trades)
                elif _is_past_order_cutoff():
                    self._log("INFO", "Past 2:00 PM — no new virtual orders. Monitoring until square-off.")

            # Periodic re-scan: if slots available, re-scan every 15 min to fill them
            elif current_open_count < INTRADAY_PAPER_MAX_POSITIONS and not _is_past_order_cutoff() and is_market_open():
                if _monitor_tick > 0 and _monitor_tick % 45 == 0:  # ~15 min at 20s intervals
                    slots = INTRADAY_PAPER_MAX_POSITIONS - current_open_count
                    self._log("SCAN", f"{slots} slots open — periodic re-scan")
                    self._execute_scan_cycle()
                    current_open_count = len(self._active_trades)

            prev_open_count = current_open_count

        self._log("INFO", "Background thread exited")
        self._save_state()

    def _check_daily_loss_limit(self) -> bool:
        if self._daily_loss_limit_hit:
            return True
        if self._capital <= 0:
            return False
        loss_pct = abs(self._daily_realized_pnl) / self._capital * 100
        if self._daily_realized_pnl < 0 and loss_pct >= 5.0:
            self._daily_loss_limit_hit = True
            self._log("ALERT", f"DAILY LOSS LIMIT HIT: ₹{self._daily_realized_pnl:,.2f} ({loss_pct:.1f}%). No new orders.")
            return True
        return False

    def _check_drawdown_breaker(self) -> bool:
        """Check if multi-day drawdown exceeds 15% of capital. Returns True if breaker triggered."""
        try:
            from services.trade_logger import get_all_trades
            recent = get_all_trades(days=5)
            # Portfolio-level: check ALL paper sources combined
            paper_trades = [t for t in recent if "paper" in t.get("source", "")]
            if len(paper_trades) >= 5:
                pnl = sum(t.get("pnl", 0) for t in paper_trades)
                if pnl < -self._capital * 0.15:
                    return True
        except Exception:
            pass
        return False

    def _execute_scan_cycle(self):
        # Re-detect regime on each scan cycle (strategies adapt to intraday shifts)
        try:
            from services.equity_regime import detect_equity_regime
            new_regime = detect_equity_regime()
            new_strategies = new_regime.get("strategies", [])
            if new_strategies:
                new_keys = [s["strategy"] for s in new_strategies]
                new_tfs = {s["strategy"]: s["timeframe"] for s in new_strategies}
                if set(new_keys) != set(self._strategy_keys):
                    old_names = ", ".join(self._strategy_keys)
                    new_names = ", ".join(new_keys)
                    self._log("REGIME", f"Regime shifted → {new_regime.get('regime', '?')} | Strategies: {old_names} → {new_names}")
                    self._strategy_keys = new_keys
                    self._timeframes = new_tfs
                # Always update timeframes even if keys haven't changed (VIX may have changed timeframe)
                self._timeframes = new_tfs
        except Exception as e:
            pass  # Regime detection failed, keep current strategies

        # Multi-day drawdown breaker
        if self._check_drawdown_breaker():
            self._log("ALERT", "5-day drawdown > 15% — reducing to 1 order per scan (safety mode)")

        if self._check_daily_loss_limit():
            self._log("INFO", "Daily loss limit active — monitoring only")
            self._update_position_pnl()
            return

        self._scan_count += 1
        num_strategies = len(self._strategy_keys)
        self._log("SCAN", f"Scan #{self._scan_count} starting — {num_strategies} strateg{'y' if num_strategies == 1 else 'ies'}...")

        open_count = len(self._active_trades)

        if open_count >= INTRADAY_PAPER_MAX_POSITIONS:
            self._log("INFO", f"Max positions reached ({open_count}/{INTRADAY_PAPER_MAX_POSITIONS}) — skipping order placement")
            self._update_position_pnl()
            return

        slots_available = INTRADAY_PAPER_MAX_POSITIONS - open_count

        # VIX check — skip 5m strategies in high VIX
        try:
            import yfinance as yf
            vix_data = yf.Ticker("^INDIAVIX").history(period="5d", interval="1d")
            vix = float(vix_data["Close"].iloc[-1]) if vix_data is not None and len(vix_data) > 0 else 15
        except Exception:
            vix = 15

        if vix > 18:
            self._log("FILTER", f"VIX={vix:.1f} (elevated) — skipping 5m strategies, using 15m only")

        all_signals = []
        total_scanned = 0
        total_time = 0
        strategy_idx = 0  # Track regime priority position

        for strategy_key in self._strategy_keys:
            timeframe = self._timeframes.get(strategy_key, "15m")

            # Skip 5m in high VIX
            if vix > 18 and timeframe == "5m":
                from config import STRATEGY_TIMEFRAMES
                available_tfs = STRATEGY_TIMEFRAMES.get(strategy_key, [])
                if "15m" in available_tfs:
                    timeframe = "15m"
                    self._log("FILTER", f"  {strategy_key}: 5m → 15m (VIX={vix:.1f})")
                else:
                    self._log("FILTER", f"  {strategy_key}: skipped (5m only, no 15m)")
                    continue

            # High VIX → half position size (trade with less capital, reduce risk)
            scan_capital = self._capital * 0.5 if vix > 20 else self._capital
            scan_result = run_scan(strategy_key, timeframe, scan_capital)

            if "error" in scan_result:
                self._log("WARN", f"Scan error for {strategy_key}: {scan_result['error']}")
                continue

            signals = scan_result.get("signals", [])
            scanned = scan_result.get("stocks_scanned", 0)
            scan_time = scan_result.get("scan_time_seconds", 0)
            total_scanned = max(total_scanned, scanned)
            total_time += scan_time

            for sig in signals:
                sig["_strategy"] = strategy_key
                sig["_timeframe"] = timeframe
                sig["_regime_position"] = strategy_idx  # Position in regime priority list

            all_signals.extend(signals)
            self._log("SCAN", f"  {strategy_key}({timeframe}): {len(signals)} signals ({scan_time}s)")
            strategy_idx += 1

        # Deduplicate by symbol — keep highest conviction signal per symbol
        # Regime-aware: strategies listed first in regime map get a priority boost
        seen_symbols = {}
        for sig in all_signals:
            sym = sig.get("symbol", "")
            conv = _calc_conviction(sig)
            # Regime priority boost: #1 strategy gets 1.3x, #2 gets 1.15x, #3 gets 1.05x
            regime_pos = sig.get("_regime_position", 99)
            if regime_pos == 0:
                conv *= 1.5   # Primary strategy for this regime — STRONGEST boost
            elif regime_pos == 1:
                conv *= 1.2   # Secondary
            elif regime_pos == 2:
                conv *= 1.05  # Tertiary
            if sym not in seen_symbols or conv > seen_symbols[sym][1]:
                seen_symbols[sym] = (sig, conv)

        unique_signals = [s[0] for s in sorted(seen_symbols.values(), key=lambda x: x[1], reverse=True)]

        self._log("SCAN", f"Scan #{self._scan_count} complete — ~{total_scanned} stocks, {len(unique_signals)} unique signals ({total_time:.1f}s total)")
        self._save_state()

        if not unique_signals:
            return

        # ── Nifty Trend Filter ──
        # Check Nifty 50 direction to avoid trading against the market
        # Contra/mean-reversion strategies are EXEMPT — they trade against the trend by design
        CONTRA_STRATEGIES = {"play6_bb_contra", "play8_rsi_divergence"}

        nifty_trend = get_nifty_trend("5m")
        trend_signals = [s for s in unique_signals if s.get("strategy") not in CONTRA_STRATEGIES]
        contra_signals = [s for s in unique_signals if s.get("strategy") in CONTRA_STRATEGIES]

        buy_count = sum(1 for s in trend_signals if s.get("signal_type") == "BUY")
        sell_count = sum(1 for s in trend_signals if s.get("signal_type") == "SELL")
        contra_count = len(contra_signals)

        if nifty_trend == "BEARISH":
            trend_signals = [s for s in trend_signals if s.get("signal_type") == "SELL"]
            self._log("FILTER", f"Nifty BEARISH — trend: blocked {buy_count} BUY, kept {sell_count} SELL | contra: {contra_count} exempt")
        elif nifty_trend == "BULLISH":
            trend_signals = [s for s in trend_signals if s.get("signal_type") == "BUY"]
            self._log("FILTER", f"Nifty BULLISH — trend: kept {buy_count} BUY, blocked {sell_count} SELL | contra: {contra_count} exempt")
        else:
            self._log("FILTER", f"Nifty {nifty_trend} — allowing all ({buy_count} BUY, {sell_count} SELL, {contra_count} contra)")

        unique_signals = trend_signals + contra_signals

        if not unique_signals:
            self._log("FILTER", "No signals remaining after Nifty trend filter")
            return

        # ── Strategy diversity: interleave signals from different strategies ──
        from collections import OrderedDict
        by_strategy = OrderedDict()
        for s in unique_signals:
            strat = s.get("strategy", s.get("_strategy", "unknown"))
            if strat not in by_strategy:
                by_strategy[strat] = []
            by_strategy[strat].append(s)

        diversified = []
        max_rounds = max((len(v) for v in by_strategy.values()), default=0)
        for round_idx in range(max_rounds):
            for strat, signals in by_strategy.items():
                if round_idx < len(signals):
                    diversified.append(signals[round_idx])

        if len(by_strategy) > 1:
            strat_summary = ", ".join(f"{k}:{len(v)}" for k, v in by_strategy.items())
            self._log("FILTER", f"Strategy diversity: {strat_summary} — interleaved {len(diversified)} signals")

        unique_signals = diversified

        # First scan of day: allow 3 orders (morning has best signals)
        if self._scan_count <= 1:
            max_orders_per_scan = min(3, slots_available) if not self._check_drawdown_breaker() else 1
        else:
            max_orders_per_scan = 1 if self._check_drawdown_breaker() else min(2, slots_available)
        orders_placed = 0

        # Track strategy count per scan to cap concentration
        strategy_count_this_scan = {}
        max_per_strategy = max(2, slots_available // max(len(by_strategy), 1))

        for signal in unique_signals:
            if orders_placed >= max_orders_per_scan:
                self._log("INFO", f"Max 2 orders per scan — remaining slots will fill on next scan")
                break

            if _is_past_order_cutoff():
                self._log("INFO", "2:00 PM cutoff reached during order placement — stopping")
                break

            symbol = signal.get("symbol", "")
            sig_strategy = signal.get("strategy", signal.get("_strategy", "unknown"))

            # Strategy concentration limit
            existing_for_strategy = sum(1 for t in self._active_trades if t.get("strategy") == sig_strategy)
            scan_for_strategy = strategy_count_this_scan.get(sig_strategy, 0)
            if existing_for_strategy + scan_for_strategy >= max_per_strategy:
                self._log("FILTER", f"{symbol} — skipping, {sig_strategy} already has {existing_for_strategy + scan_for_strategy} positions (max {max_per_strategy})")
                continue

            active_symbols = {t["symbol"] for t in self._active_trades}
            if symbol in active_symbols:
                self._log("SKIP", f"{symbol} — already in virtual position")
                continue

            # Sector concentration check
            sym_sector = SECTOR_MAP.get(signal.get("symbol", ""), "other")
            sector_count = sum(1 for t in self._active_trades if SECTOR_MAP.get(t.get("symbol", ""), "other") == sym_sector)
            if sector_count >= MAX_PER_SECTOR and sym_sector != "other":
                self._log("FILTER", f"Sector limit: {signal['symbol']} ({sym_sector}) — already {sector_count} trades in sector")
                continue

            # Loss streak protection: track consecutive losses
            recent_trades = self._trade_history[-3:] if len(self._trade_history) >= 2 else []
            consecutive_losses = 0
            for t in reversed(recent_trades):
                if t.get("pnl", 0) < 0:
                    consecutive_losses += 1
                else:
                    break
            if consecutive_losses >= 2:
                self._log("FILTER", f"Loss streak: {consecutive_losses} consecutive losses — caution (VIX half-sizing active if applicable)")

            success = self._place_virtual_order(signal)
            if success:
                orders_placed += 1
                strategy_count_this_scan[sig_strategy] = strategy_count_this_scan.get(sig_strategy, 0) + 1

        self._update_position_pnl()

    def _place_virtual_order(self, signal: dict) -> bool:
        symbol = signal.get("symbol", "")
        signal_type = signal.get("signal_type", "")
        entry_price = signal.get("entry_price", 0)
        stop_loss = signal.get("stop_loss", 0)
        target = signal.get("target_1", 0)
        qty = signal.get("quantity", 0)
        rr = signal.get("risk_reward_ratio", "")

        if not all([symbol, signal_type, entry_price, stop_loss, target, qty]):
            self._log("WARN", f"{symbol} — incomplete signal data, skipping")
            return False

        side = 1 if signal_type == "BUY" else -1

        # Simulate realistic slippage (0.1% worse entry — matches live market orders)
        slippage = entry_price * 0.001
        if side == 1:  # BUY: fill slightly higher
            entry_price = round(entry_price + slippage, 2)
        else:  # SELL: fill slightly lower
            entry_price = round(entry_price - slippage, 2)

        # Realistic Fyers brokerage + STT + other charges
        capital_req = qty * entry_price
        turnover = qty * entry_price
        brokerage_per_leg = min(20, turnover * 0.0003)  # ₹20 or 0.03% (whichever lower)
        brokerage = round(brokerage_per_leg * 2, 2)  # Entry + Exit = 2 legs
        stt = round(turnover * 0.00025, 2)  # STT: 0.025% on sell side
        exchange_charges = round(turnover * 0.0003, 2)  # NSE transaction + SEBI + stamp
        est_brokerage = round(brokerage + stt + exchange_charges, 2)

        order_id = f"PAPER-{self._next_order_id:04d}"
        self._next_order_id += 1

        self._log("ORDER", f"Virtual {signal_type}: {symbol} | Qty={qty} | Entry=₹{entry_price} | SL=₹{stop_loss} | Target=₹{target} | R:R={rr} | Capital=₹{capital_req:,.0f}")

        trade = {
            "symbol": symbol,
            "signal_type": signal_type,
            "side": side,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target": target,
            "quantity": qty,
            "order_id": order_id,
            "risk_reward_ratio": rr,
            "capital_required": capital_req,
            "strategy": signal.get("_strategy", ""),
            "timeframe": signal.get("_timeframe", ""),
            "placed_at": now_ist().isoformat(),
            "status": "OPEN",
            "pnl": 0.0,
            "ltp": entry_price,
            "est_brokerage": est_brokerage,
            "original_sl": stop_loss,
            "max_favorable_price": entry_price,
        }

        self._active_trades.append(trade)
        self._order_count += 1
        self._save_state()
        return True

    # ── Square Off ────────────────────────────────────────────────────────

    def _square_off_all(self):
        if not self._active_trades:
            self._log("INFO", "No virtual positions to square off")
            self._save_state()
            return

        self._log("ALERT", f"Squaring off {len(self._active_trades)} virtual position(s)")

        # Get latest LTP for all open positions
        symbols = list({t["symbol"] for t in self._active_trades})
        ltp_map = self._fetch_ltp(symbols)

        for trade in self._active_trades:
            symbol = trade["symbol"]
            ltp = ltp_map.get(symbol, trade.get("ltp", trade["entry_price"]))
            side = trade["side"]

            if side == 1:
                pnl = (ltp - trade["entry_price"]) * trade["quantity"]
            else:
                pnl = (trade["entry_price"] - ltp) * trade["quantity"]

            pnl = round(pnl, 2)
            brokerage = trade.get("est_brokerage", 0)
            net_pnl = round(pnl - brokerage, 2)
            trade["pnl"] = net_pnl
            trade["gross_pnl"] = pnl
            trade["charges"] = brokerage
            trade["ltp"] = ltp
            trade["status"] = "CLOSED"
            trade["closed_at"] = now_ist().isoformat()
            trade["exit_price"] = ltp
            trade["exit_reason"] = "SQUARE_OFF"

            self._total_pnl += net_pnl; self._daily_realized_pnl += net_pnl
            self._trade_history.append(trade)
            log_trade(trade, source="paper")

            self._log("SQUAREOFF", f"{symbol} — closed at ₹{ltp} | Gross: ₹{pnl:,.2f} | Charges: ₹{brokerage} | Net P&L: ₹{net_pnl:,.2f}")

        self._active_trades = []
        self._log("ALERT", f"Virtual square-off complete. Total P&L: ₹{self._total_pnl:,.2f}")
        self._save_state()

        # End-of-day pipeline: daily report + auto-tune + QA (runs once per day)
        try:
            from services.auto_tuner import run_eod_pipeline
            eod = run_eod_pipeline("equity_paper")
            if eod.get("status") == "completed":
                r = eod.get("report", {})
                t = eod.get("tune_result", {})
                actions = t.get("actions", [])
                self._log("TRACKER", f"EOD report: {r.get('total_trades', 0)} trades, ₹{r.get('total_net_pnl', 0):,.0f} P&L")
                if actions:
                    self._log("TUNER", f"Auto-tuned {len(actions)} parameter(s): {', '.join(a.get('parameter','?') for a in actions)}")
                else:
                    self._log("TUNER", "No parameter changes needed")
        except Exception as e:
            logger.warning(f"[PaperTrader] EOD pipeline failed: {e}")

    # ── Position Monitoring ───────────────────────────────────────────────

    def _update_position_pnl(self):
        if not self._active_trades:
            return

        symbols = list({t["symbol"] for t in self._active_trades})
        ltp_map = self._fetch_ltp(symbols)

        trades_to_close = []

        for trade in self._active_trades:
            symbol = trade["symbol"]
            ltp = ltp_map.get(symbol, trade.get("ltp", trade["entry_price"]))
            side = trade["side"]
            entry = trade["entry_price"]

            if side == 1:
                pnl = (ltp - entry) * trade["quantity"]
            else:
                pnl = (entry - ltp) * trade["quantity"]

            trade["pnl"] = round(pnl, 2)
            trade["ltp"] = ltp

            # ── Trailing stop loss — lock in profits on winning trades ──
            # Store original SL on first monitoring pass (for trades loaded from state)
            if "original_sl" not in trade:
                trade["original_sl"] = trade["stop_loss"]

            if side == 1:  # BUY
                max_fav = max(trade.get("max_favorable_price", entry), ltp)
                trade["max_favorable_price"] = max_fav
                profit_pct = (max_fav - entry) / entry * 100 if entry > 0 else 0
                if profit_pct >= 1.0:  # Only trail after 1% profit
                    # Trail at 50% of max profit
                    trail_sl = round(entry + (max_fav - entry) * 0.5, 2)
                    if trail_sl > trade["stop_loss"]:
                        old_sl = trade["stop_loss"]
                        trade["stop_loss"] = trail_sl
                        self._log("TRAIL", f"{symbol} — SL trailed ₹{old_sl} → ₹{trail_sl} (max ₹{max_fav}, +{profit_pct:.1f}%)")
            else:  # SELL
                max_fav = min(trade.get("max_favorable_price", entry), ltp)
                trade["max_favorable_price"] = max_fav
                profit_pct = (entry - max_fav) / entry * 100 if entry > 0 else 0
                if profit_pct >= 1.0:  # Only trail after 1% profit
                    trail_sl = round(entry - (entry - max_fav) * 0.5, 2)
                    if trail_sl < trade["stop_loss"]:
                        old_sl = trade["stop_loss"]
                        trade["stop_loss"] = trail_sl
                        self._log("TRAIL", f"{symbol} — SL trailed ₹{old_sl} → ₹{trail_sl} (max ₹{max_fav}, +{profit_pct:.1f}%)")

            # Check SL hit
            if side == 1 and ltp <= trade["stop_loss"]:
                trade["exit_reason"] = "SL_HIT"
                trades_to_close.append(trade)
            elif side == -1 and ltp >= trade["stop_loss"]:
                trade["exit_reason"] = "SL_HIT"
                trades_to_close.append(trade)
            # Check target hit
            elif side == 1 and ltp >= trade["target"]:
                trade["exit_reason"] = "TARGET_HIT"
                trades_to_close.append(trade)
            elif side == -1 and ltp <= trade["target"]:
                trade["exit_reason"] = "TARGET_HIT"
                trades_to_close.append(trade)

        for trade in trades_to_close:
            symbol = trade["symbol"]
            reason = trade["exit_reason"]
            gross_pnl = trade["pnl"]
            brokerage = trade.get("est_brokerage", 0)
            net_pnl = round(gross_pnl - brokerage, 2)

            trade["pnl"] = net_pnl
            trade["gross_pnl"] = gross_pnl
            trade["charges"] = brokerage
            trade["status"] = "CLOSED"
            trade["closed_at"] = now_ist().isoformat()
            trade["exit_price"] = trade["ltp"]
            self._total_pnl += net_pnl; self._daily_realized_pnl += net_pnl
            self._trade_history.append(trade)
            log_trade(trade, source="paper")

            if reason == "SL_HIT":
                self._log("ORDER", f"{symbol} — SL HIT at ₹{trade['ltp']} | Net P&L: ₹{net_pnl:,.2f} (charges: ₹{brokerage})")
            else:
                self._log("ORDER", f"{symbol} — TARGET HIT at ₹{trade['ltp']} | Net P&L: ₹{net_pnl:,.2f} (charges: ₹{brokerage})")

        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()

    def _fetch_ltp(self, symbols: list[str]) -> dict[str, float]:
        """Get latest LTP from Fyers quotes API."""
        ltp_map = {}
        if not symbols:
            return ltp_map
        try:
            if not is_authenticated():
                return ltp_map
            res = get_quotes(symbols)
            quotes = res.get("d", [])
            if not quotes and isinstance(res.get("data"), dict):
                quotes = res["data"].get("d", [])
            for q in quotes:
                sym = (q.get("n", "") or q.get("symbol", "")).replace("NSE:", "").replace("-EQ", "")
                lp = 0
                v = q.get("v", {})
                if isinstance(v, dict):
                    lp = v.get("lp", 0) or v.get("close_price", 0)
                if sym and lp:
                    ltp_map[sym] = lp
        except Exception as e:
            logger.warning(f"[PaperTrader] Failed to fetch LTP: {e}")
        return ltp_map

    # ── Logging ───────────────────────────────────────────────────────────

    def _log(self, level: str, message: str):
        self._logger.log(level, message)


# ── Singleton Instance ────────────────────────────────────────────────────

paper_trader = PaperTrader()
