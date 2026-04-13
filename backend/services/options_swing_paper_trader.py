"""
Options Swing Paper Trading Engine for LuckyNavi.

Mirrors the Options Swing Trader exactly but uses virtual positions.
Key differences from intraday options paper trader:
  - Uses monthly expiry options
  - NO daily square-off — positions carry over days
  - Exit: profit target, stop loss, or 2 days before expiry
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

from services.scanner import is_market_open
from services.options_scanner import scan_options
from services.options_client import get_ltp
from services.trade_logger import log_trade
from services.broker_client import is_authenticated
from strategies.options_registry import OPTIONS_STRATEGY_MAP
from config import (
    OPTIONS_SWING_MAX_POSITIONS,
    OPTIONS_SWING_SCAN_INTERVAL_SECONDS,
    OPTIONS_SWING_EXIT_DAYS_BEFORE_EXPIRY,
    OPTIONS_STRATEGY_PARAMS,
    OPTIONS_DAILY_LOSS_LIMIT_PCT,
)

logger = logging.getLogger(__name__)

STATE_FILE = get_state_path(".options_swing_paper_trader_state.json")


class OptionsSwingPaperTrader:
    """
    Virtual options swing trading engine.
    Same scan/signal logic as OptionsSwingTrader but no real orders.
    Positions carry over days. Max 2 positions. No time-based square-off.
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
        self._logger = TraderLogger("OptionsSwingPaper")
        self._total_pnl: float = 0.0
        self._daily_realized_pnl: float = 0.0
        self._daily_loss_limit_hit: bool = False
        self._last_loss_reset_date: str = ""
        self._scan_count: int = 0
        self._order_count: int = 0
        self._started_at: Optional[str] = None
        self._next_scan_at: Optional[str] = None
        self._next_order_id: int = 1

        self._load_state()

    @property
    def is_running(self) -> bool:
        return self._running

    # ── State Persistence (cross-day — no date filter) ───────────────────

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
            "next_order_id": self._next_order_id,
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "OptionsSwingPaper")

    def _load_state(self):
        state = load_state(STATE_FILE, "OptionsSwingPaper")
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
            self._next_order_id = state.get("next_order_id", 1)

            was_running = state.get("running", False)

            if self._underlyings:
                self._log("RESTORE", f"Restored swing options state — {', '.join(self._underlyings)} | "
                          f"Active: {len(self._active_positions)} | History: {len(self._trade_history)} | P&L: {self._total_pnl:,.2f}")

                if was_running and is_market_open():
                    self._log("RESTORE", "Options swing paper trader was running — auto-resuming...")
                    self._running = True
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif was_running:
                    self._log("RESTORE", "Options swing paper trader was running but market closed — will resume when market opens")

        except Exception as e:
            logger.warning(f"[OptionsSwingPaper] Failed to load state: {e}")

    # ── Controls ──────────────────────────────────────────────────────────

    def start(self, capital: float, underlyings: list[str] = None) -> dict:
        with self._lock:
            if self._running:
                return {"error": "Options swing paper trader is already running"}

            if not is_market_open():
                now = now_ist()
                if now.weekday() >= 5:
                    return {"error": "Market is closed (Weekend). Options swing paper trading scans run during market hours."}
                return {"error": "Market is closed. Options swing paper trading scans run during market hours (9:15 AM - 3:30 PM IST)."}

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
            self._next_order_id = 1

            self._log("START", f"Options swing paper trader STARTED — {', '.join(self._underlyings)} | Capital={capital:,.0f}")
            self._log("INFO", f"SWING PAPER MODE — Max {OPTIONS_SWING_MAX_POSITIONS} positions | Monthly expiry | "
                       f"No real orders | Positions carry over days | Exit {OPTIONS_SWING_EXIT_DAYS_BEFORE_EXPIRY} days before expiry")

            self._save_state()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

            return {
                "status": "started",
                "mode": "options_swing_paper",
                "underlyings": self._underlyings,
                "capital": capital,
                "started_at": self._started_at,
            }

    def stop(self) -> dict:
        with self._lock:
            if not self._running:
                return {"status": "already_stopped", "message": "Options swing paper trader is not running"}

            self._running = False
            self._log("STOP", "Options swing paper trader STOPPED by user")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

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
            "mode": "options_swing_paper",
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

    # ── Main Loop (no square-off, no order cutoff) ────────────────────────

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
                self._log("INFO", "Market opened — resuming options swing paper scans")
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
                          f"No new virtual positions will be opened.")
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

            success = self._place_virtual_spread(signal)
            if success:
                orders_placed += 1
                active_strategies.add(sig_key)

    def _place_virtual_spread(self, signal: dict) -> bool:
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

        # Simulate realistic slippage (0.1% worse entry on each leg's premium)
        for leg in legs:
            leg_price = leg.get("price", 0)
            if leg_price > 0:
                slippage = leg_price * 0.001
                leg_side = leg.get("side", 0)
                if leg_side == 1:  # BUY leg: pay slightly more
                    leg["price"] = round(leg_price + slippage, 2)
                elif leg_side == -1:  # SELL leg: receive slightly less
                    leg["price"] = round(leg_price - slippage, 2)

        # Estimate brokerage: ₹20 per leg × 2 (entry + exit)
        num_legs = len(legs)
        est_brokerage = round(20 * num_legs * 2, 2)  # ₹20 × legs × 2 (entry + exit)

        order_id = f"OPT-SWING-P-{self._next_order_id:04d}"
        self._next_order_id += 1

        legs_str = " | ".join(f"{'BUY' if l.get('side', 0) == 1 else 'SELL'} {l.get('symbol', '')}" for l in legs)
        self._log("ORDER", f"Virtual SWING {spread_type} on {underlying}: {legs_str}")
        self._log("ORDER", f"  Premium={net_premium:.2f} | Risk={max_risk:.2f} | Reward={max_reward:.2f} | Lots={num_lots} | Expiry={expiry} | Est charges=₹{est_brokerage}")

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
            "order_id": order_id,
            "entry_time": now_ist().isoformat(),
            "placed_at": now_ist().isoformat(),
            "status": "OPEN",
            "pnl": 0.0,
            "current_net_premium": net_premium,
            "regime": signal.get("regime", ""),
            "strategy_type": signal.get("strategy_type", ""),
            "product_type": "MARGIN",
            "est_brokerage": est_brokerage,
        }

        self._active_positions.append(trade)
        self._order_count += 1
        self._save_state()
        return True

    # ── Expiry-Based Exit ─────────────────────────────────────────────────

    def _check_expiry_exits(self):
        """Close virtual positions that are within EXIT_DAYS_BEFORE_EXPIRY of expiry."""
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
                    self._log("ALERT", f"{underlying} {spread} — {days_to_expiry} days to expiry (threshold: {OPTIONS_SWING_EXIT_DAYS_BEFORE_EXPIRY}). Closing virtual position.")
                    trade["exit_reason"] = "EXPIRY_APPROACHING"
                    trades_to_close.append(trade)
            except (ValueError, TypeError) as e:
                logger.warning(f"[OptionsSwingPaper] Failed to parse expiry '{expiry_str}': {e}")

        for trade in trades_to_close:
            self._close_virtual_position(trade, trade.get("exit_reason", "EXPIRY_APPROACHING"))

        self._active_positions = [p for p in self._active_positions if p["status"] == "OPEN"]
        self._save_state()

    # ── Position Monitoring ───────────────────────────────────────────────

    def _update_position_pnl(self):
        if not self._active_positions:
            return

        trades_to_close = []

        for trade in self._active_positions:
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
                    logger.warning(f"[OptionsSwingPaper] Exit check error for {strategy_id}: {e}")

        for trade in trades_to_close:
            reason = trade.get("exit_reason", "STRATEGY_EXIT")
            underlying = trade.get("underlying", "")
            spread = trade.get("strategy", "")
            self._close_virtual_position(trade, reason)

        self._active_positions = [p for p in self._active_positions if p["status"] == "OPEN"]
        self._save_state()

    def _close_virtual_position(self, trade: dict, reason: str):
        """Close a virtual position (no real orders)."""
        gross_pnl = self._calculate_position_pnl(trade)
        brokerage = trade.get("est_brokerage", 0)
        net_pnl = round(gross_pnl - brokerage, 2)
        trade["pnl"] = net_pnl
        trade["gross_pnl"] = round(gross_pnl, 2)
        trade["charges"] = brokerage
        trade["status"] = "CLOSED"
        trade["closed_at"] = now_ist().isoformat()
        trade["exit_reason"] = reason

        self._total_pnl += net_pnl
        self._daily_realized_pnl += net_pnl
        self._trade_history.append(trade)
        log_trade(trade, source="options_swing_paper")

        underlying = trade.get("underlying", "")
        spread = trade.get("strategy", "")
        self._log("ORDER", f"{underlying} {spread} — virtual close | Net P&L: {net_pnl:,.2f} (charges: ₹{brokerage}) | Reason: {reason}")

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

options_swing_paper_trader = OptionsSwingPaperTrader()
