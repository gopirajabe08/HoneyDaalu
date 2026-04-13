"""
BTST (Buy Today Sell Tomorrow) Trading Engine for LuckyNavi.

Key differences from intraday auto-trader:
  - Product type: CNC (delivery), not INTRADAY
  - Positions carry overnight (cross-day state persistence)
  - Entry window: 2:00 PM - 3:15 PM (scan and buy)
  - No intraday square-off — positions carry overnight
  - Next-day exit logic: profit target, loss limit, max hold days
  - Max 2 positions (conservative for overnight risk)
  - SL/Target orders re-placed each morning (DAY validity expires)

Key differences from swing trader:
  - Shorter hold period (1-2 days vs weeks)
  - Percentage-based exit rules instead of fixed SL/target from signal
  - Automatic next-day exit evaluation
"""

import threading
import logging
import time
import traceback
from datetime import datetime, timedelta
from typing import Optional
from collections import OrderedDict

from services.scanner import run_scan, is_market_open, _calc_conviction
from services.market_data import get_nifty_trend
from services.trade_logger import log_trade
from services.broker_client import (
    place_order,
    cancel_order,
    get_positions,
    get_holdings,
    get_quotes,
    get_orderbook,
    get_funds,
    is_authenticated,
)
from config import (
    BTST_ORDER_START_HOUR, BTST_ORDER_START_MIN,
    BTST_ORDER_CUTOFF_HOUR, BTST_ORDER_CUTOFF_MIN,
    BTST_POSITION_CHECK_INTERVAL,
    BTST_CAPITAL_PER_POSITION, BTST_MIN_POSITIONS, BTST_MAX_POSITIONS,
    BTST_EXIT_PROFIT_TARGET_PCT, BTST_EXIT_LOSS_LIMIT_PCT, BTST_MAX_HOLD_DAYS,
    BTST_STRATEGY_TIMEFRAMES,
)
from utils.time_utils import now_ist, is_before_time, is_past_time
from utils.state_manager import get_state_path, save_state, load_state
from utils.trader_log import TraderLogger
from utils.sleep_manager import SleepManager
from services import telegram_notify

logger = logging.getLogger(__name__)

# Basic sector mapping for concentration limit (parity with auto_trader)
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

STATE_FILE = get_state_path(".btst_trader_state.json")

CONTRA_STRATEGIES = {"play6_bb_contra", "play8_rsi_divergence"}


def _is_before_order_start() -> bool:
    """True if current time is before 10:30 AM IST."""
    return is_before_time(BTST_ORDER_START_HOUR, BTST_ORDER_START_MIN)


def _is_past_order_cutoff() -> bool:
    """True if current time is past 2:00 PM IST — no new orders."""
    return is_past_time(BTST_ORDER_CUTOFF_HOUR, BTST_ORDER_CUTOFF_MIN)


class BTSTTrader:
    """
    Live BTST trading engine.

    Places CNC orders via broker. Positions carry overnight.
    Entry window: 2:00 PM - 3:15 PM. Max 2 positions.
    Next-day exit: profit target (+2%), loss limit (-1.5%), max hold (2 days).
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Auto-calculated from capital at start
        self.max_open_positions: int = BTST_MIN_POSITIONS

        # Configuration
        self._strategy_keys: list[str] = []
        self._timeframes: dict[str, str] = {}
        self._capital: float = 0.0

        # State tracking
        self._active_trades: list[dict] = []
        self._trade_history: list[dict] = []
        self._total_pnl: float = 0.0
        self._scan_count: int = 0
        self._order_count: int = 0
        self._started_at: Optional[str] = None
        self._next_scan_at: Optional[str] = None

        # Shared utilities
        self._logger = TraderLogger("BTSTTrader")
        self._sleep_mgr = SleepManager("BTSTTrader")

        # Restore state from disk (cross-day persistence)
        self._load_state()

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Sleep Prevention ──────────────────────────────────────────────────

    def _prevent_sleep(self):
        """Prevent Mac from sleeping — delegates to SleepManager."""
        self._sleep_mgr.prevent_sleep()

    def _allow_sleep(self):
        """Re-enable Mac sleep — delegates to SleepManager."""
        self._sleep_mgr.allow_sleep()

    # ── State Persistence (cross-day — no date filter) ────────────────────

    def _save_state(self):
        """Persist BTST state to disk. Cross-day — positions carry overnight."""
        state = {
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
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "BTSTTrader")

    def _load_state(self):
        """Restore BTST state from disk. No date filter — positions carry overnight."""
        try:
            state = load_state(STATE_FILE, "BTSTTrader")
            if not state:
                return

            # No date filter — BTST positions carry over days
            self._strategy_keys = state.get("strategy_keys", [])
            self._timeframes = state.get("timeframes", {})
            self._capital = state.get("capital", 0.0)
            self._active_trades = state.get("active_trades", [])
            self._trade_history = state.get("trade_history", [])
            self._total_pnl = state.get("total_pnl", 0.0)
            self._scan_count = state.get("scan_count", 0)
            self._order_count = state.get("order_count", 0)
            self._started_at = state.get("started_at")
            self._logger.entries = state.get("logs", [])

            # Recalculate max positions from restored capital
            if self._capital > 0:
                self.max_open_positions = max(
                    BTST_MIN_POSITIONS,
                    min(int(self._capital // BTST_CAPITAL_PER_POSITION), BTST_MAX_POSITIONS)
                )

            was_running = state.get("running", False)

            if self._strategy_keys:
                strat_names = ", ".join(f"{k}({self._timeframes.get(k, '')})" for k in self._strategy_keys)
                self._log("RESTORE", f"Restored BTST state — {strat_names} | "
                          f"Active: {len(self._active_trades)} | P&L: ₹{self._total_pnl:,.2f}")

                if was_running and is_market_open():
                    self._log("RESTORE", "BTST trader was running — auto-resuming...")
                    self._recover_orphaned_positions()
                    self._running = True
                    self._prevent_sleep()
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif was_running:
                    self._log("RESTORE", "BTST trader was running but market closed — will resume when market opens")

        except Exception as e:
            logger.warning(f"[BTSTTrader] Failed to load state: {e}")

    def _recover_orphaned_positions(self):
        """Detect broker CNC positions not tracked in active_trades.
        Adds them as monitored entries so they're visible and counted."""
        try:
            open_symbols, positions = self._get_open_positions_detail()
            tracked_symbols = {t["symbol"] for t in self._active_trades}

            for pos in positions:
                broker_sym = pos.get("symbol", "")
                plain = broker_sym.replace("NSE:", "").replace("-EQ", "")
                qty = pos.get("netQty", pos.get("qty", 0))

                if plain in tracked_symbols or qty == 0:
                    continue

                buy_avg = pos.get("buyAvg", 0)
                sell_avg = pos.get("sellAvg", 0)
                side = 1 if qty > 0 else -1
                entry_price = buy_avg if side == 1 else sell_avg
                ltp = pos.get("ltp", entry_price)
                pnl = pos.get("pl", pos.get("unrealized_profit", 0))

                # Calculate fallback SL (1.5% from entry)
                if side == 1:
                    recovered_sl = round(entry_price * (1 - BTST_EXIT_LOSS_LIMIT_PCT / 100), 2)
                else:
                    recovered_sl = round(entry_price * (1 + BTST_EXIT_LOSS_LIMIT_PCT / 100), 2)

                trade = {
                    "symbol": plain,
                    "signal_type": "BUY" if side == 1 else "SELL",
                    "side": side,
                    "entry_price": round(entry_price, 2),
                    "stop_loss": recovered_sl,
                    "target": round(entry_price * (1 + BTST_EXIT_PROFIT_TARGET_PCT / 100), 2) if side == 1 else round(entry_price * (1 - BTST_EXIT_PROFIT_TARGET_PCT / 100), 2),
                    "quantity": abs(qty),
                    "order_id": "recovered",
                    "sl_order_id": "",
                    "strategy": "unknown",
                    "timeframe": "",
                    "placed_at": now_ist().isoformat(),  # Approximate — actual entry date unknown
                    "status": "OPEN",
                    "pnl": round(pnl, 2),
                    "ltp": ltp,
                    "recovered": True,
                }
                self._active_trades.append(trade)
                self._log("WARN", f"Recovered orphaned BTST position: {plain} {'LONG' if side==1 else 'SHORT'} x{abs(qty)} @ ₹{entry_price:.2f} | SL=₹{recovered_sl} | P&L ₹{pnl:.2f}")

            if any(t.get("recovered") for t in self._active_trades):
                self._save_state()

        except Exception as e:
            self._log("WARN", f"BTST position recovery failed: {e}")

    # ── Controls ──────────────────────────────────────────────────────────

    def start(self, strategies: list[dict], capital: float) -> dict:
        """Start BTST trading with one or more strategies."""
        with self._lock:
            if self._running:
                return {"error": "BTST trader is already running"}

            if not is_market_open():
                now = now_ist()
                if now.weekday() >= 5:
                    return {"error": "Market is closed (Weekend). BTST trading starts during market hours."}
                return {"error": "Market is closed. BTST trading starts during market hours (9:15 AM - 3:30 PM IST)."}

            if not is_authenticated():
                return {"error": "Broker is not authenticated. Please login first."}

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
            if capital > 0:
                self.max_open_positions = max(
                    BTST_MIN_POSITIONS,
                    min(int(capital // BTST_CAPITAL_PER_POSITION), BTST_MAX_POSITIONS)
                )
            else:
                # Capital=0 means dynamic allocation at scan time from broker funds
                self.max_open_positions = BTST_MAX_POSITIONS
            self._running = True
            self._active_trades = []
            self._trade_history = []
            self._logger.clear()
            self._total_pnl = 0.0
            self._scan_count = 0
            self._order_count = 0
            self._started_at = now_ist().isoformat()
            self._next_scan_at = None

            strat_names = ", ".join(f"{k}({self._timeframes[k]})" for k in self._strategy_keys)
            self._log("START", f"BTST trader STARTED — {strat_names} | Capital=₹{capital:,.0f} | Max positions: {self.max_open_positions}")
            self._log("INFO", f"BTST MODE — CNC orders | Entry 2:00 PM - 3:15 PM | Positions carry overnight")
            self._log("INFO", f"Exit rules: +{BTST_EXIT_PROFIT_TARGET_PCT}% profit | -{BTST_EXIT_LOSS_LIMIT_PCT}% loss | Max {BTST_MAX_HOLD_DAYS} days hold")

            self._prevent_sleep()
            if self._sleep_mgr.mode == "pmset":
                self._log("INFO", "Sleep prevention ENABLED — Mac will stay awake even with lid closed")
            elif self._sleep_mgr.mode == "caffeinate":
                self._log("WARN", "Sleep prevention (caffeinate only) — keep lid OPEN!")
            else:
                self._log("WARN", "Sleep prevention FAILED — Mac may sleep if idle or lid closed")

            self._recover_orphaned_positions()
            self._save_state()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

            return {
                "status": "started",
                "mode": "btst",
                "strategies": [{"strategy": k, "timeframe": self._timeframes[k]} for k in self._strategy_keys],
                "capital": capital,
                "max_positions": self.max_open_positions,
                "started_at": self._started_at,
            }

    def stop(self) -> dict:
        """Stop BTST trading. Positions remain open (carry overnight)."""
        with self._lock:
            if not self._running:
                return {"status": "already_stopped", "message": "BTST trader is not running"}

            self._running = False
            self._log("STOP", "BTST trader STOPPED by user (positions remain open)")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._allow_sleep()
        self._save_state()

        return {
            "status": "stopped",
            "total_scans": self._scan_count,
            "total_orders": self._order_count,
            "total_pnl": round(self._total_pnl, 2),
            "active_positions": len(self._active_trades),
        }

    def status(self) -> dict:
        """Return current BTST trader state."""
        return {
            "is_running": self._running,
            "mode": "btst",
            "strategies": [{"strategy": k, "timeframe": self._timeframes.get(k, "")} for k in self._strategy_keys],
            "capital": self._capital,
            "max_positions": self.max_open_positions,
            "started_at": self._started_at,
            "next_scan_at": self._next_scan_at,
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "total_pnl": round(self._total_pnl, 2),
            "active_trades": self._active_trades,
            "trade_history": self._trade_history[-20:],
            "logs": self._logger.recent(100),
        }

    def trigger_scan(self) -> dict:
        """Trigger an immediate scan (on-demand)."""
        if not self._running:
            return {"error": "BTST trader is not running"}
        if not self._strategy_keys:
            return {"error": "No strategies configured"}
        self._log("SCAN", "Manual scan triggered by user")
        self._execute_scan_cycle()
        return {
            "status": "scan_complete",
            "scan_count": self._scan_count,
            "active_trades": len(self._active_trades),
        }

    # ── Main Loop ─────────────────────────────────────────────────────────

    def _run_loop(self):
        """Background loop: wait for entry window, scan, monitor, check exits.

        Strategy:
          1. On market open each morning: check exit rules for overnight positions
          2. Wait for 10:30 AM, then scan to fill open slots
          3. Monitor positions every 60s. Re-scan on slot open (before 2 PM cutoff)
          4. After 2:00 PM — monitor only, no new scans
          5. No square-off — positions carry overnight
        """
        self._log("INFO", "Background thread started")
        self._log("INFO", f"BTST mode: entry 2:00 PM - 3:15 PM | No intraday square-off | Positions carry overnight")

        while self._running:
            if not is_market_open():
                self._log("INFO", "Market closed — waiting for next open (BTST positions preserved)")
                while self._running and not is_market_open():
                    time.sleep(60)
                if not self._running:
                    break
                self._log("INFO", "Market opened — checking BTST exit rules for overnight positions")

            # ── Morning: check exit rules for overnight positions ──
            if self._active_trades:
                self._check_exit_rules()

            # ── Wait for 10:30 AM entry window ──
            while self._running and _is_before_order_start():
                now = now_ist()
                order_start = now.replace(hour=BTST_ORDER_START_HOUR, minute=BTST_ORDER_START_MIN, second=0, microsecond=0)
                mins_left = max(0, int((order_start - now).total_seconds() / 60))
                if mins_left % 15 == 0 and mins_left > 0:
                    self._log("INFO", f"Waiting for 2:00 PM BTST entry window — {mins_left} min left")
                time.sleep(60)

            if not self._running:
                break

            # ── Entry window scan ──
            if not _is_past_order_cutoff() and is_market_open():
                if not is_authenticated():
                    self._log("ERROR", "Broker authentication lost — cannot scan")
                else:
                    # Dynamic capital: fetch available funds from broker at scan time
                    # This allows equity intraday to use full capital during the day
                    # BTST uses whatever is free at 2:00 PM
                    if self._capital <= 0:
                        try:
                            funds = get_funds()
                            fund_list = funds.get("fund_limit", [])
                            for f in fund_list:
                                if f.get("id") == 10:
                                    avail = f.get("equityAmount", 0)
                                    # After equity cutoff (1:30 PM), free capital won't be used by equity
                                    # Take available minus ₹10K buffer, capped at ₹50K
                                    self._capital = min(max(int(avail - 10000), 0), 50000)
                                    self.max_open_positions = max(
                                        BTST_MIN_POSITIONS,
                                        min(int(self._capital // BTST_CAPITAL_PER_POSITION), BTST_MAX_POSITIONS)
                                    )
                                    self._log("INFO", f"BTST capital from broker: ₹{self._capital:,.0f} available | {self.max_open_positions} position(s)")
                                    break
                        except Exception as e:
                            self._log("WARN", f"Failed to fetch funds for BTST: {e}")

                    open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])
                    if open_count < self.max_open_positions and self._capital >= BTST_CAPITAL_PER_POSITION:
                        self._log("SCAN", "Entry window — executing scan to fill slots")
                        self._execute_scan_cycle()

            # ── Monitor loop: check positions every 60s, scan on slot open ──
            prev_open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])
            _monitor_tick = 0

            while self._running and is_market_open():
                # Sleep in 1-second ticks
                for _ in range(BTST_POSITION_CHECK_INTERVAL):
                    if not self._running:
                        break
                    time.sleep(1)

                if not self._running or not is_market_open():
                    break

                _monitor_tick += 1

                # Update P&L for active positions
                self._update_position_pnl()

                # Check exit rules every ~5 minutes
                if _monitor_tick % 5 == 0 and self._active_trades:
                    self._check_exit_rules()

                # Broker health check every ~5 minutes
                if _monitor_tick % 5 == 0:
                    try:
                        if not is_authenticated():
                            self._log("WARN", "Broker disconnected — attempting reconnect...")
                            from services.broker_client import headless_login
                            result = headless_login()
                            if "error" in result:
                                self._log("ALERT", f"Broker reconnect FAILED: {result['error']}")
                            else:
                                self._log("INFO", "Broker reconnected successfully")
                    except Exception:
                        pass

                # SL health check every ~5 minutes
                if _monitor_tick % 5 == 0:
                    self._check_sl_order_health()

                current_open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])

                # Slot opened up — scan to refill if before cutoff
                if current_open_count < prev_open_count:
                    slots_freed = prev_open_count - current_open_count
                    self._log("INFO", f"{slots_freed} BTST position(s) closed — {current_open_count}/{self.max_open_positions} slots used")

                    if current_open_count < self.max_open_positions and not _is_past_order_cutoff():
                        if is_authenticated():
                            self._log("SCAN", f"Slot available — triggering scan to fill")
                            self._execute_scan_cycle()
                            current_open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])
                    elif _is_past_order_cutoff():
                        self._log("INFO", "Past 2:00 PM — no new BTST orders. Monitoring until close.")

                # Periodic re-scan every ~15 min if slots available
                elif current_open_count < self.max_open_positions and not _is_past_order_cutoff():
                    if _monitor_tick > 0 and _monitor_tick % 15 == 0:
                        slots = self.max_open_positions - current_open_count
                        self._log("SCAN", f"{slots} BTST slots open — periodic re-scan")
                        self._execute_scan_cycle()
                        current_open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])

                prev_open_count = current_open_count

            # Market closed — save state and wait
            self._save_state()
            if self._running:
                self._log("INFO", "Market closed — BTST positions preserved overnight. Waiting for next session.")

        self._log("INFO", "Background thread exited")
        self._save_state()

    # ── Scan & Order Placement ────────────────────────────────────────────

    def _execute_scan_cycle(self):
        """Run one scan across all selected strategies: find signals and place CNC orders."""
        self._scan_count += 1
        num_strategies = len(self._strategy_keys)
        self._log("SCAN", f"BTST scan #{self._scan_count} — {num_strategies} strateg{'y' if num_strategies == 1 else 'ies'}...")

        # Check open positions
        internal_open = [t for t in self._active_trades if t["status"] == "OPEN"]
        open_symbols_broker, _ = self._get_open_positions_detail()
        open_symbols = {t["symbol"] for t in internal_open} | open_symbols_broker
        open_count = len(internal_open)

        if open_count >= self.max_open_positions:
            self._log("INFO", f"Max BTST positions reached ({open_count}/{self.max_open_positions}) — skipping")
            self._update_position_pnl()
            return

        slots_available = self.max_open_positions - open_count

        # Collect signals from all strategies
        all_signals = []
        total_scanned = 0
        total_time = 0
        strategy_idx = 0

        for strategy_key in self._strategy_keys:
            timeframe = self._timeframes.get(strategy_key, "1d")

            scan_result = run_scan(strategy_key, timeframe, self._capital, mode="swing")

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
                sig["_regime_position"] = strategy_idx

            all_signals.extend(signals)
            self._log("SCAN", f"  {strategy_key}({timeframe}): {len(signals)} signals ({scan_time}s)")
            strategy_idx += 1

        # Deduplicate by symbol — keep highest conviction signal per symbol
        seen_symbols = {}
        for sig in all_signals:
            sym = sig.get("symbol", "")
            conv = _calc_conviction(sig)
            regime_pos = sig.get("_regime_position", 99)
            if regime_pos == 0:
                conv *= 1.5
            elif regime_pos == 1:
                conv *= 1.2
            elif regime_pos == 2:
                conv *= 1.05
            if sym not in seen_symbols or conv > seen_symbols[sym][1]:
                seen_symbols[sym] = (sig, conv)

        unique_signals = [s[0] for s in sorted(seen_symbols.values(), key=lambda x: x[1], reverse=True)]

        self._log("SCAN", f"BTST scan #{self._scan_count} complete — ~{total_scanned} stocks, {len(unique_signals)} unique signals ({total_time:.1f}s)")
        self._save_state()

        if not unique_signals:
            return

        # ── Nifty Trend Filter (with contra exemption) ──
        nifty_trend = get_nifty_trend("5m")
        trend_signals = [s for s in unique_signals if s.get("strategy") not in CONTRA_STRATEGIES]
        contra_signals = [s for s in unique_signals if s.get("strategy") in CONTRA_STRATEGIES]

        buy_count = sum(1 for s in trend_signals if s.get("signal_type") == "BUY")
        sell_count = sum(1 for s in trend_signals if s.get("signal_type") == "SELL")
        contra_count = len(contra_signals)

        if nifty_trend == "BEARISH":
            trend_signals = [s for s in trend_signals if s.get("signal_type") == "SELL"]
            self._log("FILTER", f"Nifty BEARISH — blocked {buy_count} BUY, kept {sell_count} SELL | contra: {contra_count} exempt")
        elif nifty_trend == "BULLISH":
            trend_signals = [s for s in trend_signals if s.get("signal_type") == "BUY"]
            self._log("FILTER", f"Nifty BULLISH — kept {buy_count} BUY, blocked {sell_count} SELL | contra: {contra_count} exempt")
        else:
            self._log("FILTER", f"Nifty {nifty_trend} — allowing all ({buy_count} BUY, {sell_count} SELL, {contra_count} contra)")

        unique_signals = trend_signals + contra_signals

        if not unique_signals:
            self._log("FILTER", "No signals remaining after Nifty trend filter")
            return

        # ── Strategy diversity: interleave signals from different strategies ──
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

        # Place orders
        max_orders_per_scan = min(2, slots_available)
        orders_placed = 0
        strategy_count_this_scan = {}
        max_per_strategy = max(1, slots_available // max(len(by_strategy), 1))

        for signal in unique_signals:
            if orders_placed >= max_orders_per_scan:
                break

            if _is_past_order_cutoff():
                self._log("INFO", "2:00 PM cutoff reached — stopping order placement")
                break

            symbol = signal.get("symbol", "")
            sig_strategy = signal.get("strategy", signal.get("_strategy", "unknown"))

            # Strategy concentration limit
            existing_for_strategy = sum(1 for t in self._active_trades if t.get("strategy") == sig_strategy)
            scan_for_strategy = strategy_count_this_scan.get(sig_strategy, 0)
            if existing_for_strategy + scan_for_strategy >= max_per_strategy:
                self._log("FILTER", f"{symbol} — skipping, {sig_strategy} already at limit")
                continue

            # Sector concentration check
            sym_sector = SECTOR_MAP.get(symbol, "other")
            sector_count = sum(1 for t in self._active_trades if SECTOR_MAP.get(t.get("symbol", ""), "other") == sym_sector)
            if sector_count >= MAX_PER_SECTOR and sym_sector != "other":
                self._log("FILTER", f"Sector limit: {symbol} ({sym_sector}) — already {sector_count} trades in sector")
                continue

            # Skip if already in position
            if symbol in open_symbols:
                self._log("SKIP", f"{symbol} — already in position")
                continue

            active_symbols = {t["symbol"] for t in self._active_trades}
            if symbol in active_symbols:
                self._log("SKIP", f"{symbol} — already tracked in active trades")
                continue

            signal["_placed_via"] = signal.get("_strategy", "")
            success = self._place_order_for_signal(signal)
            if success:
                orders_placed += 1
                open_symbols.add(symbol)
                strategy_count_this_scan[sig_strategy] = strategy_count_this_scan.get(sig_strategy, 0) + 1

        self._update_position_pnl()

    def _place_order_for_signal(self, signal: dict) -> bool:
        """Place a CNC market entry order + CNC SL-M order for BTST."""
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
        capital_req = qty * entry_price

        # Override SL/target with BTST percentage-based rules
        if side == 1:
            btst_sl = round(entry_price * (1 - BTST_EXIT_LOSS_LIMIT_PCT / 100), 2)
            btst_target = round(entry_price * (1 + BTST_EXIT_PROFIT_TARGET_PCT / 100), 2)
        else:
            btst_sl = round(entry_price * (1 + BTST_EXIT_LOSS_LIMIT_PCT / 100), 2)
            btst_target = round(entry_price * (1 - BTST_EXIT_PROFIT_TARGET_PCT / 100), 2)

        # Use tighter of signal SL vs BTST SL
        if side == 1:
            stop_loss = max(stop_loss, btst_sl) if stop_loss > 0 else btst_sl
        else:
            stop_loss = min(stop_loss, btst_sl) if stop_loss > 0 else btst_sl

        self._log("ORDER", f"Placing BTST {signal_type}: {symbol} | Qty={qty} | Entry=₹{entry_price} | SL=₹{stop_loss} | Target=₹{btst_target} | R:R={rr} | Capital=₹{capital_req:,.0f}")

        # Price validation: skip if LTP has moved >0.5% from signal entry
        try:
            quotes_res = get_quotes([symbol])
            if "d" in quotes_res and quotes_res["d"]:
                current_ltp = quotes_res["d"][0].get("v", {}).get("lp", 0)
                if current_ltp > 0 and entry_price > 0:
                    price_diff_pct = abs(current_ltp - entry_price) / entry_price
                    if price_diff_pct > 0.005:
                        self._log("SKIP", f"{symbol} — Price moved too far: LTP=₹{current_ltp:.2f} vs Entry=₹{entry_price:.2f} ({price_diff_pct*100:.2f}% drift)")
                        return False
        except Exception as e:
            self._log("WARN", f"{symbol} — LTP check failed ({e}), proceeding with order")

        try:
            # CNC market entry order
            result = place_order(
                symbol=symbol,
                qty=qty,
                side=side,
                order_type=2,  # Market
                product_type="CNC",
            )

            if "error" in result:
                self._log("ERROR", f"{symbol} — CNC entry FAILED: {result['error']}")
                return False

            entry_order_id = result.get("id", result.get("order_id", "unknown"))
            if entry_order_id == "unknown" or not entry_order_id:
                self._log("ERROR", f"{symbol} — order returned no ID, likely rejected. Skipping.")
                return False

            self._log("ORDER", f"{symbol} — CNC entry PLACED (ID: {entry_order_id})")

            # Wait for entry to settle, then verify
            time.sleep(3)
            order_status = self._get_order_status(entry_order_id)
            if order_status == "rejected":
                self._log("ERROR", f"{symbol} — order REJECTED by broker (ID: {entry_order_id}). NOT tracking.")
                return False
            elif order_status == "cancelled":
                self._log("WARN", f"{symbol} — order CANCELLED on broker (ID: {entry_order_id}). NOT tracking.")
                return False
            elif order_status == "filled":
                actual_price = self._get_fill_price(entry_order_id)
                if actual_price and actual_price > 0:
                    entry_price = actual_price
                    self._log("ORDER", f"{symbol} — FILLED at ₹{actual_price}")
                    # Recalculate SL/target with actual fill price
                    if side == 1:
                        stop_loss = round(entry_price * (1 - BTST_EXIT_LOSS_LIMIT_PCT / 100), 2)
                        btst_target = round(entry_price * (1 + BTST_EXIT_PROFIT_TARGET_PCT / 100), 2)
                    else:
                        stop_loss = round(entry_price * (1 + BTST_EXIT_LOSS_LIMIT_PCT / 100), 2)
                        btst_target = round(entry_price * (1 - BTST_EXIT_PROFIT_TARGET_PCT / 100), 2)

            # Place SL-M order (CNC, DAY validity — re-placed each morning)
            sl_side = -1 if side == 1 else 1
            sl_order_id = ""
            time.sleep(5)
            for attempt in range(5):
                sl_result = place_order(
                    symbol=symbol,
                    qty=qty,
                    side=sl_side,
                    order_type=4,  # SL-M
                    product_type="CNC",
                    stop_price=stop_loss,
                )
                if "error" not in sl_result:
                    sl_order_id = sl_result.get("id", sl_result.get("order_id", ""))
                    self._log("ORDER", f"{symbol} — CNC SL-M order PLACED (ID: {sl_order_id}) at ₹{stop_loss}")
                    break
                self._log("WARN", f"{symbol} — SL-M attempt {attempt+1}/5 failed: {sl_result.get('error', '')}")
                time.sleep(10 if attempt < 2 else 30)

            if not sl_order_id:
                self._log("ERROR", f"{symbol} — SL-M ORDER FAILED after 5 attempts! Closing position for safety.")
                # CRITICAL: Don't hold overnight without SL — exit immediately
                try:
                    exit_side = -1 if side == 1 else 1
                    exit_result = place_order(symbol=symbol, qty=qty, side=exit_side, order_type=2, product_type="CNC")
                    if "error" not in exit_result:
                        self._log("ORDER", f"{symbol} — Emergency CNC exit placed (SL failed, position too risky)")
                    else:
                        self._log("ERROR", f"{symbol} — Emergency exit ALSO FAILED: {exit_result.get('error')}. CLOSE MANUALLY!")
                except Exception as e:
                    self._log("ERROR", f"{symbol} — Emergency exit exception: {e}. CLOSE MANUALLY!")
                return False

            trade = {
                "symbol": symbol,
                "signal_type": signal_type,
                "side": side,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "target": btst_target,
                "quantity": qty,
                "order_id": entry_order_id,
                "sl_order_id": sl_order_id,
                "risk_reward_ratio": rr,
                "capital_required": capital_req,
                "strategy": signal.get("_placed_via", signal.get("_strategy", "")),
                "timeframe": signal.get("_timeframe", ""),
                "placed_at": now_ist().isoformat(),
                "status": "OPEN",
                "pnl": 0.0,
                "ltp": entry_price,
            }

            self._active_trades.append(trade)
            self._order_count += 1
            self._save_state()

            # Telegram: BTST position placed notification
            try:
                telegram_notify.btst_position(
                    symbol, entry_price, qty,
                    signal.get("_placed_via", signal.get("_strategy", ""))
                )
            except Exception:
                pass

            return True

        except Exception as e:
            self._log("ERROR", f"{symbol} — order EXCEPTION: {e}")
            self._log("ERROR", traceback.format_exc())
            return False

    # ── Exit Rules (BTST-specific) ────────────────────────────────────────

    def _check_exit_rules(self):
        """Apply BTST exit rules: profit target, loss limit, max hold days.
        Called each morning and periodically during the day."""
        if not self._active_trades:
            return

        trades_to_exit = []

        for trade in self._active_trades:
            if trade["status"] != "OPEN":
                continue

            symbol = trade["symbol"]
            entry_price = trade.get("entry_price", 0)
            ltp = trade.get("ltp", 0)
            side = trade.get("side", 1)

            if entry_price <= 0 or ltp <= 0:
                continue

            # Gap protection — if stock opened beyond SL, exit immediately
            sl = trade.get("stop_loss", 0)
            if sl > 0:
                if side == 1 and ltp < sl:  # BUY — gapped below SL
                    self._log("ALERT", f"BTST GAP DOWN: {symbol} opened at ₹{ltp:.2f} below SL ₹{sl:.2f} — exiting immediately")
                    trade["_exit_reason"] = "BTST_GAP_DOWN"
                    trades_to_exit.append(trade)
                    continue
                elif side == -1 and ltp > sl:  # SELL — gapped above SL
                    self._log("ALERT", f"BTST GAP UP: {symbol} opened at ₹{ltp:.2f} above SL ₹{sl:.2f} — exiting immediately")
                    trade["_exit_reason"] = "BTST_GAP_UP"
                    trades_to_exit.append(trade)
                    continue

            # Calculate P&L percentage
            if side == 1:
                pnl_pct = (ltp - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - ltp) / entry_price * 100

            # Days held
            placed = trade.get("placed_at", "")
            days_held = 0
            if placed:
                try:
                    placed_date = datetime.fromisoformat(placed).date()
                    days_held = (now_ist().date() - placed_date).days
                    trade["days_held"] = days_held
                except Exception:
                    pass

            # Rule 1: Profit target
            if pnl_pct >= BTST_EXIT_PROFIT_TARGET_PCT:
                self._log("ORDER", f"{symbol} — BTST PROFIT TARGET hit: +{pnl_pct:.2f}% (target: +{BTST_EXIT_PROFIT_TARGET_PCT}%)")
                trade["_exit_reason"] = "BTST_PROFIT_TARGET"
                trades_to_exit.append(trade)
                continue

            # Rule 2: Loss limit
            if pnl_pct <= -BTST_EXIT_LOSS_LIMIT_PCT:
                self._log("ORDER", f"{symbol} — BTST LOSS LIMIT hit: {pnl_pct:.2f}% (limit: -{BTST_EXIT_LOSS_LIMIT_PCT}%)")
                trade["_exit_reason"] = "BTST_LOSS_LIMIT"
                trades_to_exit.append(trade)
                continue

            # Rule 3: Max hold days
            if days_held >= BTST_MAX_HOLD_DAYS:
                self._log("ORDER", f"{symbol} — BTST MAX HOLD DAYS reached: {days_held} days (max: {BTST_MAX_HOLD_DAYS})")
                trade["_exit_reason"] = "BTST_MAX_HOLD"
                trades_to_exit.append(trade)
                continue

        # Execute exits
        for trade in trades_to_exit:
            self._exit_position(trade, trade.get("_exit_reason", "BTST_EXIT"))

    def _exit_position(self, trade: dict, reason: str):
        """Place CNC sell order to close a BTST position."""
        symbol = trade["symbol"]
        qty = trade["quantity"]
        side = trade["side"]
        close_side = -1 if side == 1 else 1

        # Cancel pending SL order first
        sl_order_id = trade.get("sl_order_id", "")
        if sl_order_id:
            try:
                cancel_order(sl_order_id)
                self._log("ORDER", f"{symbol} — cancelled SL order (ID: {sl_order_id})")
            except Exception:
                pass

        self._log("ORDER", f"{symbol} — placing CNC market exit ({reason})")

        try:
            result = place_order(
                symbol=symbol,
                qty=qty,
                side=close_side,
                order_type=2,  # Market
                product_type="CNC",
            )

            if "error" not in result:
                ltp = trade.get("ltp", 0)
                entry = trade.get("entry_price", 0)
                pnl = round((ltp - entry) * qty * side, 2) if ltp > 0 and entry > 0 else trade.get("pnl", 0)
                self._total_pnl += pnl
                trade["status"] = "CLOSED"
                trade["closed_at"] = now_ist().isoformat()
                trade["exit_reason"] = reason
                trade["exit_price"] = ltp if ltp > 0 else entry
                trade["pnl"] = pnl
                self._trade_history.append(trade)
                log_trade(trade, source="btst")
                self._log("ORDER", f"{symbol} — BTST exit placed ({reason}). P&L: ₹{pnl:.2f}")
                # Telegram: BTST trade closed notification
                try:
                    telegram_notify.trade_closed(
                        symbol, trade.get("signal_type", "BUY"), pnl,
                        reason, engine="BTST"
                    )
                except Exception:
                    pass
            else:
                self._log("ERROR", f"{symbol} — BTST exit FAILED: {result['error']}. SELL MANUALLY!")
        except Exception as e:
            self._log("ERROR", f"{symbol} — BTST exit exception: {e}. SELL MANUALLY!")
            self._log("ERROR", traceback.format_exc())

        # Clean closed trades
        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()

    # ── Position Monitoring ───────────────────────────────────────────────

    def _update_position_pnl(self):
        """Refresh P&L for active BTST trades using broker positions and holdings."""
        if not self._active_trades:
            return

        _, positions = self._get_open_positions_detail()

        pnl_map = {}
        ltp_map = {}
        position_symbols = set()
        for pos in positions:
            sym = pos.get("symbol", "").replace("NSE:", "").replace("-EQ", "")
            pnl_map[sym] = pos.get("pl", pos.get("unrealized_profit", 0))
            ltp_map[sym] = pos.get("ltp", 0)
            position_symbols.add(sym)

        # Also check holdings (CNC positions move here after settlement)
        holdings_symbols = self._get_holdings_symbols()
        all_held_symbols = position_symbols | holdings_symbols

        for trade in self._active_trades:
            if trade["status"] != "OPEN":
                continue

            symbol = trade["symbol"]
            if symbol in pnl_map:
                trade["pnl"] = pnl_map[symbol]

            # Days held
            placed = trade.get("placed_at", "")
            if placed:
                try:
                    placed_date = datetime.fromisoformat(placed).date()
                    trade["days_held"] = (now_ist().date() - placed_date).days
                except Exception:
                    pass

            # Get LTP
            ltp = ltp_map.get(symbol, 0)
            if ltp == 0:
                ltp = self._get_ltp(symbol)
            if ltp > 0:
                trade["ltp"] = ltp

            # Update P&L from LTP if not in positions
            if symbol not in pnl_map and ltp > 0:
                entry = trade.get("entry_price", 0)
                qty = trade.get("quantity", 0)
                side = trade.get("side", 1)
                if entry > 0 and qty > 0:
                    trade["pnl"] = round((ltp - entry) * qty * side, 2)

            # Re-place SL order if missing/expired (CNC orders are DAY validity)
            if trade["status"] == "OPEN" and symbol in all_held_symbols and is_market_open():
                self._replace_sl_if_needed(trade)

            # Check if SL order filled on exchange
            sl_order_id = trade.get("sl_order_id", "")
            if sl_order_id and self._is_order_filled(sl_order_id):
                sl_price = trade.get("stop_loss", 0)
                entry = trade.get("entry_price", 0)
                qty = trade.get("quantity", 0)
                side = trade.get("side", 1)
                pnl = round((sl_price - entry) * qty * side, 2) if sl_price > 0 and entry > 0 else trade.get("pnl", 0)
                self._total_pnl += pnl
                trade["status"] = "CLOSED"
                trade["closed_at"] = now_ist().isoformat()
                trade["exit_reason"] = "SL_HIT"
                trade["exit_price"] = sl_price
                trade["pnl"] = pnl
                self._trade_history.append(trade)
                log_trade(trade, source="btst")
                self._log("ORDER", f"{symbol} — BTST SL filled on exchange. P&L: ₹{pnl:.2f}")
                # Telegram: BTST SL hit notification
                try:
                    telegram_notify.trade_closed(
                        symbol, trade.get("signal_type", "BUY"), pnl,
                        "SL_HIT", engine="BTST"
                    )
                except Exception:
                    pass
                continue

            # Fallback: position gone from both positions + holdings
            if trade["status"] == "OPEN" and symbol not in all_held_symbols:
                placed_at_str = trade.get("placed_at", "")
                if placed_at_str:
                    try:
                        placed_at = datetime.fromisoformat(placed_at_str)
                        age_seconds = (now_ist() - placed_at).total_seconds()
                        if age_seconds < 120:
                            continue  # Grace period for new orders
                    except (ValueError, TypeError):
                        pass

                self._log("WARN", f"{symbol} — not found in positions/holdings. May be settlement delay or SL triggered.")

        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()

    def _replace_sl_if_needed(self, trade: dict):
        """Re-place SL order if it's not active on exchange (DAY validity expired)."""
        sl_order_id = trade.get("sl_order_id", "")
        has_valid_sl = sl_order_id and self._is_order_pending(sl_order_id)
        if has_valid_sl:
            return

        symbol = trade["symbol"]
        stop_loss = trade.get("stop_loss", 0)
        qty = trade.get("quantity", 0)
        side = trade.get("side", 1)
        exit_side = -1 if side == 1 else 1

        self._log("ORDER", f"{symbol} — no active SL order, placing CNC SL-M at ₹{stop_loss}")
        sl_result = place_order(
            symbol=symbol, qty=qty, side=exit_side,
            order_type=4, product_type="CNC", stop_price=stop_loss,
        )
        if "error" not in sl_result:
            new_sl_id = sl_result.get("id", sl_result.get("order_id", ""))
            trade["sl_order_id"] = new_sl_id
            self._log("ORDER", f"{symbol} — SL-M re-placed (ID: {new_sl_id}) at ₹{stop_loss}")
        else:
            self._log("WARN", f"{symbol} — SL re-placement failed: {sl_result.get('error', '')}")

    def _check_sl_order_health(self):
        """Verify SL orders are still pending on broker for all active trades.
        If cancelled/rejected, re-place them."""
        active_with_sl = [t for t in self._active_trades
                          if t["status"] == "OPEN" and t.get("sl_order_id")]
        if not active_with_sl:
            return

        try:
            orderbook = get_orderbook()
            orders = orderbook.get("orderBook", [])
            if not orders:
                data = orderbook.get("data", {})
                if isinstance(data, dict):
                    orders = data.get("orderBook", [])

            order_status_map = {}
            for order in orders:
                oid = order.get("id", "")
                if oid:
                    order_status_map[oid] = order.get("status", 0)

            for trade in active_with_sl:
                sl_oid = trade.get("sl_order_id", "")
                if not sl_oid:
                    continue

                status = order_status_map.get(sl_oid, None)
                if status is None or status in (4, 6):
                    continue  # Not found or still pending — OK
                if status == 2:
                    continue  # SL filled — position monitoring handles closure

                # Status 1 (cancelled) or 5 (rejected)
                symbol = trade["symbol"]
                status_label = "CANCELLED" if status == 1 else "REJECTED"
                self._log("WARN", f"{symbol} — BTST SL order {sl_oid} is {status_label}! Re-placing SL...")

                try:
                    sl_price = trade.get("stop_loss", 0)
                    qty = trade.get("quantity", 0)
                    side = trade.get("side", 1)
                    sl_side = -1 if side == 1 else 1

                    if sl_price > 0 and qty > 0:
                        sl_result = place_order(
                            symbol=symbol, qty=qty, side=sl_side,
                            order_type=4, product_type="CNC", stop_price=sl_price,
                        )
                        if "error" not in sl_result:
                            new_sl_id = sl_result.get("id", sl_result.get("order_id", ""))
                            trade["sl_order_id"] = new_sl_id
                            self._log("ORDER", f"{symbol} — BTST SL re-placed (new ID: {new_sl_id}) @ ₹{sl_price}")
                            self._save_state()
                        else:
                            self._log("ERROR", f"{symbol} — BTST SL re-place FAILED: {sl_result.get('error', '')}")
                except Exception as e:
                    self._log("ERROR", f"{symbol} — BTST SL re-place exception: {e}")

        except Exception as e:
            self._log("WARN", f"BTST SL health check failed: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_open_positions_detail(self) -> tuple[set, list]:
        """Get open CNC position symbols and full position data from broker."""
        try:
            positions_data = get_positions()
            if "error" in positions_data:
                return set(), []

            positions = positions_data.get("netPositions", [])
            if not positions:
                positions = positions_data.get("data", {}).get("netPositions", []) if isinstance(positions_data.get("data"), dict) else []

            open_symbols = set()
            open_positions = []

            for pos in positions:
                qty = pos.get("netQty", pos.get("qty", 0))
                if qty != 0:
                    # Only include CNC positions (BTST uses CNC)
                    prod = pos.get("productType", "")
                    if prod != "CNC":
                        continue
                    broker_sym = pos.get("symbol", "")
                    plain = broker_sym.replace("NSE:", "").replace("-EQ", "")
                    open_symbols.add(plain)
                    open_positions.append(pos)

            return open_symbols, open_positions
        except Exception as e:
            self._log("ERROR", f"Error fetching positions: {e}")
            return set(), []

    def _get_holdings_symbols(self) -> set:
        """Get symbols from CNC holdings (positions move here after settlement)."""
        try:
            holdings_data = get_holdings()
            holdings = holdings_data.get("holdings", [])
            symbols = set()
            for h in holdings:
                sym = h.get("symbol", "").replace("NSE:", "").replace("-EQ", "")
                qty = h.get("quantity", h.get("remainingQuantity", 0))
                if qty > 0 and sym:
                    symbols.add(sym)
            return symbols
        except Exception as e:
            self._log("ERROR", f"Error fetching holdings: {e}")
            return set()

    def _get_ltp(self, symbol: str) -> float:
        """Get last traded price for a symbol via quotes API."""
        try:
            broker_symbol = f"NSE:{symbol}-EQ"
            quotes = get_quotes([broker_symbol])
            if quotes and "d" in quotes:
                for q in quotes["d"]:
                    if q.get("n", "") == broker_symbol:
                        return q.get("v", {}).get("lp", 0)
            return 0
        except Exception:
            return 0

    def _get_order_status(self, order_id: str) -> str:
        """Check order status from broker orderbook."""
        try:
            orderbook = get_orderbook()
            orders = orderbook.get("orderBook", [])
            if not orders:
                data = orderbook.get("data", {})
                if isinstance(data, dict):
                    orders = data.get("orderBook", [])
            for order in orders:
                if order.get("id", "") == order_id:
                    status = order.get("status", 0)
                    if status == 2:
                        return "filled"
                    elif status == 5:
                        return "rejected"
                    elif status == 1:
                        return "cancelled"
                    elif status in (4, 6):
                        return "pending"
            return "unknown"
        except Exception:
            return "unknown"

    def _get_fill_price(self, order_id: str) -> float:
        """Get actual fill price from broker orderbook."""
        try:
            orderbook = get_orderbook()
            orders = orderbook.get("orderBook", [])
            if not orders:
                data = orderbook.get("data", {})
                if isinstance(data, dict):
                    orders = data.get("orderBook", [])
            for order in orders:
                if order.get("id", "") == order_id:
                    return order.get("tradedPrice", 0) or order.get("limitPrice", 0)
            return 0
        except Exception:
            return 0

    def _is_order_filled(self, order_id: str) -> bool:
        """Check if a specific order was filled (status=2 in broker)."""
        try:
            orderbook = get_orderbook()
            orders = orderbook.get("orderBook", [])
            for order in orders:
                if order.get("id", "") == order_id:
                    return order.get("status") == 2 and order.get("filledQty", 0) > 0
            return False
        except Exception:
            return False

    def _is_order_pending(self, order_id: str) -> bool:
        """Check if a specific order is still pending/open."""
        try:
            orderbook = get_orderbook()
            orders = orderbook.get("orderBook", [])
            for order in orders:
                if order.get("id", "") == order_id:
                    status = order.get("status", 0)
                    return status in (4, 6)  # transit or pending
            return False
        except Exception:
            return False

    # ── Logging ───────────────────────────────────────────────────────────

    def _log(self, level: str, message: str):
        """Add a timestamped log entry."""
        self._logger.log(level, message)


# ── Singleton Instance ────────────────────────────────────────────────────
import sys as _sys
_module = _sys.modules.get(__name__)
if _module and hasattr(_module, 'btst_trader') and isinstance(getattr(_module, 'btst_trader'), BTSTTrader):
    pass
else:
    btst_trader = BTSTTrader()
