"""
Strategy Attribution Tracker — Auto-generates daily performance reports.

Called after square-off to create daily/YYYY-MM-DD.json reports.
Claude references these files before making any strategy changes.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

from utils.time_utils import now_ist

logger = logging.getLogger(__name__)

TRACKING_DIR = Path(__file__).parent.parent / "tracking"
DAILY_DIR = TRACKING_DIR / "daily"
REGISTRY_FILE = TRACKING_DIR / "strategy_registry.json"
CHANGELOG_FILE = TRACKING_DIR / "changelog.json"


def _ensure_dirs():
    DAILY_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_json(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def get_daily_report(date_str: str = None) -> dict:
    """Get a daily report by date string (YYYY-MM-DD). Defaults to today."""
    if not date_str:
        date_str = now_ist().strftime("%Y-%m-%d")
    path = DAILY_DIR / f"{date_str}.json"
    return _load_json(path)


def get_recent_reports(days: int = 5) -> list[dict]:
    """Get the last N daily reports."""
    reports = []
    today = now_ist().date()
    for i in range(days):
        d = today - timedelta(days=i)
        report = get_daily_report(d.strftime("%Y-%m-%d"))
        if report:
            reports.append(report)
    return reports


def get_strategy_registry() -> dict:
    """Get the master strategy parameter registry."""
    return _load_json(REGISTRY_FILE)


def get_changelog() -> dict:
    """Get the parameter changelog."""
    return _load_json(CHANGELOG_FILE)


def log_parameter_change(change: dict):
    """Log a parameter change to changelog.json."""
    changelog = get_changelog()
    if "changes" not in changelog:
        changelog["changes"] = []
    change["timestamp"] = now_ist().isoformat()
    changelog["changes"].append(change)
    _save_json(CHANGELOG_FILE, changelog)
    logger.info(f"[Tracker] Parameter change logged: {change.get('parameter', '?')} in {change.get('file', '?')}")


def generate_daily_report(
    paper_trades: list = None,
    auto_trades: list = None,
    swing_trades: list = None,
    swing_paper_trades: list = None,
    options_paper_trades: list = None,
    options_auto_trades: list = None,
    futures_paper_trades: list = None,
    futures_auto_trades: list = None,
    market_info: dict = None,
    engine_statuses: dict = None,
) -> dict:
    """
    Generate a comprehensive daily report from trade data.
    Called after market close / square-off.
    """
    _ensure_dirs()
    today = now_ist().strftime("%Y-%m-%d")

    # Combine all trade sources
    all_trades = []
    source_map = {
        "paper": paper_trades or [],
        "auto": auto_trades or [],
        "swing": swing_trades or [],
        "swing_paper": swing_paper_trades or [],
        "options_paper": options_paper_trades or [],
        "options_auto": options_auto_trades or [],
        "futures_paper": futures_paper_trades or [],
        "futures_auto": futures_auto_trades or [],
    }

    for source, trades in source_map.items():
        for t in trades:
            t["_source"] = source
            all_trades.append(t)

    # Strategy breakdown
    strategy_perf = defaultdict(lambda: {
        "trades": 0, "wins": 0, "losses": 0, "breakeven": 0,
        "sl_hits": 0, "target_hits": 0, "square_offs": 0, "manual_closes": 0,
        "gross_pnl": 0, "charges": 0, "net_pnl": 0,
        "total_time_seconds": 0, "trades_detail": [],
        "directions": {"BUY": {"count": 0, "pnl": 0}, "SELL": {"count": 0, "pnl": 0}},
    })

    for t in all_trades:
        strat = t.get("strategy", t.get("strategy_id", "unknown"))
        source = t.get("_source", "unknown")
        key = f"{strat}|{source}"
        p = strategy_perf[key]
        pnl = t.get("pnl", 0)
        gross = t.get("gross_pnl", pnl)
        charges = t.get("charges", 0)

        p["trades"] += 1
        p["gross_pnl"] += gross
        p["charges"] += charges
        p["net_pnl"] += pnl
        p["strategy"] = strat
        p["source"] = source
        p["timeframe"] = t.get("timeframe", "")

        if pnl > 0:
            p["wins"] += 1
        elif pnl < 0:
            p["losses"] += 1
        else:
            p["breakeven"] += 1

        reason = t.get("exit_reason", "")
        if reason == "SL_HIT":
            p["sl_hits"] += 1
        elif reason == "TARGET_HIT":
            p["target_hits"] += 1
        elif reason == "SQUARE_OFF":
            p["square_offs"] += 1
        elif reason == "MANUAL_CLOSE":
            p["manual_closes"] += 1

        # Direction tracking
        direction = t.get("signal_type", "UNKNOWN")
        if direction in p["directions"]:
            p["directions"][direction]["count"] += 1
            p["directions"][direction]["pnl"] += pnl

        # Time in trade
        placed = t.get("placed_at", "")
        closed = t.get("closed_at", "")
        if placed and closed:
            try:
                placed_dt = datetime.fromisoformat(placed)
                closed_dt = datetime.fromisoformat(closed)
                p["total_time_seconds"] += (closed_dt - placed_dt).total_seconds()
            except Exception:
                pass

        # Trade detail
        sym = t.get("symbol", t.get("underlying", "?"))
        p["trades_detail"].append({
            "symbol": sym,
            "direction": direction,
            "entry": t.get("entry_price", 0),
            "exit": t.get("exit_price", 0),
            "sl": t.get("stop_loss", 0),
            "target": t.get("target", 0),
            "pnl": pnl,
            "exit_reason": reason,
            "time_placed": placed,
            "time_closed": closed,
        })

    # Compute averages
    for key, p in strategy_perf.items():
        if p["trades"] > 0:
            p["win_rate_pct"] = round(p["wins"] / p["trades"] * 100, 1)
            p["avg_time_minutes"] = round(p["total_time_seconds"] / p["trades"] / 60, 1)
            wins = [d["pnl"] for d in p["trades_detail"] if d["pnl"] > 0]
            losses = [d["pnl"] for d in p["trades_detail"] if d["pnl"] < 0]
            p["avg_win"] = round(sum(wins) / len(wins), 2) if wins else 0
            p["avg_loss"] = round(sum(losses) / len(losses), 2) if losses else 0
            # Expectancy = (win_rate * avg_win) + (loss_rate * avg_loss)
            wr = p["wins"] / p["trades"]
            p["expectancy_per_trade"] = round(wr * p["avg_win"] + (1 - wr) * p["avg_loss"], 2)
        else:
            p["win_rate_pct"] = 0
            p["avg_time_minutes"] = 0
            p["avg_win"] = 0
            p["avg_loss"] = 0
            p["expectancy_per_trade"] = 0

    # Auto-generate insights
    insights = []
    for key, p in strategy_perf.items():
        strat = p.get("strategy", "?")
        source = p.get("source", "?")
        prefix = f"{strat} ({source})"

        if p["sl_hits"] > 0 and p["trades"] > 0:
            sl_rate = p["sl_hits"] / p["trades"] * 100
            if sl_rate > 60:
                insights.append(f"⚠️ {prefix}: {sl_rate:.0f}% SL hit rate — SLs likely too tight or signals counter-trend")

        if p["square_offs"] > 0 and p["trades"] > 0:
            sq_rate = p["square_offs"] / p["trades"] * 100
            if sq_rate > 50:
                insights.append(f"⚠️ {prefix}: {sq_rate:.0f}% square-off rate — trades not reaching target within session")

        if p["win_rate_pct"] > 0 and p["win_rate_pct"] < 35:
            insights.append(f"⚠️ {prefix}: {p['win_rate_pct']}% win rate — consider disabling or restricting")

        if p["win_rate_pct"] >= 60:
            insights.append(f"✅ {prefix}: {p['win_rate_pct']}% win rate — strong performer")

        if p["expectancy_per_trade"] < 0:
            insights.append(f"⚠️ {prefix}: negative expectancy ₹{p['expectancy_per_trade']} per trade")

        # Direction analysis
        for direction in ["BUY", "SELL"]:
            d = p["directions"].get(direction, {})
            if d.get("count", 0) >= 2 and d.get("pnl", 0) < -500:
                insights.append(f"⚠️ {prefix}: {direction} signals lost ₹{abs(d['pnl']):,.0f} today — possible regime mismatch")

    # Best and worst trades
    best_trade = max(all_trades, key=lambda t: t.get("pnl", 0)) if all_trades else {}
    worst_trade = min(all_trades, key=lambda t: t.get("pnl", 0)) if all_trades else {}

    # Source totals
    source_pnl = defaultdict(float)
    for t in all_trades:
        source_pnl[t.get("_source", "unknown")] += t.get("pnl", 0)

    report = {
        "date": today,
        "generated_at": now_ist().isoformat(),
        "market_snapshot": market_info or {},
        "engines_active": engine_statuses or {},
        "strategy_performance": {k: dict(v) for k, v in strategy_perf.items()},
        "source_pnl_summary": dict(source_pnl),
        "total_trades": len(all_trades),
        "total_net_pnl": round(sum(t.get("pnl", 0) for t in all_trades), 2),
        "best_trade": {
            "symbol": best_trade.get("symbol", best_trade.get("underlying", "?")),
            "strategy": best_trade.get("strategy", "?"),
            "pnl": best_trade.get("pnl", 0),
            "source": best_trade.get("_source", "?"),
        } if best_trade else {},
        "worst_trade": {
            "symbol": worst_trade.get("symbol", worst_trade.get("underlying", "?")),
            "strategy": worst_trade.get("strategy", "?"),
            "pnl": worst_trade.get("pnl", 0),
            "source": worst_trade.get("_source", "?"),
        } if worst_trade else {},
        "auto_insights": insights,
        "parameter_changes_today": [],
        "recommendations": [],
    }

    # Auto-compare with previous days and generate recommendations
    recommendations = _generate_recommendations(report)
    report["recommendations"] = recommendations

    # Save
    report_path = DAILY_DIR / f"{today}.json"
    _save_json(report_path, report)
    logger.info(f"[Tracker] Daily report saved: {report_path}")

    return report


def _generate_recommendations(today_report: dict) -> list[dict]:
    """
    Compare today's performance with previous days and generate
    actionable recommendations with data backing.
    """
    recs = []
    today = today_report.get("date", "")
    today_perf = today_report.get("strategy_performance", {})
    today_pnl = today_report.get("total_net_pnl", 0)
    today_trades = today_report.get("total_trades", 0)

    # Load previous reports (last 5 days)
    prev_reports = []
    today_date = now_ist().date()
    for i in range(1, 6):
        d = today_date - timedelta(days=i)
        r = get_daily_report(d.strftime("%Y-%m-%d"))
        if r and r.get("total_trades", 0) > 0:
            prev_reports.append(r)

    if not prev_reports:
        recs.append({
            "type": "info",
            "title": "First day with tracker",
            "detail": "No previous data to compare. Tomorrow's report will show day-over-day trends.",
            "action": "none"
        })
        return recs

    # Aggregate previous days
    prev_total_pnl = sum(r.get("total_net_pnl", 0) for r in prev_reports)
    prev_avg_pnl = prev_total_pnl / len(prev_reports)
    prev_total_trades = sum(r.get("total_trades", 0) for r in prev_reports)
    prev_avg_trades = prev_total_trades / len(prev_reports)

    # 1. Overall P&L trend
    if today_pnl > prev_avg_pnl + 500:
        recs.append({
            "type": "positive",
            "title": "P&L improved significantly",
            "detail": f"Today: ₹{today_pnl:,.0f} vs avg ₹{prev_avg_pnl:,.0f} (prev {len(prev_reports)} days). Current parameters working well.",
            "action": "hold — don't change what's working"
        })
    elif today_pnl < prev_avg_pnl - 500:
        recs.append({
            "type": "negative",
            "title": "P&L declined vs average",
            "detail": f"Today: ₹{today_pnl:,.0f} vs avg ₹{prev_avg_pnl:,.0f}. Check if market regime shifted or if a single bad trade skewed results.",
            "action": "review worst trade — was it a regime mismatch or strategy flaw?"
        })

    # 2. Per-strategy comparison with previous days
    prev_strat_perf = defaultdict(lambda: {"total_pnl": 0, "total_trades": 0, "total_wins": 0, "days": 0})
    for r in prev_reports:
        for key, perf in r.get("strategy_performance", {}).items():
            prev_strat_perf[key]["total_pnl"] += perf.get("net_pnl", 0)
            prev_strat_perf[key]["total_trades"] += perf.get("trades", 0)
            prev_strat_perf[key]["total_wins"] += perf.get("wins", 0)
            prev_strat_perf[key]["days"] += 1

    for key, perf in today_perf.items():
        strat_name = perf.get("strategy", key.split("|")[0])
        source = perf.get("source", key.split("|")[-1] if "|" in key else "")
        today_wr = perf.get("win_rate_pct", 0)
        today_exp = perf.get("expectancy_per_trade", 0)
        today_strat_pnl = perf.get("net_pnl", 0)

        prev = prev_strat_perf.get(key)
        if prev and prev["total_trades"] > 0:
            prev_wr = prev["total_wins"] / prev["total_trades"] * 100
            prev_exp = prev["total_pnl"] / prev["total_trades"]

            # Strategy improved
            if today_exp > prev_exp + 100:
                recs.append({
                    "type": "positive",
                    "title": f"{strat_name} ({source}) improved",
                    "detail": f"Expectancy: ₹{today_exp:,.0f}/trade vs prev avg ₹{prev_exp:,.0f}/trade. Win rate: {today_wr}% vs {prev_wr:.0f}%.",
                    "action": "hold — strategy performing well with current parameters"
                })
            # Strategy degraded
            elif today_exp < prev_exp - 200 and perf.get("trades", 0) >= 2:
                recs.append({
                    "type": "negative",
                    "title": f"{strat_name} ({source}) degraded",
                    "detail": f"Expectancy: ₹{today_exp:,.0f}/trade vs prev avg ₹{prev_exp:,.0f}/trade. Win rate: {today_wr}% vs {prev_wr:.0f}%.",
                    "action": f"investigate — check if regime mismatch or SL issues"
                })

    # 3. SL analysis — are SLs still too tight?
    total_sl_hits = sum(p.get("sl_hits", 0) for p in today_perf.values())
    total_today = sum(p.get("trades", 0) for p in today_perf.values())
    if total_today >= 3:
        sl_rate = total_sl_hits / total_today * 100
        if sl_rate > 50:
            recs.append({
                "type": "warning",
                "title": f"High SL hit rate: {sl_rate:.0f}%",
                "detail": f"{total_sl_hits} of {total_today} trades hit SL. Consider widening ATR multiplier further or checking entry quality.",
                "action": "if SL rate > 50% for 3 consecutive days → increase ATR mult by 0.5"
            })
        elif sl_rate < 20 and total_today >= 5:
            recs.append({
                "type": "positive",
                "title": f"SL hit rate healthy: {sl_rate:.0f}%",
                "detail": f"Only {total_sl_hits} of {total_today} trades hit SL. Current SL width is working.",
                "action": "hold — SL levels appropriate"
            })

    # 4. Square-off analysis — are trades reaching targets?
    total_targets = sum(p.get("target_hits", 0) for p in today_perf.values())
    total_squareoffs = sum(p.get("square_offs", 0) for p in today_perf.values())
    if total_today >= 3:
        target_rate = total_targets / total_today * 100
        squareoff_rate = total_squareoffs / total_today * 100
        if squareoff_rate > 60:
            recs.append({
                "type": "warning",
                "title": f"Too many square-offs: {squareoff_rate:.0f}%",
                "detail": f"{total_squareoffs} of {total_today} trades closed at 3:15 PM without hitting SL or target. Targets may be too far or entry timing too late.",
                "action": "consider tighter targets (1:1.5 R:R) or earlier entry window"
            })
        if target_rate > 40:
            recs.append({
                "type": "positive",
                "title": f"Strong target hit rate: {target_rate:.0f}%",
                "detail": f"{total_targets} of {total_today} trades hit their profit target.",
                "action": "hold — signal quality and targets are well-calibrated"
            })

    # 5. Trade count check
    if today_trades < 3 and today_trades < prev_avg_trades * 0.5:
        recs.append({
            "type": "warning",
            "title": f"Low trade count: {today_trades}",
            "detail": f"Only {today_trades} trades vs prev avg {prev_avg_trades:.0f}. Volume filter or regime detection may be too restrictive.",
            "action": "if < 3 trades for 3 consecutive days → reduce volume threshold from 1.3x to 1.2x"
        })

    # 6. Direction bias check
    buy_pnl = sum(
        p["directions"].get("BUY", {}).get("pnl", 0) for p in today_perf.values()
    )
    sell_pnl = sum(
        p["directions"].get("SELL", {}).get("pnl", 0) for p in today_perf.values()
    )
    if abs(buy_pnl - sell_pnl) > 2000 and today_trades >= 4:
        better = "BUY" if buy_pnl > sell_pnl else "SELL"
        worse = "SELL" if better == "BUY" else "BUY"
        recs.append({
            "type": "info",
            "title": f"{better} signals outperformed {worse}",
            "detail": f"{better}: ₹{max(buy_pnl, sell_pnl):,.0f} | {worse}: ₹{min(buy_pnl, sell_pnl):,.0f}. Regime detection should be filtering direction.",
            "action": "verify regime detection is correctly blocking counter-trend signals"
        })

    if not recs:
        recs.append({
            "type": "info",
            "title": "No significant changes detected",
            "detail": "Performance is within normal range. Continue observing.",
            "action": "hold all parameters — collect more data"
        })

    return recs


def generate_report_from_api():
    """
    Convenience function: fetch all trade data from internal modules
    and generate the daily report. Called from API endpoint.
    """
    from services.trade_logger import get_all_trades

    today_trades = get_all_trades(days=1)

    # Split by source
    paper = [t for t in today_trades if t.get("source") == "paper"]
    auto = [t for t in today_trades if t.get("source") == "auto"]
    swing = [t for t in today_trades if t.get("source") == "swing"]
    swing_paper = [t for t in today_trades if t.get("source") == "swing_paper"]
    options_paper = [t for t in today_trades if t.get("source") == "options_paper"]
    options_auto = [t for t in today_trades if t.get("source") == "options_auto"]
    futures_paper = [t for t in today_trades if t.get("source") == "futures_paper"]
    futures_auto = [t for t in today_trades if t.get("source") == "futures_auto"]

    return generate_daily_report(
        paper_trades=paper,
        auto_trades=auto,
        swing_trades=swing,
        swing_paper_trades=swing_paper,
        options_paper_trades=options_paper,
        options_auto_trades=options_auto,
        futures_paper_trades=futures_paper,
        futures_auto_trades=futures_auto,
    )
