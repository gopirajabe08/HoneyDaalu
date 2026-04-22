"""FastAPI backend for LuckyNavi trading platform."""

import sys
import os

# Add backend dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

from strategies import STRATEGY_MAP
from services.scanner import run_scan, get_market_status
from services import broker_client
from services import telegram_notify
from services.auto_trader import auto_trader
from services.paper_trader import paper_trader
from services.swing_trader import swing_trader
from services.swing_paper_trader import swing_paper_trader
from services.btst_trader import btst_trader
from services.btst_paper_trader import btst_paper_trader
from services.options_auto_trader import options_auto_trader
from services.options_paper_trader import options_paper_trader
from services.options_swing_trader import options_swing_trader
from services.options_swing_paper_trader import options_swing_paper_trader
from services.futures_auto_trader import futures_auto_trader
from services.futures_paper_trader import futures_paper_trader
from services.futures_swing_trader import futures_swing_trader
from services.futures_swing_paper_trader import futures_swing_paper_trader
from services.backtester import run_backtest_api
from services.auth import request_otp, verify_otp, verify_token
from services.strategy_tracker import (
    get_daily_report, get_recent_reports, get_strategy_registry,
    get_changelog, generate_report_from_api,
)
from config import STRATEGY_TIMEFRAMES, SWING_STRATEGY_TIMEFRAMES

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="LuckyNavi", version="1.0.0")


def _live_enabled() -> bool:
    return os.getenv("HONEYDAALU_DISABLE_LIVE", "").strip().lower() not in ("1", "true", "yes", "on")


@app.on_event("shutdown")
def notify_shutdown():
    """Send Telegram alert when server stops (manual stop, crash, or systemctl stop)."""
    if not _live_enabled():
        return  # Paper-only mode — routine restarts don't need Telegram spam
    try:
        from services import telegram_notify
        telegram_notify.send("⚠️ <b>System Stopped</b>\nBackend process exited. Will auto-start at 9:00 AM next trading day.")
    except Exception:
        pass


@app.on_event("startup")
def auto_connect_broker():
    """Auto-connect broker on server startup — fresh TOTP login daily."""
    from pathlib import Path
    lock = Path(__file__).parent / ".startup_lock"
    import os, time as _t
    pid = os.getpid()
    if lock.exists():
        # Check if lock is from THIS process (same PID) — skip duplicate
        try:
            lock_pid = int(lock.read_text().strip())
            if lock_pid == pid:
                return
        except Exception:
            pass
    lock.write_text(str(pid))
    # EC2 server runs 24/7 — no sleep prevention needed

    if not broker_client.is_configured():
        logger.warning("Broker credentials not configured in .env — skipping auto-connect")
        return

    # A1: Always fresh login daily — clear stale tokens
    broker_client.logout()
    print("[Startup] Attempting fresh TOTP login...", flush=True)
    for attempt in range(1, 4):
        result = broker_client.headless_login()
        import time as _time
        _time.sleep(3)  # Wait for token to propagate
        if broker_client.is_authenticated():
            profile = broker_client.get_profile()
            name = profile.get("data", {}).get("name", "Unknown")
            print(f"[Startup] Broker connected: {name} (attempt {attempt})", flush=True)
            if _live_enabled():
                try:
                    from services import telegram_notify
                    telegram_notify.send(f"✅ <b>TradeJini Login SUCCESS</b>\n{name}\nAttempt {attempt}/3")
                except Exception:
                    pass
            break
        else:
            print(f"[Startup] Login attempt {attempt}/3 — not authenticated yet, retrying...", flush=True)
            _time.sleep(5)
    else:
        print("[Startup] WARNING: Broker login failed after 3 attempts — live engines will not start", flush=True)
        try:
            from services import telegram_notify
            telegram_notify.send("🚨 <b>TradeJini Login FAILED</b>\n3 attempts exhausted.\nCheck immediately!\nNo live trading today until fixed.")
        except Exception:
            pass

    # Verify market data works before starting engines
    _market_data_ok = False
    try:
        import yfinance as yf
        test = yf.Ticker("RELIANCE.NS")
        test_data = test.history(period="5d", interval="15m")
        if test_data is not None and len(test_data) > 10:
            print(f"[Startup] Market data: OK ({len(test_data)} candles for RELIANCE)", flush=True)
            _market_data_ok = True
        else:
            print("[Startup] WARNING: Market data check failed — yfinance may need upgrade", flush=True)
            try:
                import subprocess
                subprocess.run(["pip", "install", "--upgrade", "yfinance", "-q"], capture_output=True, timeout=30)
                print("[Startup] yfinance upgraded — retrying...", flush=True)
            except Exception:
                pass
    except Exception as e:
        print(f"[Startup] WARNING: Market data check error: {e}", flush=True)

    # ── Pre-market system health check ──────────────────────────────────────
    # Verify: broker connected, data flowing, strategies loadable, funds visible.
    # Send a Telegram summary so we know the system is ready before market opens.
    try:
        _broker_ok = broker_client.is_authenticated()
        _strat_count = 0
        try:
            from strategies import STRATEGY_MAP
            _strat_count = len(STRATEGY_MAP)
        except Exception:
            pass
        _funds_avail = 0
        _funds_ok = False
        try:
            _fdata = broker_client.get_funds()
            for _fi in _fdata.get("fund_limit", []):
                if _fi.get("id") == 10:
                    _funds_avail = _fi.get("equityAmount", 0)
                    _funds_ok = True
                    break
        except Exception:
            pass

        _checks = {
            "Broker": "OK" if _broker_ok else "FAIL",
            "Market data": "OK" if _market_data_ok else "WARN",
            "Strategies": f"{_strat_count} loaded" if _strat_count > 0 else "FAIL",
            "Funds": f"₹{_funds_avail:,.0f} available" if _funds_ok else "WARN",
        }
        _all_ok = _broker_ok and _strat_count > 0

        # Only send audit Telegram when live is enabled, OR audit has failures (always alert on failures)
        if _live_enabled() or not _all_ok:
            _check_lines = "\n".join(f"  {'✅' if v not in ('FAIL','WARN') else ('🚨' if v=='FAIL' else '⚠️')} {k}: {v}" for k, v in _checks.items())
            _audit_msg = (
                f"{'🟢' if _all_ok else '🔴'} <b>Pre-Market Audit</b>\n\n"
                f"{_check_lines}\n\n"
                f"{'System READY — all checks passed.' if _all_ok else 'WARNING: One or more checks failed!'}"
            )
            telegram_notify.send(_audit_msg)
        print(f"[Startup] Pre-market audit: {'PASS' if _all_ok else 'WARN'}", flush=True)
    except Exception as _pma_err:
        print(f"[Startup] Pre-market audit error: {_pma_err}", flush=True)

    # Start market monitor daemon
    from services.market_monitor import start_monitor
    start_monitor()

    # Auto-start engines based on available capital and market conditions
    import threading
    def _auto_start_engines():
        """Auto-start paper + live engines based on capital and conditions."""
        import time, traceback
        time.sleep(5)  # Wait for server to fully initialize

        def _log(msg):
            """Print to stdout (visible in logs) AND use logger."""
            print(f"[AutoStart] {msg}", flush=True)
            logger.info(f"[AutoStart] {msg}")

        try:
            from services.equity_regime import detect_equity_regime
            from config import SWING_STRATEGY_TIMEFRAMES
            from utils.time_utils import now_ist

            # Guard: don't start engines after market close — prevents wasted resources
            boot_now = now_ist()
            if boot_now.weekday() >= 5:
                _log("Weekend — skipping engine start")
                return
            if boot_now.hour > 15 or (boot_now.hour == 15 and boot_now.minute >= 30):
                _log(f"After market close ({boot_now.strftime('%H:%M')}) — skipping engine start")
                return

            _log("Starting engines...")

            # Futures paper — use futures regime for strategy selection
            def _get_futures_regime_strategies():
                try:
                    from services.futures_regime import detect_futures_regime
                    fut_regime = detect_futures_regime()
                    return fut_regime.get("strategies", [])
                except Exception:
                    return []

            def _btst_strategies():
                """Build BTST strategy list using BTST-specific timeframes (1d/1h), not intraday 15m."""
                from config import BTST_STRATEGY_TIMEFRAMES
                regime_strats = detect_equity_regime().get("strategy_ids", [])
                btst_strats = []
                for key in regime_strats:
                    if key in BTST_STRATEGY_TIMEFRAMES:
                        tf = BTST_STRATEGY_TIMEFRAMES[key][0]  # Use first valid BTST timeframe
                        btst_strats.append({"strategy": key, "timeframe": tf})
                if not btst_strats:
                    # Fallback: use all BTST strategies with their default timeframes
                    for key, tfs in BTST_STRATEGY_TIMEFRAMES.items():
                        btst_strats.append({"strategy": key, "timeframe": tfs[0]})
                return btst_strats

            # ── Wait for market open BEFORE any engine start ──
            # cron fires at 9:00 AM IST but market opens 9:15. paper_trader.start()
            # rejects with "Market is closed" if called before 9:15, and historically
            # AutoStart masked this error as "already running or restored from state",
            # leaving paper engines silently dead from 9:00 → user-manual-restart.
            from services.scanner import is_market_open
            if not is_market_open():
                _log("Market not open yet — waiting for 9:15 AM IST before starting engines...")
                while not is_market_open():
                    time.sleep(30)
                _log("Market is OPEN — proceeding with engine start")

            # ── Clean stale state (live AND paper) BEFORE any engine start ──
            # Without this, yesterday's running=True flag causes start() to no-op
            # with "already running", leaving engines silently dead for the whole day.
            _stale_engines_all = [
                ("Equity Live", auto_trader),
                ("Options Live", options_auto_trader),
                ("BTST Live", btst_trader),
                ("Equity Paper", paper_trader),
                ("Options Paper", options_paper_trader),
                ("BTST Paper", btst_paper_trader),
            ]
            for _stale_name, _stale_engine in _stale_engines_all:
                try:
                    if getattr(_stale_engine, '_running', False):
                        _stale_engine.stop()
                        _log(f"{_stale_name}: stopped stale state — will restart with fresh capital")
                except Exception:
                    pass
            import os as _os
            for _sf in ['.auto_trader_state.json', '.options_auto_trader_state.json', '.btst_trader_state.json',
                        '.paper_trader_state.json', '.options_paper_trader_state.json', '.btst_paper_trader_state.json']:
                _sf_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), _sf)
                if _os.path.exists(_sf_path):
                    try:
                        import json as _json
                        with open(_sf_path) as _f:
                            _sd = _json.load(_f)
                        if _sd.get('date') != now_ist().strftime('%Y-%m-%d'):
                            _os.remove(_sf_path)
                            _log(f"Deleted stale state file: {_sf} (from {_sd.get('date')})")
                    except Exception:
                        pass

            # Auto-start only engines with proven edge or clear potential
            # Others are hidden (not auto-started) but still available via UI/API
            paper_configs = [
                ("Equity Intraday Paper", lambda: paper_trader.start(
                    strategies=detect_equity_regime().get("strategies", []),
                    capital=75000)),
                ("BTST Paper", lambda: btst_paper_trader.start(
                    strategies=_btst_strategies(),
                    capital=50000)),
                # PAUSED 2026-04-22 — TradeJini options symbol format + NFO spot price
                # endpoint not yet supported. Scanner hammers chart endpoint with bad
                # symbols → 429 rate limits. Not in current strategic path (equity
                # swing via Option 1 plan). Re-enable after Fix 11 lands.
                # ("Options Intraday Paper", lambda: options_paper_trader.start(
                #     capital=25000, underlyings=["NIFTY", "BANKNIFTY"])),
                # Hidden — no proven edge yet. Can start manually from UI if needed:
                # ("Equity Swing Paper", lambda: swing_paper_trader.start(...)),
                # ("Options Swing Paper", lambda: options_swing_paper_trader.start(...)),
                # ("Futures Intraday Paper", lambda: futures_paper_trader.start(...)),
                # ("Futures Swing Paper", lambda: futures_swing_paper_trader.start(...)),
            ]

            for name, start_fn in paper_configs:
                try:
                    result = start_fn()
                    if result and not result.get("error"):
                        _log(f"{name}: started")
                    else:
                        err = (result or {}).get("error", "unknown — empty result")
                        _log(f"{name}: NOT STARTED — {err}")
                except Exception as e:
                    _log(f"{name}: FAILED — {e}")

            # ── Kill-switch: skip all live engines if HONEYDAALU_DISABLE_LIVE is set ──
            # Paper engines already started above; this only blocks live.
            if os.getenv("HONEYDAALU_DISABLE_LIVE", "").strip().lower() in ("1", "true", "yes", "on"):
                _log("Live engines DISABLED by HONEYDAALU_DISABLE_LIVE env var — paper engines continue")
                return

            # ── Live engines: Equity Intraday + Options Intraday ONLY ──
            # Market-open wait + stale-state cleanup already ran above (before paper).
            # Futures Live and all Swing Live stay paper-only until proven profitable.
            # A2: Verify broker is truly connected (retry up to 5 times, re-login if needed)
            for _broker_check in range(5):
                if broker_client.is_authenticated():
                    break
                _log(f"Broker not authenticated — re-login attempt {_broker_check+1}/5...")
                try:
                    broker_client.headless_login()
                    time.sleep(3)
                except Exception:
                    pass
                time.sleep(5)
            else:
                _log("Broker not connected after 5 re-login attempts — skipping live engines")
                try:
                    from services import telegram_notify
                    telegram_notify.send("🚨 <b>ALERT: Broker Disconnected Mid-Day</b>\n5 re-login attempts failed.\nLive engines stopped. Check immediately!")
                except Exception:
                    pass
                return

            try:
                funds = broker_client.get_funds()
                fund_list = funds.get("fund_limit", [])
                available = 0
                for f in fund_list:
                    if f.get("id") == 10:
                        available = f.get("equityAmount", 0)

                if available <= 0:
                    _log("No funds available — skipping live engines")
                    return

                _log(f"Available capital: ₹{available:,.0f}")

                # Detect market conditions for allocation
                regime = detect_equity_regime()
                vix = regime.get("components", {}).get("vix", 15)
                regime_name = regime.get("regime", "neutral")

                # ══════════════════════════════════════════════════════════
                # DYNAMIC CAPITAL ALLOCATION — PERFORMANCE-BASED
                #
                # Checks last 3 days: which engine made money?
                # Allocates MORE to the winner, LESS to the loser.
                # VIX modifier: high VIX favors Options, low VIX favors Equity.
                # Both losing? Reduce exposure, hold more cash.
                # ══════════════════════════════════════════════════════════

                # Check NFO segment
                nfo_enabled = False
                for _nfo_try in range(3):
                    nfo_enabled = broker_client.is_nfo_enabled()
                    if nfo_enabled:
                        break
                    time.sleep(5)

                # Get rolling 3-day performance
                opt_pnl_3d = 0
                eq_pnl_3d = 0
                try:
                    from services.trade_logger import get_all_trades
                    recent = get_all_trades(days=3)
                    for t in recent:
                        src = t.get("source", "")
                        pnl = t.get("pnl", 0)
                        if src in ("options_auto",):
                            opt_pnl_3d += pnl
                        elif src in ("auto",):
                            eq_pnl_3d += pnl
                    _log(f"Rolling 3-day P&L: Options ₹{opt_pnl_3d:,.0f} | Equity ₹{eq_pnl_3d:,.0f}")
                except Exception:
                    _log("Could not fetch rolling P&L — using default allocation")

                # Calculate allocation based on performance + VIX
                opt_capital = 0
                eq_capital = int(available)

                if available < 40000 or not nfo_enabled:
                    # Too little to split OR NFO not enabled → all to equity
                    opt_capital = 0
                    eq_capital = int(available)
                    if not nfo_enabled:
                        _log("NFO: NOT ENABLED — all to equity")
                else:
                    # Base split from performance
                    if opt_pnl_3d > 0 and eq_pnl_3d <= 0:
                        # Options winning, equity losing → heavy options
                        opt_pct = 0.65
                    elif eq_pnl_3d > 0 and opt_pnl_3d <= 0:
                        # Equity winning, options losing → heavy equity
                        opt_pct = 0.30
                    elif opt_pnl_3d > 0 and eq_pnl_3d > 0:
                        # Both winning → split by expectancy ratio
                        total = abs(opt_pnl_3d) + abs(eq_pnl_3d)
                        opt_pct = max(0.30, min(0.65, opt_pnl_3d / total)) if total > 0 else 0.50
                    elif opt_pnl_3d < 0 and eq_pnl_3d < 0:
                        # Both losing → conservative, hold more cash
                        opt_pct = 0.35
                        # Reduce total allocation by 20% (hold cash)
                        available = int(available * 0.80)
                        _log(f"Both engines losing — reduced allocation to ₹{available:,} (20% cash reserve)")
                    else:
                        # No data yet → default 50/50
                        opt_pct = 0.50

                    # VIX modifier: high VIX boosts options (higher premiums)
                    if vix > 22:
                        opt_pct = min(0.65, opt_pct + 0.10)
                        _log(f"VIX {vix:.1f} > 22 — boosting options allocation +10%")
                    elif vix < 15:
                        opt_pct = max(0.25, opt_pct - 0.10)
                        _log(f"VIX {vix:.1f} < 15 — boosting equity allocation +10%")

                    # Apply allocation (cap options at ₹50K for spread margin safety)
                    opt_capital = min(int(available * opt_pct), 50000)
                    eq_capital = int(available - opt_capital)

                    # Minimums: at least ₹15K for options (1 spread), ₹20K for equity
                    if opt_capital < 15000:
                        opt_capital = 0
                        eq_capital = int(available)
                    if eq_capital < 20000:
                        eq_capital = 0

                _log(f"Dynamic allocation: Options ₹{opt_capital:,} ({opt_capital*100//(available or 1)}%) | Equity ₹{eq_capital:,} ({eq_capital*100//(available or 1)}%) | BTST dynamic at 2 PM")

                # BTST Live: deferred start at 1:50 PM (10 min before entry window)
                # No capital reserved upfront. Equity gets 100%. BTST uses available funds at 2 PM.
                def _start_btst_deferred():
                    """Wait until 1:50 PM, then start BTST Live with dynamic capital."""
                    import time as _time
                    from utils.time_utils import now_ist
                    while True:
                        now = now_ist()
                        if now.hour > 13 or (now.hour == 13 and now.minute >= 50):
                            break
                        if now.hour >= 15 and now.minute >= 30:
                            _log("BTST Live: market closed before BTST window — skipped today")
                            return
                        _time.sleep(30)
                    try:
                        _log("BTST Live: 1:50 PM — starting BTST engine")
                        btst_strats = _btst_strategies()
                        r = btst_trader.start(strategies=btst_strats, capital=0)
                        if not r.get("error"):
                            _log(f"BTST Live: started | {len(btst_strats)} strategies (daily TF) | capital from broker at scan time")
                        else:
                            _log(f"BTST Live error: {r.get('error')}")
                    except Exception as e:
                        _log(f"BTST Live FAILED: {e}")
                        traceback.print_exc()

                # BTST Live disabled for Phase 1 — prove equity first, then enable
                # threading.Thread(target=_start_btst_deferred, daemon=True, name="BTSTDeferredStart").start()
                _log("BTST Live: DISABLED (Phase 1 — equity only)")

                # Start Equity Live — FIRST priority
                if eq_capital >= 20000:
                    try:
                        strategies = regime.get("strategies", [])
                        r = auto_trader.start(strategies=strategies, capital=eq_capital)
                        if not r.get("error"):
                            _log(f"Equity Live: ₹{eq_capital:,} | {len(strategies)} strategies | {regime_name}")
                        else:
                            _log(f"Equity Live error: {r.get('error')}")
                    except Exception as e:
                        _log(f"Equity Live FAILED: {e}")
                        traceback.print_exc()

                # Start Options Live — LAST priority, spread margin fix active
                # BUY legs placed first → broker recognizes spread → reduced margin
                opt_status = "DISABLED (NFO not enabled)"
                if nfo_enabled and opt_capital >= 15000:
                    try:
                        opt_underlyings = ["BANKNIFTY"]
                        if opt_capital >= 30000:
                            opt_underlyings = ["NIFTY", "BANKNIFTY"]
                        r = options_auto_trader.start(capital=opt_capital, underlyings=opt_underlyings)
                        if not r.get("error"):
                            opt_status = f"₹{opt_capital:,} | {opt_underlyings}"
                            _log(f"Options Live: {opt_status}")
                        else:
                            opt_status = f"ERROR: {r.get('error')}"
                            _log(f"Options Live error: {r.get('error')}")
                    except Exception as e:
                        opt_status = f"FAILED: {e}"
                        _log(f"Options Live FAILED: {e}")
                elif not nfo_enabled:
                    opt_status = "DISABLED (NFO not enabled)"
                else:
                    opt_status = f"DISABLED (₹{opt_capital:,} too low, need ₹15K+)"

                _log("═" * 50)
                _log(f"AUTO-START COMPLETE")
                _log(f"  Regime: {regime_name} | VIX: {vix:.1f}")
                _log(f"  Options Live: {opt_status} (PRIMARY — ₹795/trade on paper)")
                _log(f"  Equity Live:  ₹{eq_capital:,} | {len(regime.get('strategies', []))} strategies")
                _log(f"  BTST Live:    DISABLED (Phase 1)")
                _log(f"  Paper engines running")
                _log(f"  Auto-shutdown: 3:45 PM")
                _log("═" * 50)

                # Telegram: morning brief
                try:
                    engines = []
                    if nfo_enabled and opt_capital >= 15000:
                        engines.append(f"Options Live: ₹{opt_capital:,} (primary)")
                    else:
                        engines.append("Options: paper only")
                    if eq_capital >= 20000:
                        engines.append(f"Equity Live: ₹{eq_capital:,}")
                    engines.append("BTST Live: 1:50 PM")
                    telegram_notify.morning_brief(available, regime_name, vix, engines)
                except Exception:
                    pass

            except Exception as e:
                _log(f"Live allocation FAILED: {e}")
                traceback.print_exc()

        except Exception as e:
            print(f"[AutoStart] FATAL: {e}", flush=True)
            traceback.print_exc()

    # Prevent duplicate threads — check if already running
    import threading as _th
    existing = [t.name for t in _th.enumerate()]
    if "AutoStartEngines" not in existing:
        _th.Thread(target=_auto_start_engines, daemon=True, name="AutoStartEngines").start()
    else:
        print("[AutoStart] Thread already running — skipping duplicate", flush=True)

    # C9: Auto-shutdown after market close
    def _auto_shutdown():
        """Auto-shutdown server after market close + EOD analysis."""
        import time
        from utils.time_utils import now_ist

        # Cold-start guard: if server starts after 3:45 PM, skip auto-shutdown entirely.
        # This prevents crash loops when server is restarted after market hours.
        boot_time = now_ist()
        if boot_time.hour > 15 or (boot_time.hour == 15 and boot_time.minute >= 45):
            print(f"[AutoShutdown] Server started at {boot_time.strftime('%H:%M')} (after 3:45 PM) — skipping auto-shutdown to prevent crash loop", flush=True)
            return
        if boot_time.weekday() >= 5:
            print(f"[AutoShutdown] Weekend — skipping auto-shutdown", flush=True)
            return

        _half_day_sent = False
        while True:
            now = now_ist()
            # Wait until 3:45 PM
            if now.hour >= 15 and now.minute >= 45:
                break
            if now.hour >= 16:
                break

            # Half-day summary at 1:00 PM
            if not _half_day_sent and now.hour >= 13:
                _half_day_sent = True
                try:
                    total_pnl = 0.0
                    open_count = 0
                    closed_count = 0
                    wins = 0
                    losses = 0
                    # Gather stats from auto_trader
                    if auto_trader._running:
                        total_pnl += getattr(auto_trader, '_total_pnl', 0)
                        open_count += len([t for t in auto_trader._active_trades if t.get("status") == "OPEN"])
                        for t in getattr(auto_trader, '_trade_history', []):
                            closed_count += 1
                            if t.get("pnl", 0) >= 0:
                                wins += 1
                            else:
                                losses += 1
                    telegram_notify.half_day_summary(total_pnl, open_count, closed_count, wins, losses)
                except Exception:
                    pass

            time.sleep(60)

        print("[AutoShutdown] 3:45 PM — starting EOD pipeline...", flush=True)

        # Day-end summary via Telegram
        try:
            from services.broker_client import get_funds as _eod_funds, get_tradebook as _eod_trades
            broker_trades = 0
            broker_pnl = 0
            try:
                tb = _eod_trades()
                for t in tb.get("tradeBook", []):
                    broker_trades += 1
                    broker_pnl += t.get("pl", 0)
            except Exception:
                pass

            # Fallback to internal tracking if broker data unavailable
            if broker_trades == 0:
                for t in getattr(auto_trader, '_trade_history', []):
                    broker_trades += 1
                    broker_pnl += t.get("pnl", 0)
                for t in getattr(options_auto_trader, '_trade_history', []):
                    broker_trades += 1
                    broker_pnl += t.get("pnl", 0)

            total_pnl = round(broker_pnl, 2)
            trades = broker_trades
            wins = 0
            losses = 0
            for t in getattr(auto_trader, '_trade_history', []):
                if t.get("pnl", 0) >= 0:
                    wins += 1
                else:
                    losses += 1
            for t in getattr(options_auto_trader, '_trade_history', []):
                if t.get("pnl", 0) >= 0:
                    wins += 1
                else:
                    losses += 1

            capital = 0
            try:
                funds = _eod_funds()
                for f_item in funds.get("fund_limit", []):
                    if f_item.get("id") == 10:
                        capital = f_item.get("equityAmount", 0)
            except Exception:
                capital = getattr(auto_trader, '_capital', 100000)

            charges = round(trades * 65, 2) if trades > 0 else 0
            net_pnl = round(total_pnl - charges, 2)
            btst_open = len([t for t in getattr(btst_trader, '_active_trades', []) if t.get("status") == "OPEN"])

            # Build strategy-level breakdown for day_end notification
            _strat_map = {}
            _all_hist = (
                list(getattr(auto_trader, '_trade_history', []))
                + list(getattr(options_auto_trader, '_trade_history', []))
            )
            for _t in _all_hist:
                _k = _t.get("strategy", "unknown") or "unknown"
                if _k not in _strat_map:
                    _strat_map[_k] = {"name": _k, "trades": 0, "wins": 0, "pnl": 0.0}
                _strat_map[_k]["trades"] += 1
                _strat_map[_k]["pnl"] += _t.get("pnl", 0)
                if _t.get("pnl", 0) >= 0:
                    _strat_map[_k]["wins"] += 1
            _strategy_breakdown = sorted(_strat_map.values(), key=lambda x: x["pnl"], reverse=True)

            # Best and worst individual trade
            _best = max(_all_hist, key=lambda x: x.get("pnl", 0), default=None)
            _worst = min(_all_hist, key=lambda x: x.get("pnl", 0), default=None)

            # Live vs paper P&L
            _live_pnl = (
                getattr(auto_trader, '_total_pnl', 0)
                + getattr(options_auto_trader, '_total_pnl', 0)
            )
            _paper_pnl_traders = [
                getattr(paper_trader, '_total_pnl', None),
                getattr(options_paper_trader, '_total_pnl', None),
            ]
            _paper_pnl = sum(v for v in _paper_pnl_traders if v is not None)

            telegram_notify.day_end(
                total_pnl, charges, net_pnl, trades, wins, losses, capital, btst_open,
                strategy_breakdown=_strategy_breakdown if _strategy_breakdown else None,
                best_trade=_best,
                worst_trade=_worst,
                live_pnl=_live_pnl,
                paper_pnl=_paper_pnl,
            )
        except Exception:
            pass

        # ── Post-market reconciliation: broker orderbook vs our trade log ──────
        # Count how many broker-confirmed trades we have vs what we tracked internally.
        # Mismatches = orders that went to broker but weren't logged (or vice versa).
        try:
            from services.broker_client import get_tradebook as _recon_trades
            _recon_tb = _recon_trades()
            _broker_order_ids = set()
            for _ro in _recon_tb.get("tradeBook", []):
                _oid = str(_ro.get("orderId", "") or _ro.get("id", ""))
                if _oid:
                    _broker_order_ids.add(_oid)

            _internal_order_ids = set()
            for _it in (
                list(getattr(auto_trader, '_trade_history', []))
                + list(getattr(options_auto_trader, '_trade_history', []))
                + list(getattr(btst_trader, '_trade_history', []))
            ):
                _oid = str(_it.get("order_id", "") or "")
                if _oid and _oid not in ("recovered", "unknown", ""):
                    _internal_order_ids.add(_oid)

            _broker_only = _broker_order_ids - _internal_order_ids  # on broker but not logged
            _log_only = _internal_order_ids - _broker_order_ids     # logged but not on broker

            _mismatch_count = len(_broker_only) + len(_log_only)
            print(f"[AutoShutdown] Reconciliation: broker={len(_broker_order_ids)} trades | log={len(_internal_order_ids)} | mismatches={_mismatch_count}", flush=True)

            if _mismatch_count > 0:
                _recon_msg = (
                    f"⚠️ <b>Post-Market Reconciliation</b>\n\n"
                    f"Broker trades: {len(_broker_order_ids)}\n"
                    f"Our log: {len(_internal_order_ids)}\n"
                    f"Mismatches: {_mismatch_count}\n\n"
                )
                if _broker_only:
                    _recon_msg += f"Broker-only (not in log): {', '.join(sorted(_broker_only)[:5])}\n"
                if _log_only:
                    _recon_msg += f"Log-only (not in broker): {', '.join(sorted(_log_only)[:5])}\n"
                _recon_msg += "\nReview trade log manually!"
                from services.telegram_notify import send as _recon_send
                _recon_send(_recon_msg)
            else:
                from services.telegram_notify import send as _recon_send
                _recon_send(
                    f"✅ <b>Reconciliation OK</b>\n"
                    f"Broker={len(_broker_order_ids)} | Log={len(_internal_order_ids)} | No mismatches"
                )
        except Exception as _recon_err:
            print(f"[AutoShutdown] Reconciliation error: {_recon_err}", flush=True)

        # Run EOD analysis
        try:
            from services.auto_tuner import run_eod_pipeline
            run_eod_pipeline("auto_shutdown")
        except Exception as e:
            print(f"[AutoShutdown] EOD pipeline error: {e}", flush=True)

        # Re-enable sleep
        try:
            import subprocess
            subprocess.run(["sudo", "-n", "pmset", "disablesleep", "0"], capture_output=True, timeout=5)
            print("[AutoShutdown] Sleep re-enabled", flush=True)
        except:
            pass

        print("[AutoShutdown] Server shutting down. Trading day complete.", flush=True)
        try:
            from services.telegram_notify import send as _shutdown_send
            _shutdown_send("🔴 <b>System Shutdown</b>\nTrading day complete. Auto-start at 9:00 AM tomorrow.")
            import time as _t; _t.sleep(2)
        except Exception:
            pass

        # Graceful shutdown
        import os, signal
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=_auto_shutdown, daemon=True, name="AutoShutdown").start()

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173",
                   "http://3.109.167.163", "http://3.109.167.163:80",
                   "https://3.109.167.163", "https://3.109.167.163:443"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════
#  Auth Middleware — protect all /api/* routes except /api/auth/*
# ═══════════════════════════════════════════════════════════════════════════

# Paths that don't require authentication
AUTH_EXEMPT_PREFIXES = ("/api/auth/", "/docs", "/openapi.json", "/redoc")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """JWT auth check for all /api/* routes except /api/auth/*."""
    path = request.url.path

    # Root path — no auth needed
    if path == "/":
        return await call_next(request)

    # Auth endpoints — no auth needed
    if any(path.startswith(prefix) for prefix in AUTH_EXEMPT_PREFIXES):
        return await call_next(request)

    # OPTIONS (CORS preflight) — no auth needed
    if request.method == "OPTIONS":
        return await call_next(request)

    # All /api/* routes require auth
    if path.startswith("/api/"):
        auth_header = request.headers.get("authorization", "")

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "Authentication required", "code": "NO_TOKEN"},
            )

        token = auth_header[7:]  # Strip "Bearer "
        result = verify_token(token)

        if not result.get("valid"):
            return JSONResponse(
                status_code=401,
                content={"error": result.get("error", "Invalid token"), "code": "INVALID_TOKEN"},
            )

        # Attach email to request state for downstream use
        request.state.user_email = result["email"]

    return await call_next(request)


# ═══════════════════════════════════════════════════════════════════════════
#  Auth Endpoints
# ═══════════════════════════════════════════════════════════════════════════


class OTPRequest(BaseModel):
    email: str


class OTPVerify(BaseModel):
    email: str
    otp: str


@app.post("/api/auth/request-otp")
def auth_request_otp(req: OTPRequest):
    """Send a 6-digit OTP to the configured Telegram chat."""
    return request_otp(req.email)


@app.post("/api/auth/verify-otp")
def auth_verify_otp(req: OTPVerify):
    """Verify OTP and return a JWT token."""
    return verify_otp(req.email, req.otp)


@app.get("/api/auth/status")
def auth_status(request: Request):
    """Check if the current token is valid."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return {"authenticated": False}

    token = auth_header[7:]
    result = verify_token(token)

    if result.get("valid"):
        return {"authenticated": True, "email": result["email"]}

    return {"authenticated": False, "error": result.get("error", "Invalid token")}


# ═══════════════════════════════════════════════════════════════════════════
#  General
# ═══════════════════════════════════════════════════════════════════════════


@app.get("/")
def root():
    return {"status": "ok", "app": "LuckyNavi"}


@app.get("/api/market/status")
def market_status():
    """Check if NSE market is currently open."""
    return get_market_status()


# ═══════════════════════════════════════════════════════════════════════════
#  SEBI Compliance
# ═══════════════════════════════════════════════════════════════════════════


@app.get("/api/compliance/status")
def compliance_status():
    """Get SEBI algo trading compliance status."""
    from services.sebi_compliance import get_compliance_status
    return get_compliance_status()


@app.get("/api/compliance/ops")
def compliance_ops():
    """Get current OPS (Orders Per Second) statistics."""
    from services.sebi_compliance import get_ops_stats
    return get_ops_stats()


@app.get("/api/compliance/strategies")
def compliance_strategies():
    """Get strategy-to-algo-ID mapping."""
    from services.sebi_compliance import STRATEGY_ALGO_IDS
    return {"strategies": STRATEGY_ALGO_IDS}


# ═══════════════════════════════════════════════════════════════════════════
#  Strategies
# ═══════════════════════════════════════════════════════════════════════════


@app.get("/api/strategies")
def list_strategies():
    """List all 6 strategies from the playbook."""
    result = []
    for key, strategy in STRATEGY_MAP.items():
        info = strategy.info()
        info["id"] = key
        info["timeframes"] = STRATEGY_TIMEFRAMES.get(key, [])
        result.append(info)
    return result


@app.get("/api/strategies/swing")
def list_swing_strategies_early():
    """List strategies that support swing trading."""
    result = []
    for key in SWING_STRATEGY_TIMEFRAMES:
        strategy = STRATEGY_MAP.get(key)
        if strategy:
            info = strategy.info()
            info["id"] = key
            info["timeframes"] = SWING_STRATEGY_TIMEFRAMES[key]
            result.append(info)
    return result


@app.get("/api/strategies/{strategy_id}")
def get_strategy(strategy_id: str):
    strategy = STRATEGY_MAP.get(strategy_id)
    if strategy is None:
        return {"error": f"Strategy '{strategy_id}' not found"}
    info = strategy.info()
    info["id"] = strategy_id
    info["timeframes"] = STRATEGY_TIMEFRAMES.get(strategy_id, [])
    return info


@app.get("/api/scan/{strategy_id}")
def scan_strategy(strategy_id: str, timeframe: str = "15m", capital: float = 100000):
    """Scan Nifty 500 stocks for signals."""
    return run_scan(strategy_id, timeframe, capital)


@app.get("/api/timeframes/{strategy_id}")
def get_timeframes(strategy_id: str):
    tfs = STRATEGY_TIMEFRAMES.get(strategy_id)
    if tfs is None:
        return {"error": f"Strategy '{strategy_id}' not found"}
    return {"strategy": strategy_id, "timeframes": tfs}


# ═══════════════════════════════════════════════════════════════════════════
#  Broker Authentication
# ═══════════════════════════════════════════════════════════════════════════


@app.get("/api/broker/status")
def broker_status():
    """Check broker connection status."""
    configured = broker_client.is_configured()
    if not configured:
        return {
            "connected": False,
            "configured": False,
            "message": "Broker API credentials not set. Add credentials to backend/.env",
        }

    authenticated = broker_client.is_authenticated()
    if authenticated:
        profile = broker_client.get_profile()
        data = profile.get("data", {})
        return {
            "connected": True,
            "configured": True,
            "profile": {
                "name": data.get("name", ""),
                "email": data.get("email_id", ""),
                "pan": data.get("pan", ""),
                "fy_id": data.get("fy_id", ""),
            },
        }

    return {
        "connected": False,
        "configured": True,
        "message": "Credentials configured. Please login.",
    }


@app.get("/api/broker/login")
def broker_login():
    """Get the broker OAuth2 login URL."""
    if not broker_client.is_configured():
        return {"error": "Broker API credentials not configured in .env"}

    auth_url = broker_client.get_auth_url()
    if auth_url:
        return {"auth_url": auth_url}
    return {"error": "Failed to generate auth URL"}


@app.get("/api/broker/callback")
def broker_callback(
    auth_code: Optional[str] = Query(None),
    s: Optional[str] = Query(None, alias="auth_code"),
):
    """
    OAuth2 callback handler.
    Broker redirects here with ?auth_code=xxx after user logs in.
    """
    code = auth_code or s
    if not code:
        return {"error": "No auth_code received"}

    result = broker_client.generate_token(code)

    if "error" in result:
        return result

    # Redirect to frontend after successful auth
    return RedirectResponse(url="http://localhost:3000?broker_auth=success")


class AuthCodeRequest(BaseModel):
    auth_code: str


@app.post("/api/broker/verify")
def broker_verify(req: AuthCodeRequest):
    """Exchange a manually-pasted auth code for an access token."""
    result = broker_client.generate_token(req.auth_code)
    return result


@app.post("/api/broker/headless-login")
def broker_headless_login():
    """Trigger headless TOTP login."""
    return broker_client.headless_login()


@app.post("/api/broker/logout")
def broker_logout():
    """Clear broker session."""
    return broker_client.logout()


# ═══════════════════════════════════════════════════════════════════════════
#  Broker Account & Funds
# ═══════════════════════════════════════════════════════════════════════════


@app.get("/api/broker/profile")
def broker_profile():
    return broker_client.get_profile()


@app.get("/api/broker/funds")
def broker_funds():
    return broker_client.get_funds()


# ═══════════════════════════════════════════════════════════════════════════
#  Broker Orders
# ═══════════════════════════════════════════════════════════════════════════


class OrderRequest(BaseModel):
    symbol: str
    qty: int
    side: int              # 1=Buy, -1=Sell
    order_type: int = 2    # 1=Limit, 2=Market, 3=SL, 4=SL-M
    product_type: str = "INTRADAY"
    limit_price: float = 0
    stop_price: float = 0


class BracketOrderRequest(BaseModel):
    symbol: str
    qty: int
    side: int
    limit_price: float
    stop_loss: float
    target: float


@app.post("/api/broker/order")
def place_order(req: OrderRequest):
    """Place a regular order."""
    return broker_client.place_order(
        symbol=req.symbol,
        qty=req.qty,
        side=req.side,
        order_type=req.order_type,
        product_type=req.product_type,
        limit_price=req.limit_price,
        stop_price=req.stop_price,
    )


@app.post("/api/broker/order/bracket")
def place_bracket_order(req: BracketOrderRequest):
    """Place a bracket order (entry + SL + target)."""
    return broker_client.place_bracket_order(
        symbol=req.symbol,
        qty=req.qty,
        side=req.side,
        limit_price=req.limit_price,
        stop_loss=req.stop_loss,
        target=req.target,
    )


@app.delete("/api/broker/order/{order_id}")
def cancel_order(order_id: str):
    return broker_client.cancel_order(order_id)


@app.get("/api/broker/orders")
def get_orderbook():
    return broker_client.get_orderbook()


@app.get("/api/broker/trades")
def get_tradebook():
    return broker_client.get_tradebook()


# ═══════════════════════════════════════════════════════════════════════════
#  Broker Positions & Holdings
# ═══════════════════════════════════════════════════════════════════════════


@app.get("/api/broker/positions")
def get_positions():
    return broker_client.get_positions()


@app.get("/api/broker/holdings")
def get_holdings():
    return broker_client.get_holdings()


# ═══════════════════════════════════════════════════════════════════════════
#  Broker Market Data
# ═══════════════════════════════════════════════════════════════════════════


@app.get("/api/broker/quotes")
def get_quotes(symbols: str = Query(..., description="Comma-separated NSE symbols")):
    """Get live quotes. Usage: ?symbols=RELIANCE,TCS,INFY"""
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    return broker_client.get_quotes(symbol_list)


@app.get("/api/broker/depth/{symbol}")
def get_market_depth(symbol: str):
    """Get market depth for a symbol."""
    return broker_client.get_market_depth(symbol)


# ═══════════════════════════════════════════════════════════════════════════
#  Auto-Trading Engine
# ═══════════════════════════════════════════════════════════════════════════


class StrategySelection(BaseModel):
    strategy: str
    timeframe: str


class AutoStartRequest(BaseModel):
    strategies: list[StrategySelection]
    capital: float = 100000


@app.get("/api/equity/regime")
def get_equity_regime():
    """Get current equity market regime and auto-selected strategies."""
    from services.equity_regime import detect_equity_regime
    return detect_equity_regime()


class EquityAutoStartRequest(BaseModel):
    capital: float = 100000


@app.post("/api/auto/start-auto")
def auto_start_regime(req: EquityAutoStartRequest):
    """Start equity intraday live with auto strategy selection based on market regime."""
    from services.equity_regime import detect_equity_regime
    regime = detect_equity_regime()
    strategies = regime.get("strategies", [])
    if not strategies:
        return {"error": "No strategies selected by regime detector"}
    result = auto_trader.start(
        strategies=[{"strategy": s["strategy"], "timeframe": s["timeframe"]} for s in strategies],
        capital=req.capital,
    )
    result["regime"] = regime
    return result


@app.post("/api/paper/start-auto")
def paper_start_regime(req: EquityAutoStartRequest):
    """Start equity intraday paper with auto strategy selection."""
    from services.equity_regime import detect_equity_regime
    regime = detect_equity_regime()
    strategies = regime.get("strategies", [])
    if not strategies:
        return {"error": "No strategies selected by regime detector"}
    result = paper_trader.start(
        strategies=[{"strategy": s["strategy"], "timeframe": s["timeframe"]} for s in strategies],
        capital=req.capital,
    )
    result["regime"] = regime
    return result


@app.post("/api/auto/start")
def auto_start(req: AutoStartRequest):
    """Start the auto-trading engine with one or more strategies (manual selection)."""
    return auto_trader.start(
        strategies=[s.model_dump() for s in req.strategies],
        capital=req.capital,
    )


@app.post("/api/auto/stop")
def auto_stop():
    """Stop the auto-trading engine."""
    return auto_trader.stop()


@app.get("/api/auto/status")
def auto_status():
    """Get auto-trader current state, active trades, and logs."""
    return auto_trader.status()


# ═══════════════════════════════════════════════════════════════════════════
#  Paper Trading (Virtual Auto-Trader)
# ═══════════════════════════════════════════════════════════════════════════


@app.post("/api/paper/start")
def paper_start(req: AutoStartRequest):
    """Start virtual auto-trading with one or more strategies."""
    return paper_trader.start(
        strategies=[s.model_dump() for s in req.strategies],
        capital=req.capital,
    )


@app.post("/api/paper/stop")
def paper_stop():
    """Stop virtual auto-trading."""
    return paper_trader.stop()


@app.get("/api/paper/status")
def paper_status():
    """Get paper trader current state, virtual trades, and logs."""
    return paper_trader.status()


# ═══════════════════════════════════════════════════════════════════════════
#  Swing Trading (Live)
# ═══════════════════════════════════════════════════════════════════════════


class SwingStartRequest(BaseModel):
    strategies: list[StrategySelection]
    capital: float = 100000
    scan_interval_minutes: int = 240


@app.post("/api/swing/start")
def swing_start(req: SwingStartRequest):
    """Start the live swing trading engine."""
    return swing_trader.start(
        strategies=[s.model_dump() for s in req.strategies],
        capital=req.capital,
        scan_interval_minutes=req.scan_interval_minutes,
    )


@app.post("/api/swing/start-auto")
def swing_start_regime(req: EquityAutoStartRequest):
    """Start equity swing live with auto strategy selection from regime."""
    from config import SWING_STRATEGY_TIMEFRAMES
    strategies = [{"strategy": s, "timeframe": tfs[0]} for s, tfs in SWING_STRATEGY_TIMEFRAMES.items()]
    if not strategies:
        return {"error": "No swing strategies configured"}
    result = swing_trader.start(strategies=strategies, capital=req.capital)
    result["auto_regime"] = True
    result["strategies_count"] = len(strategies)
    return result


@app.post("/api/swing/stop")
def swing_stop():
    return swing_trader.stop()


@app.get("/api/swing/status")
def swing_status():
    return swing_trader.status()


@app.post("/api/swing/scan")
def swing_trigger_scan():
    return swing_trader.trigger_scan()


# ═══════════════════════════════════════════════════════════════════════════
#  Swing Paper Trading (Virtual)
# ═══════════════════════════════════════════════════════════════════════════


@app.post("/api/swing-paper/start")
def swing_paper_start(req: SwingStartRequest):
    """Start virtual swing trading."""
    return swing_paper_trader.start(
        strategies=[s.model_dump() for s in req.strategies],
        capital=req.capital,
        scan_interval_minutes=req.scan_interval_minutes,
    )


@app.post("/api/swing-paper/start-auto")
def swing_paper_start_regime(req: EquityAutoStartRequest):
    """Start equity swing paper with auto strategy selection."""
    from config import SWING_STRATEGY_TIMEFRAMES
    strategies = [{"strategy": s, "timeframe": tfs[0]} for s, tfs in SWING_STRATEGY_TIMEFRAMES.items()]
    if not strategies:
        return {"error": "No swing strategies configured"}
    result = swing_paper_trader.start(strategies=strategies, capital=req.capital)
    result["auto_regime"] = True
    result["strategies_count"] = len(strategies)
    return result


@app.post("/api/swing-paper/stop")
def swing_paper_stop():
    return swing_paper_trader.stop()


@app.get("/api/swing-paper/status")
def swing_paper_status():
    return swing_paper_trader.status()


@app.post("/api/swing-paper/close/{symbol}")
def swing_paper_close_trade(symbol: str):
    return swing_paper_trader.force_close_trade(symbol)


@app.post("/api/swing-paper/scan")
def swing_paper_trigger_scan():
    return swing_paper_trader.trigger_scan()


# ═══════════════════════════════════════════════════════════════════════════
#  BTST Trading (Live) — Buy Today Sell Tomorrow (CNC orders)
# ═══════════════════════════════════════════════════════════════════════════


class BTSTStartRequest(BaseModel):
    strategies: list[StrategySelection]
    capital: float = 100000


@app.post("/api/btst/start")
def btst_start(req: BTSTStartRequest):
    """Start the live BTST trading engine."""
    return btst_trader.start(
        strategies=[s.model_dump() for s in req.strategies],
        capital=req.capital,
    )


def _build_btst_strategies() -> list[dict]:
    """BTST strategies need daily/hourly timeframes, not intraday 5m/15m."""
    from services.equity_regime import detect_equity_regime
    from config import BTST_STRATEGY_TIMEFRAMES
    regime_ids = detect_equity_regime().get("strategy_ids", [])
    btst_strats = [{"strategy": k, "timeframe": BTST_STRATEGY_TIMEFRAMES[k][0]}
                   for k in regime_ids if k in BTST_STRATEGY_TIMEFRAMES]
    if not btst_strats:
        btst_strats = [{"strategy": k, "timeframe": tfs[0]}
                       for k, tfs in BTST_STRATEGY_TIMEFRAMES.items()]
    return btst_strats


@app.post("/api/btst/start-auto")
def btst_start_regime(req: EquityAutoStartRequest):
    """Start BTST live with auto strategy selection from regime."""
    strategies = _build_btst_strategies()
    if not strategies:
        return {"error": "No BTST strategies available"}
    result = btst_trader.start(strategies=strategies, capital=req.capital)
    result["auto_regime"] = True
    result["strategies_count"] = len(strategies)
    return result


@app.post("/api/btst/stop")
def btst_stop():
    """Stop the live BTST trading engine."""
    return btst_trader.stop()


@app.get("/api/btst/status")
def btst_status():
    """Get BTST trader current state, active trades, and logs."""
    return btst_trader.status()


@app.post("/api/btst/scan")
def btst_trigger_scan():
    """Trigger a manual BTST scan."""
    return btst_trader.trigger_scan()


# ═══════════════════════════════════════════════════════════════════════════
#  BTST Paper Trading (Virtual)
# ═══════════════════════════════════════════════════════════════════════════


@app.post("/api/btst-paper/start")
def btst_paper_start(req: BTSTStartRequest):
    """Start virtual BTST trading."""
    return btst_paper_trader.start(
        strategies=[s.model_dump() for s in req.strategies],
        capital=req.capital,
    )


@app.post("/api/btst-paper/start-auto")
def btst_paper_start_regime(req: EquityAutoStartRequest):
    """Start BTST paper with auto strategy selection."""
    strategies = _build_btst_strategies()
    if not strategies:
        return {"error": "No BTST strategies available"}
    result = btst_paper_trader.start(strategies=strategies, capital=req.capital)
    result["auto_regime"] = True
    result["strategies_count"] = len(strategies)
    return result


@app.post("/api/btst-paper/stop")
def btst_paper_stop():
    """Stop virtual BTST trading."""
    return btst_paper_trader.stop()


@app.get("/api/btst-paper/status")
def btst_paper_status():
    """Get BTST paper trader current state, virtual trades, and logs."""
    return btst_paper_trader.status()


@app.post("/api/btst-paper/close/{symbol}")
def btst_paper_close_trade(symbol: str):
    """Force close a single BTST paper trade."""
    return btst_paper_trader.force_close_trade(symbol)


@app.post("/api/btst-paper/scan")
def btst_paper_trigger_scan():
    """Trigger a manual BTST paper scan."""
    return btst_paper_trader.trigger_scan()


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy Stats (persistent trade history)
# ═══════════════════════════════════════════════════════════════════════════


@app.get("/api/strategy/stats")
def strategy_stats(source: str = Query(None, description="Filter: 'live' for auto/swing, 'paper' for paper, None for all")):
    """Get per-strategy success percentage from historical trades."""
    from services.trade_logger import get_strategy_stats
    return get_strategy_stats(source_filter=source)


@app.get("/api/trades/history")
def trade_history(
    days: int = Query(30, description="Number of days to fetch"),
    source: str = Query(None, description="Filter: 'live' (auto+swing), 'paper', 'btst', 'btst_paper', or None for all"),
):
    """Get all trades from the last N days, with estimated brokerage per trade."""
    from services.trade_logger import get_all_trades
    trades = get_all_trades(days)
    valid_sources = {"auto", "paper", "swing", "swing_paper",
                     "options_auto", "options_paper", "options_swing", "options_swing_paper",
                     "futures_auto", "futures_paper", "futures_swing", "futures_swing_paper",
                     "btst", "btst_auto", "btst_paper"}
    if source in valid_sources:
        trades = [t for t in trades if t.get("source") == source]
    elif source == "live":
        trades = [t for t in trades if t.get("source") in ("auto", "swing", "options_auto", "options_swing", "futures_auto", "futures_swing", "btst", "btst_auto")]
    elif source == "all_paper":
        trades = [t for t in trades if t.get("source") in ("paper", "swing_paper", "options_paper", "options_swing_paper", "futures_paper", "futures_swing_paper", "btst_paper")]
    # Add brokerage estimate to each trade
    for t in trades:
        t["charges"] = _estimate_trade_brokerage(t)
        pnl = t.get("pnl", 0)
        t["net_pnl"] = round(pnl - t["charges"], 2)
    return trades


def _estimate_trade_brokerage(trade: dict) -> float:
    """
    Estimate broker charges for a single round-trip trade.
    Handles both equity intraday and options F&O charge structures.
    Paper trades return 0.
    """
    if trade.get("source") in ("paper", "swing_paper", "options_paper", "options_swing_paper", "futures_paper", "futures_swing_paper", "btst_paper"):
        return 0.0

    source = trade.get("source", "")
    is_options = source.startswith("options_")

    if is_options:
        # Options F&O: charges based on premium, not stock price
        legs = trade.get("legs", [])
        num_orders = max(len(legs) * 2, 2)  # entry + exit for each leg (spread=4, iron condor=8)
        lot_size = trade.get("lot_size", 1)
        num_lots = trade.get("quantity", 1)
        total_qty = lot_size * num_lots

        # Calculate premium turnover from legs
        buy_premium = 0.0
        sell_premium = 0.0
        for leg in legs:
            price = leg.get("price", 0)
            side = leg.get("side", 0)
            leg_value = price * total_qty
            if side == 1:  # BUY
                buy_premium += leg_value
            else:  # SELL
                sell_premium += leg_value

        # If no legs data, fallback to net_premium
        if not legs:
            net_premium = abs(trade.get("net_premium", 0))
            premium_turnover = net_premium * total_qty * 2  # rough estimate
            buy_premium = premium_turnover / 2
            sell_premium = premium_turnover / 2

        premium_turnover = buy_premium + sell_premium
        if premium_turnover == 0:
            return 0.0

        brokerage = num_orders * 20.0  # ₹20 per order
        stt = sell_premium * 0.000625  # 0.0625% on sell-side premium
        exchange = premium_turnover * 0.000495  # 0.0495% on premium turnover
        gst = (brokerage + exchange) * 0.18
        sebi = premium_turnover * 0.000001  # ₹10 per crore
        stamp = buy_premium * 0.00003  # 0.003% on buy-side premium

        return round(brokerage + stt + exchange + gst + sebi + stamp, 2)

    else:
        # Equity intraday/swing
        qty = abs(trade.get("quantity", 0))
        entry = trade.get("entry_price", 0)
        exit_p = trade.get("exit_price", 0)
        if qty == 0 or entry == 0:
            return 0.0

        side = trade.get("side", 1)
        if side >= 0:  # BUY first
            buy_val = entry * qty
            sell_val = exit_p * qty
        else:  # SELL first
            sell_val = entry * qty
            buy_val = exit_p * qty

        turnover = buy_val + sell_val
        brokerage = 40.0  # ₹20 per leg × 2
        stt = sell_val * 0.00025  # 0.025% on sell side
        exchange = turnover * 0.0000297  # ~0.00297%
        gst = (brokerage + exchange) * 0.18
        sebi = turnover * 0.000001  # ₹10 per crore
        stamp = buy_val * 0.00003  # 0.003% on buy side

        return round(brokerage + stt + exchange + gst + sebi + stamp, 2)


@app.get("/api/trades/daily-pnl")
def daily_pnl(
    days: int = Query(30, description="Number of days to fetch"),
    source: str = Query(None, description="Filter: 'live' (auto+swing), 'paper', or None for all"),
):
    """Get daily P&L summary aggregated by date."""
    from services.trade_logger import get_all_trades
    from collections import defaultdict

    trades = get_all_trades(days)
    if source in ("auto", "paper", "swing", "swing_paper",
                   "options_auto", "options_paper", "options_swing", "options_swing_paper",
                   "futures_auto", "futures_paper", "futures_swing", "futures_swing_paper",
                   "btst_auto", "btst_paper"):
        trades = [t for t in trades if t.get("source") == source]
    elif source == "live":
        trades = [t for t in trades if t.get("source") in ("auto", "swing", "options_auto", "options_swing", "futures_auto", "futures_swing", "btst_auto")]
    elif source == "all_paper":
        trades = [t for t in trades if t.get("source") in ("paper", "swing_paper", "options_paper", "options_swing_paper", "futures_paper", "futures_swing_paper", "btst_paper")]
    daily = defaultdict(lambda: {
        "total_pnl": 0.0,
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "brokerage": 0.0,
        "strategies": set(),
        "auto_trades": 0,
        "paper_trades": 0,
    })

    for t in trades:
        date = t.get("date", "")
        if not date:
            continue
        d = daily[date]
        pnl = t.get("pnl", 0)
        d["total_pnl"] += pnl
        # Use actual charges if available (paper traders calc realistic brokerage), else estimate
        d["brokerage"] += t.get("charges", _estimate_trade_brokerage(t))
        d["trades"] += 1
        if pnl > 0:
            d["wins"] += 1
            d["gross_profit"] += pnl
        elif pnl < 0:
            d["losses"] += 1
            d["gross_loss"] += pnl
        if t.get("strategy"):
            d["strategies"].add(t["strategy"])
        src = t.get("source", "")
        if "paper" in src:
            d["paper_trades"] += 1
        else:
            d["auto_trades"] += 1

    result = []
    for date in sorted(daily.keys()):
        d = daily[date]
        closed = d["wins"] + d["losses"]
        brokerage = round(d["brokerage"], 2)
        total_pnl = round(d["total_pnl"], 2)
        result.append({
            "date": date,
            "total_pnl": total_pnl,
            "brokerage": brokerage,
            "net_pnl": round(total_pnl - brokerage, 2),
            "trades": d["trades"],
            "wins": d["wins"],
            "losses": d["losses"],
            "win_rate": round((d["wins"] / closed) * 100, 1) if closed > 0 else 0,
            "gross_profit": round(d["gross_profit"], 2),
            "gross_loss": round(d["gross_loss"], 2),
            "strategies": sorted(d["strategies"]),
            "auto_trades": d["auto_trades"],
            "paper_trades": d["paper_trades"],
        })

    # Running cumulative P&L (net of brokerage)
    cumulative = 0.0
    for r in result:
        cumulative += r["net_pnl"]
        r["cumulative_pnl"] = round(cumulative, 2)

    # Enrich with capital tracking
    from services.capital_tracker import get_daily_capital
    capital_source = "paper" if source == "paper" else "live"
    result = get_daily_capital(result, source=capital_source)

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  Capital Tracking
# ═══════════════════════════════════════════════════════════════════════════


class CapitalSetRequest(BaseModel):
    amount: float
    source: str = "live"


class CapitalTxnRequest(BaseModel):
    amount: float
    type: str  # "add" or "withdraw"
    source: str = "live"
    note: str = ""


@app.post("/api/capital/set")
def set_capital(req: CapitalSetRequest):
    """Set the initial/starting capital."""
    from services.capital_tracker import set_initial_capital
    return set_initial_capital(req.amount, req.source)


@app.post("/api/capital/transaction")
def add_capital_transaction(req: CapitalTxnRequest):
    """Record a fund addition or withdrawal."""
    from services.capital_tracker import add_transaction
    return add_transaction(req.amount, req.type, req.source, req.note)


@app.get("/api/capital/info")
def get_capital_info(source: str = Query("live")):
    """Get current capital info: initial capital + all transactions."""
    from services.capital_tracker import get_initial_capital, get_transactions
    txns = get_transactions(source)
    initial = get_initial_capital(source)
    total_added = sum(t["amount"] for t in txns if t["type"] == "add")
    total_withdrawn = sum(t["amount"] for t in txns if t["type"] == "withdraw")
    return {
        "initial_capital": initial,
        "total_added": round(total_added, 2),
        "total_withdrawn": round(total_withdrawn, 2),
        "transactions": txns,
    }


@app.delete("/api/capital/transaction/{index}")
def delete_capital_transaction(index: int, source: str = Query("live")):
    """Delete a fund transaction by index."""
    from services.capital_tracker import delete_transaction
    return delete_transaction(index, source)


# ═══════════════════════════════════════════════════════════════════════════
#  Backtest
# ═══════════════════════════════════════════════════════════════════════════


class BacktestRequest(BaseModel):
    strategy: str
    timeframe: str
    capital: float = 100000
    date: Optional[str] = None  # "YYYY-MM-DD" or None for last trading day


@app.post("/api/backtest")
def run_backtest(req: BacktestRequest):
    """Run a strategy backtest on historical data."""
    return run_backtest_api(
        strategy_key=req.strategy,
        timeframe=req.timeframe,
        capital=req.capital,
        date=req.date,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  EOD Analysis & Strategy Tuning
# ═══════════════════════════════════════════════════════════════════════════


@app.post("/api/eod/analyse")
def eod_analyse():
    """Generate EOD analysis with parameter recommendations."""
    from services.eod_analyser import generate_eod_report
    return generate_eod_report()


@app.post("/api/eod/apply")
def eod_apply_recommendations():
    """Apply EOD recommendations to strategy parameters."""
    from services.eod_analyser import generate_eod_report, apply_recommendations
    report = generate_eod_report()
    recs = report.get("recommendations", [])
    if not recs or not any(r.get("changes") for r in recs):
        return {"applied": 0, "message": "No parameter changes to apply."}
    result = apply_recommendations(recs)
    return result


@app.get("/api/eod/config")
def eod_get_config():
    """Get current strategy parameter config."""
    from services.eod_analyser import get_current_config
    return get_current_config()


# ═══════════════════════════════════════════════════════════════════════════
#  Algo Specialists
# ═══════════════════════════════════════════════════════════════════════════


@app.get("/api/specialists")
def list_specialists():
    """List all 6 algo specialist profiles."""
    from services.specialist_analyser import get_specialists
    return get_specialists()


@app.post("/api/specialist/{specialist_id}/analyse")
def run_specialist(specialist_id: str):
    """Run a specialist's analysis on current trading data."""
    from services.specialist_analyser import run_specialist_analysis
    return run_specialist_analysis(specialist_id)


class DeployRequest(BaseModel):
    deploy_key: str


@app.post("/api/specialist/deploy")
def deploy_recommendation(req: DeployRequest):
    """Deploy a specialist recommendation."""
    from services.specialist_analyser import deploy_recommendation as _deploy
    return _deploy(req.deploy_key)


# ═══════════════════════════════════════════════════════════════════════════
#  Options Trading
# ═══════════════════════════════════════════════════════════════════════════


class OptionsStartRequest(BaseModel):
    capital: float = 200000
    underlyings: list[str] = ["NIFTY", "BANKNIFTY"]


@app.get("/api/options/strategies")
def list_options_strategies():
    """List all options strategies with current regime info."""
    from strategies.options_registry import OPTIONS_STRATEGY_MAP
    from services.market_regime import detect_regime
    regime = detect_regime("NIFTY")
    strategies_list = []
    for key, strat in OPTIONS_STRATEGY_MAP.items():
        info = strat.info()
        info["id"] = key
        info["recommended"] = key in regime.get("recommended_strategies", [])
        strategies_list.append(info)
    return {"strategies": strategies_list, "regime": regime}


@app.get("/api/options/regime")
def get_market_regime(underlying: str = "NIFTY"):
    """Get current market regime (bullish/bearish/neutral/volatile)."""
    from services.market_regime import detect_regime
    return detect_regime(underlying)


@app.get("/api/options/scan/{underlying}")
def scan_options_endpoint(underlying: str, capital: float = 200000, mode: str = "intraday"):
    """Scan NIFTY/BANKNIFTY for options spread setups."""
    from services.options_scanner import scan_options as _scan
    return _scan(underlying, capital, mode)


@app.get("/api/options/chain/{underlying}")
def get_option_chain_endpoint(underlying: str, expiry: str = "weekly"):
    """Get option chain for an underlying."""
    from services.options_client import get_option_chain as _get_chain
    return _get_chain(underlying, expiry)


# ── Options Auto-Trading (Live) ───────────────────────────────────────────


@app.post("/api/options/auto/start")
def options_auto_start(req: OptionsStartRequest):
    """Start live options auto-trading."""
    return options_auto_trader.start(capital=req.capital, underlyings=req.underlyings)


@app.post("/api/options/auto/stop")
def options_auto_stop():
    """Stop live options auto-trading."""
    return options_auto_trader.stop()


@app.get("/api/options/auto/status")
def options_auto_status():
    """Get options auto-trader status, positions, and logs."""
    return options_auto_trader.status()


# ── Options Paper Trading (Virtual) ──────────────────────────────────────


@app.post("/api/options/paper/start")
def options_paper_start(req: OptionsStartRequest):
    """Start virtual options auto-trading."""
    return options_paper_trader.start(capital=req.capital, underlyings=req.underlyings)


@app.post("/api/options/paper/stop")
def options_paper_stop():
    """Stop virtual options auto-trading."""
    return options_paper_trader.stop()


@app.get("/api/options/paper/status")
def options_paper_status():
    """Get options paper trader status, virtual positions, and logs."""
    return options_paper_trader.status()


# ── Options Swing Trading (Live) ─────────────────────────────────────────


@app.post("/api/options/swing/start")
def options_swing_start(req: OptionsStartRequest):
    """Start live options swing trading (monthly expiry, MARGIN orders)."""
    return options_swing_trader.start(capital=req.capital, underlyings=req.underlyings)


@app.post("/api/options/swing/stop")
def options_swing_stop():
    """Stop live options swing trading."""
    return options_swing_trader.stop()


@app.get("/api/options/swing/status")
def options_swing_status():
    """Get options swing trader status, positions, and logs."""
    return options_swing_trader.status()


# ── Options Swing Paper Trading (Virtual) ────────────────────────────────


@app.post("/api/options/swing-paper/start")
def options_swing_paper_start(req: OptionsStartRequest):
    """Start virtual options swing trading."""
    return options_swing_paper_trader.start(capital=req.capital, underlyings=req.underlyings)


@app.post("/api/options/swing-paper/stop")
def options_swing_paper_stop():
    """Stop virtual options swing trading."""
    return options_swing_paper_trader.stop()


@app.get("/api/options/swing-paper/status")
def options_swing_paper_status():
    """Get options swing paper trader status, virtual positions, and logs."""
    return options_swing_paper_trader.status()


# ═══════════════════════════════════════════════════════════════════════════
#  Futures Trading
# ═══════════════════════════════════════════════════════════════════════════


class FuturesStartRequest(BaseModel):
    strategies: list[StrategySelection]
    capital: float = 200000


class FuturesSwingStartRequest(BaseModel):
    strategies: list[StrategySelection]
    capital: float = 200000
    scan_interval_minutes: int = 240


@app.get("/api/futures/strategies")
def list_futures_strategies():
    """List all 4 futures strategies with timeframes."""
    from strategies.futures_registry import FUTURES_STRATEGY_MAP, FUTURES_STRATEGY_TIMEFRAMES
    result = []
    for key, strategy in FUTURES_STRATEGY_MAP.items():
        info = strategy.info()
        info["id"] = key
        info["timeframes"] = FUTURES_STRATEGY_TIMEFRAMES.get(key, [])
        result.append(info)
    return result


@app.get("/api/futures/oi/{symbol}")
def get_futures_oi(symbol: str):
    """Get OI sentiment analysis for a single F&O stock."""
    from services.futures_oi_analyser import analyse_single_symbol
    result = analyse_single_symbol(symbol.upper())
    if result is None:
        return {"error": f"Could not fetch OI data for {symbol}"}
    return result


@app.get("/api/futures/regime")
def get_futures_regime():
    """Get current market regime and auto-selected futures strategies."""
    from services.futures_regime import detect_futures_regime
    return detect_futures_regime()


class FuturesAutoStartRequest(BaseModel):
    capital: float = 200000


@app.post("/api/futures/auto/start-auto")
def futures_auto_start_regime(req: FuturesAutoStartRequest):
    """Start live futures intraday with auto strategy selection based on market regime."""
    from services.futures_regime import detect_futures_regime
    regime = detect_futures_regime()
    strategies = regime.get("strategies", [])
    if not strategies:
        return {"error": "No strategies selected by regime detector"}
    result = futures_auto_trader.start(strategies=strategies, capital=req.capital)
    if "error" not in result:
        futures_auto_trader._auto_mode = True
    result["regime"] = regime
    return result


@app.post("/api/futures/paper/start-auto")
def futures_paper_start_regime(req: FuturesAutoStartRequest):
    """Start virtual futures intraday with auto strategy selection."""
    from services.futures_regime import detect_futures_regime
    regime = detect_futures_regime()
    strategies = regime.get("strategies", [])
    if not strategies:
        return {"error": "No strategies selected by regime detector"}
    result = futures_paper_trader.start(strategies=strategies, capital=req.capital)
    if "error" not in result:
        futures_paper_trader._auto_mode = True
    result["regime"] = regime
    return result


@app.post("/api/futures/swing/start-auto")
def futures_swing_start_regime(req: FuturesAutoStartRequest):
    """Start live futures swing with auto strategy selection."""
    from services.futures_regime import detect_futures_regime
    regime = detect_futures_regime()
    strategies = regime.get("swing_strategies", [])
    if not strategies:
        return {"error": "No strategies selected by regime detector"}
    result = futures_swing_trader.start(strategies=strategies, capital=req.capital)
    result["regime"] = regime
    return result


@app.post("/api/futures/swing-paper/start-auto")
def futures_swing_paper_start_regime(req: FuturesAutoStartRequest):
    """Start virtual futures swing with auto strategy selection."""
    from services.futures_regime import detect_futures_regime
    regime = detect_futures_regime()
    strategies = regime.get("swing_strategies", [])
    if not strategies:
        return {"error": "No strategies selected by regime detector"}
    result = futures_swing_paper_trader.start(strategies=strategies, capital=req.capital)
    result["regime"] = regime
    return result


# ── Futures Auto-Trading (Intraday Live) ───────────────────────────────


@app.post("/api/futures/auto/start")
def futures_auto_start(req: FuturesStartRequest):
    """Start live futures intraday trading."""
    return futures_auto_trader.start(
        strategies=[s.model_dump() for s in req.strategies],
        capital=req.capital,
    )


@app.post("/api/futures/auto/stop")
def futures_auto_stop():
    return futures_auto_trader.stop()


@app.get("/api/futures/auto/status")
def futures_auto_status():
    return futures_auto_trader.status()


# ── Futures Paper Trading (Intraday Virtual) ───────────────────────────


@app.post("/api/futures/paper/start")
def futures_paper_start(req: FuturesStartRequest):
    """Start virtual futures intraday trading."""
    return futures_paper_trader.start(
        strategies=[s.model_dump() for s in req.strategies],
        capital=req.capital,
    )


@app.post("/api/futures/paper/stop")
def futures_paper_stop():
    return futures_paper_trader.stop()


@app.get("/api/futures/paper/status")
def futures_paper_status():
    return futures_paper_trader.status()


# ── Futures Swing Trading (Live) ───────────────────────────────────────


@app.post("/api/futures/swing/start")
def futures_swing_start(req: FuturesSwingStartRequest):
    """Start live futures swing trading (MARGIN orders, carry over days)."""
    return futures_swing_trader.start(
        strategies=[s.model_dump() for s in req.strategies],
        capital=req.capital,
        scan_interval_minutes=req.scan_interval_minutes,
    )


@app.post("/api/futures/swing/stop")
def futures_swing_stop():
    return futures_swing_trader.stop()


@app.get("/api/futures/swing/status")
def futures_swing_status():
    return futures_swing_trader.status()


# ── Futures Swing Paper Trading (Virtual) ──────────────────────────────


@app.post("/api/futures/swing-paper/start")
def futures_swing_paper_start(req: FuturesSwingStartRequest):
    """Start virtual futures swing trading."""
    return futures_swing_paper_trader.start(
        strategies=[s.model_dump() for s in req.strategies],
        capital=req.capital,
        scan_interval_minutes=req.scan_interval_minutes,
    )


@app.post("/api/futures/swing-paper/stop")
def futures_swing_paper_stop():
    return futures_swing_paper_trader.stop()


@app.get("/api/futures/swing-paper/status")
def futures_swing_paper_status():
    return futures_swing_paper_trader.status()


# ── Futures Force Close (single position) ──────────────────────────────


@app.post("/api/futures/auto/close/{symbol}")
def futures_auto_force_close(symbol: str):
    """Force close a single futures intraday position."""
    # Auto trader doesn't have force_close, use stop + manual
    return {"error": "Use stop endpoint to close all intraday positions. For swing, use /api/futures/swing/close/{symbol}"}


@app.post("/api/futures/swing/close/{symbol}")
def futures_swing_force_close(symbol: str):
    """Force close a single futures swing position."""
    return futures_swing_trader.force_close_trade(symbol.upper())


# ═══════════════════════════════════════════════════════════════════════════
# STRATEGY TRACKER ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/tracking/daily")
def tracking_daily_report(date: str = Query(None, description="YYYY-MM-DD, defaults to today")):
    """Get daily strategy performance report."""
    return get_daily_report(date)


@app.get("/api/tracking/recent")
def tracking_recent_reports(days: int = Query(5, ge=1, le=30)):
    """Get last N daily reports."""
    return get_recent_reports(days)


@app.get("/api/tracking/registry")
def tracking_strategy_registry():
    """Get master strategy parameter registry."""
    return get_strategy_registry()


@app.get("/api/tracking/changelog")
def tracking_changelog():
    """Get parameter change history."""
    return get_changelog()


@app.post("/api/tracking/generate")
def tracking_generate_report():
    """Generate today's daily report from trade data. Call after square-off."""
    return generate_report_from_api()


@app.post("/api/tracking/auto-tune")
def tracking_auto_tune():
    """Run auto-tuner to adjust parameters based on recent performance."""
    from services.auto_tuner import run_auto_tune
    return run_auto_tune()


@app.get("/api/monitor/log")
def monitor_log(lines: int = Query(50, ge=1, le=200)):
    """Get recent market monitor log entries."""
    from services.market_monitor import get_monitor_log
    return {"log": get_monitor_log(lines)}


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    # IMPORTANT: Use app object directly (not string "main:app") to prevent
    # double module import which creates duplicate AutoTrader background threads.
    # reload=False for production — reload=True caused duplicate orders.
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
