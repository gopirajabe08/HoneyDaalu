"""
Swing Paper Trading Engine for IntraTrading.

Mirrors swing trading rules but uses virtual positions.
Key differences from intraday paper trader:
  - Max 5 open positions
  - NO 2 PM order cutoff
  - NO 3:15 PM square-off — positions carry over days
  - Configurable scan interval (default 4 hours)
  - State persists across days (no date filtering)
  - Exit on SL/target/strategy signal only
"""

import threading
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from services.scanner import run_scan, is_market_open, _calc_conviction
from services.trade_logger import log_trade
from services.fyers_client import get_quotes, is_authenticated
from config import SWING_PAPER_MAX_POSITIONS, SWING_SCAN_INTERVAL_SECONDS, SWING_DAILY_SCAN_TIMES
from utils.time_utils import now_ist
from utils.state_manager import get_state_path, save_state, load_state
from utils.trader_log import TraderLogger

logger = logging.getLogger(__name__)

STATE_FILE = get_state_path(".swing_paper_state.json")


class SwingPaperTrader:
    """
    Virtual swing trading engine.
    Same scan/signal logic but no real orders.
    Positions carry over days. Max 1 position. No time-based square-off.
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
        self._next_order_id: int = 1

        # Shared utilities
        self._logger = TraderLogger("SwingPaper")

        self._load_state()

    @property
    def is_running(self) -> bool:
        return self._running

    # ── State Persistence (cross-day — no date filter) ───────────────────

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
            "next_order_id": self._next_order_id,
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "SwingPaper")

    def _load_state(self):
        try:
            state = load_state(STATE_FILE, "SwingPaper")
            if not state:
                return

            # No date filter — swing positions carry over days
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
            self._next_order_id = state.get("next_order_id", 1)

            was_running = state.get("running", False)

            if self._strategy_keys:
                strat_names = ", ".join(f"{k}({self._timeframes.get(k, '')})" for k in self._strategy_keys)
                self._log("RESTORE", f"Restored swing state — {len(self._strategy_keys)} strategies: {strat_names} | "
                          f"Active: {len(self._active_trades)} | History: {len(self._trade_history)} | P&L: ₹{self._total_pnl:,.2f}")

                if was_running and is_market_open():
                    self._log("RESTORE", "Swing paper trader was running — auto-resuming...")
                    self._running = True
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif was_running:
                    self._log("RESTORE", "Swing paper trader was running but market closed — will resume when market opens")

        except Exception as e:
            logger.warning(f"[SwingPaper] Failed to load state: {e}")

    # ── Controls ──────────────────────────────────────────────────────────

    def start(self, strategies: list[dict], capital: float, scan_interval_minutes: int = 240) -> dict:
        with self._lock:
            if self._running:
                return {"error": "Swing paper trader is already running"}

            if not is_market_open():
                now = now_ist()
                if now.weekday() >= 5:
                    return {"error": "Market is closed (Weekend). Swing trading scans run during market hours."}
                return {"error": "Market is closed. Swing trading scans run during market hours (9:15 AM - 3:30 PM IST)."}

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
            self._next_order_id = 1

            strat_names = ", ".join(f"{k}({self._timeframes[k]})" for k in self._strategy_keys)
            if scan_interval_minutes == 0:
                times_str = ", ".join(f"{h}:{m:02d}" for h, m in SWING_DAILY_SCAN_TIMES)
                self._log("START", f"Swing paper trader STARTED — {strat_names} | Capital=₹{capital:,.0f} | Daily scans at {times_str} IST")
            else:
                self._log("START", f"Swing paper trader STARTED — {strat_names} | Capital=₹{capital:,.0f} | Scan every {scan_interval_minutes}min")
            self._log("INFO", f"SWING MODE — Max {SWING_PAPER_MAX_POSITIONS} position | No time cutoff | Positions carry over days")

            self._save_state()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

            return {
                "status": "started",
                "mode": "swing_paper",
                "strategies": [{"strategy": k, "timeframe": self._timeframes[k]} for k in self._strategy_keys],
                "capital": capital,
                "scan_interval_minutes": scan_interval_minutes,
                "started_at": self._started_at,
            }

    def stop(self) -> dict:
        with self._lock:
            if not self._running:
                return {"status": "already_stopped", "message": "Swing paper trader is not running"}

            self._running = False
            self._log("STOP", "Swing paper trader STOPPED by user")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._save_state()

        return {
            "status": "stopped",
            "total_scans": self._scan_count,
            "total_orders": self._order_count,
            "total_pnl": round(self._total_pnl, 2),
            "active_positions": len(self._active_trades),
        }

    def force_close_trade(self, symbol: str) -> dict:
        """Force-close an active paper trade by symbol."""
        with self._lock:
            trade = None
            for t in self._active_trades:
                if t["symbol"] == symbol and t["status"] == "OPEN":
                    trade = t
                    break
            if not trade:
                return {"error": f"No active trade found for {symbol}"}

            trade["status"] = "CLOSED"
            trade["exit_reason"] = "MANUAL_CLOSE"
            trade["closed_at"] = now_ist().isoformat()
            trade["exit_price"] = trade.get("ltp", trade["entry_price"])
            gross_pnl = trade.get("pnl", 0)
            brokerage = trade.get("est_brokerage", 0)
            net_pnl = round(gross_pnl - brokerage, 2)
            trade["pnl"] = net_pnl
            trade["gross_pnl"] = gross_pnl
            trade["charges"] = brokerage
            self._total_pnl += net_pnl
            self._trade_history.append(trade)
            log_trade(trade, source="swing_paper")
            self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
            self._log("ORDER", f"{symbol} — MANUAL CLOSE | Net P&L: ₹{net_pnl:,.2f} (charges: ₹{brokerage})")
            self._save_state()
            return {"status": "closed", "symbol": symbol, "pnl": round(net_pnl, 2)}

    def trigger_scan(self) -> dict:
        """Trigger an immediate scan (on-demand)."""
        if not self._running:
            return {"error": "Swing paper trader is not running"}
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
            "mode": "swing_paper",
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

    # ── Main Loop (no square-off, no order cutoff) ────────────────────────

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
                self._log("INFO", "Market closed — waiting for next market open (positions preserved)")
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
            has_open_slot = len(self._active_trades) < SWING_PAPER_MAX_POSITIONS
            in_retry_window = now.hour < 14 and now.hour >= 9 and now.weekday() < 5

            if has_open_slot and in_retry_window:
                retry_time = now + timedelta(minutes=120)  # 2 hours — daily data doesn't change every 30 min
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
        num_strategies = len(self._strategy_keys)
        self._log("SCAN", f"Swing scan #{self._scan_count} — {num_strategies} strateg{'y' if num_strategies == 1 else 'ies'}...")

        # First: update existing positions (check SL/target)
        self._update_position_pnl()

        open_count = len(self._active_trades)
        if open_count >= SWING_PAPER_MAX_POSITIONS:
            self._log("INFO", f"Max swing position reached ({open_count}/{SWING_PAPER_MAX_POSITIONS}) — monitoring only")
            return

        # Scan for new signals
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

        # Deduplicate by symbol — keep highest conviction signal per symbol
        seen_symbols = {}
        for sig in all_signals:
            sym = sig.get("symbol", "")
            conv = _calc_conviction(sig)
            if sym not in seen_symbols or conv > seen_symbols[sym][1]:
                seen_symbols[sym] = (sig, conv)

        unique_signals = [s[0] for s in sorted(seen_symbols.values(), key=lambda x: x[1], reverse=True)]

        self._log("SCAN", f"Swing scan #{self._scan_count} complete — ~{total_scanned} stocks, {len(unique_signals)} signals ({total_time:.1f}s)")
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

        # Place 1 virtual order (max 1 position)
        active_symbols = {t["symbol"] for t in self._active_trades}

        for signal in unique_signals:
            if len(self._active_trades) >= SWING_PAPER_MAX_POSITIONS:
                break

            symbol = signal.get("symbol", "")
            if symbol in active_symbols:
                self._log("SKIP", f"{symbol} — already in virtual swing position")
                continue

            self._place_virtual_order(signal)
            break  # strict: only 1 position

    def _place_virtual_order(self, signal: dict) -> bool:
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

        # Simulate realistic slippage (0.1% worse entry — matches live market orders)
        slippage = entry_price * 0.001
        if side == 1:  # BUY: fill slightly higher
            entry_price = round(entry_price + slippage, 2)
        else:  # SELL: fill slightly lower
            entry_price = round(entry_price - slippage, 2)

        capital_req = qty * entry_price

        # Realistic Fyers brokerage + STT + other charges
        turnover = qty * entry_price
        brokerage_per_leg = min(20, turnover * 0.0003)  # ₹20 or 0.03% (whichever lower)
        brokerage = round(brokerage_per_leg * 2, 2)  # Entry + Exit = 2 legs
        stt = round(turnover * 0.00025, 2)  # STT: 0.025% on sell side
        exchange_charges = round(turnover * 0.0003, 2)  # NSE transaction + SEBI + stamp
        est_brokerage = round(brokerage + stt + exchange_charges, 2)

        order_id = f"SWING-P-{self._next_order_id:04d}"
        self._next_order_id += 1

        self._log("ORDER", f"Virtual SWING {signal_type}: {symbol} | Qty={qty} | Entry=₹{entry_price} (incl slippage) | SL=₹{stop_loss} | Target=₹{target} | R:R={rr}")

        trade = {
            "symbol": symbol,
            "signal_type": signal_type,
            "side": side,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target": target,
            "quantity": qty,
            "order_id": order_id,
            "risk_reward_ratio": rr,
            "capital_required": capital_req,
            "strategy": signal.get("_strategy", ""),
            "timeframe": signal.get("_timeframe", ""),
            "placed_at": now_ist().isoformat(),
            "status": "OPEN",
            "pnl": 0.0,
            "ltp": entry_price,
            "est_brokerage": est_brokerage,
        }

        self._active_trades.append(trade)
        self._order_count += 1
        self._save_state()
        return True

    # ── Position Monitoring (SL/target check) ─────────────────────────────

    def _update_position_pnl(self):
        if not self._active_trades:
            return

        symbols = list({t["symbol"] for t in self._active_trades})
        ltp_map = self._fetch_ltp(symbols)

        trades_to_close = []

        for trade in self._active_trades:
            symbol = trade["symbol"]
            ltp = ltp_map.get(symbol, trade.get("ltp", trade["entry_price"]))
            side = trade["side"]

            if side == 1:
                pnl = (ltp - trade["entry_price"]) * trade["quantity"]
            else:
                pnl = (trade["entry_price"] - ltp) * trade["quantity"]

            trade["pnl"] = round(pnl, 2)
            trade["ltp"] = ltp

            # Days held
            placed = trade.get("placed_at", "")
            if placed:
                try:
                    placed_date = datetime.fromisoformat(placed).date()
                    trade["days_held"] = (now_ist().date() - placed_date).days
                except Exception:
                    pass

            # Check SL hit
            if side == 1 and ltp <= trade["stop_loss"]:
                trade["exit_reason"] = "SL_HIT"
                trades_to_close.append(trade)
            elif side == -1 and ltp >= trade["stop_loss"]:
                trade["exit_reason"] = "SL_HIT"
                trades_to_close.append(trade)
            # Check target hit
            elif side == 1 and ltp >= trade["target"]:
                trade["exit_reason"] = "TARGET_HIT"
                trades_to_close.append(trade)
            elif side == -1 and ltp <= trade["target"]:
                trade["exit_reason"] = "TARGET_HIT"
                trades_to_close.append(trade)

        for trade in trades_to_close:
            symbol = trade["symbol"]
            reason = trade["exit_reason"]
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
            log_trade(trade, source="swing_paper")

            if reason == "SL_HIT":
                self._log("ORDER", f"{symbol} — SL HIT at ₹{trade['ltp']} | Net P&L: ₹{net_pnl:,.2f} (charges: ₹{brokerage})")
            else:
                self._log("ORDER", f"{symbol} — TARGET HIT at ₹{trade['ltp']} | Net P&L: ₹{net_pnl:,.2f} (charges: ₹{brokerage})")

        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()

    def _fetch_ltp(self, symbols: list[str]) -> dict[str, float]:
        ltp_map = {}
        if not symbols:
            return ltp_map
        try:
            if not is_authenticated():
                return ltp_map
            res = get_quotes(symbols)
            quotes = res.get("d", [])
            if not quotes and isinstance(res.get("data"), dict):
                quotes = res["data"].get("d", [])
            for q in quotes:
                sym = (q.get("n", "") or q.get("symbol", "")).replace("NSE:", "").replace("-EQ", "")
                lp = 0
                v = q.get("v", {})
                if isinstance(v, dict):
                    lp = v.get("lp", 0) or v.get("close_price", 0)
                if sym and lp:
                    ltp_map[sym] = lp
        except Exception as e:
            logger.warning(f"[SwingPaper] Failed to fetch LTP: {e}")
        return ltp_map

    # ── Logging ───────────────────────────────────────────────────────────

    def _log(self, level: str, message: str):
        self._logger.log(level, message)


# ── Singleton Instance ────────────────────────────────────────────────────

swing_paper_trader = SwingPaperTrader()
