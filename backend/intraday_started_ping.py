"""
Intraday-started ping — Telegram confirmation at 10:30 IST.

Runs Mon-Fri at 10:30 IST via cron. Verifies the intraday engine has
actually performed at least one SCAN since the 10:30 IST scan window
opened. If not, raises a 🚨 alert so owner knows the engine is broken
even though it claims `running: true`.

Built 2026-04-30 (Day 3) to close the gap where morning_alive_ping at
09:20 IST cannot distinguish "intraday waiting for 10:30 window" from
"intraday silently broken".

Usage:
    python intraday_started_ping.py            # full run with Telegram
    python intraday_started_ping.py --dry-run  # print only
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
INTRADAY_STATE_FILE = BACKEND_DIR / ".paper_trader_state.json"
IST = timezone(timedelta(hours=5, minutes=30))
SCAN_WINDOW_OPEN = time(10, 30)


def _load_state() -> dict | None:
    if not INTRADAY_STATE_FILE.exists():
        return None
    try:
        return json.loads(INTRADAY_STATE_FILE.read_text())
    except Exception:
        return None


def _post_window_scan_count(state: dict) -> int:
    count = 0
    for log in state.get("logs", []):
        if log.get("level") != "SCAN":
            continue
        ts_str = log.get("timestamp", "")
        try:
            hour, minute, _ = ts_str.split(":")
            log_time = time(int(hour), int(minute))
        except Exception:
            continue
        if log_time >= SCAN_WINDOW_OPEN:
            count += 1
    return count


def _is_nse_holiday() -> tuple[bool, str]:
    try:
        sys.path.insert(0, str(BACKEND_DIR))
        from config import NSE_HOLIDAYS
        today = datetime.now(IST).strftime("%Y-%m-%d")
        if today in NSE_HOLIDAYS:
            return True, NSE_HOLIDAYS[today]
    except Exception:
        pass
    return False, ""


def _build_message() -> tuple[str, bool]:
    now = datetime.now(IST)
    today = now.strftime("%a %d %b")
    time_str = now.strftime("%H:%M IST")

    state = _load_state()
    if state is None:
        return (
            f"🚨 Intraday Check — {today} {time_str}\n\n"
            f"Intraday state file MISSING. Engine never started.",
            False,
        )

    if not state.get("running"):
        return (
            f"🚨 Intraday Check — {today} {time_str}\n\n"
            f"Intraday engine NOT running. Investigate.",
            False,
        )

    post_window_scans = _post_window_scan_count(state)
    if post_window_scans == 0:
        return (
            f"🚨 Intraday Check — {today} {time_str}\n\n"
            f"Intraday engine running but did NOT scan since 10:30 IST.\n"
            f"Strategies: {', '.join(state.get('strategy_keys', []))}\n"
            f"Last logs: {[l.get('message', '')[:60] for l in state.get('logs', [])[-3:]]}",
            False,
        )

    return (
        f"✅ Intraday Scanning — {today} {time_str}\n\n"
        f"₹{state.get('capital', 0):,} | "
        f"post-10:30 scans: {post_window_scans} | "
        f"orders {state.get('order_count', 0)} | "
        f"open {len(state.get('active_trades', []))}",
        True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Intraday-started ping at 10:30 IST")
    parser.add_argument("--dry-run", action="store_true", help="Print only, no Telegram")
    args = parser.parse_args()

    is_holiday, holiday_name = _is_nse_holiday()
    if is_holiday:
        now = datetime.now(IST)
        message = (
            f"🌴 NSE Holiday — {now.strftime('%a %d %b')} {now.strftime('%H:%M IST')}\n\n"
            f"Today: {holiday_name}\n"
            f"Skipping intraday check (no trading today)."
        )
        print(message)
        if args.dry_run:
            print("\n[dry-run] skipped Telegram")
            return 0
        try:
            sys.path.insert(0, str(BACKEND_DIR))
            from services import telegram_notify
            telegram_notify.send(message)
        except Exception as e:
            print(f"\n[warn] Telegram send failed: {e}", file=sys.stderr)
        return 0

    message, healthy = _build_message()
    print(message)

    if args.dry_run:
        print("\n[dry-run] skipped Telegram")
        return 0

    try:
        sys.path.insert(0, str(BACKEND_DIR))
        from services import telegram_notify
        telegram_notify.send(message)
        print("\n[ok] sent Telegram")
    except Exception as e:
        print(f"\n[warn] Telegram send failed: {e}", file=sys.stderr)
        return 1

    return 0 if healthy else 2


if __name__ == "__main__":
    sys.exit(main())
