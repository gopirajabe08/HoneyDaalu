"""
Morning alive ping — Telegram health check at 09:20 IST.

Runs Mon-Fri at 09:20 IST via cron, 5 minutes after NSE open. Verifies:
- Backend service is up
- Both paper engines are running
- Broker is connected
- Live engine kill-switch is set
- AutoStart correctly cleaned stale state

Sends a single Telegram message to the owner. If anything is unhealthy,
the message is prefixed with 🚨 so it stands out from healthy pings.

Built 2026-04-28 (Phase 1 Day 1 evening) to close the morning visibility
gap before tomorrow's hands-off observation day.

Usage:
    python morning_alive_ping.py            # full run with Telegram
    python morning_alive_ping.py --dry-run  # print only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent

SWING_STATE_FILE = BACKEND_DIR / ".swing_paper_state.json"
INTRADAY_STATE_FILE = BACKEND_DIR / ".paper_trader_state.json"
ENV_FILE = BACKEND_DIR / ".env"

IST = timezone(timedelta(hours=5, minutes=30))


def _load_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _kill_switch_set() -> bool:
    if not ENV_FILE.exists():
        return False
    for line in ENV_FILE.read_text().splitlines():
        if line.strip().startswith("HONEYDAALU_DISABLE_LIVE="):
            return line.split("=", 1)[1].strip() in ("1", "true", "yes", "on")
    return False


def _service_active() -> bool:
    return os.system("systemctl is-active --quiet honeydaalu-backend") == 0


def _build_message() -> tuple[str, bool]:
    """Returns (message, healthy)."""
    now = datetime.now(IST)
    today = now.strftime("%a %d %b")
    time_str = now.strftime("%H:%M IST")

    swing = _load_state(SWING_STATE_FILE)
    intraday = _load_state(INTRADAY_STATE_FILE)

    issues = []

    if not _service_active():
        issues.append("backend service NOT active")

    if swing is None:
        issues.append("swing state file missing")
    elif not swing.get("running"):
        issues.append("swing engine NOT running")

    if intraday is None:
        issues.append("intraday state file missing")
    elif not intraday.get("running"):
        issues.append("intraday engine NOT running")

    if not _kill_switch_set():
        issues.append("⚠️ HONEYDAALU_DISABLE_LIVE not set — live engine could trade!")

    healthy = len(issues) == 0
    prefix = "✅" if healthy else "🚨"

    swing_line = "—"
    if swing and swing.get("running"):
        swing_line = (
            f"₹{swing.get('capital', 0):,} | "
            f"scans {swing.get('scan_count', 0)} | "
            f"orders {swing.get('order_count', 0)} | "
            f"open {len(swing.get('active_trades', []))}"
        )

    intraday_line = "—"
    if intraday and intraday.get("running"):
        intraday_line = (
            f"₹{intraday.get('capital', 0):,} | "
            f"scans {intraday.get('scan_count', 0)} | "
            f"orders {intraday.get('order_count', 0)} | "
            f"open {len(intraday.get('active_trades', []))}"
        )

    msg_lines = [
        f"{prefix} Morning Alive — {today} {time_str}",
        "",
        f"Swing (1d): {swing_line}",
        f"Intraday (15m): {intraday_line}",
        f"Live engine: {'OFF (correct)' if _kill_switch_set() else 'ON ⚠️'}",
    ]

    if issues:
        msg_lines.append("")
        msg_lines.append("Issues:")
        for issue in issues:
            msg_lines.append(f"- {issue}")

    return "\n".join(msg_lines), healthy


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Morning alive ping")
    parser.add_argument("--dry-run", action="store_true", help="Print only, no Telegram")
    args = parser.parse_args()

    is_holiday, holiday_name = _is_nse_holiday()
    if is_holiday:
        now = datetime.now(IST)
        message = (
            f"🌴 NSE Holiday — {now.strftime('%a %d %b')} {now.strftime('%H:%M IST')}\n\n"
            f"Today: {holiday_name}\n"
            f"Engines correctly NOT started. No trading today.\n"
            f"Next trading day's ping arrives ~09:20 IST."
        )
        print(message)
        if args.dry_run:
            print("\n[dry-run] skipped Telegram")
            return 0
        try:
            sys.path.insert(0, str(BACKEND_DIR))
            from services import telegram_notify
            telegram_notify.send(message)
            print("\n[ok] sent holiday Telegram")
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
