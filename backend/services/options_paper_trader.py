"""
Options Paper Trading Engine for IntraTrading.

Mirrors the Options Auto-Trader exactly but uses virtual positions instead of real Fyers orders.
Same rules: 10 AM - 2 PM order window, max 3 positions, square-off 3 PM.
"""

import threading
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from utils.time_utils import IST, now_ist, is_before_time, is_past_time, today_ist_str
from utils.state_manager import get_state_path, save_state, load_state
from utils.trader_log import TraderLogger

from services.scanner import is_market_open
from services.options_scanner import scan_options
from services.options_client import get_ltp
from services.trade_logger import log_trade
from services.fyers_client import is_authenticated
from strategies.options_registry import OPTIONS_STRATEGY_MAP
from config import (
    OPTIONS_MAX_POSITIONS,
    OPTIONS_ORDER_START_HOUR, OPTIONS_ORDER_START_MIN,
    OPTIONS_ORDER_CUTOFF_HOUR, OPTIONS_ORDER_CUTOFF_MIN,
    OPTIONS_SQUAREOFF_HOUR, OPTIONS_SQUAREOFF_MIN,
    OPTIONS_POSITION_CHECK_INTERVAL,
    OPTIONS_STRATEGY_PARAMS,
    OPTIONS_DAILY_LOSS_LIMIT_PCT,
)

logger = logging.getLogger(__name__)

STATE_FILE = get_state_path(".options_paper_trader_state.json")
SCAN_INTERVAL = 900  # seconds — 15 minutes between new signal scans
LOSS_COOLDOWN = 1800  # seconds — 30 minutes cooldown after a losing trade


def _is_before_order_start() -> bool:
    return is_before_time(OPTIONS_ORDER_START_HOUR, OPTIONS_ORDER_START_MIN)


def _is_past_order_cutoff() -> bool:
    return is_past_time(OPTIONS_ORDER_CUTOFF_HOUR, OPTIONS_ORDER_CUTOFF_MIN)


def _is_squareoff_time() -> bool:
    return is_past_time(OPTIONS_SQUAREOFF_HOUR, OPTIONS_SQUAREOFF_MIN)


class OptionsPaperTrader:
    """
    Virtual options trading engine.
    Same logic as OptionsAutoTrader but no real orders — tracks virtual positions
    and uses Fyers quotes for live LTP.
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._capital: float = 0.0
        self._underlyings: list[str] = []

        self._active_positions: list[dict] = []
        self._trade_history: list[dict] = []
        self._logger = TraderLogger("OptionsPaperTrader")
        self._total_pnl: float = 0.0
        self._daily_realized_pnl: float = 0.0
        self._daily_loss_limit_hit: bool = False
        self._scan_count: int = 0
        self._order_count: int = 0
        self._started_at: Optional[str] = None
        self._squared_off: bool = False
        self._next_scan_at: Optional[str] = None
        self._last_loss_at: Optional[datetime] = None
        self._next_order_id: int = 1

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
            "next_order_id": self._next_order_id,
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "OptionsPaperTrader")

    def _load_state(self):
        state = load_state(STATE_FILE, "OptionsPaperTrader")
        if not state:
            return

        try:
            today = today_ist_str()
            if state.get("date") != today:
                logger.info(f"[OptionsPaperTrader] State file is from {state.get('date')}, not today ({today}) — ignoring")
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
            self._next_order_id = state.get("next_order_id", 1)

            was_running = state.get("running", False)

            if self._underlyings:
                self._log("RESTORE", f"Restored today's state — {', '.join(self._underlyings)} | "
                          f"Scans: {self._scan_count} | Orders: {self._order_count} | P&L: {self._total_pnl:,.2f} | "
                          f"Active: {len(self._active_positions)} | History: {len(self._trade_history)}")

                if was_running and not self._squared_off and is_market_open() and not _is_past_order_cutoff():
                    self._log("RESTORE", "Options paper trader was running before restart — auto-resuming...")
                    self._running = True
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif was_running and not self._squared_off and is_market_open():
                    self._log("RESTORE", "Options paper trader was running but past order cutoff — monitoring positions only")
                    self._running = True
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif was_running:
                    self._log("RESTORE", "Options paper trader was running but market closed — state preserved")

        except Exception as e:
            logger.warning(f"[OptionsPaperTrader] Failed to load state: {e}")

    # ── Controls ──────────────────────────────────────────────────────────

    def start(self, capital: float, underlyings: list[str] = None) -> dict:
        with self._lock:
            if self._running:
                return {"error": "Options paper trader is already running"}

            if not is_market_open():
                now = now_ist()
                if now.weekday() >= 5:
                    return {"error": "Market is closed (Weekend). Options paper trading runs during market hours (Mon-Fri 9:15 AM - 3:30 PM IST)."}
                return {"error": "Market is closed. Options paper trading runs during market hours (9:15 AM - 3:30 PM IST)."}

            if _is_past_order_cutoff():
                return {"error": "Cannot start after 2:00 PM IST. No new virtual orders after 2:00 PM."}

            self._underlyings = underlyings or ["NIFTY", "BANKNIFTY"]
            self._capital = capital
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
            self._next_order_id = 1

            self._log("START", f"Options paper trader STARTED — {', '.join(self._underlyings)} | Capital={capital:,.0f}")
            self._log("INFO", f"Virtual trading — NO real orders | Order window: 10:00 AM - 2:00 PM | Square-off: 3:00 PM | Max positions: {OPTIONS_MAX_POSITIONS}")

            self._save_state()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

            return {
                "status": "started",
                "mode": "options_paper",
                "underlyings": self._underlyings,
                "capital": capital,
                "started_at": self._started_at,
            }

    def stop(self) -> dict:
        with self._lock:
            if not self._running:
                return {"status": "already_stopped", "message": "Options paper trader is not running"}

            self._running = False
            self._log("STOP", "Options paper trader STOPPED by user")

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
            "mode": "options_paper",
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
            self._log("INFO", "Waiting until 10:00 AM IST to start scanning...")
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
                self._log("ALERT", "3:00 PM IST reached — initiating virtual square-off")
                self._square_off_all()
                self._squared_off = True
                self._log("STOP", "Options paper trader stopping after square-off")
                self._running = False
                break

            # Sleep in 1-second ticks
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

            # Monitor positions
            self._update_position_pnl()

            # Periodic scan
            if not _is_past_order_cutoff() and len(self._active_positions) < OPTIONS_MAX_POSITIONS:
                now = now_ist()
                should_scan = False
                if self._next_scan_at is None:
                    should_scan = True
                else:
                    try:
                        next_dt = datetime.fromisoformat(self._next_scan_at)
                        if now >= next_dt:
                            should_scan = True
                    except (ValueError, TypeError):
                        should_scan = True

                if should_scan:
                    self._execute_scan_cycle()

        self._log("INFO", "Background thread exited")
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

    def _in_loss_cooldown(self) -> bool:
        if self._last_loss_at is None:
            return False
        elapsed = (now_ist() - self._last_loss_at).total_seconds()
        if elapsed < LOSS_COOLDOWN:
            remaining = int((LOSS_COOLDOWN - elapsed) / 60)
            self._log("INFO", f"Loss cooldown — {remaining} min remaining")
            return True
        return False

    def _execute_scan_cycle(self):
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
        if open_count >= OPTIONS_MAX_POSITIONS:
            self._log("INFO", f"Max positions reached ({open_count}/{OPTIONS_MAX_POSITIONS}) — monitoring only")
            self._next_scan_at = (now_ist() + timedelta(seconds=SCAN_INTERVAL)).isoformat()
            self._save_state()
            return

        slots_available = OPTIONS_MAX_POSITIONS - open_count

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
        self._next_scan_at = (now_ist() + timedelta(seconds=SCAN_INTERVAL)).isoformat()
        self._save_state()

        if not all_signals:
            return

        orders_placed = 0
        active_strategies = {p.get("strategy") + "_" + p.get("underlying", "") for p in self._active_positions}

        for signal in all_signals:
            if orders_placed >= slots_available:
                self._log("INFO", f"All position slots filled ({OPTIONS_MAX_POSITIONS})")
                break

            if _is_past_order_cutoff():
                self._log("INFO", "2:00 PM cutoff reached — stopping virtual order placement")
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

        order_id = f"OPT-PAPER-{self._next_order_id:04d}"
        self._next_order_id += 1

        legs_str = " | ".join(f"{'BUY' if l.get('side', 0) == 1 else 'SELL'} {l.get('symbol', '')}" for l in legs)
        self._log("ORDER", f"Virtual {spread_type} on {underlying}: {legs_str}")
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
            "est_brokerage": est_brokerage,
        }

        self._active_positions.append(trade)
        self._order_count += 1
        self._save_state()
        return True

    # ── Square Off ────────────────────────────────────────────────────────

    def _square_off_all(self):
        if not self._active_positions:
            self._log("INFO", "No virtual options positions to square off")
            self._save_state()
            return

        self._log("ALERT", f"Squaring off {len(self._active_positions)} virtual spread position(s)")

        for trade in self._active_positions:
            # Calculate final P&L from current LTP
            gross_pnl = self._calculate_position_pnl(trade)
            brokerage = trade.get("est_brokerage", 0)
            net_pnl = round(gross_pnl - brokerage, 2)
            trade["pnl"] = net_pnl
            trade["gross_pnl"] = round(gross_pnl, 2)
            trade["charges"] = brokerage
            trade["status"] = "CLOSED"
            trade["closed_at"] = now_ist().isoformat()
            trade["exit_reason"] = "SQUARE_OFF"

            self._total_pnl += net_pnl
            self._daily_realized_pnl += net_pnl
            self._trade_history.append(trade)
            log_trade(trade, source="options_paper")

            underlying = trade.get("underlying", "")
            spread = trade.get("strategy", "")
            self._log("SQUAREOFF", f"{underlying} {spread} — closed | Net P&L: {net_pnl:,.2f} (charges: ₹{brokerage})")

        self._active_positions = []
        self._log("ALERT", f"Virtual square-off complete. Total P&L: {self._total_pnl:,.2f}")
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
                    logger.warning(f"[OptionsPaperTrader] Exit check error for {strategy_id}: {e}")

        for trade in trades_to_close:
            reason = trade.get("exit_reason", "STRATEGY_EXIT")
            gross_pnl = trade.get("pnl", 0)
            brokerage = trade.get("est_brokerage", 0)
            net_pnl = round(gross_pnl - brokerage, 2)
            underlying = trade.get("underlying", "")
            spread = trade.get("strategy", "")

            trade["pnl"] = net_pnl
            trade["gross_pnl"] = gross_pnl
            trade["charges"] = brokerage
            trade["status"] = "CLOSED"
            trade["closed_at"] = now_ist().isoformat()
            self._total_pnl += net_pnl
            self._daily_realized_pnl += net_pnl
            if net_pnl < 0:
                self._last_loss_at = now_ist()
            self._trade_history.append(trade)
            log_trade(trade, source="options_paper")

            self._log("ORDER", f"{underlying} {spread} — {reason} | Net P&L: {net_pnl:,.2f} (charges: ₹{brokerage})")

        self._active_positions = [p for p in self._active_positions if p["status"] == "OPEN"]
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

    # ── Logging ───────────────────────────────────────────────────────────

    def _log(self, level: str, message: str):
        self._logger.log(level, message)


# ── Singleton Instance ────────────────────────────────────────────────────

options_paper_trader = OptionsPaperTrader()
