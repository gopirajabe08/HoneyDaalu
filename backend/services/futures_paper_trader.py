"""
Futures Paper Trading Engine (Intraday Virtual).

Mirrors futures_auto_trader exactly but uses virtual positions instead of real orders.
Same rules: OI-filtered scan, max positions, 2% risk, order cutoff 2 PM, square-off 3:15 PM.
"""

import threading
import logging
import time
from typing import Optional

from services.scanner import is_market_open
from services.futures_scanner import run_futures_scan
from services.futures_oi_analyser import analyse_batch
from services.futures_regime import detect_futures_regime
from services.futures_client import get_futures_ltp_batch
from services.trade_logger import log_trade
from services.fyers_client import is_authenticated
from fno_stocks import get_fno_symbols
from utils.time_utils import now_ist, is_past_time, is_before_time
from utils.state_manager import get_state_path, save_state, load_state
from utils.trader_log import TraderLogger
from config import (
    FUTURES_ORDER_START_HOUR, FUTURES_ORDER_START_MIN,
    FUTURES_ORDER_CUTOFF_HOUR, FUTURES_ORDER_CUTOFF_MIN,
    FUTURES_SQUAREOFF_HOUR, FUTURES_SQUAREOFF_MIN,
    FUTURES_PAPER_MAX_POSITIONS, FUTURES_POSITION_CHECK_INTERVAL,
    FUTURES_DAILY_LOSS_LIMIT_PCT,
)

logger = logging.getLogger(__name__)

STATE_FILE = get_state_path(".futures_paper_trader_state.json")


def _is_before_order_start() -> bool:
    return is_before_time(FUTURES_ORDER_START_HOUR, FUTURES_ORDER_START_MIN)


def _is_past_order_cutoff() -> bool:
    return is_past_time(FUTURES_ORDER_CUTOFF_HOUR, FUTURES_ORDER_CUTOFF_MIN)


def _is_squareoff_time() -> bool:
    return is_past_time(FUTURES_SQUAREOFF_HOUR, FUTURES_SQUAREOFF_MIN)


class FuturesPaperTrader:
    """Virtual futures intraday trading engine."""

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
        self._scan_count: int = 0
        self._order_count: int = 0
        self._started_at: Optional[str] = None
        self._squared_off: bool = False
        self._next_scan_at: Optional[str] = None
        self._next_order_id: int = 1
        self._auto_mode: bool = False
        self._daily_realized_pnl: float = 0.0
        self._daily_loss_limit_hit: bool = False

        self._logger = TraderLogger("FuturesPaper")
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
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "started_at": self._started_at,
            "squared_off": self._squared_off,
            "next_order_id": self._next_order_id,
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "FuturesPaperTrader")

    def _load_state(self):
        try:
            state = load_state(STATE_FILE, "FuturesPaperTrader")
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
            self._scan_count = state.get("scan_count", 0)
            self._order_count = state.get("order_count", 0)
            self._started_at = state.get("started_at")
            self._squared_off = state.get("squared_off", False)
            self._next_order_id = state.get("next_order_id", 1)
            self._logger.entries = state.get("logs", [])

            was_running = state.get("running", False)
            if self._strategy_keys and was_running and not self._squared_off and is_market_open():
                if not _is_past_order_cutoff():
                    self._log("RESTORE", "Futures paper trader was running — auto-resuming...")
                    self._running = True
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif is_market_open():
                    self._log("RESTORE", "Past cutoff — monitoring positions only")
                    self._running = True
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
        except Exception as e:
            logger.warning(f"[FuturesPaperTrader] Failed to load state: {e}")

    # ── Controls ──────────────────────────────────────────────────────────

    def start(self, strategies: list[dict], capital: float) -> dict:
        with self._lock:
            if self._running:
                return {"error": "Futures paper trader is already running"}

            if not is_market_open():
                return {"error": "Market is closed. Paper trading runs during market hours."}

            if _is_past_order_cutoff():
                return {"error": "Cannot start after 2:00 PM IST."}

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
            self._scan_count = 0
            self._order_count = 0
            self._squared_off = False
            self._started_at = now_ist().isoformat()
            self._next_order_id = 1
            self._daily_realized_pnl = 0.0
            self._daily_loss_limit_hit = False

            strat_names = ", ".join(f"{k}({self._timeframes[k]})" for k in self._strategy_keys)
            self._log("START", f"Futures paper trader STARTED — {strat_names} | Capital=₹{capital:,.0f}")
            self._log("INFO", f"Virtual futures — NO real orders | Max positions: {FUTURES_PAPER_MAX_POSITIONS}")

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
                return {"status": "already_stopped"}
            self._running = False
            self._log("STOP", "Futures paper trader STOPPED by user")

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
            "strategies": [{"strategy": k, "timeframe": self._timeframes.get(k, "")} for k in self._strategy_keys],
            "capital": self._capital,
            "started_at": self._started_at,
            "scan_count": self._scan_count,
            "order_count": self._order_count,
            "total_pnl": round(self._total_pnl, 2),
            "active_trades": self._active_trades,
            "trade_history": self._trade_history[-20:],
            "squared_off": self._squared_off,
            "order_cutoff_passed": _is_past_order_cutoff(),
            "logs": self._logger.recent(100),
        }

    # ── Main Loop ─────────────────────────────────────────────────────────

    def _run_loop(self):
        self._log("INFO", "Background thread started")

        # Wait for 11:00 AM order window
        while self._running and _is_before_order_start():
            self._log("INFO", "Waiting for 11:00 AM order window...")
            for _ in range(60):
                if not self._running or not _is_before_order_start():
                    break
                time.sleep(1)

        if not _is_past_order_cutoff() and is_market_open() and self._running:
            self._log("SCAN", "11:00 AM — initial scan to fill slots")
            self._execute_scan_cycle()

        prev_open = len(self._active_trades)
        _monitor_tick = 0  # counter for periodic health checks

        while self._running:
            if _is_squareoff_time() and not self._squared_off:
                self._log("ALERT", "3:15 PM — virtual square-off")
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
                        self._log("WARN", "Fyers disconnected — using delayed data. Reconnect via UI.")
                except Exception:
                    pass

            current = len(self._active_trades)

            if current < prev_open and current < FUTURES_PAPER_MAX_POSITIONS:
                if not _is_past_order_cutoff() and is_market_open():
                    self._log("SCAN", "Slot opened — scanning")
                    self._execute_scan_cycle()
                    current = len(self._active_trades)

            # Periodic re-scan: if 0 positions, re-scan every ~15 min
            elif current == 0 and not _is_past_order_cutoff() and is_market_open():
                if _monitor_tick > 0 and _monitor_tick % 15 == 0:  # ~15 min at 60s intervals
                    self._log("SCAN", "No positions — periodic re-scan")
                    self._execute_scan_cycle()
                    current = len(self._active_trades)

            prev_open = current

        self._log("INFO", "Background thread exited")
        self._save_state()

    def _check_daily_loss_limit(self) -> bool:
        if self._daily_loss_limit_hit:
            return True
        if self._capital <= 0:
            return False
        loss_pct = abs(self._daily_realized_pnl) / self._capital * 100
        if self._daily_realized_pnl < 0 and loss_pct >= FUTURES_DAILY_LOSS_LIMIT_PCT:
            self._daily_loss_limit_hit = True
            self._log("ALERT", f"DAILY LOSS LIMIT HIT: ₹{self._daily_realized_pnl:,.2f} ({loss_pct:.1f}%). No new orders.")
            return True
        return False

    def _check_drawdown_breaker(self) -> bool:
        """Check if multi-day drawdown exceeds 15% of capital. Returns True if breaker triggered."""
        try:
            from services.trade_logger import get_all_trades
            recent = get_all_trades(days=5)
            futures_trades = [t for t in recent if t.get("source") == "futures_paper"]
            if len(futures_trades) >= 5:
                pnl = sum(t.get("pnl", 0) for t in futures_trades)
                if pnl < -self._capital * 0.15:
                    return True
        except Exception:
            pass
        return False

    def _execute_scan_cycle(self):
        self._scan_count += 1

        # Multi-day drawdown breaker
        if self._check_drawdown_breaker():
            self._log("ALERT", "5-day drawdown > 15% — reducing to 1 order per scan (safety mode)")

        if self._check_daily_loss_limit():
            return

        if len(self._active_trades) >= FUTURES_PAPER_MAX_POSITIONS:
            self._log("INFO", "Max positions reached")
            return

        # Fetch OI
        oi_data = analyse_batch(get_fno_symbols())

        # Re-detect regime on every scan (auto mode)
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

        slots = FUTURES_PAPER_MAX_POSITIONS - len(self._active_trades)
        all_signals = []

        for key in self._strategy_keys:
            tf = self._timeframes.get(key, "15m")
            result = run_futures_scan(key, tf, self._capital, oi_data=oi_data)
            if "error" in result:
                continue
            signals = result.get("signals", [])
            for sig in signals:
                sig["_strategy"] = key
                sig["_timeframe"] = tf
            all_signals.extend(signals)
            self._log("SCAN", f"  {key}({tf}): {len(signals)} signals")

        # Direction filter: align with NIFTY intraday direction
        # Bearish regime → only SELL. Bullish → only BUY. Neutral → both.
        try:
            from services.equity_regime import detect_equity_regime
            regime = detect_equity_regime()
            regime_name = regime.get("regime", "")
            if "bearish" in regime_name:
                before = len(all_signals)
                all_signals = [s for s in all_signals if s.get("signal_type") == "SELL"]
                if len(all_signals) < before:
                    self._log("FILTER", f"Bearish regime — filtered {before - len(all_signals)} BUY signals, kept {len(all_signals)} SELL")
            elif "bullish" in regime_name:
                before = len(all_signals)
                all_signals = [s for s in all_signals if s.get("signal_type") == "BUY"]
                if len(all_signals) < before:
                    self._log("FILTER", f"Bullish regime — filtered {before - len(all_signals)} SELL signals, kept {len(all_signals)} BUY")
        except Exception:
            pass

        # Deduplicate
        seen = {}
        for sig in all_signals:
            sym = sig.get("symbol", "")
            score = sig.get("oi_conviction", 0) + sig.get("reward", 0) / max(sig.get("risk", 1), 0.01)
            if sym not in seen or score > seen[sym][1]:
                seen[sym] = (sig, score)

        unique = [s[0] for s in sorted(seen.values(), key=lambda x: x[1], reverse=True)]
        self._log("SCAN", f"Scan #{self._scan_count} — {len(unique)} signals")
        self._save_state()

        max_orders_per_scan = 1 if self._check_drawdown_breaker() else min(2, slots)
        orders = 0
        active_syms = {t["symbol"] for t in self._active_trades}

        for signal in unique:
            if orders >= max_orders_per_scan:
                self._log("INFO", f"Max 2 orders per scan — remaining slots will fill on next scan")
                break
            if _is_past_order_cutoff():
                break
            sym = signal.get("symbol", "")
            if sym in active_syms:
                continue
            if self._place_virtual_order(signal):
                orders += 1
                active_syms.add(sym)

    def _place_virtual_order(self, signal: dict) -> bool:
        symbol = signal.get("symbol", "")
        signal_type = signal.get("signal_type", "")
        entry = signal.get("entry_price", 0)
        sl = signal.get("stop_loss", 0)
        target = signal.get("target_1", 0)
        qty = signal.get("quantity", 0)

        if not all([symbol, signal_type, entry, sl, target, qty]):
            return False

        # Simulate slippage (0.1% worse entry)
        slippage = entry * 0.001
        side = 1 if signal_type == "BUY" else -1
        entry = round(entry + slippage if side == 1 else entry - slippage, 2)

        # Realistic Fyers brokerage + STT + other charges (futures)
        turnover = entry * qty
        brokerage_per_leg = min(20, turnover * 0.0003)  # ₹20 or 0.03% (whichever lower)
        brokerage = round(brokerage_per_leg * 2, 2)  # Entry + Exit = 2 legs
        stt = round(turnover * 0.0002, 2)  # Futures: STT = 0.02% on sell side
        exchange_charges = round(turnover * 0.0003, 2)  # NSE transaction + SEBI + stamp
        est_brokerage = round(brokerage + stt + exchange_charges, 2)

        order_id = f"FPAPER-{self._next_order_id:04d}"
        self._next_order_id += 1

        self._log("ORDER", f"Virtual {signal_type}: {symbol} | {signal.get('num_lots', 0)} lots ({qty} qty) | Entry=₹{entry} (incl slippage) | SL=₹{sl} | Target=₹{target}")

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
            "strategy": signal.get("_strategy", ""),
            "timeframe": signal.get("_timeframe", ""),
            "oi_sentiment": signal.get("oi_sentiment", ""),
            "placed_at": now_ist().isoformat(),
            "status": "OPEN",
            "pnl": 0.0,
            "ltp": entry,
            "est_brokerage": est_brokerage,
            "original_sl": sl,
            "max_favorable_price": entry,
        }

        self._active_trades.append(trade)
        self._order_count += 1
        self._save_state()
        return True

    # ── Square Off ────────────────────────────────────────────────────────

    def _square_off_all(self):
        if not self._active_trades:
            self._log("INFO", "No virtual positions to square off")
            return

        symbols = [t["symbol"] for t in self._active_trades]
        ltp_map = get_futures_ltp_batch(symbols)

        for trade in self._active_trades:
            symbol = trade["symbol"]
            ltp = ltp_map.get(symbol, trade.get("ltp", trade["entry_price"]))
            side = trade["side"]
            pnl = round((ltp - trade["entry_price"]) * trade["quantity"] * (1 if side == 1 else -1), 2)

            brokerage = trade.get("est_brokerage", 0)
            net_pnl = round(pnl - brokerage, 2)
            trade["pnl"] = net_pnl
            trade["gross_pnl"] = pnl
            trade["charges"] = brokerage
            trade["ltp"] = ltp
            trade["status"] = "CLOSED"
            trade["closed_at"] = now_ist().isoformat()
            trade["exit_price"] = ltp
            trade["exit_reason"] = "SQUARE_OFF"
            self._total_pnl += net_pnl
            self._daily_realized_pnl += net_pnl
            self._trade_history.append(trade)
            log_trade(trade, source="futures_paper")
            self._log("SQUAREOFF", f"{symbol} — ₹{ltp} | Net P&L: ₹{net_pnl:,.2f} (charges: ₹{brokerage})")

        self._active_trades = []
        self._log("ALERT", f"Virtual square-off complete. P&L: ₹{self._total_pnl:,.2f}")
        self._save_state()

        # End-of-day pipeline (runs once per day, shared across all engines)
        try:
            from services.auto_tuner import run_eod_pipeline
            eod = run_eod_pipeline("futures_paper")
            if eod.get("status") == "completed":
                self._log("TRACKER", f"EOD pipeline completed — {eod.get('report', {}).get('total_trades', 0)} trades analyzed")
        except Exception as e:
            logger.warning(f"[FuturesPaper] EOD pipeline failed: {e}")

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
            entry = trade["entry_price"]
            pnl = round((ltp - entry) * trade["quantity"] * (1 if side == 1 else -1), 2)
            trade["pnl"] = pnl
            trade["ltp"] = ltp

            # ── Trailing stop loss — lock in profits on winning trades ──
            if "original_sl" not in trade:
                trade["original_sl"] = trade["stop_loss"]

            if side == 1:  # BUY
                max_fav = max(trade.get("max_favorable_price", entry), ltp)
                trade["max_favorable_price"] = max_fav
                profit_pct = (max_fav - entry) / entry * 100 if entry > 0 else 0
                if profit_pct >= 1.0:
                    trail_sl = round(entry + (max_fav - entry) * 0.5, 2)
                    if trail_sl > trade["stop_loss"]:
                        old_sl = trade["stop_loss"]
                        trade["stop_loss"] = trail_sl
                        self._log("TRAIL", f"{symbol} — SL trailed ₹{old_sl} → ₹{trail_sl} (max ₹{max_fav}, +{profit_pct:.1f}%)")
            else:  # SELL
                max_fav = min(trade.get("max_favorable_price", entry), ltp)
                trade["max_favorable_price"] = max_fav
                profit_pct = (entry - max_fav) / entry * 100 if entry > 0 else 0
                if profit_pct >= 1.0:
                    trail_sl = round(entry - (entry - max_fav) * 0.5, 2)
                    if trail_sl < trade["stop_loss"]:
                        old_sl = trade["stop_loss"]
                        trade["stop_loss"] = trail_sl
                        self._log("TRAIL", f"{symbol} — SL trailed ₹{old_sl} → ₹{trail_sl} (max ₹{max_fav}, +{profit_pct:.1f}%)")

            if (side == 1 and ltp <= trade["stop_loss"]) or (side == -1 and ltp >= trade["stop_loss"]):
                trade["exit_reason"] = "SL_HIT"
                trades_to_close.append(trade)
            elif (side == 1 and ltp >= trade["target"]) or (side == -1 and ltp <= trade["target"]):
                trade["exit_reason"] = "TARGET_HIT"
                trades_to_close.append(trade)

        for trade in trades_to_close:
            gross_pnl = trade["pnl"]
            brokerage = trade.get("est_brokerage", 0)
            net_pnl = round(gross_pnl - brokerage, 2)
            trade["pnl"] = net_pnl
            trade["gross_pnl"] = gross_pnl
            trade["charges"] = brokerage
            trade["status"] = "CLOSED"
            trade["closed_at"] = now_ist().isoformat()
            trade["exit_price"] = trade["ltp"]
            self._total_pnl += net_pnl
            self._trade_history.append(trade)
            log_trade(trade, source="futures_paper")
            self._daily_realized_pnl += trade["pnl"]
            self._log("ORDER", f"{trade['symbol']} — {trade['exit_reason']} at ₹{trade['ltp']} | P&L: ₹{trade['pnl']:,.2f}")

        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()
        self._check_daily_loss_limit()

    def _log(self, level: str, message: str):
        self._logger.log(level, message)


# ── Singleton Instance ────────────────────────────────────────────────────

futures_paper_trader = FuturesPaperTrader()
