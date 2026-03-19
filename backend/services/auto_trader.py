"""
Auto-Trading Engine for IntraTrading.

Rules:
  - Only starts during market hours (9:15 AM - 3:30 PM IST, weekdays)
  - Scans every 15 minutes
  - Places bracket orders automatically via Fyers
  - STOPS placing new orders after 2:00 PM IST
  - SQUARES OFF all open positions at 3:15 PM IST (before 3:30 close)
  - Max 4 open positions at a time
  - 2% risk per trade
  - Live logs for all activity
"""

import threading
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from services.scanner import run_scan, is_market_open, _calc_conviction
from services.market_data import get_nifty_trend
from services.trade_logger import log_trade, log_trades_batch
from services.fyers_client import (
    place_bracket_order,
    place_order,
    cancel_order,
    get_positions,
    get_quotes,
    is_authenticated,
)
from utils.time_utils import now_ist, is_before_time, is_past_time
from utils.state_manager import get_state_path, save_state, load_state
from utils.trader_log import TraderLogger
from utils.sleep_manager import SleepManager
from config import (
    INTRADAY_ORDER_START_HOUR, INTRADAY_ORDER_START_MIN,
    INTRADAY_ORDER_CUTOFF_HOUR, INTRADAY_ORDER_CUTOFF_MIN,
    INTRADAY_SQUAREOFF_HOUR, INTRADAY_SQUAREOFF_MIN,
    INTRADAY_CAPITAL_PER_POSITION, INTRADAY_MIN_POSITIONS, INTRADAY_MAX_POSITIONS_CAP,
    INTRADAY_POSITION_CHECK_INTERVAL,
)

logger = logging.getLogger(__name__)

STATE_FILE = get_state_path(".auto_trader_state.json")


def _is_before_order_start() -> bool:
    """True if current time is before 10:30 AM IST — too early for orders."""
    return is_before_time(INTRADAY_ORDER_START_HOUR, INTRADAY_ORDER_START_MIN)


def _is_past_order_cutoff() -> bool:
    """True if current time is past 2:00 PM IST — no new orders."""
    return is_past_time(INTRADAY_ORDER_CUTOFF_HOUR, INTRADAY_ORDER_CUTOFF_MIN)


def _is_squareoff_time() -> bool:
    """True if current time is 3:15 PM IST or later — square off everything."""
    return is_past_time(INTRADAY_SQUAREOFF_HOUR, INTRADAY_SQUAREOFF_MIN)


class AutoTrader:
    """
    Background auto-trading engine.

    Scans every 15 minutes during market hours (9:15 AM - 2:00 PM IST).
    Squares off all positions at 3:15 PM IST.
    Auto-stops after square-off.
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Auto-calculated from capital at start (can be changed live via specialist deploy)
        self.max_open_positions: int = INTRADAY_MIN_POSITIONS

        # Configuration — supports multiple strategies
        self._strategy_keys: list[str] = []
        self._timeframes: dict[str, str] = {}  # strategy_key -> timeframe
        self._capital: float = 0.0

        # State tracking
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

        # Shared utilities
        self._logger = TraderLogger("AutoTrader")
        self._sleep_mgr = SleepManager("AutoTrader")

        # Restore state from disk (survives server restarts)
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

    # ── State Persistence ──────────────────────────────────────────────────

    def _save_state(self):
        """Persist auto-trader state to disk so it survives server restarts."""
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
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "AutoTrader")

    def _load_state(self):
        """Restore auto-trader state from disk if it's from today."""
        try:
            state = load_state(STATE_FILE, "AutoTrader")
            if not state:
                return

            # Only restore today's state
            today = now_ist().strftime("%Y-%m-%d")
            if state.get("date") != today:
                logger.info(f"[AutoTrader] State file is from {state.get('date')}, not today ({today}) — ignoring")
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

            # Recalculate max positions from restored capital
            if self._capital > 0:
                self.max_open_positions = max(INTRADAY_MIN_POSITIONS, min(int(self._capital // INTRADAY_CAPITAL_PER_POSITION), INTRADAY_MAX_POSITIONS_CAP))

            was_running = state.get("running", False)

            if self._strategy_keys:
                strat_names = ", ".join(f"{k}({self._timeframes.get(k, '')})" for k in self._strategy_keys)
                self._log("RESTORE", f"Restored today's state — {len(self._strategy_keys)} strategies: {strat_names} | "
                          f"Scans: {self._scan_count} | Orders: {self._order_count} | P&L: ₹{self._total_pnl:,.2f} | "
                          f"Trades: {len(self._trade_history)} completed, {len(self._active_trades)} active")

                # Auto-resume if it was running before restart
                if was_running and not self._squared_off and is_market_open() and not _is_past_order_cutoff():
                    self._log("RESTORE", "Auto-trader was running before restart — auto-resuming...")
                    self._recover_orphaned_positions()
                    self._running = True
                    self._prevent_sleep()
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif was_running and not self._squared_off and is_market_open():
                    self._log("RESTORE", "Auto-trader was running but past order cutoff — monitoring positions only")
                    self._recover_orphaned_positions()
                    self._running = True
                    self._prevent_sleep()
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif was_running:
                    self._log("RESTORE", "Auto-trader was running but market is now closed — state preserved for EOD analysis")

        except Exception as e:
            logger.warning(f"[AutoTrader] Failed to load state: {e}")

    def _recover_orphaned_positions(self):
        """
        Detect Fyers INTRADAY positions not tracked in active_trades.
        Adds them as monitored entries so they're visible and counted.
        Called after start/resume to reconcile state.
        """
        try:
            open_symbols, positions = self._get_open_positions_detail()
            tracked_symbols = {t["symbol"] for t in self._active_trades}

            for pos in positions:
                prod = pos.get("productType", "")
                if prod not in ("INTRADAY", "BO"):
                    continue  # Skip CNC (swing) positions

                fyers_sym = pos.get("symbol", "")
                plain = fyers_sym.replace("NSE:", "").replace("-EQ", "")
                qty = pos.get("netQty", pos.get("qty", 0))

                if plain in tracked_symbols or qty == 0:
                    continue

                # Orphaned position — add to active_trades for monitoring
                buy_avg = pos.get("buyAvg", 0)
                sell_avg = pos.get("sellAvg", 0)
                side = 1 if qty > 0 else -1
                entry_price = buy_avg if side == 1 else sell_avg
                ltp = pos.get("ltp", entry_price)
                pnl = pos.get("pl", 0) + pos.get("unrealized_profit", 0)

                # Try to inherit strategy/timeframe from trade_history (same symbol, same day)
                inherited_strategy = "unknown"
                inherited_timeframe = ""
                today_str = now_ist().strftime("%Y-%m-%d")
                for hist in reversed(self._trade_history):
                    if hist.get("symbol") == plain and hist.get("placed_at", "").startswith(today_str):
                        inherited_strategy = hist.get("strategy", "unknown")
                        inherited_timeframe = hist.get("timeframe", "")
                        break

                trade = {
                    "symbol": plain,
                    "signal_type": "BUY" if side == 1 else "SELL",
                    "side": side,
                    "entry_price": round(entry_price, 2),
                    "stop_loss": 0,
                    "target": 0,
                    "quantity": abs(qty),
                    "order_id": "recovered",
                    "sl_order_id": "",
                    "strategy": inherited_strategy,
                    "timeframe": inherited_timeframe,
                    "placed_at": now_ist().isoformat(),
                    "status": "OPEN",
                    "pnl": round(pnl, 2),
                    "ltp": ltp,
                    "recovered": True,
                }
                self._active_trades.append(trade)
                self._log("RESTORE", f"Recovered orphaned position: {plain} {'LONG' if side==1 else 'SHORT'} x{abs(qty)} @ ₹{entry_price:.2f} | P&L ₹{pnl:.2f}")

            if any(t.get("recovered") for t in self._active_trades):
                self._save_state()

        except Exception as e:
            self._log("WARN", f"Position recovery failed: {e}")

    # ── Controls ──────────────────────────────────────────────────────────

    def start(self, strategies: list[dict], capital: float) -> dict:
        """
        Start auto-trading with one or more strategies.

        Args:
            strategies: list of {"strategy": "play1_ema_crossover", "timeframe": "15m"}
            capital: trading capital in INR
        """
        with self._lock:
            if self._running:
                return {"error": "Auto-trader is already running"}

            # Block start outside market hours
            if not is_market_open():
                now = now_ist()
                if now.weekday() >= 5:
                    return {"error": f"Market is closed (Weekend). Auto-trading can only start during market hours (Mon-Fri 9:15 AM - 3:30 PM IST)."}
                return {"error": "Market is closed. Auto-trading can only start during market hours (9:15 AM - 3:30 PM IST)."}

            # Block start after order cutoff (2 PM)
            if _is_past_order_cutoff():
                return {"error": "Cannot start after 2:00 PM IST. No new orders are placed after 2:00 PM."}

            # Validate Fyers authentication
            if not is_authenticated():
                return {"error": "Fyers is not authenticated. Please login first."}

            if not strategies:
                return {"error": "At least one strategy must be selected."}

            # Parse strategies into keys and timeframes
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
            self.max_open_positions = max(INTRADAY_MIN_POSITIONS, min(int(capital // INTRADAY_CAPITAL_PER_POSITION), INTRADAY_MAX_POSITIONS_CAP))
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

            strat_names = ", ".join(f"{k}({self._timeframes[k]})" for k in self._strategy_keys)
            self._log("START", f"Auto-trader STARTED — {len(self._strategy_keys)} strateg{'y' if len(self._strategy_keys) == 1 else 'ies'}: {strat_names} | Capital=₹{capital:,.0f}")
            self._log("INFO", f"Orders: 10:30 AM - 2:00 PM IST | Square-off: 3:15 PM IST | Max positions: {self.max_open_positions} (auto: ₹{INTRADAY_CAPITAL_PER_POSITION:,.0f}/slot)")
            if _is_before_order_start():
                self._log("INFO", "Started before 10:30 AM — scanning will begin but orders will only be placed after 10:30 AM IST")

            # Prevent Mac from sleeping (works even with lid closed if setup_sleep_prevention.sh was run)
            self._prevent_sleep()
            if self._sleep_mgr.mode == "pmset":
                self._log("INFO", "Sleep prevention ENABLED — Mac will stay awake even with lid closed")
            elif self._sleep_mgr.mode == "caffeinate":
                self._log("WARN", "Sleep prevention (caffeinate only) — keep lid OPEN! Run 'sudo bash setup_sleep_prevention.sh' for lid-close support")
            else:
                self._log("WARN", "Sleep prevention FAILED — Mac may sleep if idle or lid closed")

            # Recover any Fyers positions not tracked (e.g. from previous run)
            self._recover_orphaned_positions()

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
        """Stop auto-trading."""
        with self._lock:
            if not self._running:
                return {"status": "already_stopped", "message": "Auto-trader is not running"}

            self._running = False
            self._log("STOP", "Auto-trader STOPPED by user")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        # Re-allow Mac sleep
        self._allow_sleep()
        self._log("INFO", "Sleep prevention DISABLED — Mac can sleep normally")
        self._save_state()

        return {
            "status": "stopped",
            "total_scans": self._scan_count,
            "total_orders": self._order_count,
            "total_pnl": round(self._total_pnl, 2),
        }

    def status(self) -> dict:
        """Return current auto-trader state with live data."""
        open_symbols = []
        open_positions = []

        if self._running or self._active_trades:
            open_symbols, open_positions = self._get_open_positions_detail()

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
            "open_positions": open_positions,
            "trade_history": self._trade_history[-20:],
            "open_position_symbols": list(open_symbols),
            "squared_off": self._squared_off,
            "order_cutoff_passed": _is_past_order_cutoff(),
            "logs": self._logger.recent(100),
        }

    # ── Main Loop ─────────────────────────────────────────────────────────

    def _run_loop(self):
        """Background loop: scan-on-demand, monitor positions, square off.

        Strategy:
          1. Wait for 10:30 AM, then run ONE full scan to fill all slots.
          2. Monitor positions every 60s.  When a position closes and a slot
             opens up (before 2:00 PM cutoff), trigger an immediate scan.
          3. After 2:00 PM — monitor only, no new scans.
          4. At 3:15 PM — square off everything.
        """
        self._log("INFO", "Background thread started")
        self._log("INFO", f"Scan mode: ON-DEMAND — initial scan at 10:30 AM, then re-scan only when a slot opens")

        # ── Phase 1: Wait for 10:30 AM ──
        while self._running and _is_before_order_start():
            if _is_squareoff_time() and not self._squared_off:
                break
            self._next_scan_at = None
            now = now_ist()
            order_start = now.replace(hour=INTRADAY_ORDER_START_HOUR, minute=INTRADAY_ORDER_START_MIN, second=0, microsecond=0)
            mins_left = max(0, int((order_start - now).total_seconds() / 60))
            if mins_left % 15 == 0 and mins_left > 0:
                self._log("INFO", f"Waiting for 10:30 AM IST — {mins_left} min left")
            time.sleep(60)

        if not self._running:
            self._log("INFO", "Background thread exited")
            return

        # ── Phase 2: Initial full scan at 10:30 AM ──
        if not _is_past_order_cutoff() and not (_is_squareoff_time() and not self._squared_off):
            if not is_market_open():
                self._log("INFO", "Market closed — stopping auto-trader")
                self._running = False
                self._log("INFO", "Background thread exited")
                return
            if not is_authenticated():
                self._log("ERROR", "Fyers authentication lost — stopping auto-trader")
                self._running = False
                self._log("INFO", "Background thread exited")
                return

            self._log("SCAN", "10:30 AM — executing initial full scan to fill all slots")
            self._execute_scan_cycle()

        # ── Phase 3: Monitor loop — check positions every 60s, scan on slot open ──
        prev_open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])
        self._next_scan_at = None  # no scheduled scan — on-demand only
        _monitor_tick = 0

        while self._running:
            # Square-off check
            if _is_squareoff_time() and not self._squared_off:
                self._log("ALERT", "3:15 PM IST reached — initiating square-off of ALL open positions")
                self._square_off_all()
                self._squared_off = True
                self._allow_sleep()
                self._log("INFO", "Sleep prevention DISABLED — trading day complete")
                self._log("STOP", "Auto-trader stopping after square-off")
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

            # ── Monitor positions: detect closures, update P&L ──
            self._update_position_pnl()
            _monitor_tick += 1

            # Fyers health check every ~5 minutes (every 5th tick at 60s intervals)
            if _monitor_tick % 5 == 0:
                try:
                    if not is_authenticated():
                        self._log("WARN", "Fyers disconnected — attempting reconnect...")
                        from services.fyers_client import headless_login
                        result = headless_login()
                        if "error" in result:
                            self._log("ALERT", f"Fyers reconnect FAILED: {result['error']} — positions at risk!")
                        else:
                            self._log("INFO", "Fyers reconnected successfully")
                except Exception:
                    pass

            current_open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])

            # Did a slot open up?
            if current_open_count < prev_open_count:
                slots_freed = prev_open_count - current_open_count
                self._log("INFO", f"{slots_freed} position(s) closed — {current_open_count}/{self.max_open_positions} slots used")

                # Scan to refill if before cutoff and slots available
                if current_open_count < self.max_open_positions and not _is_past_order_cutoff():
                    if is_market_open() and is_authenticated():
                        self._log("SCAN", f"Slot available — triggering scan to fill {self.max_open_positions - current_open_count} open slot(s)")
                        self._execute_scan_cycle()
                        current_open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])
                    elif not is_authenticated():
                        self._log("ERROR", "Fyers authentication lost — cannot scan for new trades")
                elif _is_past_order_cutoff():
                    self._log("INFO", "Past 2:00 PM — no new orders. Monitoring until square-off.")

            prev_open_count = current_open_count

        self._log("INFO", "Background thread exited")

    def _check_drawdown_breaker(self) -> bool:
        """Check if multi-day drawdown exceeds 15% of capital."""
        try:
            from services.trade_logger import get_all_trades
            recent = get_all_trades(days=5)
            trades = [t for t in recent if t.get("source") == "auto"]
            if len(trades) >= 5:
                pnl = sum(t.get("pnl", 0) for t in trades)
                if pnl < -self._capital * 0.15:
                    return True
        except Exception:
            pass
        return False

    def _check_daily_loss_limit(self) -> bool:
        """Returns True if daily loss limit breached — stop opening new positions."""
        if self._daily_loss_limit_hit:
            return True
        if self._capital <= 0:
            return False
        loss_pct = abs(self._daily_realized_pnl) / self._capital * 100
        if self._daily_realized_pnl < 0 and loss_pct >= 5.0:  # 5% daily loss limit
            self._daily_loss_limit_hit = True
            self._log("ALERT", f"DAILY LOSS LIMIT HIT: ₹{self._daily_realized_pnl:,.2f} ({loss_pct:.1f}% of capital). No new orders.")
            return True
        return False

    def _execute_scan_cycle(self):
        """Run one scan across all selected strategies: find signals and place orders."""
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

        # Daily loss check
        if self._check_daily_loss_limit():
            self._log("INFO", "Daily loss limit active — skipping scan, monitoring only")
            self._update_position_pnl()
            return

        self._scan_count += 1
        num_strategies = len(self._strategy_keys)
        self._log("SCAN", f"Scan #{self._scan_count} starting — {num_strategies} strateg{'y' if num_strategies == 1 else 'ies'}...")

        # Check open positions — use internal trades as authority (Fyers has settlement delay)
        internal_open = [t for t in self._active_trades if t["status"] == "OPEN"]
        open_symbols_fyers, _ = self._get_open_positions_detail()
        # Combine both: internal OPEN trades + any Fyers positions not yet tracked
        open_symbols = {t["symbol"] for t in internal_open} | open_symbols_fyers
        open_count = len(internal_open)  # internal count is more accurate for slot tracking

        if open_count >= self.max_open_positions:
            self._log("INFO", f"Max positions reached ({open_count}/{self.max_open_positions}) — skipping order placement")
            self._update_position_pnl()
            return

        slots_available = self.max_open_positions - open_count

        # VIX check — skip 5m strategies in high VIX (whipsaw protection)
        try:
            import yfinance as yf
            vix_data = yf.Ticker("^INDIAVIX").history(period="5d", interval="1d")
            vix = float(vix_data["Close"].iloc[-1]) if vix_data is not None and len(vix_data) > 0 else 15
        except Exception:
            vix = 15

        if vix > 18:
            self._log("FILTER", f"VIX={vix:.1f} (elevated) — skipping 5m strategies, using 15m only")

        # Collect signals from all strategies
        all_signals = []
        total_scanned = 0
        total_time = 0
        strategy_idx = 0

        for strategy_key in self._strategy_keys:
            timeframe = self._timeframes.get(strategy_key, "15m")

            # Skip 5m in high VIX — use 15m fallback if available
            if vix > 18 and timeframe == "5m":
                from config import STRATEGY_TIMEFRAMES
                available_tfs = STRATEGY_TIMEFRAMES.get(strategy_key, [])
                if "15m" in available_tfs:
                    timeframe = "15m"
                    self._log("FILTER", f"  {strategy_key}: 5m → 15m (VIX={vix:.1f})")
                else:
                    self._log("FILTER", f"  {strategy_key}: skipped (5m only, no 15m available)")
                    continue

            scan_result = run_scan(strategy_key, timeframe, self._capital)

            if "error" in scan_result:
                self._log("WARN", f"Scan error for {strategy_key}: {scan_result['error']}")
                continue

            signals = scan_result.get("signals", [])
            scanned = scan_result.get("stocks_scanned", 0)
            scan_time = scan_result.get("scan_time_seconds", 0)
            total_scanned = max(total_scanned, scanned)  # stocks overlap across strategies
            total_time += scan_time

            # Tag each signal with the strategy that produced it
            for sig in signals:
                sig["_strategy"] = strategy_key
                sig["_timeframe"] = timeframe
                sig["_regime_position"] = strategy_idx

            all_signals.extend(signals)
            self._log("SCAN", f"  {strategy_key}({timeframe}): {len(signals)} signals ({scan_time}s)")
            strategy_idx += 1

        # Deduplicate by symbol — keep highest conviction signal per symbol
        # Regime-aware: strategies listed first in regime map get a priority boost
        seen_symbols = {}
        for sig in all_signals:
            sym = sig.get("symbol", "")
            conv = _calc_conviction(sig)
            regime_pos = sig.get("_regime_position", 99)
            if regime_pos == 0:
                conv *= 1.5   # Primary strategy for this regime
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
        nifty_trend = get_nifty_trend("5m")
        buy_count = sum(1 for s in unique_signals if s.get("signal_type") == "BUY")
        sell_count = sum(1 for s in unique_signals if s.get("signal_type") == "SELL")

        if nifty_trend == "BEARISH":
            # Block BUY signals on bearish days — only allow shorts
            unique_signals = [s for s in unique_signals if s.get("signal_type") == "SELL"]
            self._log("FILTER", f"Nifty BEARISH — blocked {buy_count} BUY signals, kept {sell_count} SELL signals")
        elif nifty_trend == "BULLISH":
            # Block SELL signals on bullish days — only allow longs
            unique_signals = [s for s in unique_signals if s.get("signal_type") == "BUY"]
            self._log("FILTER", f"Nifty BULLISH — kept {buy_count} BUY signals, blocked {sell_count} SELL signals")
        else:
            self._log("FILTER", f"Nifty {nifty_trend} — allowing all signals ({buy_count} BUY, {sell_count} SELL)")

        if not unique_signals:
            self._log("FILTER", "No signals remaining after Nifty trend filter")
            return

        # Stagger entries: max 2 orders per scan cycle to avoid correlated losses
        max_orders_per_scan = min(2, slots_available)
        orders_placed = 0

        for signal in unique_signals:
            if orders_placed >= max_orders_per_scan:
                self._log("INFO", f"Max 2 orders per scan — remaining {slots_available - orders_placed} slots will fill on next scan")
                break

            # Double-check time before each order
            if _is_past_order_cutoff():
                self._log("INFO", "2:00 PM cutoff reached during order placement — stopping")
                break

            symbol = signal.get("symbol", "")

            # Skip if already in position
            if symbol in open_symbols:
                self._log("SKIP", f"{symbol} — already in position")
                continue

            active_symbols = {t["symbol"] for t in self._active_trades}
            if symbol in active_symbols:
                self._log("SKIP", f"{symbol} — already tracked in active trades")
                continue

            # Place order — tag with strategy info
            signal["_placed_via"] = signal.get("_strategy", "")
            success = self._place_order_for_signal(signal)
            if success:
                orders_placed += 1
                open_symbols.add(symbol)

        self._update_position_pnl()

    def _place_order_for_signal(self, signal: dict) -> bool:
        """Place an order for a signal. Tries BO, falls back to INTRADAY+SL. Returns True if successful."""
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

        self._log("ORDER", f"Placing {signal_type} order: {symbol} | Qty={qty} | Entry=₹{entry_price} | SL=₹{stop_loss} | Target=₹{target} | R:R={rr} | Capital=₹{capital_req:,.0f}")

        try:
            result = place_bracket_order(
                symbol=symbol,
                qty=qty,
                side=side,
                limit_price=entry_price,
                stop_loss=stop_loss,
                target=target,
            )

            if "error" in result:
                self._log("ERROR", f"{symbol} — order FAILED: {result['error']}")
                return False

            order_mode = result.get("order_mode", "BO")
            order_id = result.get("id", result.get("entry_order_id", "unknown"))
            sl_order_id = result.get("sl_order_id", "")
            target_price = result.get("target_price", target)

            # Verify order actually went through (not rejected)
            if order_id == "unknown" or not order_id:
                self._log("ERROR", f"{symbol} — order returned no ID, likely rejected. Skipping.")
                return False

            if order_mode == "BO":
                self._log("ORDER", f"{symbol} — BO order PLACED (ID: {order_id})")
            else:
                self._log("ORDER", f"{symbol} — INTRADAY entry PLACED (ID: {order_id}) + SL-M (ID: {sl_order_id or 'N/A'})")

            # Wait and verify order actually filled on Fyers (not rejected)
            time.sleep(3)
            order_status = self._get_order_status(order_id)
            if order_status == "rejected":
                self._log("ERROR", f"{symbol} — order REJECTED by Fyers (ID: {order_id}). NOT tracking.")
                return False
            elif order_status == "cancelled":
                self._log("WARN", f"{symbol} — order CANCELLED on Fyers (ID: {order_id}). NOT tracking.")
                return False
            elif order_status == "pending":
                self._log("INFO", f"{symbol} — order PENDING (ID: {order_id}). Will verify on next check.")
            elif order_status == "filled":
                # Get actual fill price from orderbook
                actual_price = self._get_fill_price(order_id)
                if actual_price and actual_price > 0:
                    entry_price = actual_price
                    self._log("ORDER", f"{symbol} — FILLED at ₹{actual_price} (signal was ₹{signal.get('entry_price', 0)})")

            trade = {
                "symbol": symbol,
                "signal_type": signal_type,
                "side": side,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "target": target_price,
                "quantity": qty,
                "order_id": order_id,
                "sl_order_id": sl_order_id,
                "order_mode": order_mode,
                "risk_reward_ratio": rr,
                "capital_required": capital_req,
                "strategy": signal.get("_placed_via", signal.get("_strategy", "")),
                "timeframe": signal.get("_timeframe", ""),
                "placed_at": now_ist().isoformat(),
                "status": "OPEN",
                "pnl": 0.0,
            }

            self._active_trades.append(trade)
            self._order_count += 1
            self._save_state()
            return True

        except Exception as e:
            self._log("ERROR", f"{symbol} — order EXCEPTION: {e}")
            return False

    # ── Order Verification ─────────────────────────────────────────────

    def _get_order_status(self, order_id: str) -> str:
        """Check order status from Fyers orderbook. Returns: 'filled', 'pending', 'rejected', 'cancelled', 'unknown'."""
        try:
            from services.fyers_client import get_orderbook
            orderbook = get_orderbook()
            orders = orderbook.get("orderBook", [])
            if not orders:
                data = orderbook.get("data", {})
                if isinstance(data, dict):
                    orders = data.get("orderBook", [])
            for order in orders:
                if order.get("id", "") == order_id:
                    status = order.get("status", 0)
                    # Fyers: 1=cancelled, 2=traded/filled, 4=transit, 5=rejected, 6=pending
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
        """Get actual fill price from Fyers orderbook."""
        try:
            from services.fyers_client import get_orderbook
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

    # ── Square Off ────────────────────────────────────────────────────────

    def _square_off_all(self):
        """Square off all open intraday positions at 3:15 PM."""
        open_symbols, positions = self._get_open_positions_detail()

        if not open_symbols:
            self._log("INFO", "No open positions to square off")
            return

        self._log("ALERT", f"Squaring off {len(open_symbols)} open position(s): {', '.join(open_symbols)}")

        # Step 1: Cancel all pending SL orders from INTRADAY_SL trades
        for trade in self._active_trades:
            if trade.get("order_mode") == "INTRADAY_SL" and trade["status"] == "OPEN":
                sl_order_id = trade.get("sl_order_id", "")
                if sl_order_id:
                    try:
                        cancel_result = cancel_order(sl_order_id)
                        if "error" not in cancel_result:
                            self._log("INFO", f"{trade['symbol']} — cancelled SL order before square-off (ID: {sl_order_id})")
                        else:
                            self._log("WARN", f"{trade['symbol']} — SL cancel failed: {cancel_result.get('error', '')} (may already be triggered)")
                    except Exception as e:
                        self._log("WARN", f"{trade['symbol']} — SL cancel exception: {e}")

        # Step 2: Re-fetch positions after SL cancellations (SL may have triggered
        # between the first fetch and cancellation, changing position state)
        open_symbols, positions = self._get_open_positions_detail()

        # Step 3: Close all open positions with market orders
        for pos in positions:
            symbol_fyers = pos.get("symbol", "")
            symbol_plain = symbol_fyers.replace("NSE:", "").replace("-EQ", "")
            net_qty = pos.get("netQty", pos.get("qty", 0))
            pnl = pos.get("pl", pos.get("unrealized_profit", 0))

            if net_qty == 0:
                continue

            # Close position: sell if long (qty > 0), buy if short (qty < 0)
            close_side = -1 if net_qty > 0 else 1
            close_qty = abs(net_qty)

            self._log("SQUAREOFF", f"Closing {symbol_plain}: qty={net_qty} | P&L=₹{pnl:.2f} | Side={'SELL' if close_side == -1 else 'BUY'}")

            try:
                result = place_order(
                    symbol=symbol_plain,
                    qty=close_qty,
                    side=close_side,
                    order_type=2,  # Market order
                    product_type="INTRADAY",
                )

                if "error" in result:
                    self._log("ERROR", f"Square-off FAILED for {symbol_plain}: {result['error']}")
                else:
                    order_id = result.get("id", result.get("order_id", "unknown"))
                    self._log("SQUAREOFF", f"{symbol_plain} — squared off (ID: {order_id})")
                    self._total_pnl += pnl; self._daily_realized_pnl += pnl

                    # Move to history
                    for trade in self._active_trades:
                        if trade["symbol"] == symbol_plain and trade["status"] == "OPEN":
                            trade["status"] = "CLOSED"
                            trade["pnl"] = pnl
                            trade["closed_at"] = now_ist().isoformat()
                            trade["exit_reason"] = "SQUARE_OFF"
                            trade["exit_price"] = pos.get("ltp", 0)
                            self._trade_history.append(trade)
                            log_trade(trade, source="auto")
                            break

            except Exception as e:
                self._log("ERROR", f"Square-off EXCEPTION for {symbol_plain}: {e}")

        # Clean up active trades
        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]

        self._log("ALERT", f"Square-off complete. Total P&L: ₹{self._total_pnl:,.2f}")
        self._save_state()

        # End-of-day pipeline (runs once per day, shared across all engines)
        try:
            from services.auto_tuner import run_eod_pipeline
            eod = run_eod_pipeline("equity_live")
            if eod.get("status") == "completed":
                self._log("TRACKER", f"EOD pipeline completed — {eod.get('report', {}).get('total_trades', 0)} trades analyzed")
        except Exception as e:
            logger.warning(f"[AutoTrader] EOD pipeline failed: {e}")

    # ── Position Monitoring ───────────────────────────────────────────────

    def _update_position_pnl(self):
        """Refresh P&L for active trades and check target exits for INTRADAY_SL mode.

        NOTE: Trailing stop loss is NOT implemented here for live trading.
        Fyers bracket orders (BO) manage SL on-exchange — modifying them would
        require cancelling the BO leg and placing a new SL-M order, which adds
        execution risk. Trailing SL is implemented in PaperTrader for virtual trades.
        To add trailing for live: use INTRADAY_SL mode + modify_order() API.
        """
        _, positions = self._get_open_positions_detail()

        pnl_map = {}
        ltp_map = {}
        for pos in positions:
            sym = pos.get("symbol", "").replace("NSE:", "").replace("-EQ", "")
            pnl_map[sym] = pos.get("pl", pos.get("unrealized_profit", 0))
            ltp_map[sym] = pos.get("ltp", 0)

        trades_to_close = []

        for trade in self._active_trades:
            symbol = trade["symbol"]
            if symbol in pnl_map:
                trade["pnl"] = pnl_map[symbol]
            if symbol in ltp_map and ltp_map[symbol] > 0:
                trade["ltp"] = ltp_map[symbol]

            # For INTRADAY_SL mode: actively close at target (entry + SL + target limit all on Fyers)
            if trade.get("order_mode") == "INTRADAY_SL" and trade["status"] == "OPEN":
                ltp = ltp_map.get(symbol, 0)
                target = trade.get("target", 0)
                side = trade.get("side", 1)

                if ltp > 0 and target > 0:
                    target_hit = (side == 1 and ltp >= target) or (side == -1 and ltp <= target)
                    if target_hit:
                        trades_to_close.append(trade)

            # For BO mode: track LTP vs target to properly label exit reason
            # (Fyers handles BO exits, but we need to distinguish TARGET_HIT vs SL_HIT)
            if trade.get("order_mode") == "BO" and trade["status"] == "OPEN":
                ltp = ltp_map.get(symbol, 0)
                target = trade.get("target", 0)
                side = trade.get("side", 1)
                if ltp > 0 and target > 0:
                    target_hit = (side == 1 and ltp >= target) or (side == -1 and ltp <= target)
                    if target_hit:
                        trade["_bo_target_reached"] = True

            # Check if SL was hit (position no longer exists on Fyers)
            if trade["status"] == "OPEN" and symbol not in pnl_map:
                # Grace period: newly placed orders may take time to appear in Fyers positions.
                # Don't mark as closed if placed less than 2 minutes ago.
                placed_at_str = trade.get("placed_at", "")
                if placed_at_str:
                    try:
                        placed_at = datetime.fromisoformat(placed_at_str)
                        age_seconds = (now_ist() - placed_at).total_seconds()
                        if age_seconds < 120:
                            self._log("INFO", f"{symbol} — not in positions yet (placed {age_seconds:.0f}s ago, waiting for settlement)")
                            continue
                    except (ValueError, TypeError):
                        pass

                # Position truly closed — determine exit reason and actual P&L
                trade["status"] = "CLOSED"
                trade["closed_at"] = now_ist().isoformat()
                if trade.get("_bo_target_reached"):
                    trade["exit_reason"] = "TARGET_HIT"
                    trade["exit_price"] = trade.get("target", 0)
                else:
                    trade["exit_reason"] = "SL_HIT"
                    # Use last known LTP as exit price (more accurate than theoretical SL)
                    last_ltp = trade.get("ltp", 0)
                    trade["exit_price"] = last_ltp if last_ltp > 0 else trade.get("stop_loss", 0)

                # Calculate P&L from actual prices if not already set by Fyers
                if trade["pnl"] == 0.0 and trade["exit_price"] > 0:
                    entry = trade.get("entry_price", 0)
                    exit_p = trade["exit_price"]
                    qty = trade.get("quantity", 0)
                    side = trade.get("side", 1)
                    trade["pnl"] = round((exit_p - entry) * qty if side == 1 else (entry - exit_p) * qty, 2)

                self._trade_history.append(trade)
                log_trade(trade, source="auto")
                self._log("INFO", f"{symbol} — position closed ({trade['exit_reason']}) P&L: ₹{trade['pnl']:.2f}")

        # Exit target-hit positions
        for trade in trades_to_close:
            self._exit_trade_at_target(trade)

        # Clean closed trades from active list
        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()

    def _exit_trade_at_target(self, trade: dict):
        """Close a position that has hit its target price. Cancel SL order first.

        SAFETY: Verifies the position still exists on Fyers before placing exit.
        If the SL already triggered (closing the position), placing an exit order
        would create an unwanted OPPOSITE position.
        """
        symbol = trade["symbol"]
        qty = trade["quantity"]
        side = trade["side"]
        close_side = -1 if side == 1 else 1

        self._log("ORDER", f"{symbol} — TARGET HIT! Closing position at target ₹{trade['target']}")

        # Cancel the SL order first
        sl_order_id = trade.get("sl_order_id", "")
        if sl_order_id:
            try:
                cancel_result = cancel_order(sl_order_id)
                if "error" not in cancel_result:
                    self._log("INFO", f"{symbol} — cancelled SL order (ID: {sl_order_id})")
                else:
                    self._log("WARN", f"{symbol} — SL cancel failed: {cancel_result.get('error', '')} — SL may have already triggered")
            except Exception as e:
                self._log("WARN", f"{symbol} — SL cancel exception: {e}")

        # SAFETY: Verify position still exists on Fyers before placing exit order.
        # If the SL triggered before we could cancel it, the position is already closed.
        # Placing an exit order would create an UNWANTED opposite position.
        open_symbols, positions = self._get_open_positions_detail()
        if symbol not in open_symbols:
            self._log("WARN", f"{symbol} — position no longer on Fyers (SL likely triggered). "
                       f"Skipping exit to avoid creating opposite position.")
            trade["status"] = "CLOSED"
            trade["closed_at"] = now_ist().isoformat()
            trade["exit_reason"] = "SL_HIT"
            # Use last known LTP as exit price, fallback to stop_loss
            last_ltp = trade.get("ltp", 0)
            trade["exit_price"] = last_ltp if last_ltp > 0 else trade.get("stop_loss", 0)
            # Calculate P&L from actual prices if Fyers didn't provide it
            pnl = trade.get("pnl", 0)
            if pnl == 0.0 and trade["exit_price"] > 0:
                entry = trade.get("entry_price", 0)
                exit_p = trade["exit_price"]
                qty_val = trade.get("quantity", 0)
                pnl = round((exit_p - entry) * qty_val if side == 1 else (entry - exit_p) * qty_val, 2)
                trade["pnl"] = pnl
            self._total_pnl += pnl; self._daily_realized_pnl += pnl
            self._trade_history.append(trade)
            log_trade(trade, source="auto")
            return

        # Verify the position direction matches what we expect.
        # A LONG trade (side=1) should have positive netQty, SHORT (side=-1) negative.
        for pos in positions:
            pos_sym = pos.get("symbol", "").replace("NSE:", "").replace("-EQ", "")
            if pos_sym == symbol:
                net_qty = pos.get("netQty", pos.get("qty", 0))
                expected_direction = side  # 1=long should be positive, -1=short should be negative
                actual_direction = 1 if net_qty > 0 else -1
                if actual_direction != expected_direction:
                    self._log("WARN", f"{symbol} — position direction mismatch! Expected {'LONG' if side==1 else 'SHORT'} "
                               f"but Fyers shows NetQty={net_qty}. Skipping exit to avoid error.")
                    return
                break

        # Place market exit order
        try:
            result = place_order(
                symbol=symbol,
                qty=qty,
                side=close_side,
                order_type=2,  # Market
                product_type="INTRADAY",
            )

            if "error" not in result:
                pnl = trade.get("pnl", 0)
                # If P&L is 0, calculate from last known LTP or target
                if pnl == 0.0:
                    last_ltp = trade.get("ltp", trade.get("target", 0))
                    entry = trade.get("entry_price", 0)
                    qty_val = trade.get("quantity", 0)
                    pnl = round((last_ltp - entry) * qty_val if side == 1 else (entry - last_ltp) * qty_val, 2)
                    trade["pnl"] = pnl
                self._total_pnl += pnl; self._daily_realized_pnl += pnl
                trade["status"] = "CLOSED"
                trade["closed_at"] = now_ist().isoformat()
                trade["exit_reason"] = "TARGET_HIT"
                # Use last known LTP as exit price (closer to actual fill than theoretical target)
                trade["exit_price"] = trade.get("ltp", trade.get("target", 0))
                self._trade_history.append(trade)
                log_trade(trade, source="auto")
                self._log("ORDER", f"{symbol} — closed at target. P&L: ₹{pnl:.2f}")
            else:
                self._log("ERROR", f"{symbol} — target exit failed: {result['error']}")
        except Exception as e:
            self._log("ERROR", f"{symbol} — target exit exception: {e}")

    def _get_open_positions_detail(self) -> tuple[set, list]:
        """Get open INTRADAY/BO position symbols and full position data from Fyers.
        Excludes CNC (swing) positions so they don't consume intraday slots."""
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
                    # Skip CNC (swing) positions — they don't count against intraday slots
                    prod = pos.get("productType", "")
                    if prod == "CNC":
                        continue

                    fyers_sym = pos.get("symbol", "")
                    plain = fyers_sym.replace("NSE:", "").replace("-EQ", "")
                    open_symbols.add(plain)
                    open_positions.append(pos)

            return open_symbols, open_positions

        except Exception as e:
            self._log("ERROR", f"Error fetching positions: {e}")
            return set(), []

    # ── Logging ───────────────────────────────────────────────────────────

    def _log(self, level: str, message: str):
        """Add a timestamped log entry."""
        self._logger.log(level, message)


# ── Singleton Instance ────────────────────────────────────────────────────
# Guard against duplicate instantiation (e.g., uvicorn double-import with reload=True).
# Multiple instances = multiple background threads = duplicate orders.

import sys as _sys
_module = _sys.modules.get(__name__)
if _module and hasattr(_module, 'auto_trader') and isinstance(getattr(_module, 'auto_trader'), AutoTrader):
    auto_trader = _module.auto_trader
else:
    auto_trader = AutoTrader()
