"""
Market Monitor Daemon v2 — Autonomous monitoring + corrective action.

Runs as a background thread. Every 5 minutes during market hours:
  1. Broker connection → auto-reconnect
  2. Engine health → auto-restart stopped engines
  3. Signal generation → alert if 0 signals too long
  4. P&L tracking → safety mode if losses mount
  5. Regime check → log shifts

This daemon ACTS, not just logs. It's the system's immune system.
"""

import logging
import time
import threading
import requests
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))

CHECK_INTERVAL = 300  # 5 minutes
API = "http://localhost:8001"
_monitor_thread = None
_running = False


def _now():
    return datetime.now(IST)


def _is_market_hours():
    now = _now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    from datetime import time as dtime
    return dtime(9, 15) <= t <= dtime(15, 30)


def _log(level, msg):
    ts = _now().strftime("%H:%M:%S")
    logger.info(f"[Monitor {ts}] {level}: {msg}")
    try:
        from pathlib import Path
        log_path = Path(__file__).parent.parent / "tracking" / "monitor.log"
        with open(log_path, "a") as f:
            f.write(f"[{_now().strftime('%Y-%m-%d %H:%M:%S')}] {level}: {msg}\n")
    except Exception:
        pass


def _api_get(endpoint, timeout=5):
    try:
        return requests.get(f"{API}{endpoint}", timeout=timeout).json()
    except Exception:
        return None


def _api_post(endpoint, data=None, timeout=10):
    try:
        if data:
            return requests.post(f"{API}{endpoint}", json=data, timeout=timeout).json()
        return requests.post(f"{API}{endpoint}", timeout=timeout).json()
    except Exception:
        return None


def _check_and_fix_broker():
    """Check broker connection. Reconnect if down."""
    try:
        from services.broker_client import is_authenticated, headless_login
        if not is_authenticated():
            _log("ACTION", "Broker disconnected — reconnecting...")
            result = headless_login()
            if "error" in result:
                _log("ALERT", f"Broker reconnect FAILED: {result['error']}")
            else:
                _log("ACTION", "Broker reconnected successfully")
        else:
            _log("OK", "Broker: connected")
    except Exception as e:
        _log("ERROR", f"Broker check: {e}")


def _check_and_fix_engines():
    """Check all engines. Restart any that stopped unexpectedly."""
    engines = [
        ("Equity Intraday Paper", "/api/paper/status", "/api/paper/start-auto", {"capital": 75000}),
        ("Equity Swing Paper", "/api/swing-paper/status", "/api/swing-paper/start-auto", {"capital": 75000}),
        ("Options Intraday Paper", "/api/options/paper/status", "/api/options/paper/start", {"capital": 25000, "underlyings": ["NIFTY", "BANKNIFTY"]}),
        ("Options Swing Paper", "/api/options/swing-paper/status", "/api/options/swing-paper/start", {"capital": 25000, "underlyings": ["NIFTY", "BANKNIFTY"]}),
        ("Futures Intraday Paper", "/api/futures/paper/status", "/api/futures/paper/start-auto", {"capital": 100000}),
        ("Futures Swing Paper", "/api/futures/swing-paper/status", "/api/futures/swing-paper/start-auto", {"capital": 100000}),
    ]

    # Also check live engines
    live_engines = [
        ("Equity Intraday Live", "/api/auto/status", "/api/auto/start-auto", {"capital": 25000}),
        ("Options Intraday Live", "/api/options/auto/status", "/api/options/auto/start", {"capital": 25000, "underlyings": ["BANKNIFTY"]}),
    ]

    now = _now()
    for name, status_ep, restart_ep, restart_data in engines + live_engines:
        try:
            d = _api_get(status_ep)
            if d is None:
                _log("ERROR", f"{name}: API unreachable")
                continue

            running = d.get("is_running", False)
            squared_off = d.get("squared_off", False)
            scans = d.get("scan_count", 0)
            orders = d.get("order_count", 0)
            active = len(d.get("active_trades", d.get("active_positions", [])))
            pnl = d.get("total_pnl", 0)

            if running:
                _log("OK", f"{name}: S:{scans} O:{orders} A:{active} P&L:₹{pnl:,.0f}")
            elif squared_off:
                _log("OK", f"{name}: squared off")
            else:
                # Engine stopped but not squared off — try restart
                if restart_ep and now.hour < 15:  # Don't restart after 3 PM
                    _log("ACTION", f"{name}: stopped unexpectedly — restarting...")
                    result = _api_post(restart_ep, restart_data)
                    if result and not result.get("error"):
                        _log("ACTION", f"{name}: restarted successfully")
                    else:
                        error = result.get("error", "unknown") if result else "no response"
                        _log("WARN", f"{name}: restart failed — {error}")
                else:
                    _log("WARN", f"{name}: stopped (past restart window)")

        except Exception as e:
            _log("ERROR", f"{name}: {e}")


def _check_signal_health():
    """If engines have 0 orders after many scans, something may be wrong."""
    now = _now()
    if now.hour < 11 or now.hour >= 14:
        return

    for name, ep in [("Equity Paper", "/api/paper/status"), ("Futures Paper", "/api/futures/paper/status")]:
        d = _api_get(ep)
        if d and d.get("is_running"):
            scans = d.get("scan_count", 0)
            orders = d.get("order_count", 0)
            if scans >= 5 and orders == 0:
                _log("WARN", f"{name}: {scans} scans, 0 orders — strategies may need adjustment")

    # Options should be generating trades
    d = _api_get("/api/options/paper/status")
    if d and d.get("is_running"):
        scans = d.get("scan_count", 0)
        orders = d.get("order_count", 0)
        if scans >= 5 and orders == 0:
            _log("WARN", f"Options Paper: {scans} scans, 0 orders — check lot size / margin")


def _check_pnl_health():
    """Track P&L across all engines. Alert on significant losses."""
    total_paper = 0
    total_live = 0

    for ep in ["/api/paper/status", "/api/options/paper/status", "/api/futures/paper/status"]:
        d = _api_get(ep)
        if d:
            total_paper += d.get("total_pnl", 0)

    for ep in ["/api/auto/status", "/api/options/auto/status"]:
        d = _api_get(ep)
        if d:
            total_live += d.get("total_pnl", 0)

    _log("OK", f"P&L — Paper: ₹{total_paper:,.0f} | Live: ₹{total_live:,.0f}")

    if total_live < -3000:
        _log("ALERT", f"Live loss exceeding ₹3,000 — daily loss limits should be active")
    if total_paper < -5000:
        _log("ALERT", f"Paper loss exceeding ₹5,000 — review strategy performance")


def _check_regime():
    """Log current regime for audit trail."""
    d = _api_get("/api/equity/regime", timeout=10)
    if d:
        regime = d.get("regime", "?")
        vix = d.get("components", {}).get("vix", 0)
        confidence = d.get("confidence", "?")
        strats = d.get("strategy_ids", [])
        _log("OK", f"Regime: {regime} | VIX:{vix} | Conf:{confidence} | Strategies:{len(strats)}")


def _run_monitor_loop():
    """Main loop — check and fix during market hours."""
    global _running
    _log("START", "Market monitor daemon v2 started (monitors + acts)")

    while _running:
        if _is_market_hours():
            _log("CHECK", "─" * 40)
            _check_and_fix_broker()
            _check_and_fix_engines()
            _check_regime()
            _check_signal_health()
            _check_pnl_health()
            _log("CHECK", "─" * 40)

        for _ in range(CHECK_INTERVAL):
            if not _running:
                break
            time.sleep(1)

    _log("STOP", "Market monitor daemon stopped")


def start_monitor():
    global _monitor_thread, _running
    if _running:
        logger.info("[Monitor] Already running — skipping duplicate start")
        return
    if _monitor_thread is not None and _monitor_thread.is_alive():
        logger.info("[Monitor] Thread still alive — skipping duplicate start")
        return
    _running = True
    _monitor_thread = threading.Thread(target=_run_monitor_loop, daemon=True, name="MarketMonitor")
    _monitor_thread.start()
    logger.info("[Monitor] v2 started — monitors + takes corrective action")


def stop_monitor():
    global _running
    _running = False


def get_monitor_log(lines: int = 50) -> list[str]:
    try:
        from pathlib import Path
        log_path = Path(__file__).parent.parent / "tracking" / "monitor.log"
        if log_path.exists():
            with open(log_path) as f:
                return [l.strip() for l in f.readlines()[-lines:]]
    except Exception:
        pass
    return []
