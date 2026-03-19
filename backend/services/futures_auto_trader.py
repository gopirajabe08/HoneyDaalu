"""
Futures Auto-Trading Engine (Intraday Live).

Rules:
  - Scans F&O stocks with OI sentiment filter during market hours
  - Places futures orders via Fyers (INTRADAY product type)
  - Places exchange-level SL-M order immediately after entry (exchange protection)
  - Order window: 11:00 AM - 2:00 PM IST
  - Squares off all positions at 3:15 PM IST (with retry logic)
  - Max positions from capital / margin per lot
  - Strict 2% risk per trade
  - Daily loss limit: stops engine if realized loss exceeds 5% of capital
  - State persists to JSON (date-filtered — intraday only)
"""

import threading
import logging
import time
from typing import Optional

from services.scanner import is_market_open
from services.futures_scanner import run_futures_scan
from services.futures_oi_analyser import analyse_batch
from services.futures_regime import detect_futures_regime
from services.futures_client import (
    place_futures_order,
    get_futures_ltp_batch,
    build_futures_symbol,
    calculate_position_size,
)
from services.trade_logger import log_trade
from services.fyers_client import is_authenticated, get_quotes, cancel_order
from fno_stocks import get_fno_symbols
from utils.time_utils import now_ist, is_before_time, is_past_time
from utils.state_manager import get_state_path, save_state, load_state
from utils.trader_log import TraderLogger
from utils.sleep_manager import SleepManager
from config import (
    FUTURES_ORDER_START_HOUR, FUTURES_ORDER_START_MIN,
    FUTURES_ORDER_CUTOFF_HOUR, FUTURES_ORDER_CUTOFF_MIN,
    FUTURES_SQUAREOFF_HOUR, FUTURES_SQUAREOFF_MIN,
    FUTURES_MAX_POSITIONS_CAP,
    FUTURES_POSITION_CHECK_INTERVAL,
    FUTURES_DAILY_LOSS_LIMIT_PCT,
    FUTURES_SQUAREOFF_MAX_RETRIES,
)

logger = logging.getLogger(__name__)

STATE_FILE = get_state_path(".futures_auto_trader_state.json")


def _is_before_order_start() -> bool:
    return is_before_time(FUTURES_ORDER_START_HOUR, FUTURES_ORDER_START_MIN)


def _is_past_order_cutoff() -> bool:
    return is_past_time(FUTURES_ORDER_CUTOFF_HOUR, FUTURES_ORDER_CUTOFF_MIN)


def _is_squareoff_time() -> bool:
    return is_past_time(FUTURES_SQUAREOFF_HOUR, FUTURES_SQUAREOFF_MIN)


class FuturesAutoTrader:
    """
    Live futures intraday trading engine.
    Places futures orders via Fyers with OI-filtered strategy signals.
    Exchange-level SL-M protection on every position.
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
        self._max_positions: int = FUTURES_MAX_POSITIONS_CAP
        self._auto_mode: bool = False  # True when strategies are auto-selected by regime

        self._logger = TraderLogger("FuturesAuto")
        self._sleep_mgr = SleepManager("FuturesAuto")

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
            "daily_realized_pnl": self._daily_realized_pnl,
            "daily_loss_limit_hit": self._daily_loss_limit_hit,
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "started_at": self._started_at,
            "squared_off": self._squared_off,
            "max_positions": self._max_positions,
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "FuturesAutoTrader")

    def _load_state(self):
        try:
            state = load_state(STATE_FILE, "FuturesAutoTrader")
            if not state:
                return

            today = now_ist().strftime("%Y-%m-%d")
            if state.get("date") != today:
                return

            self._strategy_keys = state.get("strategy_keys", [])
            self._timeframes = state.get("timeframes", {})
            self._capital = state.get("capital", 0.0)
            self._active_trades = state.get("active_trades", [])
            self._trade_history = state.get("trade_history", [])
            self._total_pnl = state.get("total_pnl", 0.0)
            self._daily_realized_pnl = state.get("daily_realized_pnl", 0.0)
            self._daily_loss_limit_hit = state.get("daily_loss_limit_hit", False)
            self._scan_count = state.get("scan_count", 0)
            self._order_count = state.get("order_count", 0)
            self._started_at = state.get("started_at")
            self._squared_off = state.get("squared_off", False)
            self._max_positions = state.get("max_positions", FUTURES_MAX_POSITIONS_CAP)
            self._logger.entries = state.get("logs", [])

            was_running = state.get("running", False)
            if self._strategy_keys and was_running and not self._squared_off and is_market_open():
                self._log("RESTORE", "Futures auto trader was running — auto-resuming...")
                self._running = True
                self._sleep_mgr.prevent_sleep()
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.start()
        except Exception as e:
            logger.warning(f"[FuturesAutoTrader] Failed to load state: {e}")

    # ── Loss Checks ─────────────────────────────────────────────────────

    def _check_position_max_loss(self, trade: dict) -> bool:
        """Check if a single position has lost more than 3% of capital."""
        if self._capital <= 0:
            return False
        pnl = trade.get("pnl", 0)
        if pnl < 0 and abs(pnl) / self._capital * 100 >= 3.0:
            return True
        return False

    def _check_daily_loss_limit(self) -> bool:
        """Returns True if daily loss limit has been breached."""
        if self._daily_loss_limit_hit:
            return True
        if self._capital <= 0:
            return False
        loss_pct = abs(self._daily_realized_pnl) / self._capital * 100
        if self._daily_realized_pnl < 0 and loss_pct >= FUTURES_DAILY_LOSS_LIMIT_PCT:
            self._daily_loss_limit_hit = True
            self._log("ALERT", f"DAILY LOSS LIMIT HIT: ₹{self._daily_realized_pnl:,.2f} ({loss_pct:.1f}% of capital). No new orders.")
            return True
        return False

    def _check_drawdown_breaker(self) -> bool:
        """Check if multi-day drawdown exceeds 15% of capital. Returns True if breaker triggered."""
        try:
            from services.trade_logger import get_all_trades
            recent = get_all_trades(days=5)
            trades = [t for t in recent if t.get("source") == "futures_auto"]
            if len(trades) >= 5:
                pnl = sum(t.get("pnl", 0) for t in trades)
                if pnl < -self._capital * 0.15:
                    return True
        except Exception:
            pass
        return False

    # ── Controls ──────────────────────────────────────────────────────────

    def start(self, strategies: list[dict], capital: float) -> dict:
        with self._lock:
            if self._running:
                return {"error": "Futures auto trader is already running"}

            if not is_market_open():
                return {"error": "Market is closed. Futures trading runs during market hours (9:15 AM - 3:30 PM IST)."}

            if not is_authenticated():
                return {"error": "Fyers is not authenticated. Please login first."}

            if _is_past_order_cutoff():
                return {"error": "Cannot start after 2:00 PM IST. No new orders after cutoff."}

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
            self._daily_realized_pnl = 0.0
            self._daily_loss_limit_hit = False
            self._scan_count = 0
            self._order_count = 0
            self._squared_off = False
            self._started_at = now_ist().isoformat()
            self._next_scan_at = None

            strat_names = ", ".join(f"{k}({self._timeframes[k]})" for k in self._strategy_keys)
            self._log("START", f"Futures auto trader STARTED — {strat_names} | Capital=₹{capital:,.0f}")
            self._log("INFO", f"LIVE FUTURES — Max {self._max_positions} positions | Daily loss limit: {FUTURES_DAILY_LOSS_LIMIT_PCT}% | Exchange SL-M on every position")

            self._sleep_mgr.prevent_sleep()
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
                return {"status": "already_stopped", "message": "Futures auto trader is not running"}
            self._running = False
            self._log("STOP", "Futures auto trader STOPPED by user")

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
            "squared_off": self._squared_off,
            "order_cutoff_passed": _is_past_order_cutoff(),
            "logs": self._logger.recent(100),
        }

    # ── Main Loop ─────────────────────────────────────────────────────────

    def _run_loop(self):
        self._log("INFO", "Background thread started")

        # Wait for order start time
        while self._running and _is_before_order_start():
            self._log("INFO", "Waiting for 11:00 AM order window...")
            for _ in range(60):
                if not self._running or not _is_before_order_start():
                    break
                time.sleep(1)

        # Initial scan
        if self._running and not _is_past_order_cutoff() and is_market_open() and not self._check_daily_loss_limit():
            self._log("SCAN", "Initial scan — filling positions")
            self._execute_scan_cycle()

        # Monitor loop
        prev_open_count = len(self._active_trades)
        _monitor_tick = 0

        while self._running:
            if _is_squareoff_time() and not self._squared_off:
                self._log("ALERT", "3:15 PM — initiating square-off")
                self._square_off_all()
                self._squared_off = True
                self._running = False
                break

            for _ in range(FUTURES_POSITION_CHECK_INTERVAL):
                if not self._running:
                    break
                time.sleep(1)
                if _is_squareoff_time() and not self._squared_off:
                    break

            if not self._running:
                break

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

            # Check daily loss limit
            if self._check_daily_loss_limit():
                continue  # Skip scanning, just monitor existing positions

            current_open_count = len(self._active_trades)
            if current_open_count < prev_open_count and current_open_count < self._max_positions:
                if not _is_past_order_cutoff() and is_market_open():
                    self._log("SCAN", "Slot opened — scanning for new signal")
                    self._execute_scan_cycle()
                    current_open_count = len(self._active_trades)

            prev_open_count = current_open_count

        self._log("INFO", "Background thread exited")
        self._sleep_mgr.allow_sleep()
        self._save_state()

    def _execute_scan_cycle(self):
        self._scan_count += 1
        self._log("SCAN", f"Futures scan #{self._scan_count}...")

        # Multi-day drawdown breaker
        if self._check_drawdown_breaker():
            self._log("ALERT", "5-day drawdown > 15% — reducing to 1 order per scan (safety mode)")

        if len(self._active_trades) >= self._max_positions:
            self._log("INFO", f"Max positions reached ({len(self._active_trades)}/{self._max_positions})")
            return

        if self._check_daily_loss_limit():
            return

        # Fetch OI data
        oi_data = analyse_batch(get_fno_symbols())
        self._log("INFO", f"OI data: {len(oi_data)} stocks analysed")

        # Re-detect regime on every scan cycle (auto mode)
        if self._auto_mode:
            regime = detect_futures_regime(oi_data)
            new_strats = regime.get("strategies", [])
            if new_strats:
                new_keys = [s["strategy"] for s in new_strats]
                new_tfs = {s["strategy"]: s["timeframe"] for s in new_strats}
                if new_keys != self._strategy_keys:
                    self._log("REGIME", f"Regime changed → {regime['regime']} | Switching to: {', '.join(new_keys)}")
                    self._strategy_keys = new_keys
                    self._timeframes = new_tfs

        slots_available = self._max_positions - len(self._active_trades)
        all_signals = []

        for strategy_key in self._strategy_keys:
            timeframe = self._timeframes.get(strategy_key, "15m")
            result = run_futures_scan(strategy_key, timeframe, self._capital, oi_data=oi_data)

            if "error" in result:
                self._log("WARN", f"Scan error: {result['error']}")
                continue

            signals = result.get("signals", [])
            for sig in signals:
                sig["_strategy"] = strategy_key
                sig["_timeframe"] = timeframe
            all_signals.extend(signals)
            self._log("SCAN", f"  {strategy_key}({timeframe}): {len(signals)} signals (filtered: {result.get('filtered_liquidity', 0)} illiquid)")

        # Deduplicate
        seen = {}
        for sig in all_signals:
            sym = sig.get("symbol", "")
            score = sig.get("oi_conviction", 0) + sig.get("reward", 0) / max(sig.get("risk", 1), 0.01)
            if sym not in seen or score > seen[sym][1]:
                seen[sym] = (sig, score)

        unique = [s[0] for s in sorted(seen.values(), key=lambda x: x[1], reverse=True)]
        self._log("SCAN", f"Scan #{self._scan_count} — {len(unique)} unique signals")
        self._save_state()

        if not unique:
            return

        max_orders_per_scan = 1 if self._check_drawdown_breaker() else min(2, slots_available)
        orders_placed = 0
        active_symbols = {t["symbol"] for t in self._active_trades}

        for signal in unique:
            if orders_placed >= max_orders_per_scan:
                self._log("INFO", f"Max 2 orders per scan — remaining slots will fill on next scan")
                break
            if _is_past_order_cutoff():
                break

            symbol = signal.get("symbol", "")
            if symbol in active_symbols:
                continue

            success = self._place_order(signal)
            if success:
                orders_placed += 1
                active_symbols.add(symbol)

        self._save_state()

    def _place_order(self, signal: dict) -> bool:
        symbol = signal.get("symbol", "")
        signal_type = signal.get("signal_type", "")
        entry = signal.get("entry_price", 0)
        sl = signal.get("stop_loss", 0)
        target = signal.get("target_1", 0)
        qty = signal.get("quantity", 0)
        lot_size = signal.get("lot_size", 0)
        num_lots = signal.get("num_lots", 0)

        if not all([symbol, signal_type, entry, sl, target, qty]):
            return False

        side = 1 if signal_type == "BUY" else -1

        self._log("ORDER", f"Placing {signal_type}: {symbol} | {num_lots} lots ({qty} qty) | Entry=₹{entry} | SL=₹{sl} | Target=₹{target} | Risk: {signal.get('risk_pct_actual', '?')}%")

        try:
            # Step 1: Place market entry order
            result = place_futures_order(
                symbol=symbol, qty=qty, side=side,
                order_type=2, product_type="INTRADAY",
            )

            if "error" in result:
                self._log("ERROR", f"{symbol} — entry order FAILED: {result['error']}")
                return False

            order_id = result.get("id", result.get("order_id", "unknown"))
            self._log("ORDER", f"{symbol} — entry PLACED (ID: {order_id})")

            # Step 2: Place exchange-level SL-M order (protection)
            sl_side = -1 if side == 1 else 1
            sl_order_id = ""

            time.sleep(2)  # Brief wait for entry to settle

            for attempt in range(3):
                sl_result = place_futures_order(
                    symbol=symbol, qty=qty, side=sl_side,
                    order_type=4,  # SL-M
                    product_type="INTRADAY",
                    stop_price=sl,
                )
                if "error" not in sl_result:
                    sl_order_id = sl_result.get("id", sl_result.get("order_id", ""))
                    self._log("ORDER", f"{symbol} — SL-M order PLACED (ID: {sl_order_id}) at ₹{sl}")
                    break
                self._log("WARN", f"{symbol} — SL-M attempt {attempt+1}/3 failed: {sl_result.get('error', '')}")
                time.sleep(3)

            if not sl_order_id:
                self._log("ERROR", f"{symbol} — SL-M FAILED after 3 attempts! Position UNPROTECTED on exchange. Will monitor via LTP.")

            trade = {
                "symbol": symbol,
                "signal_type": signal_type,
                "side": side,
                "entry_price": entry,
                "stop_loss": sl,
                "target": target,
                "quantity": qty,
                "lot_size": lot_size,
                "num_lots": num_lots,
                "order_id": order_id,
                "sl_order_id": sl_order_id,
                "strategy": signal.get("_strategy", ""),
                "timeframe": signal.get("_timeframe", ""),
                "oi_sentiment": signal.get("oi_sentiment", ""),
                "placed_at": now_ist().isoformat(),
                "status": "OPEN",
                "pnl": 0.0,
                "ltp": entry,
            }

            self._active_trades.append(trade)
            self._order_count += 1
            self._save_state()
            return True

        except Exception as e:
            self._log("ERROR", f"{symbol} — order exception: {e}")
            return False

    # ── Square Off ────────────────────────────────────────────────────────

    def _square_off_all(self):
        if not self._active_trades:
            self._log("INFO", "No positions to square off")
            return

        self._log("ALERT", f"Squaring off {len(self._active_trades)} position(s)")

        symbols = [t["symbol"] for t in self._active_trades]
        ltp_map = get_futures_ltp_batch(symbols)

        for trade in self._active_trades:
            symbol = trade["symbol"]
            ltp = ltp_map.get(symbol, trade.get("ltp", trade["entry_price"]))
            side = trade["side"]
            close_side = -1 if side == 1 else 1

            # Cancel SL order first
            sl_oid = trade.get("sl_order_id", "")
            if sl_oid:
                try:
                    cancel_order(sl_oid)
                except Exception:
                    pass

            # Place exit with retry
            exit_success = False
            for attempt in range(FUTURES_SQUAREOFF_MAX_RETRIES):
                try:
                    result = place_futures_order(
                        symbol=symbol, qty=trade["quantity"], side=close_side,
                        order_type=2, product_type="INTRADAY",
                    )
                    if "error" not in result:
                        exit_success = True
                        break
                    self._log("WARN", f"{symbol} — square-off attempt {attempt+1}/{FUTURES_SQUAREOFF_MAX_RETRIES} failed: {result.get('error', '')}")
                except Exception as e:
                    self._log("WARN", f"{symbol} — square-off attempt {attempt+1} exception: {e}")
                time.sleep(2)

            if not exit_success:
                self._log("ERROR", f"{symbol} — SQUARE-OFF FAILED after {FUTURES_SQUAREOFF_MAX_RETRIES} retries! CLOSE MANUALLY!")

            pnl = round((ltp - trade["entry_price"]) * trade["quantity"] * (1 if side == 1 else -1), 2)
            trade["pnl"] = pnl
            trade["ltp"] = ltp
            trade["status"] = "CLOSED"
            trade["closed_at"] = now_ist().isoformat()
            trade["exit_price"] = ltp
            trade["exit_reason"] = "SQUARE_OFF"
            self._total_pnl += pnl
            self._daily_realized_pnl += pnl
            self._trade_history.append(trade)
            log_trade(trade, source="futures_auto")
            self._log("SQUAREOFF", f"{symbol} — closed at ₹{ltp} | P&L: ₹{pnl:,.2f}")

        self._active_trades = []
        self._log("ALERT", f"Square-off complete. Total P&L: ₹{self._total_pnl:,.2f}")
        self._save_state()

        # End-of-day pipeline (runs once per day, shared across all engines)
        try:
            from services.auto_tuner import run_eod_pipeline
            eod = run_eod_pipeline("futures_live")
            if eod.get("status") == "completed":
                self._log("TRACKER", f"EOD pipeline completed — {eod.get('report', {}).get('total_trades', 0)} trades analyzed")
        except Exception as e:
            logger.warning(f"[FuturesAuto] EOD pipeline failed: {e}")

    # ── Position Monitoring ───────────────────────────────────────────────

    def _update_position_pnl(self):
        if not self._active_trades:
            return

        symbols = [t["symbol"] for t in self._active_trades]
        ltp_map = get_futures_ltp_batch(symbols)

        trades_to_close = []
        for trade in self._active_trades:
            symbol = trade["symbol"]
            ltp = ltp_map.get(symbol, trade.get("ltp", trade["entry_price"]))
            side = trade["side"]
            pnl = round((ltp - trade["entry_price"]) * trade["quantity"] * (1 if side == 1 else -1), 2)
            trade["pnl"] = pnl
            trade["ltp"] = ltp

            # Per-position max loss cap (3% of capital)
            if self._check_position_max_loss(trade):
                trade["exit_reason"] = "MAX_LOSS_CAP"
                trades_to_close.append(trade)
                self._log("ALERT", f"{symbol} — position loss exceeds 3% of capital, force closing")
                continue

            # Check SL (exchange SL-M should handle this, but monitor as fallback)
            if (side == 1 and ltp <= trade["stop_loss"]) or (side == -1 and ltp >= trade["stop_loss"]):
                trade["exit_reason"] = "SL_HIT"
                trades_to_close.append(trade)
            # Check target
            elif (side == 1 and ltp >= trade["target"]) or (side == -1 and ltp <= trade["target"]):
                trade["exit_reason"] = "TARGET_HIT"
                trades_to_close.append(trade)

        for trade in trades_to_close:
            symbol = trade["symbol"]
            side = trade["side"]
            close_side = -1 if side == 1 else 1

            # Cancel SL order if taking profit (target hit)
            sl_oid = trade.get("sl_order_id", "")
            if sl_oid and trade["exit_reason"] == "TARGET_HIT":
                try:
                    cancel_order(sl_oid)
                except Exception:
                    pass

            # Place exit order (for target hits; SL may have already been filled on exchange)
            if trade["exit_reason"] == "TARGET_HIT":
                try:
                    place_futures_order(
                        symbol=symbol, qty=trade["quantity"], side=close_side,
                        order_type=2, product_type="INTRADAY",
                    )
                except Exception as e:
                    self._log("ERROR", f"{symbol} — target exit order failed: {e}")

            trade["status"] = "CLOSED"
            trade["closed_at"] = now_ist().isoformat()
            trade["exit_price"] = trade["ltp"]
            self._total_pnl += trade["pnl"]
            self._daily_realized_pnl += trade["pnl"]
            self._trade_history.append(trade)
            log_trade(trade, source="futures_auto")
            self._log("ORDER", f"{symbol} — {trade['exit_reason']} at ₹{trade['ltp']} | P&L: ₹{trade['pnl']:,.2f}")

        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()

        # Check daily loss limit after closures
        self._check_daily_loss_limit()

    # ── Logging ───────────────────────────────────────────────────────────

    def _log(self, level: str, message: str):
        self._logger.log(level, message)


# ── Singleton Instance ────────────────────────────────────────────────────

futures_auto_trader = FuturesAutoTrader()
