"""
Regime-filter report generator. Auto-runs on EC2 via cron:
  - Every Friday 16:00 IST → writes reports/weekly_YYYY-Www.md
  - On Day 30 (2026-06-04 approx) → writes reports/day30_memo.md
  - On Day 60 (2026-07-16 approx) → writes reports/day60_memo.md

Data sources:
  - backend/.trade_history.json         (all paper+live trades)
  - backend/tracking/regime_decisions_*.jsonl  (per-day decision logs)
  - backend/tracking/regime_safety_state.json  (safety breach counter)

Writes the report to disk + sends a Telegram summary (bypasses paper-mode
silence since these are genuine scheduled status updates). The file stays
untracked in reports/ — surviving deploy.sh's `git reset --hard` because
untracked files are not touched. Earlier versions also tried git-push from
EC2; that failed silently (no GitHub auth on the box) and the local commit
got wiped on next deploy, losing every Friday's report. Removed.

Usage (manual / testing):
  python regime_report_generator.py                  # auto-decide by calendar
  python regime_report_generator.py --type weekly
  python regime_report_generator.py --type day30 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.time_utils import now_ist  # noqa: E402

PHASE3_START = date(2026, 4, 23)     # Day 1 of the 60-day soak

ROOT = Path(__file__).resolve().parent.parent
BACKEND = Path(__file__).resolve().parent
TRADE_HISTORY = BACKEND / ".trade_history.json"
TRACKING_DIR = BACKEND / "tracking"
REPORTS_DIR = ROOT / "reports"

# Success criteria (spec day 60)
TARGET_WIN_RATE_PCT = 55.0
TARGET_MAX_DAILY_DD = 5_000.0
TARGET_BLOCK_RATE_PCT = 20.0
TARGET_MIN_ALLOWED_DAYS = 15


def count_trading_days(start: date, end: date) -> int:
    n = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def phase3_day_number(today: date | None = None) -> int:
    today = today or now_ist().date()
    if today < PHASE3_START:
        return 0
    return count_trading_days(PHASE3_START, today)


def load_trade_history() -> list[dict]:
    if not TRADE_HISTORY.exists():
        return []
    try:
        with open(TRADE_HISTORY) as f:
            return json.load(f)
    except Exception:
        return []


def load_decisions(date_range: tuple[date, date]) -> list[dict]:
    start, end = date_range
    out: list[dict] = []
    if not TRACKING_DIR.exists():
        return out
    for f in sorted(TRACKING_DIR.glob("regime_decisions_*.jsonl")):
        stem = f.stem.replace("regime_decisions_", "")
        try:
            d = date.fromisoformat(stem)
        except ValueError:
            continue
        if not (start <= d <= end):
            continue
        try:
            with open(f) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        rec.setdefault("_date", d.isoformat())
                        out.append(rec)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue
    return out


def load_safety_state() -> dict:
    path = TRACKING_DIR / "regime_safety_state.json"
    if not path.exists():
        return {"tripped": False, "consecutive_breaches": 0, "history": []}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {"tripped": False, "consecutive_breaches": 0, "history": []}


@dataclass
class DayStats:
    trading_date: date
    scan_allowed: bool
    block_reason: str
    trades: int
    wins: int
    losses: int
    gross_pnl: float
    net_pnl: float
    symbols: list[str]


def aggregate_by_day(decisions: list[dict], trades: list[dict], date_range: tuple[date, date]) -> list[DayStats]:
    start, end = date_range
    result: list[DayStats] = []

    # Decisions keyed by date
    by_date_decisions: dict[str, list[dict]] = {}
    for d in decisions:
        by_date_decisions.setdefault(d.get("_date", ""), []).append(d)

    # Trades keyed by date (paper source, within range)
    by_date_trades: dict[str, list[dict]] = {}
    for t in trades:
        if t.get("source") != "paper":
            continue
        td = t.get("date", "")
        if not td:
            continue
        try:
            d_obj = date.fromisoformat(td)
        except ValueError:
            continue
        if start <= d_obj <= end:
            by_date_trades.setdefault(td, []).append(t)

    cur = start
    while cur <= end:
        if cur.weekday() >= 5:
            cur += timedelta(days=1)
            continue
        iso = cur.isoformat()
        day_dec = by_date_decisions.get(iso, [])
        scan_blocked = any(d.get("event") == "scan_blocked" for d in day_dec)
        scan_allowed = any(d.get("event") == "scan_allowed" for d in day_dec) and not scan_blocked
        block_reason = ""
        if scan_blocked:
            block_evt = next((d for d in day_dec if d.get("event") == "scan_blocked"), {})
            block_reason = block_evt.get("reason", "")

        day_tr = by_date_trades.get(iso, [])
        wins = sum(1 for t in day_tr if t.get("pnl", 0) > 0)
        losses = sum(1 for t in day_tr if t.get("pnl", 0) <= 0)
        gross = sum(t.get("pnl", 0) for t in day_tr)
        symbols = sorted({t.get("symbol", "") for t in day_tr if t.get("symbol")})

        result.append(DayStats(
            trading_date=cur,
            scan_allowed=scan_allowed,
            block_reason=block_reason,
            trades=len(day_tr),
            wins=wins,
            losses=losses,
            gross_pnl=round(gross, 2),
            net_pnl=round(gross, 2),  # trade_logger pnl is already net of charges
            symbols=symbols,
        ))
        cur += timedelta(days=1)
    return result


def render_report(report_type: str, date_range: tuple[date, date],
                  day_stats: list[DayStats], safety_state: dict) -> tuple[str, str]:
    start, end = date_range
    today = now_ist().date()
    day_num = phase3_day_number(today)

    # Aggregates
    tot_trading_days = len([d for d in day_stats])  # weekdays in range
    allowed_days = sum(1 for d in day_stats if d.scan_allowed)
    blocked_days = sum(1 for d in day_stats if not d.scan_allowed and d.block_reason)
    no_data_days = sum(1 for d in day_stats if not d.scan_allowed and not d.block_reason)
    total_trades = sum(d.trades for d in day_stats)
    total_wins = sum(d.wins for d in day_stats)
    total_losses = sum(d.losses for d in day_stats)
    win_rate = (total_wins / total_trades * 100) if total_trades else 0.0
    total_net = sum(d.net_pnl for d in day_stats)
    max_daily_dd = min((d.net_pnl for d in day_stats), default=0.0)
    block_rate = (blocked_days / max(1, allowed_days + blocked_days)) * 100 if (allowed_days + blocked_days) else 0.0

    # Top symbols
    sym_pnl: Counter = Counter()
    sym_trades: Counter = Counter()
    for d in day_stats:
        for s in d.symbols:
            # We don't have per-symbol pnl breakdown here; only counts
            sym_trades[s] += 1

    title_map = {
        "weekly": f"Weekly Report — week ending {end.isoformat()}",
        "day30": "Day 30 Checkpoint Memo",
        "day60": "Day 60 Final Memo (go/no-go)",
    }
    filename_map = {
        "weekly": f"weekly_{end.isocalendar()[0]}-W{end.isocalendar()[1]:02d}.md",
        "day30": "day30_memo.md",
        "day60": "day60_memo.md",
    }
    filename = filename_map.get(report_type, f"report_{today.isoformat()}.md")

    lines: list[str] = []
    lines.append(f"# {title_map.get(report_type, report_type)}")
    lines.append("")
    lines.append(f"_Auto-generated {today.isoformat()} — Phase 3 day {day_num} of 60._")
    lines.append("")
    lines.append(f"**Window covered:** {start.isoformat()} → {end.isoformat()} "
                 f"({tot_trading_days} weekdays)")
    lines.append("")

    lines.append("## Regime filter decisions")
    lines.append("")
    lines.append(f"- Allowed days: **{allowed_days}**")
    lines.append(f"- Blocked days: **{blocked_days}**")
    if no_data_days:
        lines.append(f"- No-data days (weekends/holidays/logs missing): {no_data_days}")
    lines.append(f"- Block rate: **{block_rate:.1f}%** (target >20%)")
    lines.append("")

    lines.append("## Paper trade results")
    lines.append("")
    lines.append(f"- Trades placed: **{total_trades}** (wins {total_wins} / losses {total_losses})")
    lines.append(f"- Win rate: **{win_rate:.1f}%** (target >55%)")
    lines.append(f"- Net P&L: **₹{total_net:+,.0f}**")
    lines.append(f"- Worst single day: **₹{max_daily_dd:+,.0f}** (safety trip threshold: ₹-10,000)")
    lines.append("")

    lines.append("## Safety state")
    lines.append("")
    lines.append(f"- Tripped: **{'YES' if safety_state.get('tripped') else 'no'}**")
    lines.append(f"- Consecutive breach counter: {safety_state.get('consecutive_breaches', 0)}")
    lines.append(f"- Last recorded day: {safety_state.get('last_date', '—')} "
                 f"(P&L ₹{safety_state.get('last_pnl', 0):+,.0f})")
    lines.append("")

    # Day-by-day
    lines.append("## Day-by-day")
    lines.append("")
    lines.append("| Date | Scan | Trades | W/L | Net P&L | Symbols / Reason |")
    lines.append("|---|---|---|---|---|---|")
    for d in day_stats:
        if d.scan_allowed:
            scan = "🟢 allow"
            detail = ", ".join(d.symbols) if d.symbols else "(no entries)"
        elif d.block_reason:
            scan = "🔴 block"
            detail = d.block_reason
        else:
            scan = "— no data"
            detail = ""
        wl = f"{d.wins}/{d.losses}" if d.trades else "—"
        lines.append(f"| {d.trading_date} | {scan} | {d.trades} | {wl} | "
                     f"₹{d.net_pnl:+,.0f} | {detail} |")
    lines.append("")

    # Success criteria verdict (day30 + day60 only)
    if report_type in ("day30", "day60"):
        lines.append("## Success criteria")
        lines.append("")
        lines.append("| Criterion | Target | Actual | Verdict |")
        lines.append("|---|---|---|---|")
        lines.append(f"| Win rate | >{TARGET_WIN_RATE_PCT:.0f}% | {win_rate:.1f}% | "
                     f"{'✅' if win_rate > TARGET_WIN_RATE_PCT else '❌'} |")
        lines.append(f"| Net P&L | positive | ₹{total_net:+,.0f} | "
                     f"{'✅' if total_net > 0 else '❌'} |")
        lines.append(f"| Max single-day DD | < ₹{TARGET_MAX_DAILY_DD:,.0f} | ₹{max_daily_dd:+,.0f} | "
                     f"{'✅' if max_daily_dd > -TARGET_MAX_DAILY_DD else '❌'} |")
        lines.append(f"| Block rate | >{TARGET_BLOCK_RATE_PCT:.0f}% | {block_rate:.1f}% | "
                     f"{'✅' if block_rate > TARGET_BLOCK_RATE_PCT else '❌'} |")
        if report_type == "day60":
            lines.append(f"| Allowed days | ≥ {TARGET_MIN_ALLOWED_DAYS} | {allowed_days} | "
                         f"{'✅' if allowed_days >= TARGET_MIN_ALLOWED_DAYS else '❌'} |")
        lines.append("")

        all_pass = (
            win_rate > TARGET_WIN_RATE_PCT
            and total_net > 0
            and max_daily_dd > -TARGET_MAX_DAILY_DD
            and block_rate > TARGET_BLOCK_RATE_PCT
            and (report_type != "day60" or allowed_days >= TARGET_MIN_ALLOWED_DAYS)
        )
        if report_type == "day60":
            lines.append(f"**Recommendation:** {'PROPOSE GOING LIVE (ASK OWNER)' if all_pass else 'KILL FILTER — criteria not met'}")
        else:
            lines.append(f"**Halfway read:** {'on track' if all_pass else 'off track — review before day 60'}")
        lines.append("")

    # Telegram summary (short-form)
    telegram = (
        f"📊 <b>{title_map.get(report_type, report_type)}</b>\n"
        f"Phase 3 day {day_num}/60\n"
        f"Allowed {allowed_days} / Blocked {blocked_days}\n"
        f"Trades: {total_trades} | W/L: {total_wins}/{total_losses} | WR: {win_rate:.1f}%\n"
        f"Net P&L: ₹{total_net:+,.0f}\n"
        f"Worst day: ₹{max_daily_dd:+,.0f}\n"
        f"Safety: {'🚨 TRIPPED' if safety_state.get('tripped') else '✅ clean'}"
    )

    return "\n".join(lines), telegram


def send_telegram(msg: str) -> bool:
    try:
        from services import telegram_notify
        telegram_notify.send(msg)
        return True
    except Exception as e:
        print(f"[report] telegram send failed: {e}", flush=True)
        return False


def decide_report_type(today: date | None = None) -> str | None:
    today = today or now_ist().date()
    d = phase3_day_number(today)
    if d <= 0:
        return None
    if d == 30:
        return "day30"
    if d == 60:
        return "day60"
    # Weekly: Friday only
    if today.weekday() == 4:
        return "weekly"
    return None


def build_date_range(report_type: str, today: date | None = None) -> tuple[date, date]:
    today = today or now_ist().date()
    if report_type == "weekly":
        # Monday of this week → today (Friday)
        monday = today - timedelta(days=today.weekday())
        return (max(monday, PHASE3_START), today)
    if report_type == "day30":
        return (PHASE3_START, today)
    if report_type == "day60":
        return (PHASE3_START, today)
    return (PHASE3_START, today)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", choices=("weekly", "day30", "day60", "auto"), default="auto")
    ap.add_argument("--dry-run", action="store_true", help="Print report; skip file write + telegram")
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()

    report_type = args.type
    if report_type == "auto":
        rt = decide_report_type()
        if rt is None:
            print(f"[report] no scheduled report for today ({now_ist().date()}) — exit", flush=True)
            return 0
        report_type = rt

    date_range = build_date_range(report_type)
    decisions = load_decisions(date_range)
    trades = load_trade_history()
    safety = load_safety_state()
    day_stats = aggregate_by_day(decisions, trades, date_range)

    report, telegram_msg = render_report(report_type, date_range, day_stats, safety)

    REPORTS_DIR.mkdir(exist_ok=True)
    filename_map = {
        "weekly": f"weekly_{date_range[1].isocalendar()[0]}-W{date_range[1].isocalendar()[1]:02d}.md",
        "day30": "day30_memo.md",
        "day60": "day60_memo.md",
    }
    if args.dry_run:
        print("--- REPORT ---")
        print(report)
        print("--- TELEGRAM ---")
        print(telegram_msg)
        return 0

    out = REPORTS_DIR / filename_map[report_type]
    out.write_text(report)
    print(f"[report] wrote {out}", flush=True)

    if not args.no_telegram:
        send_telegram(telegram_msg)

    return 0


if __name__ == "__main__":
    sys.exit(main())
