"""
Paper engines EOD report generator.

Runs at 15:45 IST via cron Mon-Fri during stabilization phase. Reads both
paper engine state files, computes the day's summary (P&L, trades, win rate,
per-strategy attribution), writes a daily markdown report to reports/, and
sends a Telegram summary to the owner.

Built 2026-04-28 (Phase 1 Day 1) to close the EOD measurement gap.
The existing services/eod_analyser.py is live-focused (broker_client +
auto_trader); paper engines need their own report path.

Usage:
    python paper_eod_report.py            # full run: report + Telegram
    python paper_eod_report.py --dry-run  # print report, skip Telegram + file
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
REPORTS_DIR = REPO_ROOT / "reports"

SWING_STATE_FILE = BACKEND_DIR / ".swing_paper_state.json"
INTRADAY_STATE_FILE = BACKEND_DIR / ".paper_trader_state.json"

IST = timezone(timedelta(hours=5, minutes=30))


def _load_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as e:
        print(f"[WARN] failed to parse {path.name}: {e}", file=sys.stderr)
        return None


def _summarize_engine(state: dict | None, label: str) -> dict:
    if state is None:
        return {"label": label, "running": False, "missing": True}

    history = state.get("trade_history", [])
    active = state.get("active_trades", [])

    closed_today = [t for t in history if t.get("status") == "CLOSED"]
    wins = [t for t in closed_today if t.get("pnl", 0) > 0]
    losses = [t for t in closed_today if t.get("pnl", 0) < 0]
    total_pnl = sum(t.get("pnl", 0) for t in closed_today)

    per_strategy = defaultdict(lambda: {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0})
    for t in closed_today:
        key = t.get("strategy", "unknown")
        per_strategy[key]["trades"] += 1
        per_strategy[key]["pnl"] += t.get("pnl", 0)
        if t.get("pnl", 0) > 0:
            per_strategy[key]["wins"] += 1
        elif t.get("pnl", 0) < 0:
            per_strategy[key]["losses"] += 1

    win_rate = (len(wins) / len(closed_today) * 100) if closed_today else 0

    return {
        "label": label,
        "running": state.get("running", False),
        "missing": False,
        "capital": state.get("capital", 0),
        "scan_count": state.get("scan_count", 0),
        "order_count": state.get("order_count", 0),
        "active_count": len(active),
        "active_trades": active,
        "closed_count": len(closed_today),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "per_strategy": dict(per_strategy),
    }


def _format_engine_section(s: dict) -> str:
    if s["missing"]:
        return f"### {s['label']}\n_State file missing — engine likely never started today._\n"

    has_activity = s["scan_count"] > 0 or s["order_count"] > 0 or s["closed_count"] > 0 or s["active_count"] > 0
    if not s["running"] and not has_activity:
        return f"### {s['label']}\n_Not running, no activity today._\n"

    status_suffix = "" if s["running"] else " _(squared off, end-of-day)_"
    pnl_emoji = "+" if s["total_pnl"] >= 0 else ""
    lines = [
        f"### {s['label']}{status_suffix}",
        f"- Capital: ₹{s['capital']:,}",
        f"- Scans: {s['scan_count']} | Orders: {s['order_count']}",
        f"- Open positions: {s['active_count']}",
        f"- Closed today: {s['closed_count']} ({s['wins']} wins / {s['losses']} losses, win rate {s['win_rate']:.0f}%)",
        f"- **Day P&L: {pnl_emoji}₹{s['total_pnl']:,.2f}**",
    ]

    if s["per_strategy"]:
        lines.append("")
        lines.append("**Per-strategy:**")
        for key, m in s["per_strategy"].items():
            sign = "+" if m["pnl"] >= 0 else ""
            lines.append(f"- `{key}`: {m['trades']} trades, {sign}₹{m['pnl']:,.2f} ({m['wins']}W/{m['losses']}L)")

    if s["active_trades"]:
        lines.append("")
        lines.append("**Open positions (carry):**")
        for t in s["active_trades"]:
            sym = t.get("symbol", "?")
            qty = t.get("quantity", t.get("qty", "?"))
            entry = t.get("entry_price", t.get("entry", "?"))
            lines.append(f"- {sym} qty={qty} entry=₹{entry}")

    return "\n".join(lines) + "\n"


def _build_report(swing: dict, intraday: dict, today: date) -> tuple[str, str]:
    """Returns (markdown_report, telegram_summary)."""

    combined_pnl = (swing.get("total_pnl") or 0) + (intraday.get("total_pnl") or 0)
    combined_trades = (swing.get("closed_count") or 0) + (intraday.get("closed_count") or 0)
    combined_wins = (swing.get("wins") or 0) + (intraday.get("wins") or 0)
    combined_active = (swing.get("active_count") or 0) + (intraday.get("active_count") or 0)
    combined_win_rate = (combined_wins / combined_trades * 100) if combined_trades else 0
    pnl_emoji = "🟢" if combined_pnl > 0 else ("🔴" if combined_pnl < 0 else "⚪")

    md = f"""# Paper EOD Report — {today.strftime('%A, %d %B %Y')}

**Phase 1 Day** _(20-day stabilization)_
**Generated:** {datetime.now(IST).strftime('%H:%M:%S IST')}

## Combined
- **Day P&L: ₹{combined_pnl:,.2f}** {pnl_emoji}
- Total trades: {combined_trades} ({combined_wins}W, win rate {combined_win_rate:.0f}%)
- Open carry positions: {combined_active}

{_format_engine_section(swing)}
{_format_engine_section(intraday)}

---
_Auto-generated by paper_eod_report.py. Phase 1 (paper-only). No live capital at risk._
"""

    sign = "+" if combined_pnl >= 0 else ""
    tg = (
        f"📊 Paper EOD — {today.strftime('%a %d %b')}\n\n"
        f"{pnl_emoji} Day P&L: {sign}₹{combined_pnl:,.2f}\n"
        f"Trades: {combined_trades} ({combined_wins}W / {combined_trades - combined_wins}L) | Win {combined_win_rate:.0f}%\n"
        f"Carry: {combined_active}\n\n"
        f"Swing: ₹{swing.get('total_pnl', 0):,.0f} ({swing.get('closed_count', 0)} trades, scans {swing.get('scan_count', 0)})\n"
        f"Intraday: ₹{intraday.get('total_pnl', 0):,.0f} ({intraday.get('closed_count', 0)} trades, scans {intraday.get('scan_count', 0)})"
    )

    return md, tg


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
    parser = argparse.ArgumentParser(description="Paper engines EOD report")
    parser.add_argument("--dry-run", action="store_true", help="Print only, no Telegram or file")
    args = parser.parse_args()

    is_holiday, holiday_name = _is_nse_holiday()
    if is_holiday:
        now = datetime.now(IST)
        message = (
            f"🌴 NSE Holiday — {now.strftime('%a %d %b')}\n\n"
            f"Today: {holiday_name}\n"
            f"No trading today. EOD report skipped.\n"
            f"Next trading day's EOD arrives ~15:45 IST."
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

    today = datetime.now(IST).date()

    swing_state = _load_state(SWING_STATE_FILE)
    intraday_state = _load_state(INTRADAY_STATE_FILE)

    swing = _summarize_engine(swing_state, "Equity Swing Paper (1d)")
    intraday = _summarize_engine(intraday_state, "Equity Intraday Paper (15m)")

    md, tg = _build_report(swing, intraday, today)

    print(md)
    print("---TELEGRAM---")
    print(tg)

    if args.dry_run:
        print("\n[dry-run] skipped Telegram + file write")
        return 0

    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"paper_eod_{today.isoformat()}.md"
    report_path.write_text(md)
    print(f"\n[ok] wrote {report_path}")

    try:
        sys.path.insert(0, str(BACKEND_DIR))
        from services import telegram_notify
        telegram_notify.send(tg)
        print("[ok] sent Telegram summary")
    except Exception as e:
        print(f"[warn] Telegram send failed: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
