"""
Futures Swing Trading Engine (Live).

Key differences from intraday futures:
  - MARGIN product type (positions carry over days)
  - No 2 PM order cutoff, no 3:15 PM square-off
  - Exchange-level SL-M order on every position (re-placed daily — DAY validity)
  - Contract rollover: close current month, re-open next month near expiry
  - Daily loss limit: stops new orders if realized loss exceeds threshold
  - Exit retry logic with configurable retries
  - State persists across days
"""

import threading
import logging
import time
from datetime import timedelta
from typing import Optional

from services.scanner import is_market_open
from services.futures_scanner import run_futures_scan
from services.futures_oi_analyser import analyse_batch
from services.futures_client import (
    place_futures_order,
    get_futures_ltp_batch,
    days_to_expiry,
    build_futures_symbol,
    get_current_expiry,
    get_next_expiry,
)
from services.trade_logger import log_trade
from services.fyers_client import is_authenticated, cancel_order, get_orderbook
from fno_stocks import get_fno_symbols
from utils.time_utils import now_ist
from utils.state_manager import get_state_path, save_state, load_state
from utils.trader_log import TraderLogger
from utils.sleep_manager import SleepManager
from config import (
    FUTURES_SWING_MAX_POSITIONS,
    FUTURES_SWING_SCAN_INTERVAL_SECONDS,
    FUTURES_SWING_EXIT_DAYS_BEFORE_EXPIRY,
    FUTURES_DAILY_LOSS_LIMIT_PCT,
    FUTURES_SQUAREOFF_MAX_RETRIES,
)

logger = logging.getLogger(__name__)

STATE_FILE = get_state_path(".futures_swing_trader_state.json")

# Per-position max loss cap (% of capital) — force close if breached
POSITION_MAX_LOSS_PCT = 3.0


class FuturesSwingTrader:
    """Live futures swing trading engine. MARGIN orders, positions carry over days."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._strategy_keys: list[str] = []
        self._timeframes: dict[str, str] = {}
        self._capital: float = 0.0
        self._scan_interval: int = FUTURES_SWING_SCAN_INTERVAL_SECONDS

        self._active_trades: list[dict] = []
        self._trade_history: list[dict] = []
        self._total_pnl: float = 0.0
        self._daily_realized_pnl: float = 0.0
        self._daily_loss_limit_hit: bool = False
        self._last_daily_reset: str = ""
        self._scan_count: int = 0
        self._order_count: int = 0
        self._started_at: Optional[str] = None
        self._next_scan_at: Optional[str] = None

        self._logger = TraderLogger("FuturesSwing")
        self._sleep_mgr = SleepManager("FuturesSwing")

        self._load_state()

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Daily Loss Limit ──────────────────────────────────────────────────

    def _reset_daily_pnl_if_new_day(self):
        """Reset daily P&L tracking at the start of each new trading day."""
        today = now_ist().strftime("%Y-%m-%d")
        if self._last_daily_reset != today:
            self._daily_realized_pnl = 0.0
            self._daily_loss_limit_hit = False
            self._last_daily_reset = today

    def _check_daily_loss_limit(self) -> bool:
        if self._daily_loss_limit_hit:
            return True
        if self._capital <= 0:
            return False
        loss_pct = abs(self._daily_realized_pnl) / self._capital * 100
        if self._daily_realized_pnl < 0 and loss_pct >= FUTURES_DAILY_LOSS_LIMIT_PCT:
            self._daily_loss_limit_hit = True
            self._log("ALERT", f"DAILY LOSS LIMIT HIT: ₹{self._daily_realized_pnl:,.2f} ({loss_pct:.1f}%). No new orders today.")
            return True
        return False

    def _check_position_max_loss(self, trade: dict) -> bool:
        """Check if a single position has lost more than POSITION_MAX_LOSS_PCT of capital."""
        if self._capital <= 0:
            return False
        pnl = trade.get("pnl", 0)
        if pnl < 0 and abs(pnl) / self._capital * 100 >= POSITION_MAX_LOSS_PCT:
            return True
        return False

    # ── State Persistence ─────────────────────────────────────────────────

    def _save_state(self):
        state = {
            "running": self._running,
            "strategy_keys": self._strategy_keys,
            "timeframes": self._timeframes,
            "capital": self._capital,
            "scan_interval": self._scan_interval,
            "active_trades": self._active_trades,
            "trade_history": self._trade_history,
            "total_pnl": self._total_pnl,
            "daily_realized_pnl": self._daily_realized_pnl,
            "daily_loss_limit_hit": self._daily_loss_limit_hit,
            "last_daily_reset": self._last_daily_reset,
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "started_at": self._started_at,
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "FuturesSwingTrader")

    def _load_state(self):
        try:
            state = load_state(STATE_FILE, "FuturesSwingTrader")
            if not state:
                return

            self._strategy_keys = state.get("strategy_keys", [])
            self._timeframes = state.get("timeframes", {})
            self._capital = state.get("capital", 0.0)
            self._scan_interval = state.get("scan_interval", FUTURES_SWING_SCAN_INTERVAL_SECONDS)
            self._active_trades = state.get("active_trades", [])
            self._trade_history = state.get("trade_history", [])
            self._total_pnl = state.get("total_pnl", 0.0)
            self._daily_realized_pnl = state.get("daily_realized_pnl", 0.0)
            self._daily_loss_limit_hit = state.get("daily_loss_limit_hit", False)
            self._last_daily_reset = state.get("last_daily_reset", "")
            self._scan_count = state.get("scan_count", 0)
            self._order_count = state.get("order_count", 0)
            self._started_at = state.get("started_at")
            self._logger.entries = state.get("logs", [])

            was_running = state.get("running", False)
            if self._strategy_keys and was_running and is_market_open():
                self._log("RESTORE", "Futures swing trader was running — auto-resuming...")
                self._running = True
                self._sleep_mgr.prevent_sleep()
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.start()
        except Exception as e:
            logger.warning(f"[FuturesSwingTrader] Failed to load state: {e}")

    # ── Controls ──────────────────────────────────────────────────────────

    def start(self, strategies: list[dict], capital: float, scan_interval_minutes: int = 240) -> dict:
        with self._lock:
            if self._running:
                return {"error": "Futures swing trader is already running"}
            if not is_market_open():
                return {"error": "Market is closed."}
            if not is_authenticated():
                return {"error": "Fyers not authenticated."}
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
            self._scan_interval = scan_interval_minutes * 60
            self._running = True
            self._active_trades = []
            self._trade_history = []
            self._logger.clear()
            self._total_pnl = 0.0
            self._daily_realized_pnl = 0.0
            self._daily_loss_limit_hit = False
            self._last_daily_reset = now_ist().strftime("%Y-%m-%d")
            self._scan_count = 0
            self._order_count = 0
            self._started_at = now_ist().isoformat()

            strat_names = ", ".join(f"{k}({self._timeframes[k]})" for k in self._strategy_keys)
            self._log("START", f"Futures swing STARTED — {strat_names} | Capital=₹{capital:,.0f}")
            self._log("INFO", f"SWING MODE — Max {FUTURES_SWING_MAX_POSITIONS} positions | MARGIN orders | Exchange SL-M | Rollover near expiry | Daily loss limit: {FUTURES_DAILY_LOSS_LIMIT_PCT}%")

            self._sleep_mgr.prevent_sleep()
            self._save_state()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

            return {
                "status": "started",
                "mode": "futures_swing",
                "strategies": [{"strategy": k, "timeframe": self._timeframes[k]} for k in self._strategy_keys],
                "capital": capital,
            }

    def stop(self) -> dict:
        with self._lock:
            if not self._running:
                return {"status": "already_stopped"}
            self._running = False
            self._log("STOP", "Futures swing STOPPED (positions remain open)")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._sleep_mgr.allow_sleep()
        self._save_state()
        return {"status": "stopped", "total_pnl": round(self._total_pnl, 2)}

    def force_close_trade(self, symbol: str) -> dict:
        """Force close a single position by symbol."""
        trade = None
        for t in self._active_trades:
            if t["symbol"] == symbol and t["status"] == "OPEN":
                trade = t
                break
        if not trade:
            return {"error": f"No open position found for {symbol}"}

        self._close_trade(trade, "FORCE_CLOSE")
        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()
        return {"status": "closed", "symbol": symbol, "pnl": trade.get("pnl", 0)}

    def status(self) -> dict:
        return {
            "is_running": self._running,
            "mode": "futures_swing",
            "strategies": [{"strategy": k, "timeframe": self._timeframes.get(k, "")} for k in self._strategy_keys],
            "capital": self._capital,
            "started_at": self._started_at,
            "next_scan_at": self._next_scan_at,
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "total_pnl": round(self._total_pnl, 2),
            "daily_realized_pnl": round(self._daily_realized_pnl, 2),
            "daily_loss_limit_hit": self._daily_loss_limit_hit,
            "active_trades": self._active_trades,
            "trade_history": self._trade_history[-20:],
            "days_to_expiry": days_to_expiry(),
            "logs": self._logger.recent(100),
        }

    # ── Main Loop ─────────────────────────────────────────────────────────

    def _run_loop(self):
        self._log("INFO", "Background thread started")
        self._execute_scan_cycle()

        while self._running:
            if not is_market_open():
                self._log("INFO", "Market closed — waiting")
                while self._running and not is_market_open():
                    time.sleep(60)
                if not self._running:
                    break
                self._log("INFO", "Market opened — resuming")
                self._reset_daily_pnl_if_new_day()
                # Re-place SL orders (DAY validity expired overnight)
                self._replace_sl_orders()
                self._execute_scan_cycle()
                continue

            # Check expiry proximity — rollover or close
            dte = days_to_expiry()
            if dte <= FUTURES_SWING_EXIT_DAYS_BEFORE_EXPIRY and self._active_trades:
                self._log("ALERT", f"Expiry in {dte} days — rolling over positions")
                self._rollover_or_close()

            next_scan = now_ist() + timedelta(seconds=self._scan_interval)
            self._next_scan_at = next_scan.isoformat()

            for _ in range(self._scan_interval):
                if not self._running:
                    break
                time.sleep(1)

            if not self._running:
                break

            self._reset_daily_pnl_if_new_day()
            self._update_position_pnl()

            if is_market_open():
                self._execute_scan_cycle()

        self._log("INFO", "Background thread exited")
        self._sleep_mgr.allow_sleep()
        self._save_state()

    # ── SL Order Management ───────────────────────────────────────────────

    def _place_sl_order(self, trade: dict) -> str:
        """Place SL-M order for a trade. Returns order ID or empty string."""
        symbol = trade["symbol"]
        qty = trade["quantity"]
        side = trade["side"]
        sl = trade["stop_loss"]
        sl_side = -1 if side == 1 else 1

        for attempt in range(3):
            sl_result = place_futures_order(
                symbol=symbol, qty=qty, side=sl_side,
                order_type=4, product_type="MARGIN",
                stop_price=sl,
            )
            if "error" not in sl_result:
                sl_id = sl_result.get("id", sl_result.get("order_id", ""))
                self._log("ORDER", f"{symbol} — SL-M PLACED (ID: {sl_id}) at ₹{sl}")
                return sl_id
            self._log("WARN", f"{symbol} — SL-M attempt {attempt+1}/3 failed: {sl_result.get('error', '')}")
            time.sleep(3)

        self._log("ERROR", f"{symbol} — SL-M FAILED after 3 attempts! Position UNPROTECTED on exchange.")
        return ""

    def _replace_sl_orders(self):
        """Re-place SL-M orders for all open positions (DAY validity expired overnight)."""
        if not self._active_trades:
            return

        self._log("INFO", "Re-placing SL-M orders (new trading day)")
        for trade in self._active_trades:
            if trade["status"] != "OPEN":
                continue
            # Cancel old SL if exists
            old_sl = trade.get("sl_order_id", "")
            if old_sl:
                try:
                    cancel_order(old_sl)
                except Exception:
                    pass
            # Place new SL
            new_sl_id = self._place_sl_order(trade)
            trade["sl_order_id"] = new_sl_id

        self._save_state()

    # ── Scan & Order ──────────────────────────────────────────────────────

    def _execute_scan_cycle(self):
        self._scan_count += 1
        self._update_position_pnl()

        if len(self._active_trades) >= FUTURES_SWING_MAX_POSITIONS:
            self._log("INFO", f"Max positions ({FUTURES_SWING_MAX_POSITIONS}) — monitoring only")
            return

        if self._check_daily_loss_limit():
            return

        if not is_authenticated():
            self._log("ERROR", "Fyers auth lost")
            return

        oi_data = analyse_batch(get_fno_symbols())
        all_signals = []

        for key in self._strategy_keys:
            tf = self._timeframes.get(key, "1d")
            result = run_futures_scan(key, tf, self._capital, oi_data=oi_data)
            if "error" in result:
                continue
            signals = result.get("signals", [])
            for sig in signals:
                sig["_strategy"] = key
                sig["_timeframe"] = tf
            all_signals.extend(signals)
            self._log("SCAN", f"  {key}({tf}): {len(signals)} signals")

        seen = {}
        for sig in all_signals:
            sym = sig.get("symbol", "")
            score = sig.get("oi_conviction", 0)
            if sym not in seen or score > seen[sym][1]:
                seen[sym] = (sig, score)

        unique = [s[0] for s in sorted(seen.values(), key=lambda x: x[1], reverse=True)]
        self._log("SCAN", f"Swing scan #{self._scan_count} — {len(unique)} signals")

        active_syms = {t["symbol"] for t in self._active_trades}
        for signal in unique:
            if len(self._active_trades) >= FUTURES_SWING_MAX_POSITIONS:
                break
            sym = signal.get("symbol", "")
            if sym in active_syms:
                continue
            self._place_order(signal)
            break

        self._save_state()

    def _place_order(self, signal: dict) -> bool:
        symbol = signal.get("symbol", "")
        signal_type = signal.get("signal_type", "")
        entry = signal.get("entry_price", 0)
        sl = signal.get("stop_loss", 0)
        target = signal.get("target_1", 0)
        qty = signal.get("quantity", 0)
        side = 1 if signal_type == "BUY" else -1

        self._log("ORDER", f"Placing SWING {signal_type}: {symbol} | {signal.get('num_lots', 0)} lots | Entry=₹{entry} | SL=₹{sl} | Target=₹{target}")

        try:
            # Step 1: Market entry
            result = place_futures_order(
                symbol=symbol, qty=qty, side=side,
                order_type=2, product_type="MARGIN",
            )
            if "error" in result:
                self._log("ERROR", f"{symbol} — order FAILED: {result['error']}")
                return False

            order_id = result.get("id", result.get("order_id", "unknown"))
            self._log("ORDER", f"{symbol} — entry PLACED (ID: {order_id})")

            # Step 2: Exchange-level SL-M
            time.sleep(2)
            trade = {
                "symbol": symbol,
                "signal_type": signal_type,
                "side": side,
                "entry_price": entry,
                "stop_loss": sl,
                "target": target,
                "quantity": qty,
                "lot_size": signal.get("lot_size", 0),
                "num_lots": signal.get("num_lots", 0),
                "order_id": order_id,
                "sl_order_id": "",
                "strategy": signal.get("_strategy", ""),
                "timeframe": signal.get("_timeframe", ""),
                "oi_sentiment": signal.get("oi_sentiment", ""),
                "placed_at": now_ist().isoformat(),
                "status": "OPEN",
                "pnl": 0.0,
            }

            sl_order_id = self._place_sl_order(trade)
            trade["sl_order_id"] = sl_order_id

            self._active_trades.append(trade)
            self._order_count += 1
            self._save_state()
            return True
        except Exception as e:
            self._log("ERROR", f"{symbol} — exception: {e}")
            return False

    # ── Contract Rollover ─────────────────────────────────────────────────

    def _rollover_or_close(self):
        """Near expiry: close current month position, re-open in next month contract."""
        for trade in list(self._active_trades):
            symbol = trade["symbol"]
            side = trade["side"]
            close_side = -1 if side == 1 else 1
            qty = trade["quantity"]

            self._log("ALERT", f"{symbol} — rolling over to next month contract")

            # Cancel existing SL
            sl_oid = trade.get("sl_order_id", "")
            if sl_oid:
                try:
                    cancel_order(sl_oid)
                except Exception:
                    pass

            # Step 1: Close current month
            exit_success = False
            for attempt in range(FUTURES_SQUAREOFF_MAX_RETRIES):
                try:
                    result = place_futures_order(
                        symbol=symbol, qty=qty, side=close_side,
                        order_type=2, product_type="MARGIN",
                    )
                    if "error" not in result:
                        exit_success = True
                        break
                    self._log("WARN", f"{symbol} — rollover exit attempt {attempt+1} failed: {result.get('error', '')}")
                except Exception as e:
                    self._log("WARN", f"{symbol} — rollover exit exception: {e}")
                time.sleep(2)

            # Get LTP for P&L on this leg
            ltp_map = get_futures_ltp_batch([symbol])
            ltp = ltp_map.get(symbol, trade.get("ltp", trade["entry_price"]))
            leg_pnl = round((ltp - trade["entry_price"]) * qty * (1 if side == 1 else -1), 2)

            if not exit_success:
                self._log("ERROR", f"{symbol} — ROLLOVER EXIT FAILED! Close manually!")
                continue

            self._log("ORDER", f"{symbol} — closed current month at ₹{ltp} | Leg P&L: ₹{leg_pnl:,.2f}")

            # Step 2: Re-enter in next month contract
            time.sleep(3)
            next_expiry = get_next_expiry()
            next_symbol = build_futures_symbol(symbol, next_expiry)

            try:
                re_entry = place_futures_order(
                    symbol=symbol, qty=qty, side=side,
                    order_type=2, product_type="MARGIN",
                )
                # Note: place_futures_order uses get_current_expiry() which after
                # current expiry date will automatically point to next month

                if "error" in re_entry:
                    self._log("ERROR", f"{symbol} — rollover RE-ENTRY FAILED: {re_entry['error']}. Closing position instead.")
                    # Fall through to close logic below
                else:
                    new_order_id = re_entry.get("id", re_entry.get("order_id", "unknown"))
                    self._log("ORDER", f"{symbol} — re-entered next month (ID: {new_order_id})")

                    # Update trade with new entry price and SL
                    new_ltp_map = get_futures_ltp_batch([symbol])
                    new_entry = new_ltp_map.get(symbol, ltp)
                    trade["entry_price"] = new_entry
                    trade["order_id"] = new_order_id
                    trade["placed_at"] = now_ist().isoformat()
                    trade["pnl"] = 0.0

                    # Place new SL
                    time.sleep(2)
                    new_sl_id = self._place_sl_order(trade)
                    trade["sl_order_id"] = new_sl_id

                    self._total_pnl += leg_pnl
                    self._daily_realized_pnl += leg_pnl
                    self._save_state()
                    continue

            except Exception as e:
                self._log("ERROR", f"{symbol} — rollover re-entry exception: {e}")

            # If re-entry failed, close the trade entirely
            trade["pnl"] = leg_pnl
            trade["status"] = "CLOSED"
            trade["closed_at"] = now_ist().isoformat()
            trade["exit_price"] = ltp
            trade["exit_reason"] = "EXPIRY_CLOSE"
            self._total_pnl += leg_pnl
            self._daily_realized_pnl += leg_pnl
            self._trade_history.append(trade)
            log_trade(trade, source="futures_swing")
            self._log("ORDER", f"{symbol} — closed (rollover failed) | P&L: ₹{leg_pnl:,.2f}")

        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()

    # ── Trade Close Helper ────────────────────────────────────────────────

    def _close_trade(self, trade: dict, reason: str):
        """Close a single trade with retry logic."""
        symbol = trade["symbol"]
        side = trade["side"]
        close_side = -1 if side == 1 else 1

        # Cancel SL order
        sl_oid = trade.get("sl_order_id", "")
        if sl_oid:
            try:
                cancel_order(sl_oid)
            except Exception:
                pass

        exit_success = False
        for attempt in range(FUTURES_SQUAREOFF_MAX_RETRIES):
            try:
                result = place_futures_order(
                    symbol=symbol, qty=trade["quantity"], side=close_side,
                    order_type=2, product_type="MARGIN",
                )
                if "error" not in result:
                    exit_success = True
                    break
                self._log("WARN", f"{symbol} — exit attempt {attempt+1}/{FUTURES_SQUAREOFF_MAX_RETRIES} failed")
            except Exception as e:
                self._log("WARN", f"{symbol} — exit exception: {e}")
            time.sleep(2)

        if not exit_success:
            self._log("ERROR", f"{symbol} — EXIT FAILED after {FUTURES_SQUAREOFF_MAX_RETRIES} retries! CLOSE MANUALLY!")

        pnl = trade.get("pnl", 0)
        trade["status"] = "CLOSED"
        trade["closed_at"] = now_ist().isoformat()
        trade["exit_price"] = trade.get("ltp", trade["entry_price"])
        trade["exit_reason"] = reason
        self._total_pnl += pnl
        self._daily_realized_pnl += pnl
        self._trade_history.append(trade)
        log_trade(trade, source="futures_swing")
        self._log("ORDER", f"{symbol} — {reason} | P&L: ₹{pnl:,.2f}")

    # ── Position Monitoring ───────────────────────────────────────────────

    def _update_position_pnl(self):
        if not self._active_trades:
            return

        symbols = [t["symbol"] for t in self._active_trades]
        ltp_map = get_futures_ltp_batch(symbols)

        trades_to_close = []
        for trade in self._active_trades:
            symbol = trade["symbol"]
            ltp = ltp_map.get(symbol, trade.get("ltp", trade.get("entry_price", 0)))
            side = trade["side"]
            pnl = round((ltp - trade["entry_price"]) * trade["quantity"] * (1 if side == 1 else -1), 2)
            trade["pnl"] = pnl
            trade["ltp"] = ltp

            # Per-position max loss cap
            if self._check_position_max_loss(trade):
                trade["exit_reason"] = "MAX_LOSS_CAP"
                trades_to_close.append(trade)
                self._log("ALERT", f"{symbol} — position loss exceeds {POSITION_MAX_LOSS_PCT}% of capital, force closing")
                continue

            # SL hit (exchange SL-M should handle, this is fallback)
            if (side == 1 and ltp <= trade["stop_loss"]) or (side == -1 and ltp >= trade["stop_loss"]):
                trade["exit_reason"] = "SL_HIT"
                trades_to_close.append(trade)
            # Target hit
            elif (side == 1 and ltp >= trade["target"]) or (side == -1 and ltp <= trade["target"]):
                trade["exit_reason"] = "TARGET_HIT"
                trades_to_close.append(trade)

        for trade in trades_to_close:
            # Cancel SL for target hits
            if trade["exit_reason"] in ("TARGET_HIT", "MAX_LOSS_CAP"):
                sl_oid = trade.get("sl_order_id", "")
                if sl_oid:
                    try:
                        cancel_order(sl_oid)
                    except Exception:
                        pass

            # Place exit for non-SL reasons (SL may have filled on exchange)
            if trade["exit_reason"] != "SL_HIT":
                self._close_trade(trade, trade["exit_reason"])
            else:
                # SL hit — mark closed, exchange SL-M should have executed
                trade["status"] = "CLOSED"
                trade["closed_at"] = now_ist().isoformat()
                trade["exit_price"] = trade["ltp"]
                self._total_pnl += trade["pnl"]
                self._daily_realized_pnl += trade["pnl"]
                self._trade_history.append(trade)
                log_trade(trade, source="futures_swing")
                self._log("ORDER", f"{trade['symbol']} — SL_HIT | P&L: ₹{trade['pnl']:,.2f}")

        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()
        self._check_daily_loss_limit()

    def _log(self, level: str, message: str):
        self._logger.log(level, message)


futures_swing_trader = FuturesSwingTrader()
