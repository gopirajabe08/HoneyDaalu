"""
Options Auto-Trading Engine for IntraTrading.

Rules:
  - Scans NIFTY/BANKNIFTY for spread setups during market hours
  - Places spread orders via Fyers options_client
  - Order window: 10:00 AM - 2:00 PM IST
  - Squares off all positions at 3:00 PM IST
  - Max 3 open spread positions at a time
  - Monitors positions every 60s via LTP
  - State persists to JSON (date-filtered — intraday only)
"""

import threading
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from utils.time_utils import IST, now_ist, is_before_time, is_past_time, today_ist_str
from utils.state_manager import get_state_path, save_state, load_state
from utils.trader_log import TraderLogger
from utils.sleep_manager import SleepManager

from services.scanner import is_market_open
from services.options_scanner import scan_options
from services.options_client import get_ltp, get_ltp_batch, place_spread_orders, place_option_order
from services.trade_logger import log_trade
from services.fyers_client import is_authenticated
from strategies.options_registry import OPTIONS_STRATEGY_MAP
from config import (
    OPTIONS_CAPITAL_PER_POSITION, OPTIONS_MIN_POSITIONS, OPTIONS_MAX_POSITIONS_CAP,
    OPTIONS_ORDER_START_HOUR, OPTIONS_ORDER_START_MIN,
    OPTIONS_ORDER_CUTOFF_HOUR, OPTIONS_ORDER_CUTOFF_MIN,
    OPTIONS_SQUAREOFF_HOUR, OPTIONS_SQUAREOFF_MIN,
    OPTIONS_POSITION_CHECK_INTERVAL,
    OPTIONS_STRATEGY_PARAMS,
    OPTIONS_DAILY_LOSS_LIMIT_PCT,
)

logger = logging.getLogger(__name__)

STATE_FILE = get_state_path(".options_auto_trader_state.json")
SCAN_INTERVAL = 900  # seconds — 15 minutes between new signal scans
LOSS_COOLDOWN = 1800  # seconds — 30 minutes cooldown after a losing trade before scanning again


def _is_before_order_start() -> bool:
    return is_before_time(OPTIONS_ORDER_START_HOUR, OPTIONS_ORDER_START_MIN)


def _is_past_order_cutoff() -> bool:
    return is_past_time(OPTIONS_ORDER_CUTOFF_HOUR, OPTIONS_ORDER_CUTOFF_MIN)


def _is_squareoff_time() -> bool:
    return is_past_time(OPTIONS_SQUAREOFF_HOUR, OPTIONS_SQUAREOFF_MIN)


class OptionsAutoTrader:
    """
    Live options auto-trading engine.
    Places spread orders on NIFTY/BANKNIFTY via Fyers.
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._capital: float = 0.0
        self._underlyings: list[str] = []
        self._max_positions: int = OPTIONS_MIN_POSITIONS

        self._active_positions: list[dict] = []
        self._trade_history: list[dict] = []
        self._logger = TraderLogger("OptionsAutoTrader")
        self._total_pnl: float = 0.0
        self._daily_realized_pnl: float = 0.0
        self._daily_loss_limit_hit: bool = False
        self._scan_count: int = 0
        self._order_count: int = 0
        self._started_at: Optional[str] = None
        self._squared_off: bool = False
        self._next_scan_at: Optional[str] = None
        self._last_loss_at: Optional[datetime] = None  # cooldown after losing trade
        self._ltp_fail_counts: dict[str, int] = {}  # symbol -> consecutive failure count
        self._sleep_mgr = SleepManager("OptionsAutoTrader")

        self._load_state()

    @property
    def is_running(self) -> bool:
        return self._running

    # ── State Persistence ──────────────────────────────────────────────────

    def _save_state(self):
        state = {
            "date": today_ist_str(),
            "running": self._running,
            "capital": self._capital,
            "underlyings": self._underlyings,
            "active_positions": self._active_positions,
            "trade_history": self._trade_history,
            "total_pnl": self._total_pnl,
            "daily_realized_pnl": self._daily_realized_pnl,
            "daily_loss_limit_hit": self._daily_loss_limit_hit,
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "started_at": self._started_at,
            "squared_off": self._squared_off,
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "OptionsAutoTrader")

    def _load_state(self):
        state = load_state(STATE_FILE, "OptionsAutoTrader")
        if not state:
            return

        try:
            today = today_ist_str()
            if state.get("date") != today:
                logger.info(f"[OptionsAutoTrader] State file is from {state.get('date')}, not today ({today}) — ignoring")
                return

            self._capital = state.get("capital", 0.0)
            self._underlyings = state.get("underlyings", [])
            self._active_positions = state.get("active_positions", [])
            self._trade_history = state.get("trade_history", [])
            self._total_pnl = state.get("total_pnl", 0.0)
            self._daily_realized_pnl = state.get("daily_realized_pnl", 0.0)
            self._daily_loss_limit_hit = state.get("daily_loss_limit_hit", False)
            self._scan_count = state.get("scan_count", 0)
            self._order_count = state.get("order_count", 0)
            self._started_at = state.get("started_at")
            self._squared_off = state.get("squared_off", False)
            self._logger.entries = state.get("logs", [])

            was_running = state.get("running", False)

            if self._underlyings:
                self._log("RESTORE", f"Restored today's state — {', '.join(self._underlyings)} | "
                          f"Scans: {self._scan_count} | Orders: {self._order_count} | P&L: {self._total_pnl:,.2f} | "
                          f"Active: {len(self._active_positions)} | History: {len(self._trade_history)}")

                if was_running and not self._squared_off and is_market_open():
                    self._log("RESTORE", "Options auto trader was running — auto-resuming...")
                    self._reconcile_positions()
                    self._running = True
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif was_running:
                    self._log("RESTORE", "Options auto trader was running but market closed — state preserved")

        except Exception as e:
            logger.warning(f"[OptionsAutoTrader] Failed to load state: {e}")

    # ── Controls ──────────────────────────────────────────────────────────

    def start(self, capital: float, underlyings: list[str] = None) -> dict:
        with self._lock:
            if self._running:
                return {"error": "Options auto trader is already running"}

            if not is_market_open():
                now = now_ist()
                if now.weekday() >= 5:
                    return {"error": "Market is closed (Weekend). Options trading runs during market hours (Mon-Fri 9:15 AM - 3:30 PM IST)."}
                return {"error": "Market is closed. Options trading runs during market hours (9:15 AM - 3:30 PM IST)."}

            if not is_authenticated():
                return {"error": "Fyers is not authenticated. Please login first."}

            if _is_past_order_cutoff():
                return {"error": "Cannot start after 2:00 PM IST. No new orders after 2:00 PM."}

            self._underlyings = underlyings or ["NIFTY", "BANKNIFTY"]
            self._capital = capital
            self._max_positions = max(OPTIONS_MIN_POSITIONS, min(int(capital // OPTIONS_CAPITAL_PER_POSITION), OPTIONS_MAX_POSITIONS_CAP))
            self._running = True
            self._active_positions = []
            self._trade_history = []
            self._logger.entries = []
            self._total_pnl = 0.0
            self._daily_realized_pnl = 0.0
            self._daily_loss_limit_hit = False
            self._scan_count = 0
            self._order_count = 0
            self._squared_off = False
            self._started_at = now_ist().isoformat()
            self._next_scan_at = None
            self._ltp_fail_counts = {}

            self._log("START", f"Options auto trader STARTED — {', '.join(self._underlyings)} | Capital=₹{capital:,.0f}")
            self._log("INFO", f"LIVE orders via Fyers | Order window: 10:00 AM - 2:00 PM | Square-off: 3:00 PM | Max positions: {self._max_positions} (auto: ₹{OPTIONS_CAPITAL_PER_POSITION:,.0f}/slot)")

            self._reconcile_positions()
            self._save_state()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

            self._sleep_mgr.prevent_sleep()
            self._log("INFO", f"Sleep prevention: {self._sleep_mgr.mode or 'unavailable'}")

            return {
                "status": "started",
                "mode": "options_auto",
                "underlyings": self._underlyings,
                "capital": capital,
                "started_at": self._started_at,
            }

    def stop(self) -> dict:
        with self._lock:
            if not self._running:
                return {"status": "already_stopped", "message": "Options auto trader is not running"}

            self._running = False
            self._log("STOP", "Options auto trader STOPPED by user")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._sleep_mgr.allow_sleep()
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
            "mode": "options_auto",
            "underlyings": self._underlyings,
            "capital": self._capital,
            "started_at": self._started_at,
            "next_scan_at": self._next_scan_at,
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "total_pnl": round(self._total_pnl, 2),
            "daily_realized_pnl": round(self._daily_realized_pnl, 2),
            "daily_loss_limit_hit": self._daily_loss_limit_hit,
            "active_positions": self._active_positions,
            "trade_history": self._trade_history[-20:],
            "squared_off": self._squared_off,
            "order_cutoff_passed": _is_past_order_cutoff(),
            "logs": self._logger.entries[-100:],
        }

    # ── Main Loop ─────────────────────────────────────────────────────────

    def _run_loop(self):
        self._log("INFO", "Background thread started")

        # Wait for order start time if before 10 AM
        if _is_before_order_start() and is_market_open():
            start_time = now_ist().replace(hour=OPTIONS_ORDER_START_HOUR, minute=OPTIONS_ORDER_START_MIN, second=0)
            wait_secs = int((start_time - now_ist()).total_seconds())
            self._log("INFO", f"Waiting until 10:00 AM IST to start scanning ({wait_secs}s)...")
            while self._running and _is_before_order_start():
                time.sleep(10)
            if not self._running:
                self._log("INFO", "Background thread exited (stopped during pre-market wait)")
                self._save_state()
                return

        # Initial scan
        if not _is_past_order_cutoff() and is_market_open():
            self._log("SCAN", "Executing initial scan")
            self._execute_scan_cycle()
        elif not is_market_open():
            self._log("INFO", "Market closed — stopping")
            self._running = False
            self._save_state()
            return

        # Monitor loop
        while self._running:
            # Square-off check
            if _is_squareoff_time() and not self._squared_off:
                self._log("ALERT", "3:00 PM IST reached — initiating square-off of all spread positions")
                self._square_off_all()
                self._squared_off = True
                self._log("STOP", "Options auto trader stopping after square-off")
                self._running = False
                break

            # Sleep in 1-second ticks for responsiveness
            for _ in range(OPTIONS_POSITION_CHECK_INTERVAL):
                if not self._running:
                    break
                time.sleep(1)
                if _is_squareoff_time() and not self._squared_off:
                    break

            if not self._running:
                break
            if _is_squareoff_time() and not self._squared_off:
                continue

            # Monitor positions: check P&L, exit triggers
            self._update_position_pnl()

            # Periodic scan for new positions (every 5 minutes, before cutoff)
            if not _is_past_order_cutoff() and len(self._active_positions) < self._max_positions:
                now = now_ist()
                next_scan = self._next_scan_at
                should_scan = False
                if next_scan is None:
                    should_scan = True
                else:
                    try:
                        next_dt = datetime.fromisoformat(next_scan)
                        if now >= next_dt:
                            should_scan = True
                    except (ValueError, TypeError):
                        should_scan = True

                if should_scan:
                    self._execute_scan_cycle()

        self._log("INFO", "Background thread exited")
        self._sleep_mgr.allow_sleep()
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

    def _in_loss_cooldown(self) -> bool:
        """Check if we're in 30-min cooldown after a losing trade."""
        if self._last_loss_at is None:
            return False
        elapsed = (now_ist() - self._last_loss_at).total_seconds()
        if elapsed < LOSS_COOLDOWN:
            remaining = int((LOSS_COOLDOWN - elapsed) / 60)
            self._log("INFO", f"Loss cooldown active — {remaining} min remaining before next scan")
            return True
        return False

    def _execute_scan_cycle(self):
        # Loss cooldown — wait 30 min after a losing trade
        if self._in_loss_cooldown():
            return

        self._scan_count += 1
        self._log("SCAN", f"Options scan #{self._scan_count} — {', '.join(self._underlyings)}...")

        # Daily loss limit circuit breaker
        if self._check_daily_loss_limit():
            self._log("INFO", "Daily loss limit active — skipping scan, monitoring existing positions only")
            self._next_scan_at = (now_ist() + timedelta(seconds=SCAN_INTERVAL)).isoformat()
            self._save_state()
            return

        open_count = len(self._active_positions)
        if open_count >= self._max_positions:
            self._log("INFO", f"Max positions reached ({open_count}/{self._max_positions}) — monitoring only")
            self._next_scan_at = (now_ist() + timedelta(seconds=SCAN_INTERVAL)).isoformat()
            self._save_state()
            return

        slots_available = self._max_positions - open_count

        all_signals = []
        for underlying in self._underlyings:
            result = scan_options(underlying, self._capital, mode="intraday")
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

        self._log("SCAN", f"Options scan #{self._scan_count} complete — {len(all_signals)} total signals")

        # Set next scan time
        self._next_scan_at = (now_ist() + timedelta(seconds=SCAN_INTERVAL)).isoformat()
        self._save_state()

        if not all_signals:
            return

        # Place orders for best signals
        orders_placed = 0
        active_strategies = {p.get("strategy") + "_" + p.get("underlying", "") for p in self._active_positions}

        for signal in all_signals:
            if orders_placed >= slots_available:
                self._log("INFO", f"All position slots filled ({self._max_positions})")
                break

            if _is_past_order_cutoff():
                self._log("INFO", "2:00 PM cutoff reached — stopping order placement")
                break

            # Avoid duplicate strategy+underlying combos
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

        self._log("ORDER", f"Placing {spread_type} on {underlying} | "
                  f"Premium={net_premium:.2f} | Risk={max_risk:.2f} | Reward={max_reward:.2f} | "
                  f"Lots={num_lots} | Expiry={expiry}")

        try:
            result = place_spread_orders(legs, product_type="INTRADAY", use_limit=True)

            if "error" in result:
                self._log("ERROR", f"{underlying} {spread_type} — order FAILED: {result['error']}")
                return False

            order_ids = result.get("order_ids", [])
            self._log("ORDER", f"{underlying} {spread_type} — orders PLACED (IDs: {order_ids})")

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
            }

            self._active_positions.append(trade)
            self._order_count += 1
            self._save_state()
            return True

        except Exception as e:
            self._log("ERROR", f"{underlying} {spread_type} — order exception: {e}")
            return False

    # ── Square Off ────────────────────────────────────────────────────────

    def _square_off_all(self):
        if not self._active_positions:
            self._log("INFO", "No options positions to square off")
            self._save_state()
            return

        self._log("ALERT", f"Squaring off {len(self._active_positions)} spread position(s)")

        for trade in self._active_positions:
            self._close_position(trade, "SQUARE_OFF")

        # Keep CLOSE_FAILED positions visible so they can be manually resolved
        failed = [p for p in self._active_positions if p.get("status") == "CLOSE_FAILED"]
        if failed:
            self._log("ALERT", f"{len(failed)} position(s) FAILED to close — they remain in active list for manual resolution")
        self._active_positions = failed
        self._log("ALERT", f"Square-off complete. Total P&L: {self._total_pnl:,.2f}")
        self._sleep_mgr.allow_sleep()
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
                "side": -1 if leg["side"] == 1 else 1,  # Reverse side
            }
            close_legs.append(close_leg)

        close_succeeded = False
        close_error_msg = ""
        try:
            result = place_spread_orders(close_legs, product_type="INTRADAY", use_limit=False)
            if "error" in result:
                close_error_msg = result["error"]
                self._log("ERROR", f"{underlying} {spread_type} — close FAILED: {close_error_msg}. CLOSE MANUALLY!")
            else:
                close_succeeded = True
                self._log("ORDER", f"{underlying} {spread_type} — closed (IDs: {result.get('order_ids', [])})")
        except Exception as e:
            close_error_msg = str(e)
            self._log("ERROR", f"{underlying} {spread_type} — close exception: {e}. CLOSE MANUALLY!")

        # Calculate final P&L from current prices
        pnl = self._calculate_position_pnl(trade)
        trade["pnl"] = pnl
        trade["closed_at"] = now_ist().isoformat()
        trade["exit_reason"] = reason

        if close_succeeded:
            trade["status"] = "CLOSED"
            self._total_pnl += pnl
            self._daily_realized_pnl += pnl
            # Set loss cooldown if this was a losing trade
            if pnl < 0:
                self._last_loss_at = now_ist()
                self._log("INFO", f"Loss cooldown activated — no new scans for {LOSS_COOLDOWN // 60} min")
        else:
            trade["status"] = "CLOSE_FAILED"
            trade["close_error"] = close_error_msg
            self._log("ALERT", f"{underlying} {spread_type} — marked CLOSE_FAILED. Position may still be open in broker. MANUAL INTERVENTION REQUIRED!")

        self._trade_history.append(trade)
        log_trade(trade, source="options_auto")

        self._log("SQUAREOFF", f"{underlying} {spread_type} — P&L: {pnl:,.2f} | Status: {trade['status']} | Reason: {reason}")

    # ── Position Monitoring ───────────────────────────────────────────────

    def _update_position_pnl(self):
        if not self._active_positions:
            return

        trades_to_close = []
        MAX_LTP_FAILURES = 3

        # Batch fetch all LTPs
        all_symbols = []
        for trade in self._active_positions:
            if trade.get("status") == "CLOSE_FAILED":
                continue
            for leg in trade.get("legs", []):
                sym = leg.get("symbol", "")
                if sym:
                    all_symbols.append(sym)

        batch_prices = get_ltp_batch(list(set(all_symbols))) if all_symbols else {}

        for trade in self._active_positions:
            if trade.get("status") == "CLOSE_FAILED":
                continue  # Skip positions stuck in CLOSE_FAILED

            # Use batch LTP results for each leg
            legs = trade.get("legs", [])
            current_prices = {}
            ltp_failed_symbols = []
            for leg in legs:
                symbol = leg.get("symbol", "")
                ltp = batch_prices.get(symbol, 0)
                if ltp > 0:
                    current_prices[symbol] = ltp
                    self._ltp_fail_counts[symbol] = 0  # Reset on success
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
                    # Use max_risk as worst-case P&L estimate
                    max_risk = trade.get("max_risk", 0)
                    if max_risk > 0:
                        trade["pnl"] = round(-max_risk, 2)
                        trade["ltp_warning"] = f"LTP unavailable for {symbol} ({fail_count} failures). P&L set to max risk."

            # Calculate current P&L (only if we have prices, otherwise keep max-risk estimate)
            if current_prices:
                pnl = self._calculate_pnl_from_prices(trade, current_prices)
                trade["pnl"] = round(pnl, 2)
            trade["current_prices"] = current_prices

            # Check exit conditions via strategy
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
                    logger.warning(f"[OptionsAutoTrader] Exit check error for {strategy_id}: {e}")

        # Close triggered positions
        for trade in trades_to_close:
            reason = trade.get("exit_reason", "STRATEGY_EXIT")
            underlying = trade.get("underlying", "")
            spread = trade.get("strategy", "")
            pnl = trade.get("pnl", 0)
            self._log("ORDER", f"{underlying} {spread} — EXIT triggered ({reason}) | P&L: {pnl:,.2f}")
            self._close_position(trade, reason)

        self._active_positions = [p for p in self._active_positions if p["status"] in ("OPEN", "CLOSE_FAILED")]
        self._save_state()

    def _calculate_position_pnl(self, trade: dict) -> float:
        """Calculate P&L by fetching current LTP for all legs."""
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
        Credit spread: (net_premium_entry - current_net_cost) * lot_size * num_lots
        Debit spread: (current_net_value - net_premium_entry) * lot_size * num_lots
        """
        legs = trade.get("legs", [])
        lot_size = trade.get("lot_size", 1)
        num_lots = trade.get("quantity", 1)
        strategy_type = trade.get("strategy_type", "")
        entry_premium = trade.get("net_premium", 0)

        # For each leg, calculate P&L based on side:
        #   SELL leg (side=-1): profit when premium drops → (entry_price - current_price)
        #   BUY leg (side=1):   profit when premium rises → (current_price - entry_price)
        pnl_per_unit = 0.0
        for leg in legs:
            symbol = leg.get("symbol", "")
            side = leg.get("side", 0)
            entry_price = leg.get("price", 0)
            current_price = current_prices.get(symbol, entry_price)
            if side == -1:  # SELL: profit from decay
                pnl_per_unit += (entry_price - current_price)
            else:  # BUY: profit from appreciation
                pnl_per_unit += (current_price - entry_price)

        pnl = pnl_per_unit * lot_size * num_lots

        return round(pnl, 2)

    # ── Position Reconciliation ──────────────────────────────────────────

    def _reconcile_positions(self):
        """Check Fyers for option positions not tracked in _active_positions.
        Logs warnings for any untracked positions found."""
        try:
            from services.fyers_client import get_positions
            result = get_positions()
            if not result or "error" in result:
                return

            fyers_positions = result.get("netPositions", result.get("positions", []))
            if not fyers_positions:
                return

            tracked_symbols = set()
            for pos in self._active_positions:
                for leg in pos.get("legs", []):
                    tracked_symbols.add(leg.get("symbol", ""))

            untracked = []
            for fp in fyers_positions:
                symbol = fp.get("symbol", "")
                qty = fp.get("netQty", fp.get("qty", 0))
                product = fp.get("productType", "")

                # Only check INTRADAY option positions
                if product != "INTRADAY" or qty == 0:
                    continue
                if symbol in tracked_symbols:
                    continue

                # Check if it's an options symbol (contains CE or PE)
                if "CE" not in symbol and "PE" not in symbol:
                    continue

                untracked.append({
                    "symbol": symbol,
                    "qty": qty,
                    "pnl": fp.get("pl", 0),
                    "ltp": fp.get("ltp", 0),
                })

            if untracked:
                for u in untracked:
                    self._log("ALERT", f"UNTRACKED option position found: {u['symbol']} qty={u['qty']} P&L={u['pnl']:.2f} — NOT managed by this trader. Check broker manually.")
                self._log("WARN", f"{len(untracked)} untracked option position(s) found in Fyers. These may be from a previous session or manual trades.")
        except Exception as e:
            self._log("WARN", f"Position reconciliation failed: {e}")

    # ── Logging ───────────────────────────────────────────────────────────

    def _log(self, level: str, message: str):
        self._logger.log(level, message)


# ── Singleton Instance ────────────────────────────────────────────────────

options_auto_trader = OptionsAutoTrader()
