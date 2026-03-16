"""
Swing Trading Engine for IntraTrading.

Key differences from intraday auto-trader:
  - Max 1 open position (strict)
  - NO 2 PM order cutoff
  - NO 3:15 PM square-off — positions carry over days
  - Uses CNC (delivery) product type, not INTRADAY
  - Configurable scan interval (default 4 hours)
  - State persists across days (no date filtering)
  - Exit on SL/target only
"""

import threading
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from services.scanner import run_scan, is_market_open
from services.trade_logger import log_trade
from services.fyers_client import (
    place_order,
    cancel_order,
    get_positions,
    get_holdings,
    get_quotes,
    get_orderbook,
    is_authenticated,
)
from config import SWING_MAX_POSITIONS, SWING_SCAN_INTERVAL_SECONDS, SWING_DAILY_SCAN_TIMES
from utils.time_utils import now_ist
from utils.state_manager import get_state_path, save_state, load_state
from utils.trader_log import TraderLogger
from utils.sleep_manager import SleepManager

logger = logging.getLogger(__name__)

STATE_FILE = get_state_path(".swing_trader_state.json")


class SwingTrader:
    """
    Live swing trading engine.
    Places CNC orders via Fyers. Positions carry over days.
    Max 1 position. No time-based square-off.
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._strategy_keys: list[str] = []
        self._timeframes: dict[str, str] = {}
        self._capital: float = 0.0
        self._scan_interval: int = SWING_SCAN_INTERVAL_SECONDS

        self._active_trades: list[dict] = []
        self._trade_history: list[dict] = []
        self._total_pnl: float = 0.0
        self._scan_count: int = 0
        self._order_count: int = 0
        self._started_at: Optional[str] = None
        self._next_scan_at: Optional[str] = None

        # Shared utilities
        self._logger = TraderLogger("SwingTrader")
        self._sleep_mgr = SleepManager("SwingTrader")

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

    # ── State Persistence (cross-day) ─────────────────────────────────────

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
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "started_at": self._started_at,
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "SwingTrader")

    def _load_state(self):
        try:
            state = load_state(STATE_FILE, "SwingTrader")
            if not state:
                return

            # No date filter — positions carry over days
            self._strategy_keys = state.get("strategy_keys", [])
            self._timeframes = state.get("timeframes", {})
            self._capital = state.get("capital", 0.0)
            self._scan_interval = state.get("scan_interval", SWING_SCAN_INTERVAL_SECONDS)
            self._active_trades = state.get("active_trades", [])
            self._trade_history = state.get("trade_history", [])
            self._total_pnl = state.get("total_pnl", 0.0)
            self._scan_count = state.get("scan_count", 0)
            self._order_count = state.get("order_count", 0)
            self._started_at = state.get("started_at")
            self._logger.entries = state.get("logs", [])

            was_running = state.get("running", False)

            if self._strategy_keys:
                strat_names = ", ".join(f"{k}({self._timeframes.get(k, '')})" for k in self._strategy_keys)
                self._log("RESTORE", f"Restored swing state — {strat_names} | "
                          f"Active: {len(self._active_trades)} | P&L: ₹{self._total_pnl:,.2f}")

                if was_running and is_market_open():
                    self._log("RESTORE", "Swing trader was running — auto-resuming...")
                    self._running = True
                    self._prevent_sleep()
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif was_running:
                    self._log("RESTORE", "Swing trader was running but market closed — will resume when market opens")

        except Exception as e:
            logger.warning(f"[SwingTrader] Failed to load state: {e}")

    # ── Controls ──────────────────────────────────────────────────────────

    def start(self, strategies: list[dict], capital: float, scan_interval_minutes: int = 240) -> dict:
        with self._lock:
            if self._running:
                return {"error": "Swing trader is already running"}

            if not is_market_open():
                now = now_ist()
                if now.weekday() >= 5:
                    return {"error": "Market is closed (Weekend). Swing trading scans run during market hours."}
                return {"error": "Market is closed. Swing trading scans run during market hours (9:15 AM - 3:30 PM IST)."}

            if not is_authenticated():
                return {"error": "Fyers is not authenticated. Please login first."}

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
            self._scan_count = 0
            self._order_count = 0
            self._started_at = now_ist().isoformat()
            self._next_scan_at = None

            strat_names = ", ".join(f"{k}({self._timeframes[k]})" for k in self._strategy_keys)
            if scan_interval_minutes == 0:
                times_str = ", ".join(f"{h}:{m:02d}" for h, m in SWING_DAILY_SCAN_TIMES)
                self._log("START", f"Swing trader STARTED — {strat_names} | Capital=₹{capital:,.0f} | Daily scans at {times_str} IST")
            else:
                self._log("START", f"Swing trader STARTED — {strat_names} | Capital=₹{capital:,.0f} | Scan every {scan_interval_minutes}min")
            self._log("INFO", f"SWING MODE — Max {SWING_MAX_POSITIONS} position | CNC orders | Positions carry over days")

            self._prevent_sleep()
            self._save_state()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

            return {
                "status": "started",
                "mode": "swing",
                "strategies": [{"strategy": k, "timeframe": self._timeframes[k]} for k in self._strategy_keys],
                "capital": capital,
                "scan_interval_minutes": scan_interval_minutes,
                "started_at": self._started_at,
            }

    def stop(self) -> dict:
        with self._lock:
            if not self._running:
                return {"status": "already_stopped", "message": "Swing trader is not running"}

            self._running = False
            self._log("STOP", "Swing trader STOPPED by user (positions remain open)")

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

    def trigger_scan(self) -> dict:
        """Trigger an immediate scan (on-demand)."""
        if not self._running:
            return {"error": "Swing trader is not running"}
        if not self._strategy_keys:
            return {"error": "No strategies configured"}
        self._log("SCAN", "Manual scan triggered by user")
        self._execute_scan_cycle()
        return {
            "status": "scan_complete",
            "scan_count": self._scan_count,
            "active_trades": len(self._active_trades),
        }

    def status(self) -> dict:
        return {
            "is_running": self._running,
            "mode": "swing",
            "strategies": [{"strategy": k, "timeframe": self._timeframes.get(k, "")} for k in self._strategy_keys],
            "capital": self._capital,
            "scan_interval_minutes": self._scan_interval // 60,
            "started_at": self._started_at,
            "next_scan_at": self._next_scan_at,
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "total_pnl": round(self._total_pnl, 2),
            "active_trades": self._active_trades,
            "trade_history": self._trade_history[-20:],
            "logs": self._logger.recent(100),
        }

    # ── Main Loop ─────────────────────────────────────────────────────────

    def _run_loop(self):
        self._log("INFO", "Background thread started")

        if self._scan_interval == 0:
            self._run_loop_daily()
        else:
            self._run_loop_interval()

        self._log("INFO", "Background thread exited")
        self._save_state()

    def _run_loop_interval(self):
        """Interval-based scan loop (for 1h, 2h, 4h strategies)."""
        self._execute_scan_cycle()

        while self._running:
            if not is_market_open():
                self._log("INFO", "Market closed — waiting for next open (positions preserved)")
                while self._running and not is_market_open():
                    time.sleep(60)
                if not self._running:
                    break
                self._log("INFO", "Market opened — resuming swing scans")
                self._execute_scan_cycle()
                continue

            next_scan = now_ist() + timedelta(seconds=self._scan_interval)
            self._next_scan_at = next_scan.isoformat()

            for _ in range(self._scan_interval):
                if not self._running:
                    break
                time.sleep(1)

            if not self._running:
                break

            if is_market_open():
                self._execute_scan_cycle()

    def _run_loop_daily(self):
        """Daily scheduled scan loop (9:20 AM + 3:35 PM IST for 1d candles).
        If morning scan finds no signal and slot is open, retries every 30 min until 2 PM."""
        times_str = ", ".join(f"{h}:{m:02d}" for h, m in SWING_DAILY_SCAN_TIMES)
        self._log("INFO", f"Daily scan mode — scheduled at {times_str} IST (retries every 30min if no signal)")

        # Immediate scan on start (uses last completed daily candle)
        self._execute_scan_cycle()

        while self._running:
            # If slot is open and before 2 PM, retry in 30 min instead of waiting for next scheduled scan
            now = now_ist()
            has_open_slot = len(self._active_trades) < SWING_MAX_POSITIONS
            in_retry_window = now.hour < 14 and now.hour >= 9 and now.weekday() < 5

            if has_open_slot and in_retry_window:
                retry_time = now + timedelta(minutes=30)
                self._next_scan_at = retry_time.isoformat()
                self._log("INFO", f"No position open — retry scan at {retry_time.strftime('%I:%M %p IST')}")
                self._save_state()

                while self._running:
                    if now_ist() >= retry_time:
                        break
                    time.sleep(30)

                if not self._running:
                    break

                now = now_ist()
                if now.weekday() < 5 and is_market_open():
                    self._log("SCAN", "Retry scan — looking for new signal")
                    self._execute_scan_cycle()
                continue

            # Position is open or past 2 PM — wait for next morning scan
            next_time = self._get_next_morning_scan_time()
            self._next_scan_at = next_time.isoformat()
            self._log("INFO", f"Next morning scan at {next_time.strftime('%I:%M %p IST on %a %d %b')}")
            self._save_state()

            # Monitor existing position while waiting
            while self._running:
                now = now_ist()
                if now >= next_time:
                    break
                # Check position SL/target every 5 minutes during market hours
                if len(self._active_trades) > 0 and is_market_open():
                    self._update_position_pnl()
                    self._save_state()
                time.sleep(300 if len(self._active_trades) > 0 and is_market_open() else 30)

            if not self._running:
                break

            now = now_ist()
            if now.weekday() >= 5:
                self._log("INFO", "Weekend — skipping scan")
                continue

            self._log("SCAN", "Morning scan — using yesterday's completed daily candle")
            self._execute_scan_cycle()

    def _get_next_daily_scan_time(self) -> datetime:
        """Get next scheduled daily scan time."""
        now = now_ist()
        for h, m in SWING_DAILY_SCAN_TIMES:
            t = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if t > now and t.weekday() < 5:
                return t
        next_day = now + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        h, m = SWING_DAILY_SCAN_TIMES[0]
        return next_day.replace(hour=h, minute=m, second=0, microsecond=0)

    def _get_next_morning_scan_time(self) -> datetime:
        """Get next morning scan time (9:20 AM on next trading day)."""
        now = now_ist()
        h, m = SWING_DAILY_SCAN_TIMES[0]  # 9:20 AM
        today_morning = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if today_morning > now and now.weekday() < 5:
            return today_morning
        next_day = now + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day.replace(hour=h, minute=m, second=0, microsecond=0)

    def _execute_scan_cycle(self, eod_scan: bool = False):
        self._scan_count += 1
        self._log("SCAN", f"Swing scan #{self._scan_count}...")

        # First: check existing position SL/target via Fyers positions
        self._update_position_pnl()

        open_count = len(self._active_trades)
        if open_count >= SWING_MAX_POSITIONS:
            self._log("INFO", f"Max swing position reached ({open_count}/{SWING_MAX_POSITIONS}) — monitoring only")
            return

        if not is_authenticated():
            self._log("ERROR", "Fyers authentication lost")
            return

        all_signals = []
        total_scanned = 0
        total_time = 0

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

            all_signals.extend(signals)
            self._log("SCAN", f"  {strategy_key}({timeframe}): {len(signals)} signals ({scan_time}s)")

        # Deduplicate
        seen_symbols = {}
        for sig in all_signals:
            sym = sig.get("symbol", "")
            rr_val = sig.get("reward", 0) / max(sig.get("risk", 1), 0.01)
            if sym not in seen_symbols or rr_val > seen_symbols[sym][1]:
                seen_symbols[sym] = (sig, rr_val)

        unique_signals = [s[0] for s in sorted(seen_symbols.values(), key=lambda x: x[1], reverse=True)]
        self._log("SCAN", f"Swing scan #{self._scan_count} — {len(unique_signals)} signals ({total_time:.1f}s)")
        self._save_state()

        if not unique_signals:
            return

        # EOD scan: log signals as alerts for next session, don't place orders
        if eod_scan:
            for sig in unique_signals[:5]:
                sym = sig.get("symbol", "")
                sig_type = sig.get("signal_type", "")
                entry = sig.get("entry_price", 0)
                sl = sig.get("stop_loss", 0)
                tgt = sig.get("target_1", 0)
                rr = sig.get("risk_reward_ratio", "")
                self._log("ALERT", f"EOD signal: {sig_type} {sym} @ ₹{entry:.2f} | SL ₹{sl:.2f} | Target ₹{tgt:.2f} | R:R {rr}")
            self._log("INFO", f"EOD scan done — {len(unique_signals)} signals ready for next morning session")
            return

        # Place 1 order only (morning/interval scans)
        open_symbols, _ = self._get_open_positions_detail()
        active_symbols = {t["symbol"] for t in self._active_trades}

        for signal in unique_signals:
            if len(self._active_trades) >= SWING_MAX_POSITIONS:
                break

            symbol = signal.get("symbol", "")
            if symbol in open_symbols or symbol in active_symbols:
                continue

            self._place_order_for_signal(signal)
            break

    def _place_order_for_signal(self, signal: dict) -> bool:
        symbol = signal.get("symbol", "")
        signal_type = signal.get("signal_type", "")
        entry_price = signal.get("entry_price", 0)
        stop_loss = signal.get("stop_loss", 0)
        target = signal.get("target_1", 0)
        qty = signal.get("quantity", 0)
        rr = signal.get("risk_reward_ratio", "")

        if not all([symbol, signal_type, entry_price, stop_loss, target, qty]):
            self._log("WARN", f"{symbol} — incomplete signal, skipping")
            return False

        side = 1 if signal_type == "BUY" else -1

        self._log("ORDER", f"Placing SWING {signal_type}: {symbol} | Qty={qty} | Entry=₹{entry_price} | SL=₹{stop_loss} | Target=₹{target} | R:R={rr}")

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
            self._log("ORDER", f"{symbol} — CNC entry PLACED (ID: {entry_order_id})")

            # Place SL-M order (with retry + longer delays for CNC settlement)
            sl_side = -1 if side == 1 else 1
            sl_order_id = ""
            # Wait for entry order to settle before placing SL
            time.sleep(10)
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
                time.sleep(10 if attempt < 2 else 30)  # Longer wait for CNC position to settle

            if not sl_order_id:
                self._log("ERROR", f"⚠ {symbol} — SL-M ORDER FAILED after 5 attempts! Position is UNPROTECTED. Place SL manually!")

            # Place CNC limit order at target price (sits on exchange independently)
            target_side = -1 if side == 1 else 1
            target_order_id = ""
            target_result = place_order(
                symbol=symbol,
                qty=qty,
                side=target_side,
                order_type=1,  # Limit
                product_type="CNC",
                limit_price=target,
            )
            if "error" not in target_result:
                target_order_id = target_result.get("id", target_result.get("order_id", ""))
                self._log("ORDER", f"{symbol} — CNC target limit order PLACED (ID: {target_order_id}) at ₹{target}")
            else:
                self._log("WARN", f"{symbol} — target limit order FAILED: {target_result.get('error', '')}. Will monitor via LTP.")

            trade = {
                "symbol": symbol,
                "signal_type": signal_type,
                "side": side,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "target": target,
                "quantity": qty,
                "order_id": entry_order_id,
                "sl_order_id": sl_order_id,
                "target_order_id": target_order_id,
                "risk_reward_ratio": rr,
                "capital_required": qty * entry_price,
                "strategy": signal.get("_strategy", ""),
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
            self._log("ERROR", f"{symbol} — order exception: {e}")
            return False

    # ── Position Monitoring ───────────────────────────────────────────────

    def _update_position_pnl(self):
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

        trades_to_close = []

        for trade in self._active_trades:
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

            # Get LTP from positions or via quotes API
            ltp = ltp_map.get(symbol, 0)
            if ltp == 0:
                ltp = self._get_ltp(symbol)
            target = trade.get("target", 0)
            stop_loss = trade.get("stop_loss", 0)
            side = trade.get("side", 1)

            # Update P&L from LTP if not in positions
            if symbol not in pnl_map and ltp > 0:
                entry = trade.get("entry_price", 0)
                qty = trade.get("quantity", 0)
                if entry > 0 and qty > 0:
                    trade["pnl"] = round((ltp - entry) * qty * side, 2)

            # ── Re-place SL + target orders if missing/expired (CNC orders are DAY validity) ──
            if trade["status"] == "OPEN" and symbol in all_held_symbols and is_market_open():
                qty = trade.get("quantity", 0)
                exit_side = -1 if side == 1 else 1

                # Re-place SL order if not active
                sl_order_id = trade.get("sl_order_id", "")
                has_valid_sl = sl_order_id and self._is_order_pending(sl_order_id)
                if not has_valid_sl:
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

                # Re-place target order if not active
                target_order_id = trade.get("target_order_id", "")
                has_valid_target = target_order_id and self._is_order_pending(target_order_id)
                if not has_valid_target and target > 0:
                    self._log("ORDER", f"{symbol} — no active target order, placing CNC limit at ₹{target}")
                    tgt_result = place_order(
                        symbol=symbol, qty=qty, side=exit_side,
                        order_type=1, product_type="CNC", limit_price=target,
                    )
                    if "error" not in tgt_result:
                        new_tgt_id = tgt_result.get("id", tgt_result.get("order_id", ""))
                        trade["target_order_id"] = new_tgt_id
                        self._log("ORDER", f"{symbol} — target limit re-placed (ID: {new_tgt_id}) at ₹{target}")
                    else:
                        self._log("WARN", f"{symbol} — target re-placement failed: {tgt_result.get('error', '')}")

            # ── Check if target order filled on exchange ──
            target_order_id = trade.get("target_order_id", "")
            if target_order_id and self._is_order_filled(target_order_id):
                # Target hit on exchange — cancel SL, mark closed
                sl_oid = trade.get("sl_order_id", "")
                if sl_oid:
                    try:
                        cancel_order(sl_oid)
                        self._log("ORDER", f"{symbol} — SL order cancelled (target filled)")
                    except Exception:
                        pass
                pnl = trade.get("pnl", 0)
                entry = trade.get("entry_price", 0)
                tgt = trade.get("target", 0)
                if entry > 0 and tgt > 0:
                    pnl = round((tgt - entry) * trade.get("quantity", 0) * side, 2)
                self._total_pnl += pnl
                trade["status"] = "CLOSED"
                trade["closed_at"] = now_ist().isoformat()
                trade["exit_reason"] = "TARGET_HIT"
                trade["exit_price"] = tgt
                trade["pnl"] = pnl
                self._trade_history.append(trade)
                log_trade(trade, source="swing")
                self._log("ORDER", f"{symbol} — TARGET filled on exchange. P&L: ₹{pnl:.2f}")
                continue

            # ── Check if SL order filled on exchange ──
            sl_order_id = trade.get("sl_order_id", "")
            if sl_order_id and self._is_order_filled(sl_order_id):
                # SL hit on exchange — cancel target, mark closed
                tgt_oid = trade.get("target_order_id", "")
                if tgt_oid:
                    try:
                        cancel_order(tgt_oid)
                        self._log("ORDER", f"{symbol} — target order cancelled (SL filled)")
                    except Exception:
                        pass
                pnl = trade.get("pnl", 0)
                entry = trade.get("entry_price", 0)
                sl_price = trade.get("stop_loss", 0)
                if entry > 0 and sl_price > 0:
                    pnl = round((sl_price - entry) * trade.get("quantity", 0) * side, 2)
                self._total_pnl += pnl
                trade["status"] = "CLOSED"
                trade["closed_at"] = now_ist().isoformat()
                trade["exit_reason"] = "SL_HIT"
                trade["exit_price"] = sl_price
                trade["pnl"] = pnl
                self._trade_history.append(trade)
                log_trade(trade, source="swing")
                self._log("ORDER", f"{symbol} — SL filled on exchange. P&L: ₹{pnl:.2f}")
                continue

            # ── Fallback: LTP-based target check (if no target order on exchange) ──
            if ltp > 0 and target > 0 and not target_order_id:
                target_hit = (side == 1 and ltp >= target) or (side == -1 and ltp <= target)
                if target_hit:
                    trade["exit_reason"] = "TARGET_HIT"
                    trades_to_close.append(trade)
                    continue

            # ── Fallback: position gone from both positions + holdings ──
            if trade["status"] == "OPEN" and symbol not in all_held_symbols:
                if not sl_order_id:
                    # No SL order — check LTP against SL level
                    if ltp > 0 and stop_loss > 0:
                        sl_hit = (side == 1 and ltp <= stop_loss) or (side == -1 and ltp >= stop_loss)
                        if sl_hit:
                            self._log("ORDER", f"{symbol} — SL level breached (LTP ₹{ltp} vs SL ₹{stop_loss}). Placing market exit...")
                            self._exit_trade_at_market(trade, "SL_HIT")
                        else:
                            self._log("WARN", f"{symbol} — not found in positions/holdings but SL not breached (LTP ₹{ltp}). May be settlement delay.")
                    else:
                        self._log("WARN", f"{symbol} — not found in positions/holdings, no SL order, cannot determine LTP")

        # Exit target-hit positions
        for trade in trades_to_close:
            self._exit_trade_at_target(trade)

        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()

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

    def _is_order_filled(self, order_id: str) -> bool:
        """Check if a specific order was filled (status=2 in Fyers)."""
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
        """Check if a specific order is still pending/open (status=6 or trigger_pending in Fyers)."""
        try:
            orderbook = get_orderbook()
            orders = orderbook.get("orderBook", [])
            for order in orders:
                if order.get("id", "") == order_id:
                    # Fyers status: 1=cancelled, 2=traded/filled, 4=transit, 5=rejected, 6=pending
                    status = order.get("status", 0)
                    return status in (4, 6)  # transit or pending (includes trigger-pending SL orders)
            return False
        except Exception:
            return False

    def _get_ltp(self, symbol: str) -> float:
        """Get last traded price for a symbol via quotes API."""
        try:
            fyers_symbol = f"NSE:{symbol}-EQ"
            quotes = get_quotes([fyers_symbol])
            if quotes and "d" in quotes:
                for q in quotes["d"]:
                    if q.get("n", "") == fyers_symbol:
                        return q.get("v", {}).get("lp", 0)
            return 0
        except Exception:
            return 0

    def _exit_trade_at_market(self, trade: dict, reason: str):
        """Exit a trade at market price (used when SL breached but no SL order on exchange)."""
        symbol = trade["symbol"]
        qty = trade["quantity"]
        side = trade["side"]
        close_side = -1 if side == 1 else 1

        # Cancel any pending target order
        target_order_id = trade.get("target_order_id", "")
        if target_order_id:
            try:
                cancel_order(target_order_id)
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
                ltp = self._get_ltp(symbol)
                entry = trade.get("entry_price", 0)
                pnl = round((ltp - entry) * qty * side, 2) if ltp > 0 and entry > 0 else trade.get("pnl", 0)
                self._total_pnl += pnl
                trade["status"] = "CLOSED"
                trade["closed_at"] = now_ist().isoformat()
                trade["exit_reason"] = reason
                trade["exit_price"] = ltp if ltp > 0 else trade.get("stop_loss", 0)
                trade["pnl"] = pnl
                self._trade_history.append(trade)
                log_trade(trade, source="swing")
                self._log("ORDER", f"{symbol} — market exit placed. P&L: ₹{pnl:.2f}")
            else:
                self._log("ERROR", f"{symbol} — market exit FAILED: {result['error']}. SELL MANUALLY!")
        except Exception as e:
            self._log("ERROR", f"{symbol} — market exit exception: {e}. SELL MANUALLY!")

    def _exit_trade_at_target(self, trade: dict):
        """Fallback target exit via market order (when no target limit order on exchange)."""
        symbol = trade["symbol"]
        qty = trade["quantity"]
        side = trade["side"]
        close_side = -1 if side == 1 else 1

        self._log("ORDER", f"{symbol} — TARGET HIT (LTP)! Closing swing position")

        # Cancel SL order
        sl_order_id = trade.get("sl_order_id", "")
        if sl_order_id:
            try:
                cancel_order(sl_order_id)
            except Exception:
                pass

        # Cancel target order if exists
        target_order_id = trade.get("target_order_id", "")
        if target_order_id:
            try:
                cancel_order(target_order_id)
            except Exception:
                pass

        try:
            result = place_order(
                symbol=symbol,
                qty=qty,
                side=close_side,
                order_type=2,
                product_type="CNC",
            )

            if "error" not in result:
                pnl = trade.get("pnl", 0)
                self._total_pnl += pnl
                trade["status"] = "CLOSED"
                trade["closed_at"] = now_ist().isoformat()
                trade["exit_reason"] = "TARGET_HIT"
                trade["exit_price"] = trade.get("ltp", trade.get("target", 0))
                self._trade_history.append(trade)
                log_trade(trade, source="swing")
                self._log("ORDER", f"{symbol} — closed at target. P&L: ₹{pnl:.2f}")
            else:
                self._log("ERROR", f"{symbol} — target exit failed: {result['error']}")
        except Exception as e:
            self._log("ERROR", f"{symbol} — target exit exception: {e}")

    def _get_open_positions_detail(self) -> tuple[set, list]:
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
        self._logger.log(level, message)


# ── Singleton Instance ────────────────────────────────────────────────────

swing_trader = SwingTrader()
