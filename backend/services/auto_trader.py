"""
Auto-Trading Engine for LuckyNavi.

Rules:
  - Only starts during market hours (9:15 AM - 3:30 PM IST, weekdays)
  - Scans every 15 minutes
  - Places bracket orders automatically via broker
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
from services.broker_client import (
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
from services import telegram_notify
from config import (
    INTRADAY_ORDER_START_HOUR, INTRADAY_ORDER_START_MIN,
    INTRADAY_ORDER_CUTOFF_HOUR, INTRADAY_ORDER_CUTOFF_MIN,
    INTRADAY_SQUAREOFF_HOUR, INTRADAY_SQUAREOFF_MIN,
    INTRADAY_CAPITAL_PER_POSITION, INTRADAY_MIN_POSITIONS, INTRADAY_MAX_POSITIONS_CAP,
    INTRADAY_POSITION_CHECK_INTERVAL,
)

logger = logging.getLogger(__name__)

# Basic sector mapping for concentration limit (parity with paper_trader)
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
            "daily_realized_pnl": self._daily_realized_pnl,
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "started_at": self._started_at,
            "squared_off": self._squared_off,
            "margin_exhausted": getattr(self, '_margin_exhausted', False),
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
                # Clear any stale active trades from previous day
                self._active_trades = []
                self._trade_history = []
                return

            self._strategy_keys = state.get("strategy_keys", [])
            self._timeframes = state.get("timeframes", {})
            self._capital = state.get("capital", 0.0)
            self._active_trades = state.get("active_trades", [])
            # Fix any positions with missing SL from old state
            for t in self._active_trades:
                if (t.get("stop_loss") or 0) == 0 and t.get("entry_price", 0) > 0:
                    ep = t["entry_price"]
                    t["stop_loss"] = round(ep * (0.985 if t.get("side", 1) == 1 else 1.015), 2)
            self._trade_history = state.get("trade_history", [])
            self._total_pnl = state.get("total_pnl", 0.0)
            self._daily_realized_pnl = state.get("daily_realized_pnl", 0.0)
            self._scan_count = state.get("scan_count", 0)
            self._order_count = state.get("order_count", 0)
            self._started_at = state.get("started_at")
            self._squared_off = state.get("squared_off", False)
            self._margin_exhausted = state.get("margin_exhausted", False)
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
        Detect broker INTRADAY positions not tracked in active_trades.
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

                broker_sym = pos.get("symbol", "")
                # Skip options/futures — equity engine only tracks equity (-EQ) positions
                if "CE" in broker_sym or "PE" in broker_sym or "FUT" in broker_sym:
                    continue

                plain = broker_sym.replace("NSE:", "").replace("-EQ", "")
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

                # Calculate fallback SL (1.5% from entry) since original strategy SL is unknown
                if side == 1:  # BUY/LONG
                    recovered_sl = round(entry_price * 0.985, 2)
                else:  # SELL/SHORT
                    recovered_sl = round(entry_price * 1.015, 2)

                trade = {
                    "symbol": plain,
                    "signal_type": "BUY" if side == 1 else "SELL",
                    "side": side,
                    "entry_price": round(entry_price, 2),
                    "stop_loss": recovered_sl,
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
                self._log("WARN", f"Recovered orphaned position with calculated SL: {plain} {'LONG' if side==1 else 'SHORT'} x{abs(qty)} @ ₹{entry_price:.2f} | SL=₹{recovered_sl} (1.5% fallback) | P&L ₹{pnl:.2f}")

            # Fix any existing tracked positions that have SL=0 (from old state files)
            for t in self._active_trades:
                if (t.get("stop_loss") or 0) == 0 and t.get("entry_price", 0) > 0:
                    ep = t["entry_price"]
                    if t.get("side", 1) == 1:
                        t["stop_loss"] = round(ep * 0.985, 2)
                    else:
                        t["stop_loss"] = round(ep * 1.015, 2)
                    self._log("WARN", f"Fixed missing SL for {t['symbol']}: SL=₹{t['stop_loss']} (1.5% fallback)")

            if any(t.get("recovered") for t in self._active_trades):
                self._save_state()

            # If any positions were recovered, set margin exhausted to prevent new orders
            # Engine should only MONITOR recovered positions, not place new ones
            recovered_count = sum(1 for t in self._active_trades if t.get("recovered"))
            if recovered_count > 0:
                self._margin_exhausted = True
                self._log("WARN", f"{recovered_count} recovered positions — monitor only mode, no new orders")

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

            # Validate broker authentication
            if not is_authenticated():
                return {"error": "Broker is not authenticated. Please login first."}

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

            # Recover any broker positions not tracked (e.g. from previous run)
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
                self._log("ERROR", "Broker authentication lost — stopping auto-trader")
                self._running = False
                self._log("INFO", "Background thread exited")
                return

            self._log("SCAN", "10:30 AM — executing initial full scan to fill all slots")

            # Smart scan timing: wait for 15m candle close
            # Candle closes at XX:00, XX:15, XX:30, XX:45
            # Scanning mid-candle uses incomplete data → false signals
            now = now_ist()
            minutes = now.minute
            next_candle_close = 15 - (minutes % 15)
            if next_candle_close > 2 and next_candle_close < 15:
                self._log("INFO", f"Waiting {next_candle_close} min for 15m candle close before scanning")
                for _ in range(next_candle_close * 60):
                    if not self._running:
                        break
                    time.sleep(1)

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
            _monitor_tick += 1
            self._update_position_pnl(monitor_tick=_monitor_tick)

            # Broker health check every ~5 minutes (every 5th tick at 60s intervals)
            if _monitor_tick % 5 == 0:
                try:
                    if not is_authenticated():
                        _disconnect_ticks = getattr(self, '_broker_disconnect_ticks', 0) + 1
                        self._broker_disconnect_ticks = _disconnect_ticks
                        self._log("WARN", "Broker disconnected — attempting reconnect...")
                        try:
                            telegram_notify.broker_disconnected()
                            if _disconnect_ticks >= 2:
                                telegram_notify.broker_still_disconnected(_disconnect_ticks * 5)
                        except Exception:
                            pass
                        from services.broker_client import headless_login
                        result = headless_login()
                        if "error" in result:
                            self._log("ALERT", f"Broker reconnect FAILED: {result['error']} — positions at risk!")
                        else:
                            self._log("INFO", "Broker reconnected successfully")
                            self._broker_disconnect_ticks = 0
                            try:
                                telegram_notify.broker_reconnected()
                            except Exception:
                                pass
                    else:
                        self._broker_disconnect_ticks = 0
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

                        # Smart scan timing: wait for 15m candle close
                        now = now_ist()
                        minutes = now.minute
                        next_candle_close = 15 - (minutes % 15)
                        if next_candle_close > 2 and next_candle_close < 15:
                            self._log("INFO", f"Waiting {next_candle_close} min for 15m candle close before scanning")
                            for _ in range(next_candle_close * 60):
                                if not self._running:
                                    break
                                time.sleep(1)

                        self._execute_scan_cycle()
                        current_open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])
                    elif not is_authenticated():
                        self._log("ERROR", "Broker authentication lost — cannot scan for new trades")
                elif _is_past_order_cutoff():
                    self._log("INFO", "Past 2:00 PM — no new orders. Monitoring until square-off.")

            # Periodic re-scan: if slots available, re-scan every ~15 min to fill them
            elif current_open_count < self.max_open_positions and not _is_past_order_cutoff() and is_market_open():
                if _monitor_tick > 0 and _monitor_tick % 45 == 0:
                    slots = self.max_open_positions - current_open_count
                    self._log("SCAN", f"{slots} slots open — periodic re-scan")

                    # Smart scan timing: wait for 15m candle close
                    now = now_ist()
                    minutes = now.minute
                    next_candle_close = 15 - (minutes % 15)
                    if next_candle_close > 2 and next_candle_close < 15:
                        self._log("INFO", f"Waiting {next_candle_close} min for 15m candle close before scanning")
                        for _ in range(next_candle_close * 60):
                            if not self._running:
                                break
                            time.sleep(1)

                    self._execute_scan_cycle()
                    current_open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])

            prev_open_count = current_open_count

        self._log("INFO", "Background thread exited")

    def _check_drawdown_breaker(self) -> bool:
        """Check if multi-day drawdown exceeds 15% of capital."""
        try:
            from services.trade_logger import get_all_trades
            recent = get_all_trades(days=5)
            # Portfolio-level: check ALL live sources combined
            live_trades = [t for t in recent if t.get("source") in ("auto", "swing", "options_auto", "futures_auto")]
            if len(live_trades) >= 5:
                pnl = sum(t.get("pnl", 0) for t in live_trades)
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

    def _is_correlated(self, symbol: str) -> bool:
        """Check if symbol is in same sector/industry group as existing positions.
        Avoids picking stocks that move together — reduces portfolio correlation risk."""
        CORRELATION_GROUPS = {
            "banking": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK", "BANDHANBNK", "FEDERALBNK", "IDFCFIRSTB", "INDUSINDBK", "PNB"],
            "it": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "MPHASIS", "COFORGE", "PERSISTENT", "NAUKRI"],
            "pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "AUROPHARMA", "BIOCON", "LUPIN", "TORNTPHARM", "ALKEM", "IPCALAB"],
            "auto": ["TATAMOTORS", "M&M", "MARUTI", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "ASHOKLEY", "TVSMOTOR"],
            "energy": ["RELIANCE", "ONGC", "BPCL", "HINDPETRO", "IOC", "GAIL", "ADANIENT", "ADANIGREEN", "ADANIPOWER"],
            "metal": ["TATASTEEL", "HINDALCO", "JSWSTEEL", "VEDL", "NATIONALUM", "COALINDIA", "NMDC", "MOIL"],
            "fmcg": ["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO", "GODREJCP", "COLPAL"],
            "realty": ["DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "BRIGADE", "LODHA", "SOBHA"],
            "finance": ["BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "MUTHOOTFIN", "SHRIRAMFIN", "M&MFIN", "LICHSGFIN"],
        }

        # Find which group the new symbol belongs to
        symbol_group = None
        for group, members in CORRELATION_GROUPS.items():
            if symbol in members:
                symbol_group = group
                break

        if symbol_group is None:
            return False  # Unknown group = no correlation concern

        # Check if any active trade is in the same group
        for trade in self._active_trades:
            if trade.get("status") != "OPEN":
                continue
            trade_sym = trade.get("symbol", "")
            for group, members in CORRELATION_GROUPS.items():
                if trade_sym in members and group == symbol_group:
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

        # VIX-adjusted SL multiplier — wider SL in high VIX to avoid premature hits
        try:
            from services.equity_regime import detect_equity_regime as _detect_regime
            _regime_data = _detect_regime()
            _vix = _regime_data.get("components", {}).get("vix", 15)
            from config import VIX_SL_ADJUSTMENTS
            self._vix_atr_mult = 2.5  # default
            for level in ["high", "elevated", "normal", "low"]:
                adj = VIX_SL_ADJUSTMENTS[level]
                if _vix >= adj["threshold"] or level == "low":
                    self._vix_atr_mult = adj["atr_mult"]
                    break
            if self._vix_atr_mult != 2.5:
                self._log("VIX", f"VIX={_vix:.1f} — SL multiplier adjusted to {self._vix_atr_mult}x ATR")
        except Exception:
            self._vix_atr_mult = 2.5

        # Daily loss check
        if self._check_daily_loss_limit():
            self._log("INFO", "Daily loss limit active — skipping scan, monitoring only")
            self._update_position_pnl()
            return

        # Margin check — skip ALL orders if available funds are insufficient
        try:
            from services.broker_client import get_funds as _get_funds
            funds = _get_funds()
            for f in funds.get("fund_limit", []):
                if f.get("id") == 10:
                    avail = f.get("equityAmount", 0)
                    if avail < 10000:  # Less than ₹10K available = margin exhausted
                        self._margin_exhausted = True
                        self._log("WARN", f"Insufficient margin: ₹{avail:,.0f} available — skipping scan")
                        try:
                            telegram_notify.margin_warning(avail)
                        except Exception:
                            pass
                        self._update_position_pnl()
                        return
                    else:
                        self._margin_exhausted = False  # Reset if margin is available
                    break
        except Exception:
            pass  # Funds check failed, proceed cautiously

        self._scan_count += 1
        num_strategies = len(self._strategy_keys)
        self._log("SCAN", f"Scan #{self._scan_count} starting — {num_strategies} strateg{'y' if num_strategies == 1 else 'ies'}...")

        # Check open positions — use internal trades as authority (broker has settlement delay)
        internal_open = [t for t in self._active_trades if t["status"] == "OPEN"]
        open_symbols_broker, _ = self._get_open_positions_detail()
        # Combine both: internal OPEN trades + any broker positions not yet tracked
        open_symbols = {t["symbol"] for t in internal_open} | open_symbols_broker
        # Use MAX of internal count and broker count as the authority
        broker_open_count = len(open_symbols_broker)
        open_count = max(len(internal_open), broker_open_count)

        if open_count >= self.max_open_positions:
            self._log("INFO", f"Max positions reached ({open_count}/{self.max_open_positions}) — skipping order placement")
            self._margin_exhausted = True  # Prevent SL health check from spamming orders
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

            # High VIX → half position size (reduce risk in volatile markets)
            scan_capital = self._capital * 0.5 if vix > 20 else self._capital
            scan_result = run_scan(strategy_key, timeframe, scan_capital)

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
        # Pick the best signal from each strategy first (round-robin), then fill remaining
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
                self._log("INFO", f"Max 2 orders per scan — remaining {slots_available - orders_placed} slots will fill on next scan")
                break

            # Double-check time before each order
            if _is_past_order_cutoff():
                self._log("INFO", "2:00 PM cutoff reached during order placement — stopping")
                break

            symbol = signal.get("symbol", "")
            sig_strategy = signal.get("strategy", signal.get("_strategy", "unknown"))

            # Strategy concentration limit — don't put all eggs in one basket
            existing_for_strategy = sum(1 for t in self._active_trades if t.get("strategy") == sig_strategy)
            scan_for_strategy = strategy_count_this_scan.get(sig_strategy, 0)
            if existing_for_strategy + scan_for_strategy >= max_per_strategy:
                self._log("FILTER", f"{symbol} — skipping, {sig_strategy} already has {existing_for_strategy + scan_for_strategy} positions (max {max_per_strategy})")
                continue

            # Sector concentration check (parity with paper_trader)
            sym_sector = SECTOR_MAP.get(symbol, "other")
            sector_count = sum(1 for t in self._active_trades if SECTOR_MAP.get(t.get("symbol", ""), "other") == sym_sector)
            if sector_count >= MAX_PER_SECTOR and sym_sector != "other":
                self._log("FILTER", f"Sector limit: {symbol} ({sym_sector}) — already {sector_count} trades in sector")
                continue

            # Correlation check — avoid picking stocks that move together
            if self._is_correlated(symbol):
                self._log("FILTER", f"{symbol} — correlated with existing position, skipping")
                continue

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
            self._margin_exhausted = False
            success = self._place_order_for_signal(signal)
            if success:
                orders_placed += 1
                open_symbols.add(symbol)
                strategy_count_this_scan[sig_strategy] = strategy_count_this_scan.get(sig_strategy, 0) + 1
            elif self._margin_exhausted:
                self._log("WARN", "Margin exhausted — stopping order placement for this scan")
                break

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

        # VIX-adjust the SL and target if VIX is elevated
        vix_mult = getattr(self, '_vix_atr_mult', 2.5)
        if vix_mult > 2.5 and entry_price > 0 and stop_loss > 0:
            sl_distance = abs(entry_price - stop_loss)
            adjusted_sl_distance = sl_distance * (vix_mult / 2.5)
            target_distance = abs(target - entry_price)
            adjusted_target_distance = target_distance * (vix_mult / 2.5)
            if side == 1:  # BUY
                stop_loss = round(entry_price - adjusted_sl_distance, 2)
                target = round(entry_price + adjusted_target_distance, 2)
            else:  # SELL
                stop_loss = round(entry_price + adjusted_sl_distance, 2)
                target = round(entry_price - adjusted_target_distance, 2)
            self._log("VIX", f"{symbol} — SL/target widened by {vix_mult/2.5:.1f}x (VIX mult {vix_mult}): SL=₹{stop_loss} Target=₹{target}")

        # Net R:R filter after charges — skip trades where charges eat the profit
        # Uses original qty (before any test mode override) to evaluate trade quality
        # Approximate round-trip charges: brokerage + STT + exchange + GST + SEBI ≈ ₹65
        _charges = 65
        _net_profit = abs(target - entry_price) * qty - _charges
        _net_loss = abs(entry_price - stop_loss) * qty + _charges
        if _net_loss > 0:
            _net_rr = _net_profit / _net_loss
            if _net_rr < 1.5:
                self._log("SKIP", f"{symbol} — net R:R {_net_rr:.2f} after charges (need >= 1.5) | "
                          f"profit=₹{_net_profit:.0f} loss=₹{_net_loss:.0f} charges=₹{_charges}")
                return False

        # Phase 1 test mode: override qty to 1 share for safety
        from config import PHASE1_TEST_MODE, PHASE1_TEST_QTY
        if PHASE1_TEST_MODE:
            qty = PHASE1_TEST_QTY
            signal["quantity"] = qty

        capital_req = qty * entry_price

        self._log("ORDER", f"Placing {signal_type} order: {symbol} | Qty={qty} | Entry=₹{entry_price} | SL=₹{stop_loss} | Target=₹{target} | R:R={rr} | Capital=₹{capital_req:,.0f}")

        # Dynamic margin check — adjust qty to fit available funds
        try:
            from services.broker_client import get_funds as _check_funds
            funds_resp = _check_funds()
            avail = 0
            for f in funds_resp.get("fund_limit", []):
                if f.get("id") == 10:
                    avail = f.get("equityAmount", 0)
                    break
            # Use 60% of available funds max per position (leave buffer for SL margin)
            max_position_value = avail * 0.6
            max_qty = int(max_position_value / entry_price) if entry_price > 0 else 0
            if max_qty <= 0:
                self._log("WARN", f"{symbol} — Cannot afford even 1 share (available ₹{avail:,.0f}, price ₹{entry_price:.2f})")
                self._margin_exhausted = True
                return False
            if qty > max_qty:
                self._log("INFO", f"{symbol} — Reducing qty from {qty} to {max_qty} (margin: ₹{avail:,.0f}, 60% = ₹{max_position_value:,.0f})")
                qty = max_qty
                signal["quantity"] = qty
        except Exception:
            pass  # Funds check failed, proceed cautiously

        # Price validation: skip if LTP has moved >0.5% from signal entry
        # Also check bid-ask spread: skip if spread > 1% (illiquid, high hidden cost)
        try:
            quotes_res = get_quotes([symbol])
            if "d" in quotes_res and quotes_res["d"]:
                quote_v = quotes_res["d"][0].get("v", {})
                current_ltp = quote_v.get("lp", 0)
                if current_ltp > 0 and entry_price > 0:
                    price_diff_pct = abs(current_ltp - entry_price) / entry_price
                    if price_diff_pct > 0.005:
                        self._log("SKIP", f"{symbol} — Price moved too far from signal: LTP=₹{current_ltp:.2f} vs Entry=₹{entry_price:.2f} ({price_diff_pct*100:.2f}% drift)")
                        return False

                # Bid-ask spread check — skip if spread > 1%
                bid = quote_v.get("bid_price", quote_v.get("bp", 0))
                ask = quote_v.get("ask_price", quote_v.get("ap", quote_v.get("op", 0)))
                if bid > 0 and ask > 0 and ask > bid:
                    spread_pct = (ask - bid) / bid * 100
                    if spread_pct > 1.0:
                        self._log("SKIP", f"{symbol} — Bid-ask spread too wide: {spread_pct:.2f}% (bid=₹{bid:.2f} ask=₹{ask:.2f}) — skipping to avoid hidden cost")
                        return False
        except Exception as e:
            self._log("WARN", f"{symbol} — LTP/spread check failed ({e}), proceeding with order")

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
                error_msg = result['error'].lower()
                self._log("ERROR", f"{symbol} — order FAILED: {result['error']}")
                if "margin" in error_msg or "shortfall" in error_msg:
                    self._margin_exhausted = True
                return False

            order_mode = result.get("order_mode", "BO")
            order_id = result.get("id", result.get("entry_order_id", "")) or ""
            sl_order_id = result.get("sl_order_id", "")
            target_price = result.get("target_price", target)

            # Verify order actually went through (not rejected)
            if not order_id:
                self._log("ERROR", f"{symbol} — order returned no ID, likely rejected. Skipping.")
                return False

            if order_mode == "BO":
                self._log("ORDER", f"{symbol} — BO order PLACED (ID: {order_id})")
            else:
                self._log("ORDER", f"{symbol} — INTRADAY entry PLACED (ID: {order_id}) + SL-M (ID: {sl_order_id or 'N/A'})")

            # Wait and verify order actually filled on broker (not rejected)
            time.sleep(3)
            order_status = self._get_order_status(order_id)
            if order_status == "rejected":
                self._log("ERROR", f"{symbol} — order REJECTED by broker (ID: {order_id}). NOT tracking.")
                return False
            elif order_status == "cancelled":
                self._log("WARN", f"{symbol} — order CANCELLED on broker (ID: {order_id}). NOT tracking.")
                return False
            elif order_status == "pending":
                self._log("INFO", f"{symbol} — order PENDING (ID: {order_id}). Will verify on next check.")
            elif order_status == "filled":
                # Get actual fill price from orderbook
                actual_price = self._get_fill_price(order_id)
                if actual_price and actual_price > 0:
                    signal_price = signal.get("entry_price", 0)
                    slippage_pct = 0.0
                    if signal_price > 0:
                        slippage_pct = round((actual_price - signal_price) / signal_price * 100, 4)
                    self._log("ORDER", f"{symbol} — FILLED at ₹{actual_price} (signal ₹{signal_price}) | slippage {slippage_pct:+.3f}%")
                    if abs(slippage_pct) > 0.3:
                        self._log("WARN", f"{symbol} — HIGH SLIPPAGE: {slippage_pct:+.3f}% (fill ₹{actual_price} vs signal ₹{signal_price})")
                    entry_price = actual_price

            target_order_id = result.get("target_order_id", "")

            # Calculate slippage (signal price vs actual fill price)
            _signal_price = signal.get("entry_price", 0)
            _slippage_pct = 0.0
            if _signal_price > 0 and entry_price > 0:
                _slippage_pct = round((entry_price - _signal_price) / _signal_price * 100, 4)

            trade = {
                "symbol": symbol,
                "signal_type": signal_type,
                "side": side,
                "entry_price": entry_price,
                "signal_price": _signal_price,
                "slippage_pct": _slippage_pct,
                "stop_loss": stop_loss,
                "target": target_price,
                "quantity": qty,
                "order_id": order_id,
                "sl_order_id": sl_order_id,
                "target_order_id": target_order_id,
                "order_mode": order_mode,
                "risk_reward_ratio": rr,
                "capital_required": capital_req,
                "strategy": signal.get("_placed_via", signal.get("_strategy", "")),
                "timeframe": signal.get("_timeframe", ""),
                "placed_at": now_ist().isoformat(),
                "status": "OPEN",
                "pnl": 0.0,
            }

            # SEBI audit log — record every order placed
            try:
                from services.sebi_compliance import audit_order
                audit_order(
                    order_data={
                        "symbol": symbol,
                        "side": signal_type,
                        "qty": qty,
                        "entry_price": _signal_price,
                        "strategy": trade["strategy"],
                        "order_tag": order_id,
                    },
                    outcome="placed",
                    extra=f"fill=₹{entry_price} slippage={_slippage_pct:+.3f}%",
                )
            except Exception:
                pass

            self._active_trades.append(trade)
            self._order_count += 1
            self._save_state()

            # Telegram: trade placed notification
            try:
                telegram_notify.trade_placed(
                    symbol, signal_type, qty, entry_price, stop_loss,
                    signal.get("_placed_via", signal.get("_strategy", "")),
                    engine="Equity"
                )
            except Exception:
                pass

            return True

        except Exception as e:
            self._log("ERROR", f"{symbol} — order EXCEPTION: {e}")
            return False

    # ── Order Verification ─────────────────────────────────────────────

    def _get_order_status(self, order_id: str) -> str:
        """Check order status from broker orderbook. Returns: 'filled', 'pending', 'rejected', 'cancelled', 'unknown'."""
        try:
            from services.broker_client import get_orderbook
            orderbook = get_orderbook()
            orders = orderbook.get("orderBook", [])
            if not orders:
                data = orderbook.get("data", {})
                if isinstance(data, dict):
                    orders = data.get("orderBook", [])
            for order in orders:
                if order.get("id", "") == order_id:
                    status = order.get("status", 0)
                    # Broker: 1=cancelled, 2=traded/filled, 4=transit, 5=rejected, 6=pending
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
            from services.broker_client import get_orderbook
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

        # Step 1: Cancel all pending SL and target orders from INTRADAY_SL trades
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
                target_order_id = trade.get("target_order_id", "")
                if target_order_id:
                    try:
                        cancel_result = cancel_order(target_order_id)
                        if "error" not in cancel_result:
                            self._log("INFO", f"{trade['symbol']} — cancelled target order before square-off (ID: {target_order_id})")
                        else:
                            self._log("WARN", f"{trade['symbol']} — target cancel failed: {cancel_result.get('error', '')} (may already be filled)")
                    except Exception as e:
                        self._log("WARN", f"{trade['symbol']} — target cancel exception: {e}")

        # Step 2: Re-fetch positions after SL cancellations (SL may have triggered
        # between the first fetch and cancellation, changing position state)
        open_symbols, positions = self._get_open_positions_detail()

        # Step 3: Close all open positions with market orders
        for pos in positions:
            symbol_broker = pos.get("symbol", "")
            symbol_plain = symbol_broker.replace("NSE:", "").replace("-EQ", "")
            net_qty = pos.get("netQty", pos.get("qty", 0))
            pnl = pos.get("pl", pos.get("unrealized_profit", 0))

            if net_qty == 0:
                continue

            # Close position: sell if long (qty > 0), buy if short (qty < 0)
            close_side = -1 if net_qty > 0 else 1
            close_qty = abs(net_qty)

            self._log("SQUAREOFF", f"Closing {symbol_plain}: qty={net_qty} | P&L=₹{pnl:.2f} | Side={'SELL' if close_side == -1 else 'BUY'}")

            # Place exit with retry (max 3 attempts, parity with futures_auto_trader)
            SQUAREOFF_MAX_RETRIES = 3
            exit_success = False
            for attempt in range(SQUAREOFF_MAX_RETRIES):
                try:
                    result = place_order(
                        symbol=symbol_plain,
                        qty=close_qty,
                        side=close_side,
                        order_type=2,  # Market order
                        product_type="INTRADAY",
                    )

                    if "error" not in result:
                        exit_success = True
                        order_id = result.get("id", result.get("order_id", "unknown"))
                        self._log("SQUAREOFF", f"{symbol_plain} — squared off (ID: {order_id})")
                        break
                    self._log("WARN", f"{symbol_plain} — square-off attempt {attempt+1}/{SQUAREOFF_MAX_RETRIES} failed: {result.get('error', '')}")
                except Exception as e:
                    self._log("WARN", f"{symbol_plain} — square-off attempt {attempt+1}/{SQUAREOFF_MAX_RETRIES} exception: {e}")
                time.sleep(3)

            if exit_success:
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
                        # Telegram: trade closed (square-off)
                        try:
                            telegram_notify.trade_closed(
                                symbol_plain, trade.get("signal_type", "BUY"), pnl,
                                "SQUARE_OFF", engine="Equity"
                            )
                        except Exception:
                            pass
                        break
            else:
                self._log("ERROR", f"{symbol_plain} — SQUARE-OFF FAILED after {SQUAREOFF_MAX_RETRIES} retries! CLOSE MANUALLY!")

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

    def _update_position_pnl(self, monitor_tick: int = 0):
        """Refresh P&L for active trades, trail SL on winners, check target exits.

        Trailing SL for INTRADAY_SL mode: cancels old SL-M, places new one at trailed price.
        BO mode: broker manages SL on-exchange (no trailing for BO).
        """
        _, positions = self._get_open_positions_detail()

        # SL order health check every ~5 minutes (every 15th tick at ~20s intervals)
        # DISABLED when margin is exhausted to prevent rejection spam
        if monitor_tick > 0 and monitor_tick % 15 == 0 and not getattr(self, '_margin_exhausted', False):
            self._check_sl_order_health()

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

            # For INTRADAY_SL mode: actively close at target (entry + SL + target limit all on broker)
            if trade.get("order_mode") == "INTRADAY_SL" and trade["status"] == "OPEN":
                ltp = ltp_map.get(symbol, 0)
                target = trade.get("target", 0)
                side = trade.get("side", 1)

                if ltp > 0 and target > 0:
                    target_hit = (side == 1 and ltp >= target) or (side == -1 and ltp <= target)
                    if target_hit:
                        trades_to_close.append(trade)

            # For BO mode: track LTP vs target to properly label exit reason
            # (broker handles BO exits, but we need to distinguish TARGET_HIT vs SL_HIT)
            if trade.get("order_mode") == "BO" and trade["status"] == "OPEN":
                ltp = ltp_map.get(symbol, 0)
                target = trade.get("target", 0)
                side = trade.get("side", 1)
                if ltp > 0 and target > 0:
                    target_hit = (side == 1 and ltp >= target) or (side == -1 and ltp <= target)
                    if target_hit:
                        trade["_bo_target_reached"] = True

            # Check if SL was hit (position no longer exists on broker)
            if trade["status"] == "OPEN" and symbol not in pnl_map:
                # Grace period: newly placed orders may take time to appear in broker positions.
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

                # Cancel orphaned target/SL orders for the closed trade
                _target_oid = trade.get("target_order_id", "")
                _sl_oid = trade.get("sl_order_id", "")

                # Determine exit reason: check if target order was filled on exchange
                target_filled = False
                if _target_oid:
                    try:
                        target_status = self._get_order_status(_target_oid)
                        target_filled = (target_status == "filled")
                    except Exception:
                        pass

                if trade.get("_bo_target_reached") or target_filled:
                    trade["exit_reason"] = "TARGET_HIT"
                    trade["exit_price"] = trade.get("target", 0)
                    # Target hit — cancel the SL order
                    if _sl_oid:
                        try:
                            cancel_order(_sl_oid)
                            self._log("INFO", f"{symbol} — target filled, cancelled SL order (ID: {_sl_oid})")
                        except Exception:
                            pass
                else:
                    trade["exit_reason"] = "SL_HIT"
                    # Use last known LTP as exit price (more accurate than theoretical SL)
                    last_ltp = trade.get("ltp", 0)
                    trade["exit_price"] = last_ltp if last_ltp > 0 else trade.get("stop_loss", 0)
                    # SL hit — cancel the target order
                    if _target_oid:
                        try:
                            cancel_order(_target_oid)
                            self._log("INFO", f"{symbol} — SL hit, cancelled target order (ID: {_target_oid})")
                        except Exception:
                            pass

                # Calculate P&L from actual prices if not already set by broker
                if trade["pnl"] == 0.0 and trade["exit_price"] > 0:
                    entry = trade.get("entry_price", 0)
                    exit_p = trade["exit_price"]
                    qty = trade.get("quantity", 0)
                    side = trade.get("side", 1)
                    trade["pnl"] = round((exit_p - entry) * qty if side == 1 else (entry - exit_p) * qty, 2)

                self._trade_history.append(trade)
                log_trade(trade, source="auto")
                self._log("INFO", f"{symbol} — position closed ({trade['exit_reason']}) P&L: ₹{trade['pnl']:.2f}")

                # Telegram: trade closed notification
                try:
                    telegram_notify.trade_closed(
                        symbol, trade.get("signal_type", "BUY"), trade["pnl"],
                        trade["exit_reason"], engine="Equity"
                    )
                except Exception:
                    pass

        # ── Flash crash protection — emergency exit if any position drops >3% ──
        for trade in list(self._active_trades):
            if trade["status"] != "OPEN":
                continue
            entry = trade.get("entry_price", 0)
            ltp = trade.get("ltp", entry)
            if entry <= 0 or ltp <= 0:
                continue

            if trade.get("side", 1) == 1:  # BUY
                loss_pct = (entry - ltp) / entry
            else:  # SELL
                loss_pct = (ltp - entry) / entry

            if loss_pct >= 0.03:  # 3% loss
                self._log("ALERT", f"FLASH CRASH: {trade['symbol']} down {loss_pct*100:.1f}% — EMERGENCY EXIT")
                # Telegram: flash crash alert
                try:
                    telegram_notify.flash_crash(trade['symbol'], loss_pct * 100)
                except Exception:
                    pass
                # Cancel SL and target orders
                for oid_key in ["sl_order_id", "target_order_id"]:
                    oid = trade.get(oid_key, "")
                    if oid:
                        try:
                            cancel_order(oid)
                        except Exception:
                            pass
                # Place market exit order
                try:
                    exit_side = -1 if trade.get("side", 1) == 1 else 1
                    result = place_order(
                        symbol=trade["symbol"], qty=trade["quantity"], side=exit_side,
                        order_type=2, product_type="INTRADAY",
                    )
                    trade["status"] = "CLOSED"
                    trade["closed_at"] = now_ist().isoformat()
                    trade["exit_reason"] = "FLASH_CRASH"
                    trade["exit_price"] = ltp
                    trade["pnl"] = round(-loss_pct * entry * trade["quantity"], 2)
                    self._total_pnl += trade["pnl"]
                    self._daily_realized_pnl += trade["pnl"]
                    self._trade_history.append(trade)
                    log_trade(trade, source="auto")
                    self._log("ORDER", f"{trade['symbol']} — EMERGENCY EXIT placed (loss {loss_pct*100:.1f}%)")
                except Exception as e:
                    self._log("ERROR", f"{trade['symbol']} — emergency exit FAILED: {e}")

        # ── Trailing SL for INTRADAY_SL mode (every 3rd tick ~60s) ──
        # BO mode: broker manages SL on-exchange, no trailing.
        # INTRADAY_SL mode: cancel old SL-M, place new at trailed price.
        if monitor_tick > 0 and monitor_tick % 3 == 0:
            for trade in self._active_trades:
                if trade["status"] != "OPEN":
                    continue
                if trade.get("order_mode") != "INTRADAY_SL":
                    continue  # Only trail INTRADAY_SL trades (not BO)

                entry = trade.get("entry_price", 0)
                ltp = trade.get("ltp", entry)
                side = trade.get("side", 1)
                current_sl = trade.get("stop_loss", 0)
                symbol = trade["symbol"]

                if entry <= 0 or ltp <= 0:
                    continue

                # Store original SL on first pass
                if "original_sl" not in trade:
                    trade["original_sl"] = current_sl

                new_sl = current_sl

                # ── Risk-based levels ──────────────────────────────────────────
                # original_sl is stored at first pass so we always know 1R distance.
                original_sl = trade.get("original_sl", current_sl)
                risk = abs(entry - original_sl)  # 1x risk distance

                if side == 1:  # BUY / LONG
                    profit_pct = (ltp - entry) / entry
                    profit_abs = ltp - entry

                    if profit_pct >= 0.02:
                        # Trail to lock 50% of profit once 2% achieved
                        new_sl = round(entry + (ltp - entry) * 0.5, 2)
                    elif risk > 0 and profit_abs >= risk:
                        # Breakeven SL: profit reached 1x risk — move SL to entry (zero risk)
                        new_sl = round(entry * 1.001, 2)  # tiny tick above entry
                    elif profit_pct >= 0.01:
                        # Fallback: move to breakeven at 1% if risk not calculable
                        if risk == 0:
                            new_sl = round(entry * 1.001, 2)

                    if new_sl > current_sl:
                        old_sl_id = trade.get("sl_order_id", "")
                        if old_sl_id:
                            try:
                                cancel_order(old_sl_id)
                            except Exception:
                                pass
                        try:
                            sl_result = place_order(
                                symbol=symbol, qty=trade["quantity"], side=-1,
                                order_type=4, product_type="INTRADAY", stop_price=new_sl,
                            )
                            if "error" not in sl_result:
                                trade["stop_loss"] = new_sl
                                trade["sl_order_id"] = sl_result.get("id", sl_result.get("order_id", ""))
                                self._log("TRAIL", f"{symbol} — SL trailed: ₹{current_sl:.2f} → ₹{new_sl:.2f} (profit {profit_pct*100:.1f}% | risk=₹{risk:.2f})")
                                self._save_state()
                                # Telegram: only notify on breakeven move (risk-free = meaningful)
                                if not trade.get("_breakeven_notified") and new_sl >= entry * 0.999:
                                    trade["_breakeven_notified"] = True
                                    try:
                                        telegram_notify.sl_breakeven(symbol, entry, new_sl)
                                    except Exception:
                                        pass
                            else:
                                self._log("WARN", f"{symbol} — SL trail failed: {sl_result.get('error', '')}")
                        except Exception as e:
                            self._log("WARN", f"{symbol} — SL trail exception: {e}")

                else:  # SELL / SHORT
                    profit_pct = (entry - ltp) / entry
                    profit_abs = entry - ltp

                    if profit_pct >= 0.02:
                        new_sl = round(entry - (entry - ltp) * 0.5, 2)
                    elif risk > 0 and profit_abs >= risk:
                        # Breakeven SL: profit reached 1x risk — move SL to entry
                        new_sl = round(entry * 0.999, 2)  # tiny tick below entry
                    elif profit_pct >= 0.01:
                        if risk == 0:
                            new_sl = round(entry * 0.999, 2)

                    if current_sl == 0 or new_sl < current_sl:
                        old_sl_id = trade.get("sl_order_id", "")
                        if old_sl_id:
                            try:
                                cancel_order(old_sl_id)
                            except Exception:
                                pass
                        try:
                            sl_result = place_order(
                                symbol=symbol, qty=trade["quantity"], side=1,
                                order_type=4, product_type="INTRADAY", stop_price=new_sl,
                            )
                            if "error" not in sl_result:
                                trade["stop_loss"] = new_sl
                                trade["sl_order_id"] = sl_result.get("id", sl_result.get("order_id", ""))
                                self._log("TRAIL", f"{symbol} — SL trailed: ₹{current_sl:.2f} → ₹{new_sl:.2f} (profit {profit_pct*100:.1f}% | risk=₹{risk:.2f})")
                                self._save_state()
                                # Telegram: only notify on breakeven move (risk-free = meaningful)
                                if not trade.get("_breakeven_notified") and new_sl <= entry * 1.001:
                                    trade["_breakeven_notified"] = True
                                    try:
                                        telegram_notify.sl_breakeven(symbol, entry, new_sl)
                                    except Exception:
                                        pass
                            else:
                                self._log("WARN", f"{symbol} — SL trail failed: {sl_result.get('error', '')}")
                        except Exception as e:
                            self._log("WARN", f"{symbol} — SL trail exception: {e}")

        # ── Cancel orders pending > 60 seconds (every 3rd tick) ──
        if monitor_tick > 0 and monitor_tick % 3 == 0:
            for trade in self._active_trades:
                if trade["status"] != "OPEN":
                    continue
                order_id = trade.get("order_id", "")
                if not order_id or order_id == "recovered":
                    continue
                order_status = self._get_order_status(order_id)
                if order_status == "pending":
                    placed_at_str = trade.get("placed_at", "")
                    if placed_at_str:
                        try:
                            placed_time = datetime.fromisoformat(placed_at_str)
                            elapsed = (now_ist() - placed_time).total_seconds()
                            if elapsed > 60:
                                cancel_order(order_id)
                                trade["status"] = "CLOSED"
                                trade["exit_reason"] = "CANCELLED_PENDING"
                                trade["closed_at"] = now_ist().isoformat()
                                trade["pnl"] = 0.0
                                self._trade_history.append(trade)
                                self._log("WARN", f"{trade['symbol']} — cancelled pending entry order after {elapsed:.0f}s")
                        except Exception:
                            pass

        # Exit target-hit positions
        for trade in trades_to_close:
            self._exit_trade_at_target(trade)

        # Clean closed trades from active list
        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()

    def _check_sl_order_health(self):
        """Verify SL orders are still pending on broker for all active trades.

        If an SL order was cancelled/rejected (e.g. by exchange glitch), re-place it.
        Called every ~5 minutes (every 15th monitoring tick).
        """
        # Skip if margin is exhausted
        if getattr(self, '_margin_exhausted', False):
            return

        # Additional: check actual broker funds
        try:
            from services.broker_client import get_funds as _sl_check_funds
            funds_resp = _sl_check_funds()
            for f in funds_resp.get("fund_limit", []):
                if f.get("id") == 10:
                    if f.get("equityAmount", 0) < 5000:
                        self._margin_exhausted = True
                        self._log("WARN", "SL health check: insufficient funds, skipping")
                        return
                    break
        except Exception:
            pass

        active_with_sl = [t for t in self._active_trades
                          if t["status"] == "OPEN" and t.get("sl_order_id")]
        if not active_with_sl:
            return

        try:
            from services.broker_client import get_orderbook
            orderbook = get_orderbook()
            orders = orderbook.get("orderBook", [])
            if not orders:
                data = orderbook.get("data", {})
                if isinstance(data, dict):
                    orders = data.get("orderBook", [])

            # Build lookup: order_id -> status code
            order_status_map = {}
            for order in orders:
                oid = order.get("id", "")
                if oid:
                    order_status_map[oid] = order.get("status", 0)

            margin_failed = False
            for trade in active_with_sl:
                if margin_failed:
                    break  # Stop checking all SLs if margin is exhausted

                # Skip SL re-placement for recovered/unknown positions
                if trade.get("recovered") or trade.get("strategy") == "unknown":
                    continue

                sl_oid = trade.get("sl_order_id", "")
                if not sl_oid:
                    continue

                status = order_status_map.get(sl_oid, None)
                # Broker status: 1=cancelled, 2=traded/filled, 4=transit, 5=rejected, 6=pending
                if status is None:
                    # Order not found in orderbook — might be too old or system issue
                    continue
                if status in (4, 6):
                    # Still pending/transit — all good
                    continue
                if status == 2:
                    # SL was triggered (filled) — position monitoring will handle closure
                    continue

                # Status 1 (cancelled) or 5 (rejected) — SL is NOT protecting this position!
                symbol = trade["symbol"]
                status_label = "CANCELLED" if status == 1 else "REJECTED"

                # Only re-place if we haven't already failed due to margin
                sl_retry_key = f"_sl_retry_failed_{symbol}"
                if getattr(self, sl_retry_key, False):
                    continue  # Already tried and failed — don't spam broker

                self._log("WARN", f"{symbol} — SL order {sl_oid} is {status_label}! Re-placing SL...")

                # Re-place the SL order
                try:
                    sl_price = trade.get("stop_loss", 0)
                    qty = trade.get("quantity", 0)
                    side = trade.get("side", 1)
                    sl_side = -1 if side == 1 else 1  # opposite side for SL

                    if sl_price > 0 and qty > 0:
                        sl_result = place_order(
                            symbol=symbol,
                            qty=qty,
                            side=sl_side,
                            order_type=4,  # SL-M (stop-loss market)
                            product_type="INTRADAY",
                            stop_price=sl_price,
                        )
                        if "error" not in sl_result:
                            new_sl_id = sl_result.get("id", sl_result.get("order_id", ""))
                            trade["sl_order_id"] = new_sl_id
                            self._log("ORDER", f"{symbol} — SL re-placed successfully (new ID: {new_sl_id}) @ ₹{sl_price}")
                            self._save_state()
                            setattr(self, sl_retry_key, False)
                        else:
                            error_msg = sl_result.get('error', '').lower()
                            self._log("ERROR", f"{symbol} — SL re-place FAILED: {sl_result.get('error', '')}")
                            if "margin" in error_msg or "shortfall" in error_msg:
                                setattr(self, sl_retry_key, True)
                                margin_failed = True
                                self._margin_exhausted = True
                                self._log("WARN", f"Margin exhausted — stopping ALL SL re-place attempts")
                    else:
                        self._log("ERROR", f"{symbol} — cannot re-place SL: invalid price={sl_price} or qty={qty}")
                except Exception as e:
                    self._log("ERROR", f"{symbol} — SL re-place exception: {e}")

        except Exception as e:
            self._log("WARN", f"SL health check failed: {e}")

    def _exit_trade_at_target(self, trade: dict):
        """Close a position that has hit its target price. Cancel SL order first.

        SAFETY: Verifies the position still exists on broker before placing exit.
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

        # Cancel the target order (if it exists as a separate limit order)
        target_order_id = trade.get("target_order_id", "")
        if target_order_id:
            try:
                cancel_result = cancel_order(target_order_id)
                if "error" not in cancel_result:
                    self._log("INFO", f"{symbol} — cancelled target order (ID: {target_order_id})")
                else:
                    self._log("WARN", f"{symbol} — target cancel failed: {cancel_result.get('error', '')} — may already be filled")
            except Exception as e:
                self._log("WARN", f"{symbol} — target cancel exception: {e}")

        # SAFETY: Verify position still exists on broker before placing exit order.
        # If the SL triggered before we could cancel it, the position is already closed.
        # Placing an exit order would create an UNWANTED opposite position.
        open_symbols, positions = self._get_open_positions_detail()
        if symbol not in open_symbols:
            # Position already closed — determine if target or SL filled
            _tgt_filled = False
            if target_order_id:
                try:
                    _tgt_status = self._get_order_status(target_order_id)
                    _tgt_filled = (_tgt_status == "filled")
                except Exception:
                    pass
            exit_reason = "TARGET_HIT" if _tgt_filled else "SL_HIT"
            self._log("WARN", f"{symbol} — position no longer on broker ({exit_reason}). "
                       f"Skipping exit to avoid creating opposite position.")
            trade["status"] = "CLOSED"
            trade["closed_at"] = now_ist().isoformat()
            trade["exit_reason"] = exit_reason
            # Use target price if target filled, otherwise last LTP or stop_loss
            if _tgt_filled:
                trade["exit_price"] = trade.get("target", trade.get("ltp", 0))
            else:
                last_ltp = trade.get("ltp", 0)
                trade["exit_price"] = last_ltp if last_ltp > 0 else trade.get("stop_loss", 0)
            # Calculate P&L from actual prices if broker didn't provide it
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
                               f"but broker shows NetQty={net_qty}. Skipping exit to avoid error.")
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
        """Get open INTRADAY/BO position symbols and full position data from broker.
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

                    broker_sym = pos.get("symbol", "")
                    # Skip options/futures — equity engine only counts equity positions
                    if "CE" in broker_sym or "PE" in broker_sym or "FUT" in broker_sym:
                        continue

                    plain = broker_sym.replace("NSE:", "").replace("-EQ", "")
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
