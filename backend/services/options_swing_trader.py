"""
Options Swing Trading Engine for IntraTrading.

Key differences from intraday options auto-trader:
  - Uses monthly expiry options (higher premium, more time value)
  - NO daily square-off — positions carry over days
  - NO 2 PM order cutoff
  - Exit: profit target, stop loss, or 2 days before expiry
  - Product type: MARGIN (not INTRADAY)
  - Max 2 open positions
  - Scans every 4 hours during market hours
  - State persists across days (no date filtering)
"""

import threading
import logging
import time
from datetime import datetime, timedelta, date
from typing import Optional

from utils.time_utils import now_ist, today_ist_str
from utils.state_manager import get_state_path, save_state, load_state
from utils.trader_log import TraderLogger
from utils.sleep_manager import SleepManager

from services.scanner import is_market_open
from services.options_scanner import scan_options
from services.options_client import get_ltp, get_ltp_batch, place_spread_orders, get_nearest_expiry
from services.trade_logger import log_trade
from services.fyers_client import is_authenticated
from strategies.options_registry import OPTIONS_STRATEGY_MAP
from config import (
    OPTIONS_SWING_MAX_POSITIONS,
    OPTIONS_SWING_SCAN_INTERVAL_SECONDS,
    OPTIONS_SWING_EXIT_DAYS_BEFORE_EXPIRY,
    OPTIONS_STRATEGY_PARAMS,
    OPTIONS_DAILY_LOSS_LIMIT_PCT,
)

logger = logging.getLogger(__name__)

STATE_FILE = get_state_path(".options_swing_trader_state.json")


class OptionsSwingTrader:
    """
    Live options swing trading engine.
    Places MARGIN spread orders via Fyers. Positions carry over days.
    Max 2 positions. No time-based square-off. Exits before expiry.
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._capital: float = 0.0
        self._underlyings: list[str] = []
        self._scan_interval: int = OPTIONS_SWING_SCAN_INTERVAL_SECONDS

        self._active_positions: list[dict] = []
        self._trade_history: list[dict] = []
        self._logger = TraderLogger("OptionsSwingTrader")
        self._sleep_mgr = SleepManager("OptionsSwingTrader")
        self._total_pnl: float = 0.0
        self._daily_realized_pnl: float = 0.0
        self._daily_loss_limit_hit: bool = False
        self._last_loss_reset_date: str = ""
        self._scan_count: int = 0
        self._order_count: int = 0
        self._started_at: Optional[str] = None
        self._next_scan_at: Optional[str] = None
        self._ltp_fail_counts: dict[str, int] = {}

        self._load_state()

    @property
    def is_running(self) -> bool:
        return self._running

    # ── State Persistence (cross-day) ─────────────────────────────────────

    def _save_state(self):
        state = {
            "running": self._running,
            "capital": self._capital,
            "underlyings": self._underlyings,
            "scan_interval": self._scan_interval,
            "active_positions": self._active_positions,
            "trade_history": self._trade_history,
            "total_pnl": self._total_pnl,
            "daily_realized_pnl": self._daily_realized_pnl,
            "daily_loss_limit_hit": self._daily_loss_limit_hit,
            "last_loss_reset_date": self._last_loss_reset_date,
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "started_at": self._started_at,
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "OptionsSwingTrader")

    def _load_state(self):
        state = load_state(STATE_FILE, "OptionsSwingTrader")
        if not state:
            return

        try:
            # No date filter — swing positions carry over days
            self._capital = state.get("capital", 0.0)
            self._underlyings = state.get("underlyings", [])
            self._scan_interval = state.get("scan_interval", OPTIONS_SWING_SCAN_INTERVAL_SECONDS)
            self._active_positions = state.get("active_positions", [])
            self._trade_history = state.get("trade_history", [])
            self._total_pnl = state.get("total_pnl", 0.0)
            self._daily_realized_pnl = state.get("daily_realized_pnl", 0.0)
            self._daily_loss_limit_hit = state.get("daily_loss_limit_hit", False)
            self._last_loss_reset_date = state.get("last_loss_reset_date", "")
            self._scan_count = state.get("scan_count", 0)
            self._order_count = state.get("order_count", 0)
            self._started_at = state.get("started_at")
            self._logger.entries = state.get("logs", [])

            was_running = state.get("running", False)

            if self._underlyings:
                self._log("RESTORE", f"Restored swing options state — {', '.join(self._underlyings)} | "
                          f"Active: {len(self._active_positions)} | P&L: {self._total_pnl:,.2f}")

                if was_running and is_market_open():
                    self._log("RESTORE", "Options swing trader was running — auto-resuming...")
                    self._running = True
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif was_running:
                    self._log("RESTORE", "Options swing trader was running but market closed — will resume when market opens")

        except Exception as e:
            logger.warning(f"[OptionsSwingTrader] Failed to load state: {e}")

    # ── Controls ──────────────────────────────────────────────────────────

    def start(self, capital: float, underlyings: list[str] = None) -> dict:
        with self._lock:
            if self._running:
                return {"error": "Options swing trader is already running"}

            if not is_market_open():
                now = now_ist()
                if now.weekday() >= 5:
                    return {"error": "Market is closed (Weekend). Options swing trading scans run during market hours."}
                return {"error": "Market is closed. Options swing trading scans run during market hours (9:15 AM - 3:30 PM IST)."}

            if not is_authenticated():
                return {"error": "Fyers is not authenticated. Please login first."}

            self._underlyings = underlyings or ["NIFTY", "BANKNIFTY"]
            self._capital = capital
            self._running = True
            self._active_positions = []
            self._trade_history = []
            self._logger.entries = []
            self._total_pnl = 0.0
            self._daily_realized_pnl = 0.0
            self._daily_loss_limit_hit = False
            self._last_loss_reset_date = today_ist_str()
            self._scan_count = 0
            self._order_count = 0
            self._started_at = now_ist().isoformat()
            self._next_scan_at = None
            self._ltp_fail_counts = {}

            self._sleep_mgr.prevent_sleep()
            self._log("START", f"Options swing trader STARTED — {', '.join(self._underlyings)} | Capital={capital:,.0f}")
            self._log("INFO", f"SWING MODE — Max {OPTIONS_SWING_MAX_POSITIONS} positions | MARGIN orders | "
                       f"Monthly expiry | Positions carry over days | Exit {OPTIONS_SWING_EXIT_DAYS_BEFORE_EXPIRY} days before expiry")

            self._save_state()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

            return {
                "status": "started",
                "mode": "options_swing",
                "underlyings": self._underlyings,
                "capital": capital,
                "started_at": self._started_at,
            }

    def stop(self) -> dict:
        with self._lock:
            if not self._running:
                return {"status": "already_stopped", "message": "Options swing trader is not running"}

            self._running = False
            self._log("STOP", "Options swing trader STOPPED by user (positions remain open)")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._sleep_mgr.allow_sleep()
        self._save_state()

        return {
            "status": "stopped",
            "total_scans": self._scan_count,
            "total_orders": self._order_count,
            "total_pnl": round(self._total_pnl, 2),
            "active_positions": len(self._active_positions),
        }

    def status(self) -> dict:
        return {
            "is_running": self._running,
            "mode": "options_swing",
            "underlyings": self._underlyings,
            "capital": self._capital,
            "scan_interval_minutes": self._scan_interval // 60,
            "started_at": self._started_at,
            "next_scan_at": self._next_scan_at,
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "total_pnl": round(self._total_pnl, 2),
            "daily_realized_pnl": round(self._daily_realized_pnl, 2),
            "daily_loss_limit_hit": self._daily_loss_limit_hit,
            "active_positions": self._active_positions,
            "trade_history": self._trade_history[-20:],
            "logs": self._logger.entries[-100:],
        }

    # ── Main Loop ─────────────────────────────────────────────────────────

    def _run_loop(self):
        self._log("INFO", "Background thread started")

        # Initial scan
        if is_market_open():
            self._execute_scan_cycle()

        while self._running:
            if not is_market_open():
                self._log("INFO", "Market closed — waiting for next open (positions preserved)")
                while self._running and not is_market_open():
                    time.sleep(60)
                if not self._running:
                    break
                self._log("INFO", "Market opened — resuming options swing scans")
                # Check expiry-based exits first thing in the morning
                self._check_expiry_exits()
                self._execute_scan_cycle()
                continue

            # Set next scan time
            next_scan = now_ist() + timedelta(seconds=self._scan_interval)
            self._next_scan_at = next_scan.isoformat()
            self._save_state()

            # Wait for next scan, checking positions every 60s
            elapsed = 0
            while self._running and elapsed < self._scan_interval:
                time.sleep(min(60, self._scan_interval - elapsed))
                elapsed += 60
                if not self._running:
                    break

                # Position monitoring during wait
                if is_market_open() and self._active_positions:
                    self._update_position_pnl()

            if not self._running:
                break

            if is_market_open():
                self._check_expiry_exits()
                self._execute_scan_cycle()

        self._sleep_mgr.allow_sleep()
        self._log("INFO", "Background thread exited")
        self._save_state()

    def _reset_daily_loss_if_new_day(self):
        """Reset daily realized P&L counter at start of each new trading day."""
        today = today_ist_str()
        if self._last_loss_reset_date != today:
            self._daily_realized_pnl = 0.0
            self._daily_loss_limit_hit = False
            self._last_loss_reset_date = today
            self._log("INFO", f"New trading day ({today}) — daily loss counter reset")
            self._save_state()

    def _check_daily_loss_limit(self) -> bool:
        """Return True if daily loss limit has been breached."""
        if self._capital <= 0:
            return False
        loss_limit = self._capital * (OPTIONS_DAILY_LOSS_LIMIT_PCT / 100.0)
        if self._daily_realized_pnl < 0 and abs(self._daily_realized_pnl) >= loss_limit:
            if not self._daily_loss_limit_hit:
                self._daily_loss_limit_hit = True
                self._log("ALERT", f"DAILY LOSS LIMIT BREACHED — Realized P&L: {self._daily_realized_pnl:,.2f} "
                          f"exceeds {OPTIONS_DAILY_LOSS_LIMIT_PCT}% of capital ({loss_limit:,.2f}). "
                          f"No new positions will be opened.")
                self._save_state()
            return True
        return False

    def _execute_scan_cycle(self):
        self._scan_count += 1
        self._log("SCAN", f"Options swing scan #{self._scan_count} — {', '.join(self._underlyings)}...")

        # Reset daily loss counter if new day (swing positions carry over)
        self._reset_daily_loss_if_new_day()

        # First: update existing positions
        self._update_position_pnl()

        # Daily loss limit circuit breaker
        if self._check_daily_loss_limit():
            self._log("INFO", "Daily loss limit active — skipping scan, monitoring existing positions only")
            return

        open_count = len(self._active_positions)
        if open_count >= OPTIONS_SWING_MAX_POSITIONS:
            self._log("INFO", f"Max swing positions reached ({open_count}/{OPTIONS_SWING_MAX_POSITIONS}) — monitoring only")
            return

        if not is_authenticated():
            self._log("ERROR", "Fyers authentication lost")
            return

        slots_available = OPTIONS_SWING_MAX_POSITIONS - open_count

        all_signals = []
        for underlying in self._underlyings:
            result = scan_options(underlying, self._capital, mode="swing")
            if "error" in result:
                self._log("WARN", f"Scan error for {underlying}: {result.get('error', '')}")
                continue

            signals = result.get("signals", [])
            regime = result.get("regime", {})
            scan_time = result.get("scan_time_seconds", 0)
            self._log("SCAN", f"  {underlying}: {len(signals)} signals | regime={regime.get('conviction', '?')} ({scan_time}s)")

            for sig in signals:
                sig["_underlying"] = underlying
            all_signals.extend(signals)

        self._log("SCAN", f"Options swing scan #{self._scan_count} complete — {len(all_signals)} signals")
        self._save_state()

        if not all_signals:
            return

        orders_placed = 0
        active_strategies = {p.get("strategy") + "_" + p.get("underlying", "") for p in self._active_positions}

        for signal in all_signals:
            if orders_placed >= slots_available:
                break

            sig_key = signal.get("strategy_id", "") + "_" + signal.get("_underlying", "")
            if sig_key in active_strategies:
                continue

            success = self._place_spread_order(signal)
            if success:
                orders_placed += 1
                active_strategies.add(sig_key)

    def _place_spread_order(self, signal: dict) -> bool:
        legs = signal.get("legs", [])
        underlying = signal.get("_underlying", signal.get("underlying", ""))
        strategy_id = signal.get("strategy_id", "")
        spread_type = signal.get("spread_type", strategy_id)
        net_premium = signal.get("net_premium", 0)
        max_risk = signal.get("max_risk", 0)
        max_reward = signal.get("max_reward", 0)
        lot_size = signal.get("lot_size", 0)
        num_lots = signal.get("num_lots", 1)
        expiry = signal.get("expiry", "")

        if not legs:
            self._log("WARN", f"{underlying} {strategy_id} — no legs in signal, skipping")
            return False

        self._log("ORDER", f"Placing SWING {spread_type} on {underlying} | "
                  f"Premium={net_premium:.2f} | Risk={max_risk:.2f} | Reward={max_reward:.2f} | "
                  f"Lots={num_lots} | Expiry={expiry}")

        try:
            result = place_spread_orders(legs, product_type="MARGIN")

            if "error" in result:
                self._log("ERROR", f"{underlying} {spread_type} — MARGIN order FAILED: {result['error']}")
                return False

            order_ids = result.get("order_ids", [])
            self._log("ORDER", f"{underlying} {spread_type} — MARGIN orders PLACED (IDs: {order_ids})")

            trade = {
                "underlying": underlying,
                "strategy": spread_type,
                "strategy_id": strategy_id,
                "legs": legs,
                "net_premium": net_premium,
                "max_risk": max_risk,
                "max_reward": max_reward,
                "lot_size": lot_size,
                "quantity": num_lots,
                "expiry": expiry,
                "order_ids": order_ids,
                "entry_time": now_ist().isoformat(),
                "placed_at": now_ist().isoformat(),
                "status": "OPEN",
                "pnl": 0.0,
                "current_net_premium": net_premium,
                "regime": signal.get("regime", ""),
                "strategy_type": signal.get("strategy_type", ""),
                "product_type": "MARGIN",
            }

            self._active_positions.append(trade)
            self._order_count += 1
            self._save_state()
            return True

        except Exception as e:
            self._log("ERROR", f"{underlying} {spread_type} — order exception: {e}")
            return False

    # ── Expiry-Based Exit ─────────────────────────────────────────────────

    def _check_expiry_exits(self):
        """Close positions that are within EXIT_DAYS_BEFORE_EXPIRY of expiry."""
        if not self._active_positions:
            return

        today = now_ist().date()
        trades_to_close = []

        for trade in self._active_positions:
            expiry_str = trade.get("expiry", "")
            if not expiry_str:
                continue

            try:
                if isinstance(expiry_str, str):
                    expiry_date = date.fromisoformat(expiry_str)
                else:
                    expiry_date = expiry_str

                days_to_expiry = (expiry_date - today).days
                if days_to_expiry <= OPTIONS_SWING_EXIT_DAYS_BEFORE_EXPIRY:
                    underlying = trade.get("underlying", "")
                    spread = trade.get("strategy", "")
                    self._log("ALERT", f"{underlying} {spread} — {days_to_expiry} days to expiry (threshold: {OPTIONS_SWING_EXIT_DAYS_BEFORE_EXPIRY}). Closing.")
                    trade["exit_reason"] = "EXPIRY_APPROACHING"
                    trades_to_close.append(trade)
            except (ValueError, TypeError) as e:
                logger.warning(f"[OptionsSwingTrader] Failed to parse expiry '{expiry_str}': {e}")

        for trade in trades_to_close:
            self._close_position(trade, trade.get("exit_reason", "EXPIRY_APPROACHING"))

        self._active_positions = [p for p in self._active_positions if p["status"] in ("OPEN", "CLOSE_FAILED")]
        self._save_state()

    # ── Position Monitoring ───────────────────────────────────────────────

    def _update_position_pnl(self):
        if not self._active_positions:
            return

        trades_to_close = []
        MAX_LTP_FAILURES = 3

        # Batch-fetch all LTPs in a single API call
        all_symbols = set()
        for trade in self._active_positions:
            if trade.get("status") == "CLOSE_FAILED":
                continue
            for leg in trade.get("legs", []):
                symbol = leg.get("symbol", "")
                if symbol:
                    all_symbols.add(symbol)

        batch_prices = {}
        if all_symbols:
            try:
                batch_prices = get_ltp_batch(list(all_symbols))
            except Exception as e:
                logger.warning(f"[OptionsSwingTrader] Batch LTP fetch failed: {e}")

        for trade in self._active_positions:
            if trade.get("status") == "CLOSE_FAILED":
                continue  # Skip positions stuck in CLOSE_FAILED

            legs = trade.get("legs", [])
            current_prices = {}
            ltp_failed_symbols = []
            for leg in legs:
                symbol = leg.get("symbol", "")
                ltp = batch_prices.get(symbol, 0)
                if ltp > 0:
                    current_prices[symbol] = ltp
                    self._ltp_fail_counts[symbol] = 0
                else:
                    ltp_failed_symbols.append(symbol)
                    self._ltp_fail_counts[symbol] = self._ltp_fail_counts.get(symbol, 0) + 1

            # Check for consecutive LTP failures
            for symbol in ltp_failed_symbols:
                fail_count = self._ltp_fail_counts.get(symbol, 0)
                if fail_count >= MAX_LTP_FAILURES:
                    underlying = trade.get("underlying", "")
                    spread = trade.get("strategy", "")
                    self._log("WARN", f"{underlying} {spread} — LTP fetch failed {fail_count}x for {symbol}. "
                              f"Assuming max risk for P&L calculation.")
                    max_risk = trade.get("max_risk", 0)
                    if max_risk > 0:
                        trade["pnl"] = round(-max_risk, 2)
                        trade["ltp_warning"] = f"LTP unavailable for {symbol} ({fail_count} failures). P&L set to max risk."

            if current_prices:
                pnl = self._calculate_pnl_from_prices(trade, current_prices)
                trade["pnl"] = round(pnl, 2)
            trade["current_prices"] = current_prices

            # Days held
            placed = trade.get("placed_at", "")
            if placed:
                try:
                    placed_date = datetime.fromisoformat(placed).date()
                    trade["days_held"] = (now_ist().date() - placed_date).days
                except Exception:
                    pass

            # Check exit via strategy
            strategy_id = trade.get("strategy_id", "")
            strategy = OPTIONS_STRATEGY_MAP.get(strategy_id)
            params = OPTIONS_STRATEGY_PARAMS.get(strategy_id, {})

            if strategy and current_prices:
                try:
                    exit_signal = strategy.check_exit(trade, current_prices, params)
                    if exit_signal:
                        trade["exit_reason"] = exit_signal.get("reason", "STRATEGY_EXIT")
                        trades_to_close.append(trade)
                        continue
                except Exception as e:
                    logger.warning(f"[OptionsSwingTrader] Exit check error for {strategy_id}: {e}")

        for trade in trades_to_close:
            reason = trade.get("exit_reason", "STRATEGY_EXIT")
            underlying = trade.get("underlying", "")
            spread = trade.get("strategy", "")
            pnl = trade.get("pnl", 0)
            self._log("ORDER", f"{underlying} {spread} — EXIT triggered ({reason}) | P&L: {pnl:,.2f}")
            self._close_position(trade, reason)

        self._active_positions = [p for p in self._active_positions if p["status"] in ("OPEN", "CLOSE_FAILED")]
        self._save_state()

    def _close_position(self, trade: dict, reason: str):
        legs = trade.get("legs", [])
        underlying = trade.get("underlying", "")
        spread_type = trade.get("strategy", "")

        # Build opposite legs for closing
        close_legs = []
        for leg in legs:
            close_leg = {
                "symbol": leg["symbol"],
                "qty": leg["qty"],
                "side": -1 if leg["side"] == 1 else 1,
            }
            close_legs.append(close_leg)

        close_succeeded = False
        close_error_msg = ""
        try:
            result = place_spread_orders(close_legs, product_type="MARGIN")
            if "error" in result:
                close_error_msg = result["error"]
                self._log("ERROR", f"{underlying} {spread_type} — close FAILED: {close_error_msg}. CLOSE MANUALLY!")
            else:
                close_succeeded = True
                self._log("ORDER", f"{underlying} {spread_type} — closed (IDs: {result.get('order_ids', [])})")
        except Exception as e:
            close_error_msg = str(e)
            self._log("ERROR", f"{underlying} {spread_type} — close exception: {e}. CLOSE MANUALLY!")

        pnl = self._calculate_position_pnl(trade)
        trade["pnl"] = round(pnl, 2)
        trade["closed_at"] = now_ist().isoformat()
        trade["exit_reason"] = reason

        if close_succeeded:
            trade["status"] = "CLOSED"
            self._total_pnl += pnl
            self._daily_realized_pnl += pnl
        else:
            trade["status"] = "CLOSE_FAILED"
            trade["close_error"] = close_error_msg
            self._log("ALERT", f"{underlying} {spread_type} — marked CLOSE_FAILED. Position may still be open in broker. MANUAL INTERVENTION REQUIRED!")

        self._trade_history.append(trade)
        log_trade(trade, source="options_swing")

        self._log("ORDER", f"{underlying} {spread_type} — P&L: {pnl:,.2f} | Status: {trade['status']} | Reason: {reason}")

    def _calculate_position_pnl(self, trade: dict) -> float:
        legs = trade.get("legs", [])
        current_prices = {}
        for leg in legs:
            symbol = leg.get("symbol", "")
            try:
                ltp = get_ltp(symbol)
                if ltp > 0:
                    current_prices[symbol] = ltp
            except Exception:
                pass
        return self._calculate_pnl_from_prices(trade, current_prices)

    def _calculate_pnl_from_prices(self, trade: dict, current_prices: dict) -> float:
        """
        Calculate P&L from current prices.
        Credit spread: profit when cost to close < premium received
        Debit spread: profit when current value > premium paid
        """
        legs = trade.get("legs", [])
        lot_size = trade.get("lot_size", 1)
        num_lots = trade.get("quantity", 1)
        strategy_type = trade.get("strategy_type", "")

        pnl_per_unit = 0.0
        for leg in legs:
            symbol = leg.get("symbol", "")
            side = leg.get("side", 0)
            entry_price = leg.get("price", 0)
            current_price = current_prices.get(symbol, entry_price)
            if side == -1:
                pnl_per_unit += (entry_price - current_price)
            else:
                pnl_per_unit += (current_price - entry_price)

        pnl = pnl_per_unit * lot_size * num_lots

        return round(pnl, 2)

    # ── Logging ───────────────────────────────────────────────────────────

    def _log(self, level: str, message: str):
        self._logger.log(level, message)


# ── Singleton Instance ────────────────────────────────────────────────────

options_swing_trader = OptionsSwingTrader()
