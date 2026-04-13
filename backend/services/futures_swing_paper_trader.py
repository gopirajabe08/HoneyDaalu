"""
Futures Swing Paper Trading Engine (Virtual).

Mirrors futures_swing_trader but with virtual positions.
No real orders. State persists across days.
Daily loss limit and per-position max loss cap enforced.
"""

import threading
import logging
import time
from datetime import timedelta
from typing import Optional

from services.scanner import is_market_open
from services.futures_scanner import run_futures_scan
from services.futures_oi_analyser import analyse_batch
from services.futures_client import get_futures_ltp_batch, days_to_expiry
from services.trade_logger import log_trade
from services.broker_client import is_authenticated
from fno_stocks import get_fno_symbols
from utils.time_utils import now_ist
from utils.state_manager import get_state_path, save_state, load_state
from utils.trader_log import TraderLogger
from config import (
    FUTURES_SWING_PAPER_MAX_POSITIONS,
    FUTURES_SWING_SCAN_INTERVAL_SECONDS,
    FUTURES_SWING_EXIT_DAYS_BEFORE_EXPIRY,
    FUTURES_DAILY_LOSS_LIMIT_PCT,
)

logger = logging.getLogger(__name__)

STATE_FILE = get_state_path(".futures_swing_paper_state.json")

POSITION_MAX_LOSS_PCT = 3.0


class FuturesSwingPaperTrader:
    """Virtual futures swing trading engine."""

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
        self._next_order_id: int = 1

        self._logger = TraderLogger("FuturesSwingPaper")
        self._load_state()

    @property
    def is_running(self) -> bool:
        return self._running

    def _reset_daily_pnl_if_new_day(self):
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
            self._log("ALERT", f"DAILY LOSS LIMIT HIT: ₹{self._daily_realized_pnl:,.2f} ({loss_pct:.1f}%). No new orders.")
            return True
        return False

    def _check_position_max_loss(self, trade: dict) -> bool:
        if self._capital <= 0:
            return False
        pnl = trade.get("pnl", 0)
        if pnl < 0 and abs(pnl) / self._capital * 100 >= POSITION_MAX_LOSS_PCT:
            return True
        return False

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
            "next_order_id": self._next_order_id,
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "FuturesSwingPaperTrader")

    def _load_state(self):
        try:
            state = load_state(STATE_FILE, "FuturesSwingPaperTrader")
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
            self._next_order_id = state.get("next_order_id", 1)
            self._logger.entries = state.get("logs", [])

            was_running = state.get("running", False)
            if self._strategy_keys and was_running and is_market_open():
                self._log("RESTORE", "Futures swing paper was running — auto-resuming...")
                self._running = True
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.start()
        except Exception as e:
            logger.warning(f"[FuturesSwingPaperTrader] Load state failed: {e}")

    def start(self, strategies: list[dict], capital: float, scan_interval_minutes: int = 240) -> dict:
        with self._lock:
            if self._running:
                return {"error": "Already running"}
            if not is_market_open():
                return {"error": "Market is closed."}
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
            self._next_order_id = 1

            strat_names = ", ".join(f"{k}({self._timeframes[k]})" for k in self._strategy_keys)
            self._log("START", f"Futures swing paper STARTED — {strat_names} | Capital=₹{capital:,.0f}")
            self._log("INFO", f"Virtual swing — Max {FUTURES_SWING_PAPER_MAX_POSITIONS} positions | Daily loss limit: {FUTURES_DAILY_LOSS_LIMIT_PCT}%")

            self._save_state()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

            return {
                "status": "started",
                "mode": "futures_swing_paper",
                "strategies": [{"strategy": k, "timeframe": self._timeframes[k]} for k in self._strategy_keys],
                "capital": capital,
            }

    def stop(self) -> dict:
        with self._lock:
            if not self._running:
                return {"status": "already_stopped"}
            self._running = False
            self._log("STOP", "Futures swing paper STOPPED")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._save_state()
        return {"status": "stopped", "total_pnl": round(self._total_pnl, 2)}

    def status(self) -> dict:
        return {
            "is_running": self._running,
            "mode": "futures_swing_paper",
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

    def _run_loop(self):
        self._log("INFO", "Background thread started")
        self._execute_scan_cycle()

        while self._running:
            if not is_market_open():
                while self._running and not is_market_open():
                    time.sleep(60)
                if not self._running:
                    break
                self._reset_daily_pnl_if_new_day()
                self._execute_scan_cycle()
                continue

            dte = days_to_expiry()
            if dte <= FUTURES_SWING_EXIT_DAYS_BEFORE_EXPIRY and self._active_trades:
                self._log("ALERT", f"Expiry in {dte} days — closing virtual positions")
                self._close_all_for_expiry()

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
        self._save_state()

    def _execute_scan_cycle(self):
        self._scan_count += 1
        self._update_position_pnl()

        if self._check_daily_loss_limit():
            return

        if len(self._active_trades) >= FUTURES_SWING_PAPER_MAX_POSITIONS:
            self._log("INFO", "Max positions reached — monitoring only")
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

        seen = {}
        for sig in all_signals:
            sym = sig.get("symbol", "")
            score = sig.get("oi_conviction", 0)
            if sym not in seen or score > seen[sym][1]:
                seen[sym] = (sig, score)

        unique = [s[0] for s in sorted(seen.values(), key=lambda x: x[1], reverse=True)]
        self._log("SCAN", f"Scan #{self._scan_count} — {len(unique)} signals")

        active_syms = {t["symbol"] for t in self._active_trades}
        for signal in unique:
            if len(self._active_trades) >= FUTURES_SWING_PAPER_MAX_POSITIONS:
                break
            sym = signal.get("symbol", "")
            if sym in active_syms:
                continue
            self._place_virtual_order(signal)
            break

        self._save_state()

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
        side = 1 if signal_type == "BUY" else -1
        slippage = entry * 0.001
        entry = round(entry + slippage if side == 1 else entry - slippage, 2)

        # Realistic brokerage + STT + other charges (futures)
        turnover = entry * qty
        brokerage_per_leg = min(20, turnover * 0.0003)  # ₹20 or 0.03% (whichever lower)
        brokerage = round(brokerage_per_leg * 2, 2)  # Entry + Exit = 2 legs
        stt = round(turnover * 0.0002, 2)  # Futures: STT = 0.02% on sell side
        exchange_charges = round(turnover * 0.0003, 2)  # NSE transaction + SEBI + stamp
        est_brokerage = round(brokerage + stt + exchange_charges, 2)

        order_id = f"FSWPAPER-{self._next_order_id:04d}"
        self._next_order_id += 1

        self._log("ORDER", f"Virtual SWING {signal_type}: {symbol} | {signal.get('num_lots', 0)} lots | Entry=₹{entry} (incl slippage)")

        trade = {
            "symbol": symbol, "signal_type": signal_type,
            "side": side,
            "entry_price": entry, "stop_loss": sl, "target": target,
            "quantity": qty, "lot_size": signal.get("lot_size", 0),
            "num_lots": signal.get("num_lots", 0), "order_id": order_id,
            "strategy": signal.get("_strategy", ""), "timeframe": signal.get("_timeframe", ""),
            "oi_sentiment": signal.get("oi_sentiment", ""),
            "placed_at": now_ist().isoformat(), "status": "OPEN", "pnl": 0.0, "ltp": entry,
            "est_brokerage": est_brokerage,
        }

        self._active_trades.append(trade)
        self._order_count += 1
        self._save_state()
        return True

    def _close_all_for_expiry(self):
        symbols = [t["symbol"] for t in self._active_trades]
        ltp_map = get_futures_ltp_batch(symbols)

        for trade in self._active_trades:
            ltp = ltp_map.get(trade["symbol"], trade.get("ltp", trade["entry_price"]))
            side = trade["side"]
            gross_pnl = round((ltp - trade["entry_price"]) * trade["quantity"] * (1 if side == 1 else -1), 2)
            brokerage = trade.get("est_brokerage", 0)
            net_pnl = round(gross_pnl - brokerage, 2)
            trade["pnl"] = net_pnl
            trade["gross_pnl"] = gross_pnl
            trade["charges"] = brokerage
            trade["ltp"] = ltp
            trade["status"] = "CLOSED"
            trade["closed_at"] = now_ist().isoformat()
            trade["exit_price"] = ltp
            trade["exit_reason"] = "EXPIRY_CLOSE"
            self._total_pnl += net_pnl
            self._daily_realized_pnl += net_pnl
            self._trade_history.append(trade)
            log_trade(trade, source="futures_swing_paper")
            self._log("ORDER", f"{trade['symbol']} — expiry close | Net P&L: ₹{net_pnl:,.2f} (charges: ₹{brokerage})")

        self._active_trades = []
        self._save_state()

    def _update_position_pnl(self):
        if not self._active_trades:
            return

        symbols = [t["symbol"] for t in self._active_trades]
        ltp_map = get_futures_ltp_batch(symbols)

        trades_to_close = []
        for trade in self._active_trades:
            ltp = ltp_map.get(trade["symbol"], trade.get("ltp", trade.get("entry_price", 0)))
            side = trade["side"]
            pnl = round((ltp - trade["entry_price"]) * trade["quantity"] * (1 if side == 1 else -1), 2)
            trade["pnl"] = pnl
            trade["ltp"] = ltp

            if self._check_position_max_loss(trade):
                trade["exit_reason"] = "MAX_LOSS_CAP"
                trades_to_close.append(trade)
                continue

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
            self._daily_realized_pnl += net_pnl
            self._trade_history.append(trade)
            log_trade(trade, source="futures_swing_paper")
            self._log("ORDER", f"{trade['symbol']} — {trade['exit_reason']} | Net P&L: ₹{net_pnl:,.2f} (charges: ₹{brokerage})")

        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()
        self._check_daily_loss_limit()

    def _log(self, level: str, message: str):
        self._logger.log(level, message)


futures_swing_paper_trader = FuturesSwingPaperTrader()
