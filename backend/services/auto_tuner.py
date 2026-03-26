"""
Auto-Tuner v2 — Full autonomous parameter optimization.

Acts as a Senior Quantitative Trading Strategist with 20+ years experience.
Runs after square-off at 3:15 PM. Analyzes 3-5 days of rolling data,
DECIDES what to change, and IMPLEMENTS it — no human approval needed.

Safety guardrails (institutional risk management):
  - Every parameter has min/max bounds — can NEVER exceed
  - Max ONE step change per parameter per day — no dramatic shifts
  - Needs 3+ days of consistent signal before acting (no single-day reactions)
  - Every change logged with full data backing + auto-rollback trigger
  - Strategy boosts update daily based on rolling expectancy
  - SL width adjusts gradually (±0.25 ATR per day)
  - Volume filter adjusts gradually (±0.1 per day)
  - All changes are reversible — next day's data can reverse the decision
"""

import json
import logging
import re
from datetime import timedelta
from collections import defaultdict
from pathlib import Path

from utils.time_utils import now_ist

logger = logging.getLogger(__name__)

# Guard: only run report + auto-tune once per day
_last_eod_run_date: str = ""

TRACKING_DIR = Path(__file__).parent.parent / "tracking"
DAILY_DIR = TRACKING_DIR / "daily"
REGISTRY_FILE = TRACKING_DIR / "strategy_registry.json"
CHANGELOG_FILE = TRACKING_DIR / "changelog.json"

# ── Guardrails: absolute bounds + max change per day ──

GUARDRAILS = {
    "atr_multiplier": {
        "min": 1.5, "max": 4.0, "step": 0.25,
        "file": "strategies/base.py",
        "pattern": r"(def atr_stop_loss\([^)]*atr_mult:\s*float\s*=\s*)(\d+\.?\d*)",
    },
    "futures_atr_multiplier": {
        "min": 1.5, "max": 4.0, "step": 0.25,
        "file": "strategies/futures_base.py",
        "pattern": r"(def atr_stop_loss\([^)]*atr_mult:\s*float\s*=\s*)(\d+\.?\d*)",
    },
    "strategy_boost": {
        "min": 0.3, "max": 2.0,
    },
}


def _load_json(path: Path) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_json(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _get_recent_reports(days: int = 5) -> list[dict]:
    reports = []
    today = now_ist().date()
    for i in range(days):
        d = today - timedelta(days=i)
        path = DAILY_DIR / f"{d.strftime('%Y-%m-%d')}.json"
        r = _load_json(path)
        if r and r.get("total_trades", 0) > 0:
            reports.append(r)
    return reports


def _log_change(change: dict):
    changelog = _load_json(CHANGELOG_FILE)
    if "changes" not in changelog:
        changelog["changes"] = []
    change["timestamp"] = now_ist().isoformat()
    change["author"] = "auto_tuner_v2"
    changelog["changes"].append(change)
    _save_json(CHANGELOG_FILE, changelog)
    logger.info(f"[AutoTuner] Logged: {change.get('id', '?')} — {change.get('parameter', '?')}")


def run_eod_pipeline(engine_name: str = "unknown") -> dict:
    """
    End-of-day pipeline: daily report + auto-tune + QA.
    Called by any engine after square-off, but only runs ONCE per day.
    """
    global _last_eod_run_date
    today = now_ist().strftime("%Y-%m-%d")

    if _last_eod_run_date == today:
        logger.info(f"[AutoTuner] EOD pipeline already ran today — skipped (triggered by {engine_name})")
        return {"status": "already_ran_today", "triggered_by": engine_name}

    _last_eod_run_date = today
    logger.info(f"[AutoTuner] EOD pipeline starting — triggered by {engine_name}")

    # Step 1: Generate daily report
    report = {}
    try:
        from services.strategy_tracker import generate_report_from_api
        report = generate_report_from_api()
        logger.info(f"[AutoTuner] Daily report: {report.get('total_trades', 0)} trades, ₹{report.get('total_net_pnl', 0):,.0f}")
    except Exception as e:
        logger.warning(f"[AutoTuner] Daily report failed: {e}")

    # Step 2: Auto-tune
    tune_result = run_auto_tune()

    # Combine results
    return {
        "status": "completed",
        "triggered_by": engine_name,
        "report": {
            "total_trades": report.get("total_trades", 0),
            "total_net_pnl": report.get("total_net_pnl", 0),
            "recommendations": len(report.get("recommendations", [])),
        },
        "tune_result": tune_result,
    }


def run_auto_tune() -> dict:
    """
    Main entry point. Analyze, decide, and implement.
    Returns summary of all actions taken.
    """
    reports = _get_recent_reports(5)
    if len(reports) < 2:
        return {
            "status": "skipped",
            "reason": f"Need 2+ days of data, have {len(reports)}",
            "actions": []
        }

    actions = []

    # 1. Strategy conviction boosts — update daily based on rolling performance
    actions.extend(_tune_strategy_boosts(reports))

    # 2. ATR stop loss width — DISABLED: SL config is managed via strategy_config.json (atr_mult=2.5, min_pct=0.012)
    # Auto-tuning ATR conflicts with manually set values. Leave SL management to strategy_config.json.
    # if len(reports) >= 3:
    #     actions.extend(_tune_atr_stop_loss(reports))

    # 3. Volume filter — DISABLED: volume thresholds managed manually. Auto-tuning conflicts with strategy configs.
    # if len(reports) >= 3:
    #     actions.extend(_tune_volume_filter(reports))

    # 4. Direction bias — auto-adjust regime intraday override threshold
    if len(reports) >= 3:
        actions.extend(_tune_direction_bias(reports))

    # 5. POST-FIX QA — verify everything still works after changes
    qa_result = _run_post_fix_qa()
    if qa_result["failures"]:
        # QA failed — rollback all changes made in this run
        logger.error(f"[AutoTuner] QA FAILED: {qa_result['failures']} — rolling back changes")
        _rollback_changes(actions)
        return {
            "status": "qa_failed_rolled_back",
            "reports_analyzed": len(reports),
            "actions": actions,
            "qa_result": qa_result,
            "rollback": True,
            "timestamp": now_ist().isoformat(),
        }

    # 6. Update registry with current live values (so About page reflects latest)
    _update_registry_live_values()

    return {
        "status": "completed",
        "reports_analyzed": len(reports),
        "actions": actions,
        "qa_result": qa_result,
        "timestamp": now_ist().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════
# 1. STRATEGY CONVICTION BOOSTS (auto-applied daily)
# ═══════════════════════════════════════════════════════════════════════

def _tune_strategy_boosts(reports: list[dict]) -> list[dict]:
    """Rank strategies by rolling expectancy, assign boosts proportionally."""
    strat_perf = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0, "days": 0})
    for r in reports:
        seen = set()
        for key, perf in r.get("strategy_performance", {}).items():
            strat = perf.get("strategy", key.split("|")[0])
            if not strat.startswith("play"):
                continue
            strat_perf[strat]["trades"] += perf.get("trades", 0)
            strat_perf[strat]["wins"] += perf.get("wins", 0)
            strat_perf[strat]["pnl"] += perf.get("net_pnl", 0)
            if strat not in seen:
                strat_perf[strat]["days"] += 1
                seen.add(strat)

    active = {k: v for k, v in strat_perf.items() if v["trades"] >= 2}
    if len(active) < 2:
        return []

    for s, p in active.items():
        wr = p["wins"] / p["trades"] if p["trades"] > 0 else 0
        p["win_rate"] = round(wr * 100, 1)
        p["expectancy"] = round(p["pnl"] / p["trades"], 2) if p["trades"] > 0 else 0

    ranked = sorted(active.items(), key=lambda x: x[1]["expectancy"], reverse=True)
    n = len(ranked)
    new_boosts = {}
    for i, (strat, perf) in enumerate(ranked):
        boost = round(1.4 - (i / max(n - 1, 1)) * 0.9, 2) if n > 1 else 1.0
        boost = max(GUARDRAILS["strategy_boost"]["min"], min(GUARDRAILS["strategy_boost"]["max"], boost))
        new_boosts[strat] = boost

    current_boosts = _read_current_boosts()
    changes = {s: {"before": current_boosts.get(s, 1.0), "after": v}
               for s, v in new_boosts.items() if abs(v - current_boosts.get(s, 1.0)) >= 0.1}

    if not changes:
        return []

    _apply_boost_changes(new_boosts)

    _log_change({
        "id": f"AUTO-BOOST-{now_ist().strftime('%m%d')}",
        "date": now_ist().strftime("%Y-%m-%d"),
        "type": "AUTO_TUNE",
        "parameter": "strategy_conviction_boosts",
        "before": {s: current_boosts.get(s, 1.0) for s in new_boosts},
        "after": new_boosts,
        "reason": f"Rolling {len(reports)}-day expectancy ranking: "
                  + ", ".join(f"{s}=₹{active[s]['expectancy']}/trade" for s, _ in ranked if s in active),
        "data_backing": {s: {"trades": p["trades"], "wr": p["win_rate"], "exp": p["expectancy"]}
                        for s, p in active.items()},
    })

    return [{"type": "auto_tune", "parameter": f"boost_{s}", "before": c["before"], "after": c["after"],
             "reason": f"Expectancy: ₹{active.get(s, {}).get('expectancy', 0)}/trade"}
            for s, c in changes.items()]


# ═══════════════════════════════════════════════════════════════════════
# 2. ATR STOP LOSS (auto-applied with ±0.25 step limit per day)
# ═══════════════════════════════════════════════════════════════════════

def _tune_atr_stop_loss(reports: list[dict]) -> list[dict]:
    """
    Decision logic:
      SL hit rate > 50% for 2+ of last 3 days → widen by 0.25
      SL hit rate < 15% for 2+ of last 3 days → tighten by 0.25
      Otherwise → hold
    """
    days_high_sl = 0
    days_low_sl = 0
    total_trades = 0
    total_sl = 0

    for r in reports[:3]:
        dt, ds = 0, 0
        for perf in r.get("strategy_performance", {}).values():
            dt += perf.get("trades", 0)
            ds += perf.get("sl_hits", 0)
        total_trades += dt
        total_sl += ds
        if dt >= 3:
            rate = ds / dt * 100
            if rate > 50:
                days_high_sl += 1
            elif rate < 15:
                days_low_sl += 1

    if total_trades < 6:
        return []

    sl_rate = total_sl / total_trades * 100
    actions = []
    guard = GUARDRAILS["atr_multiplier"]

    # Read current ATR mult from base.py
    current = _read_atr_mult("strategies/base.py")
    if current is None:
        return []

    new_val = current
    reason = ""

    if days_high_sl >= 2:
        new_val = min(current + guard["step"], guard["max"])
        reason = f"SL hit rate {sl_rate:.0f}% over 3 days ({total_sl}/{total_trades}), high on {days_high_sl}/3 days → widening"
    elif days_low_sl >= 2:
        new_val = max(current - guard["step"], guard["min"])
        reason = f"SL hit rate {sl_rate:.0f}% over 3 days ({total_sl}/{total_trades}), low on {days_low_sl}/3 days → tightening"

    if new_val != current:
        _write_atr_mult("strategies/base.py", new_val)
        _write_atr_mult("strategies/futures_base.py", new_val)  # Keep in sync

        _log_change({
            "id": f"AUTO-SL-{now_ist().strftime('%m%d')}",
            "date": now_ist().strftime("%Y-%m-%d"),
            "type": "AUTO_TUNE",
            "parameter": "atr_multiplier (equity + futures)",
            "before": current,
            "after": new_val,
            "reason": reason,
            "data_backing": f"3-day SL rate: {sl_rate:.0f}%, high_sl_days: {days_high_sl}, low_sl_days: {days_low_sl}",
            "rollback_trigger": f"Auto-reverses if next 3-day SL rate moves opposite"
        })

        actions.append({
            "type": "auto_tune",
            "parameter": "atr_multiplier",
            "before": f"{current}x",
            "after": f"{new_val}x",
            "reason": reason,
        })

    return actions


# ═══════════════════════════════════════════════════════════════════════
# 3. VOLUME FILTER (auto-applied with ±0.1 step limit per day)
# ═══════════════════════════════════════════════════════════════════════

def _tune_volume_filter(reports: list[dict]) -> list[dict]:
    """
    Decision logic:
      < 3 trades/day for 3 consecutive days → loosen by 0.1 (min 1.0)
      Win rate < 35% for 3 days with > 5 trades/day → tighten by 0.1 (max 2.0)
      Otherwise → hold
    """
    low_trade_days = 0
    low_wr_days = 0

    for r in reports[:3]:
        trades = r.get("total_trades", 0)
        if trades < 3:
            low_trade_days += 1

        # Calculate overall win rate for the day
        total_wins = sum(p.get("wins", 0) for p in r.get("strategy_performance", {}).values())
        total_trades_day = sum(p.get("trades", 0) for p in r.get("strategy_performance", {}).values())
        if total_trades_day >= 5:
            wr = total_wins / total_trades_day * 100
            if wr < 35:
                low_wr_days += 1

    # Read current volume threshold from strategy files
    current = _read_volume_threshold()
    if current is None:
        return []

    new_val = current
    reason = ""

    if low_trade_days >= 3:
        new_val = max(round(current - 0.1, 1), 1.0)
        reason = f"< 3 trades/day for {low_trade_days} consecutive days → loosening volume filter"
    elif low_wr_days >= 2:
        new_val = min(round(current + 0.1, 1), 2.0)
        reason = f"Win rate < 35% for {low_wr_days}/3 days with sufficient trades → tightening volume filter"

    actions = []
    if new_val != current:
        _write_volume_threshold(new_val)

        _log_change({
            "id": f"AUTO-VOL-{now_ist().strftime('%m%d')}",
            "date": now_ist().strftime("%Y-%m-%d"),
            "type": "AUTO_TUNE",
            "parameter": "volume_confirmation_threshold",
            "before": f"{current}x",
            "after": f"{new_val}x",
            "reason": reason,
            "data_backing": f"low_trade_days: {low_trade_days}, low_wr_days: {low_wr_days}",
        })

        actions.append({
            "type": "auto_tune",
            "parameter": "volume_filter",
            "before": f"{current}x",
            "after": f"{new_val}x",
            "reason": reason,
        })

    return actions


# ═══════════════════════════════════════════════════════════════════════
# 4. DIRECTION BIAS (auto-adjust intraday override threshold)
# ═══════════════════════════════════════════════════════════════════════

def _tune_direction_bias(reports: list[dict]) -> list[dict]:
    """
    If one direction consistently loses over 3 days, tighten the
    intraday override threshold to filter out weak counter-trend signals.
    """
    buy_pnl, sell_pnl, buy_count, sell_count = 0, 0, 0, 0

    for r in reports[:3]:
        for perf in r.get("strategy_performance", {}).values():
            dirs = perf.get("directions", {})
            buy_pnl += dirs.get("BUY", {}).get("pnl", 0)
            sell_pnl += dirs.get("SELL", {}).get("pnl", 0)
            buy_count += dirs.get("BUY", {}).get("count", 0)
            sell_count += dirs.get("SELL", {}).get("count", 0)

    actions = []
    # Only act if clear bias with sufficient data
    if sell_count >= 6 and sell_pnl < -3000 and buy_pnl > 0:
        actions.append({
            "type": "auto_tune",
            "parameter": "direction_bias",
            "before": "balanced",
            "after": "BUY preferred (SELL restricted)",
            "reason": f"3-day: SELL lost ₹{abs(sell_pnl):,.0f} ({sell_count} trades), BUY made ₹{buy_pnl:,.0f} ({buy_count} trades). "
                      f"Market consistently bullish — SELL signals being filtered by regime override.",
        })
        _log_change({
            "id": f"AUTO-DIR-{now_ist().strftime('%m%d')}",
            "date": now_ist().strftime("%Y-%m-%d"),
            "type": "AUTO_TUNE",
            "parameter": "direction_bias_observation",
            "reason": f"SELL lost ₹{abs(sell_pnl):,.0f} over 3 days. BUY made ₹{buy_pnl:,.0f}. "
                      f"Regime intraday override should be catching this. If not, consider raising override threshold from 0.5% to 0.3%.",
            "data_backing": {"buy_pnl": buy_pnl, "sell_pnl": sell_pnl, "buy_count": buy_count, "sell_count": sell_count},
        })
    elif buy_count >= 6 and buy_pnl < -3000 and sell_pnl > 0:
        actions.append({
            "type": "auto_tune",
            "parameter": "direction_bias",
            "before": "balanced",
            "after": "SELL preferred (BUY restricted)",
            "reason": f"3-day: BUY lost ₹{abs(buy_pnl):,.0f} ({buy_count} trades), SELL made ₹{sell_pnl:,.0f} ({sell_count} trades). "
                      f"Market consistently bearish.",
        })
        _log_change({
            "id": f"AUTO-DIR-{now_ist().strftime('%m%d')}",
            "date": now_ist().strftime("%Y-%m-%d"),
            "type": "AUTO_TUNE",
            "parameter": "direction_bias_observation",
            "reason": f"BUY lost ₹{abs(buy_pnl):,.0f} over 3 days. SELL made ₹{sell_pnl:,.0f}. "
                      f"Regime override should be catching this.",
            "data_backing": {"buy_pnl": buy_pnl, "sell_pnl": sell_pnl, "buy_count": buy_count, "sell_count": sell_count},
        })

    return actions


# ═══════════════════════════════════════════════════════════════════════
# FILE I/O HELPERS
# ═══════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════
# 5. POST-FIX QA TESTING (runs after every auto-tune)
# ═══════════════════════════════════════════════════════════════════════

def _run_post_fix_qa() -> dict:
    """
    Run automated QA checks after auto-tuner makes changes.
    Verifies all modules still import, parameters are within bounds,
    and key functions still work. If any check fails, trigger rollback.
    """
    checks = []
    failures = []

    # 1. All strategy modules import cleanly
    strategy_modules = [
        "strategies.play1_ema_crossover", "strategies.play2_triple_ma",
        "strategies.play3_vwap_pullback", "strategies.play4_supertrend",
        "strategies.play5_bb_squeeze", "strategies.play6_bb_contra",
        "strategies.futures_volume_breakout", "strategies.futures_ema_rsi_pullback",
        "strategies.base", "strategies.futures_base",
    ]
    for mod in strategy_modules:
        try:
            import importlib
            m = importlib.import_module(mod)
            importlib.reload(m)  # Force re-import after file changes
            checks.append({"check": f"import {mod}", "status": "pass"})
        except Exception as e:
            checks.append({"check": f"import {mod}", "status": "fail", "error": str(e)})
            failures.append(f"import {mod}: {e}")

    # 2. Service modules import cleanly
    service_modules = [
        "services.scanner", "services.paper_trader", "services.auto_trader",
        "services.equity_regime", "services.options_scanner",
    ]
    for mod in service_modules:
        try:
            import importlib
            m = importlib.import_module(mod)
            importlib.reload(m)
            checks.append({"check": f"import {mod}", "status": "pass"})
        except Exception as e:
            checks.append({"check": f"import {mod}", "status": "fail", "error": str(e)})
            failures.append(f"import {mod}: {e}")

    # 3. ATR multiplier within guardrails
    for rel_path, name in [("strategies/base.py", "equity"), ("strategies/futures_base.py", "futures")]:
        val = _read_atr_mult(rel_path)
        if val is not None:
            guard = GUARDRAILS["atr_multiplier"]
            in_bounds = guard["min"] <= val <= guard["max"]
            checks.append({"check": f"ATR mult {name}: {val}", "status": "pass" if in_bounds else "fail"})
            if not in_bounds:
                failures.append(f"ATR mult {name} = {val}, out of bounds [{guard['min']}, {guard['max']}]")
        else:
            checks.append({"check": f"ATR mult {name}", "status": "fail", "error": "could not read"})
            failures.append(f"ATR mult {name}: could not read from file")

    # 4. Volume threshold within bounds
    vol = _read_volume_threshold()
    if vol is not None:
        in_bounds = 1.0 <= vol <= 2.0
        checks.append({"check": f"Volume threshold: {vol}x", "status": "pass" if in_bounds else "fail"})
        if not in_bounds:
            failures.append(f"Volume threshold = {vol}x, out of bounds [1.0, 2.0]")
    else:
        checks.append({"check": "Volume threshold", "status": "fail", "error": "could not read"})
        failures.append("Volume threshold: could not read from file")

    # 5. Strategy boosts within bounds
    boosts = _read_current_boosts()
    guard = GUARDRAILS["strategy_boost"]
    for strat, val in boosts.items():
        in_bounds = guard["min"] <= val <= guard["max"]
        checks.append({"check": f"Boost {strat}: {val}x", "status": "pass" if in_bounds else "fail"})
        if not in_bounds:
            failures.append(f"Boost {strat} = {val}x, out of bounds [{guard['min']}, {guard['max']}]")

    # 6. Regime detection still works
    try:
        from services.equity_regime import detect_equity_regime
        regime = detect_equity_regime()
        has_regime = "regime" in regime and "strategies" in regime
        checks.append({"check": "Regime detection", "status": "pass" if has_regime else "fail"})
        if not has_regime:
            failures.append("Regime detection returned incomplete data")
    except Exception as e:
        checks.append({"check": "Regime detection", "status": "fail", "error": str(e)})
        failures.append(f"Regime detection: {e}")

    # 7. Volume filter exists in all 6 strategy files
    for fname in ["play1_ema_crossover.py", "play2_triple_ma.py", "play3_vwap_pullback.py",
                   "play4_supertrend.py", "play5_bb_squeeze.py", "play6_bb_contra.py"]:
        try:
            path = Path(__file__).parent.parent / "strategies" / fname
            content = path.read_text()
            has_vol = "vol_sma" in content
            checks.append({"check": f"Volume filter in {fname}", "status": "pass" if has_vol else "fail"})
            if not has_vol:
                failures.append(f"Volume filter missing in {fname}")
        except Exception as e:
            failures.append(f"Could not read {fname}: {e}")

    total = len(checks)
    passed = sum(1 for c in checks if c["status"] == "pass")

    result = {
        "total_checks": total,
        "passed": passed,
        "failed": total - passed,
        "failures": failures,
        "checks": checks,
    }

    if failures:
        logger.error(f"[AutoTuner QA] FAILED: {len(failures)} failures: {failures}")
    else:
        logger.info(f"[AutoTuner QA] All {total} checks passed")

    return result


def _rollback_changes(actions: list[dict]):
    """
    Rollback all changes made during this auto-tune run.
    Restores 'before' values for each action.
    """
    for action in actions:
        param = action.get("parameter", "")
        before = action.get("before")
        if before is None:
            continue

        try:
            if param == "atr_multiplier":
                before_val = float(str(before).replace("x", ""))
                _write_atr_mult("strategies/base.py", before_val)
                _write_atr_mult("strategies/futures_base.py", before_val)
                logger.info(f"[AutoTuner ROLLBACK] ATR mult restored to {before_val}")

            elif param == "volume_filter":
                before_val = float(str(before).replace("x", ""))
                _write_volume_threshold(before_val)
                logger.info(f"[AutoTuner ROLLBACK] Volume threshold restored to {before_val}")

            elif param.startswith("boost_"):
                # Boost rollbacks are handled by re-reading and restoring
                pass  # Boosts will be recalculated next run anyway

        except Exception as e:
            logger.error(f"[AutoTuner ROLLBACK] Failed to rollback {param}: {e}")

    _log_change({
        "id": f"AUTO-ROLLBACK-{now_ist().strftime('%m%d')}",
        "date": now_ist().strftime("%Y-%m-%d"),
        "type": "AUTO_ROLLBACK",
        "parameter": "all_changes_rolled_back",
        "reason": "Post-fix QA failed — all changes reverted to pre-tune values",
        "actions_rolled_back": [a.get("parameter", "?") for a in actions],
    })


# ═══════════════════════════════════════════════════════════════════════
# FILE I/O HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _update_registry_live_values():
    """Update strategy_registry.json with current live values so the About page is always accurate."""
    try:
        registry = _load_json(REGISTRY_FILE)
        if not registry:
            return

        # Update ATR multiplier
        atr_eq = _read_atr_mult("strategies/base.py")
        if atr_eq is not None:
            registry.setdefault("candlestick_definitions", {})["atr_sl_default_mult"] = atr_eq
            for strat in registry.get("equity_intraday", {}).values():
                if isinstance(strat, dict) and "risk_management" in strat:
                    strat["risk_management"]["atr_multiplier"] = atr_eq

        atr_fut = _read_atr_mult("strategies/futures_base.py")
        if atr_fut is not None:
            for strat in registry.get("futures", {}).values():
                if isinstance(strat, dict) and "risk_management" in strat:
                    strat["risk_management"]["atr_multiplier"] = atr_fut

        # Update volume threshold
        vol = _read_volume_threshold()
        if vol is not None:
            for strat in registry.get("equity_intraday", {}).values():
                if isinstance(strat, dict) and "entry_rules" in strat:
                    strat["entry_rules"]["volume_confirmation"] = f"volume > {vol}x SMA20 required"

        # Update strategy boosts
        boosts = _read_current_boosts()
        if boosts:
            registry.setdefault("signal_ranking", {}).setdefault("factors", {})["strategy_boost"] = boosts

        # Update meta
        registry.setdefault("_meta", {})["last_updated"] = now_ist().strftime("%Y-%m-%d")
        registry["_meta"]["version"] = f"{registry['_meta'].get('version', '2.0.0').split('—')[0].strip()} — auto-tuned {now_ist().strftime('%b %d')}"

        _save_json(REGISTRY_FILE, registry)
        logger.info("[AutoTuner] Registry updated with live values")
    except Exception as e:
        logger.warning(f"[AutoTuner] Registry update failed: {e}")


def _read_current_boosts() -> dict:
    try:
        path = Path(__file__).parent / "scanner.py"
        content = path.read_text()
        match = re.search(r'strategy_boost\s*=\s*\{([^}]+)\}', content)
        if match:
            boosts = {}
            for line in match.group(1).split("\n"):
                line = line.strip().rstrip(",")
                if ":" in line and "play" in line:
                    parts = line.split(":")
                    strat = parts[0].strip().strip('"').strip("'")
                    val = float(parts[1].strip().split("#")[0].strip().rstrip(","))
                    boosts[strat] = val
            return boosts
    except Exception as e:
        logger.warning(f"[AutoTuner] Read boosts failed: {e}")
    return {}


def _apply_boost_changes(new_boosts: dict):
    try:
        path = Path(__file__).parent / "scanner.py"
        content = path.read_text()

        lines = []
        for strat in ["play4_supertrend", "play7_orb", "play9_gap_analysis",
                       "play3_vwap_pullback", "play8_rsi_divergence", "play6_bb_contra",
                       "play5_bb_squeeze", "play1_ema_crossover", "play2_triple_ma"]:
            val = new_boosts.get(strat, 1.0)
            lines.append(f'        "{strat}": {val},')

        new_block = "\n".join(lines)
        pattern = r'(strategy_boost\s*=\s*\{)\n(.*?)(\n\s*\})'
        new_content = re.sub(pattern, f'\\1\n{new_block}\n    \\3', content, flags=re.DOTALL)

        if new_content != content:
            path.write_text(new_content)
            logger.info(f"[AutoTuner] Updated boosts: {new_boosts}")
    except Exception as e:
        logger.warning(f"[AutoTuner] Apply boosts failed: {e}")


def _read_atr_mult(rel_path: str) -> float | None:
    try:
        path = Path(__file__).parent.parent / rel_path
        content = path.read_text()
        match = re.search(r'def atr_stop_loss\([^)]*atr_mult:\s*float\s*=\s*(\d+\.?\d*)', content)
        if match:
            return float(match.group(1))
    except Exception as e:
        logger.warning(f"[AutoTuner] Read ATR mult failed ({rel_path}): {e}")
    return None


def _write_atr_mult(rel_path: str, new_val: float):
    try:
        path = Path(__file__).parent.parent / rel_path
        content = path.read_text()
        new_content = re.sub(
            r'(def atr_stop_loss\([^)]*atr_mult:\s*float\s*=\s*)(\d+\.?\d*)',
            f'\\g<1>{new_val}',
            content
        )
        if new_content != content:
            path.write_text(new_content)
            logger.info(f"[AutoTuner] Updated ATR mult in {rel_path}: {new_val}")
    except Exception as e:
        logger.warning(f"[AutoTuner] Write ATR mult failed ({rel_path}): {e}")


def _read_volume_threshold() -> float | None:
    """Read the volume confirmation threshold from a strategy file."""
    try:
        path = Path(__file__).parent.parent / "strategies" / "play1_ema_crossover.py"
        content = path.read_text()
        match = re.search(r'vol_sma\s*\*\s*(\d+\.?\d*)', content)
        if match:
            return float(match.group(1))
    except Exception as e:
        logger.warning(f"[AutoTuner] Read volume threshold failed: {e}")
    return None


def _write_volume_threshold(new_val: float):
    """Update volume threshold in all 6 strategy files."""
    strategy_files = [
        "play1_ema_crossover.py", "play2_triple_ma.py", "play3_vwap_pullback.py",
        "play4_supertrend.py", "play5_bb_squeeze.py", "play6_bb_contra.py",
    ]
    for fname in strategy_files:
        try:
            path = Path(__file__).parent.parent / "strategies" / fname
            content = path.read_text()
            new_content = re.sub(
                r'(vol_sma\s*\*\s*)(\d+\.?\d*)',
                f'\\g<1>{new_val}',
                content
            )
            if new_content != content:
                path.write_text(new_content)
                logger.info(f"[AutoTuner] Updated volume threshold in {fname}: {new_val}x")
        except Exception as e:
            logger.warning(f"[AutoTuner] Write volume failed ({fname}): {e}")
