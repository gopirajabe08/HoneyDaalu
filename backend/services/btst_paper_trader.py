"""
BTST Paper Trading Engine for IntraTrading.

Mirrors BTST trading rules but uses virtual positions.
Key differences from live btst_trader:
  - No Fyers orders — virtual positions only
  - Uses LTP from Fyers quotes for P&L
  - Synthetic order IDs ("BTST_PAPER_1", etc)
  - Max 4 positions (more for testing)
  - Same exit rules, same scan logic
  - State file: .btst_paper_trader_state.json
"""

import threading
import logging
import time
import traceback
from datetime import datetime, timedelta
from typing import Optional
from collections import OrderedDict

from services.scanner import run_scan, is_market_open, _calc_conviction
from services.market_data import get_nifty_trend
from services.trade_logger import log_trade
from services.fyers_client import get_quotes, is_authenticated
from config import (
    BTST_ORDER_START_HOUR, BTST_ORDER_START_MIN,
    BTST_ORDER_CUTOFF_HOUR, BTST_ORDER_CUTOFF_MIN,
    BTST_POSITION_CHECK_INTERVAL,
    BTST_CAPITAL_PER_POSITION, BTST_MIN_POSITIONS, BTST_PAPER_MAX_POSITIONS,
    BTST_EXIT_PROFIT_TARGET_PCT, BTST_EXIT_LOSS_LIMIT_PCT, BTST_MAX_HOLD_DAYS,
    BTST_STRATEGY_TIMEFRAMES,
)
from utils.time_utils import now_ist, is_before_time, is_past_time
from utils.state_manager import get_state_path, save_state, load_state
from utils.trader_log import TraderLogger

logger = logging.getLogger(__name__)

# Basic sector mapping for concentration limit (parity with auto_trader)
SECTOR_MAP = {
    'HDFCBANK': 'banking', 'ICICIBANK': 'banking', 'SBIN': 'banking', 'AXISBANK': 'banking',
    'KOTAKBANK': 'banking', 'BANKBARODA': 'banking', 'PNB': 'banking', 'INDUSINDBK': 'banking',
    'FEDERALBNK': 'banking', 'IDFCFIRSTB': 'banking', 'BANDHANBNK': 'banking', 'CANBK': 'banking',
    'TCS': 'it', 'INFY': 'it', 'WIPRO': 'it', 'HCLTECH': 'it', 'TECHM': 'it', 'LTIM': 'it',
    'RELIANCE': 'energy', 'ONGC': 'energy', 'IOC': 'energy', 'BPCL': 'energy', 'NTPC': 'energy',
    'POWERGRID': 'energy', 'ADANIGREEN': 'energy', 'ADANIPORTS': 'infra',
    'TATAMOTORS': 'auto', 'MARUTI': 'auto', 'BAJAJ-AUTO': 'auto', 'HEROMOTOCO': 'auto', 'M&M': 'auto',
    'HDFCLIFE': 'insurance', 'SBILIFE': 'insurance', 'ICICIPRULI': 'insurance',
    'BAJFINANCE': 'nbfc', 'BAJAJFINSV': 'nbfc', 'CHOLAFIN': 'nbfc', 'SHRIRAMFIN': 'nbfc',
}
MAX_PER_SECTOR = 2

STATE_FILE = get_state_path(".btst_paper_trader_state.json")

CONTRA_STRATEGIES = {"play6_bb_contra", "play8_rsi_divergence"}


def _is_before_order_start() -> bool:
    """True if current time is before 10:30 AM IST."""
    return is_before_time(BTST_ORDER_START_HOUR, BTST_ORDER_START_MIN)


def _is_past_order_cutoff() -> bool:
    """True if current time is past 2:00 PM IST — no new orders."""
    return is_past_time(BTST_ORDER_CUTOFF_HOUR, BTST_ORDER_CUTOFF_MIN)


class BTSTPaperTrader:
    """
    Virtual BTST trading engine.
    Same scan/signal/exit logic as BTSTTrader but no real orders.
    Positions carry overnight. Max 4 positions (more for testing).
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Configuration
        self._strategy_keys: list[str] = []
        self._timeframes: dict[str, str] = {}
        self._capital: float = 0.0
        self.max_open_positions: int = BTST_MIN_POSITIONS

        # State tracking
        self._active_trades: list[dict] = []
        self._trade_history: list[dict] = []
        self._total_pnl: float = 0.0
        self._scan_count: int = 0
        self._order_count: int = 0
        self._started_at: Optional[str] = None
        self._next_scan_at: Optional[str] = None
        self._next_order_id: int = 1

        # Shared utilities
        self._logger = TraderLogger("BTSTPaper")

        # Restore state from disk (cross-day persistence)
        self._load_state()

    @property
    def is_running(self) -> bool:
        return self._running

    # ── State Persistence (cross-day — no date filter) ────────────────────

    def _save_state(self):
        """Persist BTST paper state to disk. Cross-day — positions carry overnight."""
        state = {
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
            "next_order_id": self._next_order_id,
            "logs": self._logger.recent(200),
        }
        save_state(STATE_FILE, state, "BTSTPaper")

    def _load_state(self):
        """Restore BTST paper state from disk. No date filter — positions carry overnight."""
        try:
            state = load_state(STATE_FILE, "BTSTPaper")
            if not state:
                return

            # No date filter — BTST positions carry over days
            self._strategy_keys = state.get("strategy_keys", [])
            self._timeframes = state.get("timeframes", {})
            self._capital = state.get("capital", 0.0)
            self._active_trades = state.get("active_trades", [])
            self._trade_history = state.get("trade_history", [])
            self._total_pnl = state.get("total_pnl", 0.0)
            self._scan_count = state.get("scan_count", 0)
            self._order_count = state.get("order_count", 0)
            self._started_at = state.get("started_at")
            self._logger.entries = state.get("logs", [])
            self._next_order_id = state.get("next_order_id", 1)

            # Recalculate max positions from restored capital
            if self._capital > 0:
                self.max_open_positions = max(
                    BTST_MIN_POSITIONS,
                    min(int(self._capital // BTST_CAPITAL_PER_POSITION), BTST_PAPER_MAX_POSITIONS)
                )

            was_running = state.get("running", False)

            if self._strategy_keys:
                strat_names = ", ".join(f"{k}({self._timeframes.get(k, '')})" for k in self._strategy_keys)
                self._log("RESTORE", f"Restored BTST paper state — {strat_names} | "
                          f"Active: {len(self._active_trades)} | P&L: ₹{self._total_pnl:,.2f}")

                if was_running and is_market_open():
                    self._log("RESTORE", "BTST paper trader was running — auto-resuming...")
                    self._running = True
                    self._thread = threading.Thread(target=self._run_loop, daemon=True)
                    self._thread.start()
                elif was_running:
                    self._log("RESTORE", "BTST paper trader was running but market closed — will resume when market opens")

        except Exception as e:
            logger.warning(f"[BTSTPaper] Failed to load state: {e}")

    # ── Controls ──────────────────────────────────────────────────────────

    def start(self, strategies: list[dict], capital: float) -> dict:
        """Start BTST paper trading with one or more strategies."""
        with self._lock:
            if self._running:
                return {"error": "BTST paper trader is already running"}

            if not is_market_open():
                now = now_ist()
                if now.weekday() >= 5:
                    return {"error": "Market is closed (Weekend). BTST paper trading starts during market hours."}
                return {"error": "Market is closed. BTST paper trading starts during market hours (9:15 AM - 3:30 PM IST)."}

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
            self.max_open_positions = max(
                BTST_MIN_POSITIONS,
                min(int(capital // BTST_CAPITAL_PER_POSITION), BTST_PAPER_MAX_POSITIONS)
            )
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
            self._log("START", f"BTST paper trader STARTED — {strat_names} | Capital=₹{capital:,.0f} | Max positions: {self.max_open_positions}")
            self._log("INFO", f"BTST PAPER MODE — Virtual positions | Entry 10:30 AM - 2:00 PM | Positions carry overnight")
            self._log("INFO", f"Exit rules: +{BTST_EXIT_PROFIT_TARGET_PCT}% profit | -{BTST_EXIT_LOSS_LIMIT_PCT}% loss | Max {BTST_MAX_HOLD_DAYS} days hold")

            self._save_state()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

            return {
                "status": "started",
                "mode": "btst_paper",
                "strategies": [{"strategy": k, "timeframe": self._timeframes[k]} for k in self._strategy_keys],
                "capital": capital,
                "max_positions": self.max_open_positions,
                "started_at": self._started_at,
            }

    def stop(self) -> dict:
        """Stop BTST paper trading. Virtual positions remain."""
        with self._lock:
            if not self._running:
                return {"status": "already_stopped", "message": "BTST paper trader is not running"}

            self._running = False
            self._log("STOP", "BTST paper trader STOPPED by user (positions remain)")

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
            log_trade(trade, source="btst_paper")
            self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
            self._log("ORDER", f"{symbol} — MANUAL CLOSE | Net P&L: ₹{net_pnl:,.2f} (charges: ₹{brokerage})")
            self._save_state()
            return {"status": "closed", "symbol": symbol, "pnl": round(net_pnl, 2)}

    def trigger_scan(self) -> dict:
        """Trigger an immediate scan (on-demand)."""
        if not self._running:
            return {"error": "BTST paper trader is not running"}
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
        """Return current BTST paper trader state."""
        return {
            "is_running": self._running,
            "mode": "btst_paper",
            "strategies": [{"strategy": k, "timeframe": self._timeframes.get(k, "")} for k in self._strategy_keys],
            "capital": self._capital,
            "max_positions": self.max_open_positions,
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
        """Background loop: wait for entry window, scan, monitor, check exits."""
        self._log("INFO", "Background thread started")
        self._log("INFO", f"BTST paper mode: entry 10:30 AM - 2:00 PM | No intraday square-off | Positions carry overnight")

        while self._running:
            if not is_market_open():
                self._log("INFO", "Market closed — waiting for next open (BTST paper positions preserved)")
                while self._running and not is_market_open():
                    time.sleep(60)
                if not self._running:
                    break
                self._log("INFO", "Market opened — checking BTST exit rules for overnight positions")

            # ── Morning: check exit rules for overnight positions ──
            if self._active_trades:
                self._check_exit_rules()

            # ── Wait for 10:30 AM entry window ──
            while self._running and _is_before_order_start():
                now = now_ist()
                order_start = now.replace(hour=BTST_ORDER_START_HOUR, minute=BTST_ORDER_START_MIN, second=0, microsecond=0)
                mins_left = max(0, int((order_start - now).total_seconds() / 60))
                if mins_left % 15 == 0 and mins_left > 0:
                    self._log("INFO", f"Waiting for 10:30 AM entry window — {mins_left} min left")
                time.sleep(60)

            if not self._running:
                break

            # ── Entry window scan ──
            if not _is_past_order_cutoff() and is_market_open():
                open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])
                if open_count < self.max_open_positions:
                    self._log("SCAN", "Entry window — executing scan to fill slots")
                    self._execute_scan_cycle()

            # ── Monitor loop: check positions every 60s, scan on slot open ──
            prev_open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])
            _monitor_tick = 0

            while self._running and is_market_open():
                # Sleep in 1-second ticks
                for _ in range(BTST_POSITION_CHECK_INTERVAL):
                    if not self._running:
                        break
                    time.sleep(1)

                if not self._running or not is_market_open():
                    break

                _monitor_tick += 1

                # Update P&L for active positions
                self._update_position_pnl()

                # Check exit rules every ~5 minutes
                if _monitor_tick % 5 == 0 and self._active_trades:
                    self._check_exit_rules()

                current_open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])

                # Slot opened up — scan to refill if before cutoff
                if current_open_count < prev_open_count:
                    slots_freed = prev_open_count - current_open_count
                    self._log("INFO", f"{slots_freed} BTST paper position(s) closed — {current_open_count}/{self.max_open_positions} slots used")

                    if current_open_count < self.max_open_positions and not _is_past_order_cutoff():
                        self._log("SCAN", f"Slot available — triggering scan to fill")
                        self._execute_scan_cycle()
                        current_open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])
                    elif _is_past_order_cutoff():
                        self._log("INFO", "Past 2:00 PM — no new BTST paper orders. Monitoring until close.")

                # Periodic re-scan every ~15 min if slots available
                elif current_open_count < self.max_open_positions and not _is_past_order_cutoff():
                    if _monitor_tick > 0 and _monitor_tick % 15 == 0:
                        slots = self.max_open_positions - current_open_count
                        self._log("SCAN", f"{slots} BTST paper slots open — periodic re-scan")
                        self._execute_scan_cycle()
                        current_open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])

                prev_open_count = current_open_count

            # Market closed — save state and wait
            self._save_state()
            if self._running:
                self._log("INFO", "Market closed — BTST paper positions preserved overnight. Waiting for next session.")

        self._log("INFO", "Background thread exited")
        self._save_state()

    # ── Scan & Virtual Order Placement ────────────────────────────────────

    def _execute_scan_cycle(self):
        """Run one scan across all selected strategies: find signals and place virtual orders."""
        self._scan_count += 1
        num_strategies = len(self._strategy_keys)
        self._log("SCAN", f"BTST paper scan #{self._scan_count} — {num_strategies} strateg{'y' if num_strategies == 1 else 'ies'}...")

        # Update existing positions first
        self._update_position_pnl()

        # Check open positions
        open_count = len([t for t in self._active_trades if t["status"] == "OPEN"])
        if open_count >= self.max_open_positions:
            self._log("INFO", f"Max BTST paper positions reached ({open_count}/{self.max_open_positions}) — monitoring only")
            return

        slots_available = self.max_open_positions - open_count

        # Collect signals from all strategies
        all_signals = []
        total_scanned = 0
        total_time = 0
        strategy_idx = 0

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
                sig["_regime_position"] = strategy_idx

            all_signals.extend(signals)
            self._log("SCAN", f"  {strategy_key}({timeframe}): {len(signals)} signals ({scan_time}s)")
            strategy_idx += 1

        # Deduplicate by symbol — keep highest conviction signal per symbol
        seen_symbols = {}
        for sig in all_signals:
            sym = sig.get("symbol", "")
            conv = _calc_conviction(sig)
            regime_pos = sig.get("_regime_position", 99)
            if regime_pos == 0:
                conv *= 1.5
            elif regime_pos == 1:
                conv *= 1.2
            elif regime_pos == 2:
                conv *= 1.05
            if sym not in seen_symbols or conv > seen_symbols[sym][1]:
                seen_symbols[sym] = (sig, conv)

        unique_signals = [s[0] for s in sorted(seen_symbols.values(), key=lambda x: x[1], reverse=True)]

        self._log("SCAN", f"BTST paper scan #{self._scan_count} complete — ~{total_scanned} stocks, {len(unique_signals)} unique signals ({total_time:.1f}s)")
        self._save_state()

        if not unique_signals:
            return

        # ── Nifty Trend Filter (with contra exemption) ──
        nifty_trend = get_nifty_trend("5m")
        trend_signals = [s for s in unique_signals if s.get("strategy") not in CONTRA_STRATEGIES]
        contra_signals = [s for s in unique_signals if s.get("strategy") in CONTRA_STRATEGIES]

        buy_count = sum(1 for s in trend_signals if s.get("signal_type") == "BUY")
        sell_count = sum(1 for s in trend_signals if s.get("signal_type") == "SELL")
        contra_count = len(contra_signals)

        if nifty_trend == "BEARISH":
            trend_signals = [s for s in trend_signals if s.get("signal_type") == "SELL"]
            self._log("FILTER", f"Nifty BEARISH — blocked {buy_count} BUY, kept {sell_count} SELL | contra: {contra_count} exempt")
        elif nifty_trend == "BULLISH":
            trend_signals = [s for s in trend_signals if s.get("signal_type") == "BUY"]
            self._log("FILTER", f"Nifty BULLISH — kept {buy_count} BUY, blocked {sell_count} SELL | contra: {contra_count} exempt")
        else:
            self._log("FILTER", f"Nifty {nifty_trend} — allowing all ({buy_count} BUY, {sell_count} SELL, {contra_count} contra)")

        unique_signals = trend_signals + contra_signals

        if not unique_signals:
            self._log("FILTER", "No signals remaining after Nifty trend filter")
            return

        # ── Strategy diversity: interleave signals from different strategies ──
        by_strategy = OrderedDict()
        for s in unique_signals:
            strat = s.get("strategy", s.get("_strategy", "unknown"))
            if strat not in by_strategy:
                by_strategy[strat] = []
            by_strategy[strat].append(s)

        diversified = []
        max_rounds = max((len(v) for v in by_strategy.values()), default=0)
        for round_idx in range(max_rounds):
            for strat, signals in by_strategy.items():
                if round_idx < len(signals):
                    diversified.append(signals[round_idx])

        if len(by_strategy) > 1:
            strat_summary = ", ".join(f"{k}:{len(v)}" for k, v in by_strategy.items())
            self._log("FILTER", f"Strategy diversity: {strat_summary} — interleaved {len(diversified)} signals")

        unique_signals = diversified

        # Place virtual orders
        max_orders_per_scan = min(2, slots_available)
        orders_placed = 0
        active_symbols = {t["symbol"] for t in self._active_trades}
        strategy_count_this_scan = {}
        max_per_strategy = max(1, slots_available // max(len(by_strategy), 1))

        for signal in unique_signals:
            if orders_placed >= max_orders_per_scan:
                break

            if _is_past_order_cutoff():
                self._log("INFO", "2:00 PM cutoff reached — stopping virtual order placement")
                break

            symbol = signal.get("symbol", "")
            sig_strategy = signal.get("strategy", signal.get("_strategy", "unknown"))

            # Strategy concentration limit
            existing_for_strategy = sum(1 for t in self._active_trades if t.get("strategy") == sig_strategy)
            scan_for_strategy = strategy_count_this_scan.get(sig_strategy, 0)
            if existing_for_strategy + scan_for_strategy >= max_per_strategy:
                self._log("FILTER", f"{symbol} — skipping, {sig_strategy} already at limit")
                continue

            # Sector concentration check
            sym_sector = SECTOR_MAP.get(symbol, "other")
            sector_count = sum(1 for t in self._active_trades if SECTOR_MAP.get(t.get("symbol", ""), "other") == sym_sector)
            if sector_count >= MAX_PER_SECTOR and sym_sector != "other":
                self._log("FILTER", f"Sector limit: {symbol} ({sym_sector}) — already {sector_count} trades in sector")
                continue

            # Skip if already in position
            if symbol in active_symbols:
                self._log("SKIP", f"{symbol} — already in virtual BTST position")
                continue

            signal["_placed_via"] = signal.get("_strategy", "")
            success = self._place_virtual_order(signal)
            if success:
                orders_placed += 1
                active_symbols.add(symbol)
                strategy_count_this_scan[sig_strategy] = strategy_count_this_scan.get(sig_strategy, 0) + 1

    def _place_virtual_order(self, signal: dict) -> bool:
        """Place a virtual BTST order (no real Fyers orders)."""
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

        # Simulate realistic slippage (0.1% worse entry)
        slippage = entry_price * 0.001
        if side == 1:
            entry_price = round(entry_price + slippage, 2)
        else:
            entry_price = round(entry_price - slippage, 2)

        # Override SL/target with BTST percentage-based rules
        if side == 1:
            btst_sl = round(entry_price * (1 - BTST_EXIT_LOSS_LIMIT_PCT / 100), 2)
            btst_target = round(entry_price * (1 + BTST_EXIT_PROFIT_TARGET_PCT / 100), 2)
        else:
            btst_sl = round(entry_price * (1 + BTST_EXIT_LOSS_LIMIT_PCT / 100), 2)
            btst_target = round(entry_price * (1 - BTST_EXIT_PROFIT_TARGET_PCT / 100), 2)

        # Use tighter of signal SL vs BTST SL
        if side == 1:
            stop_loss = max(stop_loss, btst_sl) if stop_loss > 0 else btst_sl
        else:
            stop_loss = min(stop_loss, btst_sl) if stop_loss > 0 else btst_sl

        capital_req = qty * entry_price

        # Realistic Fyers brokerage + STT + other charges (CNC delivery)
        turnover = qty * entry_price
        brokerage_per_leg = min(20, turnover * 0.0003)
        brokerage = round(brokerage_per_leg * 2, 2)
        stt = round(turnover * 0.001, 2)  # CNC STT: 0.1% on buy + sell
        exchange_charges = round(turnover * 0.0003, 2)
        est_brokerage = round(brokerage + stt + exchange_charges, 2)

        order_id = f"BTST_PAPER_{self._next_order_id:04d}"
        self._next_order_id += 1

        self._log("ORDER", f"Virtual BTST {signal_type}: {symbol} | Qty={qty} | Entry=₹{entry_price} (incl slippage) | SL=₹{stop_loss} | Target=₹{btst_target} | R:R={rr}")

        trade = {
            "symbol": symbol,
            "signal_type": signal_type,
            "side": side,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target": btst_target,
            "quantity": qty,
            "order_id": order_id,
            "risk_reward_ratio": rr,
            "capital_required": capital_req,
            "strategy": signal.get("_placed_via", signal.get("_strategy", "")),
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

    # ── Exit Rules (BTST-specific) ────────────────────────────────────────

    def _check_exit_rules(self):
        """Apply BTST exit rules: profit target, loss limit, max hold days."""
        if not self._active_trades:
            return

        trades_to_exit = []

        for trade in self._active_trades:
            if trade["status"] != "OPEN":
                continue

            symbol = trade["symbol"]
            entry_price = trade.get("entry_price", 0)
            ltp = trade.get("ltp", 0)
            side = trade.get("side", 1)

            if entry_price <= 0 or ltp <= 0:
                continue

            # Calculate P&L percentage
            if side == 1:
                pnl_pct = (ltp - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - ltp) / entry_price * 100

            # Days held
            placed = trade.get("placed_at", "")
            days_held = 0
            if placed:
                try:
                    placed_date = datetime.fromisoformat(placed).date()
                    days_held = (now_ist().date() - placed_date).days
                    trade["days_held"] = days_held
                except Exception:
                    pass

            # Rule 1: Profit target
            if pnl_pct >= BTST_EXIT_PROFIT_TARGET_PCT:
                self._log("ORDER", f"{symbol} — BTST PROFIT TARGET hit: +{pnl_pct:.2f}% (target: +{BTST_EXIT_PROFIT_TARGET_PCT}%)")
                trade["_exit_reason"] = "BTST_PROFIT_TARGET"
                trades_to_exit.append(trade)
                continue

            # Rule 2: Loss limit
            if pnl_pct <= -BTST_EXIT_LOSS_LIMIT_PCT:
                self._log("ORDER", f"{symbol} — BTST LOSS LIMIT hit: {pnl_pct:.2f}% (limit: -{BTST_EXIT_LOSS_LIMIT_PCT}%)")
                trade["_exit_reason"] = "BTST_LOSS_LIMIT"
                trades_to_exit.append(trade)
                continue

            # Rule 3: Max hold days
            if days_held >= BTST_MAX_HOLD_DAYS:
                self._log("ORDER", f"{symbol} — BTST MAX HOLD DAYS reached: {days_held} days (max: {BTST_MAX_HOLD_DAYS})")
                trade["_exit_reason"] = "BTST_MAX_HOLD"
                trades_to_exit.append(trade)
                continue

        # Execute virtual exits
        for trade in trades_to_exit:
            self._exit_virtual_position(trade, trade.get("_exit_reason", "BTST_EXIT"))

    def _exit_virtual_position(self, trade: dict, reason: str):
        """Close a virtual BTST position."""
        symbol = trade["symbol"]
        gross_pnl = trade.get("pnl", 0)
        brokerage = trade.get("est_brokerage", 0)
        net_pnl = round(gross_pnl - brokerage, 2)

        trade["status"] = "CLOSED"
        trade["closed_at"] = now_ist().isoformat()
        trade["exit_reason"] = reason
        trade["exit_price"] = trade.get("ltp", trade["entry_price"])
        trade["pnl"] = net_pnl
        trade["gross_pnl"] = gross_pnl
        trade["charges"] = brokerage
        self._total_pnl += net_pnl
        self._trade_history.append(trade)
        log_trade(trade, source="btst_paper")
        self._log("ORDER", f"{symbol} — BTST paper exit ({reason}) | Net P&L: ₹{net_pnl:,.2f} (charges: ₹{brokerage})")

        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()

    # ── Position Monitoring ───────────────────────────────────────────────

    def _update_position_pnl(self):
        """Refresh P&L for active virtual BTST trades using Fyers LTP quotes."""
        if not self._active_trades:
            return

        symbols = list({t["symbol"] for t in self._active_trades if t["status"] == "OPEN"})
        ltp_map = self._fetch_ltp(symbols)

        for trade in self._active_trades:
            if trade["status"] != "OPEN":
                continue

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
            stop_loss = trade.get("stop_loss", 0)
            target = trade.get("target", 0)

            if ltp > 0 and stop_loss > 0:
                sl_hit = (side == 1 and ltp <= stop_loss) or (side == -1 and ltp >= stop_loss)
                if sl_hit:
                    self._log("ORDER", f"{symbol} — BTST paper SL HIT at ₹{ltp} (SL=₹{stop_loss})")
                    self._exit_virtual_position(trade, "SL_HIT")
                    continue

            # Check target hit (percentage-based target)
            if ltp > 0 and target > 0:
                target_hit = (side == 1 and ltp >= target) or (side == -1 and ltp <= target)
                if target_hit:
                    self._log("ORDER", f"{symbol} — BTST paper TARGET HIT at ₹{ltp} (target=₹{target})")
                    self._exit_virtual_position(trade, "TARGET_HIT")
                    continue

        self._active_trades = [t for t in self._active_trades if t["status"] == "OPEN"]
        self._save_state()

    def _fetch_ltp(self, symbols: list[str]) -> dict[str, float]:
        """Fetch LTP for a list of symbols via Fyers quotes API."""
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
            logger.warning(f"[BTSTPaper] Failed to fetch LTP: {e}")
        return ltp_map

    # ── Logging ───────────────────────────────────────────────────────────

    def _log(self, level: str, message: str):
        """Add a timestamped log entry."""
        self._logger.log(level, message)


# ── Singleton Instance ────────────────────────────────────────────────────

btst_paper_trader = BTSTPaperTrader()
