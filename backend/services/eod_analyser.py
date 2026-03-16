"""
EOD Analyser — Built-in algorithmic trading strategist engine.
Generates comprehensive end-of-day analysis from Fyers + auto-trader data.
Generates and applies parameter recommendations based on strategy performance.
No external API dependencies.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from services import fyers_client
from services.auto_trader import auto_trader

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "strategy_config.json")

IST = timezone(timedelta(hours=5, minutes=30))

STRATEGY_NAMES = {
    "play1_ema_crossover": "EMA-EMA Crossover",
    "play2_triple_ma": "Triple MA Trend Filter",
    "play3_vwap_pullback": "VWAP Trend-Pullback",
    "play4_supertrend": "Supertrend Power Trend",
    "play5_bb_squeeze": "BB Squeeze Breakout",
    "play6_bb_contra": "BB Mean Reversion",
}

STRATEGY_PARAMS = {
    "play1_ema_crossover": {"type": "trend-following", "indicators": "9 EMA / 21 EMA / 50 SMA filter", "ideal_market": "trending", "risk": "medium"},
    "play2_triple_ma": {"type": "trend-following", "indicators": "20 EMA / 50 SMA / 200 SMA", "ideal_market": "strong trend", "risk": "low"},
    "play3_vwap_pullback": {"type": "mean-reversion", "indicators": "Session VWAP + pullback", "ideal_market": "trending with pullbacks", "risk": "medium"},
    "play4_supertrend": {"type": "trend-following", "indicators": "Supertrend ATR(10,3) + 20 EMA", "ideal_market": "strong momentum", "risk": "high"},
    "play5_bb_squeeze": {"type": "breakout", "indicators": "BB(20,2) squeeze", "ideal_market": "low-vol before breakout", "risk": "high"},
    "play6_bb_contra": {"type": "mean-reversion", "indicators": "BB(20,2) + 200 SMA", "ideal_market": "range-bound", "risk": "low"},
}


def generate_eod_report() -> dict:
    """Collect all trading data, generate analysis, and produce recommendations."""
    now = datetime.now(IST)
    today_str = now.strftime("%A, %d %B %Y")

    data = _collect_trading_data(today_str)
    recommendations = _generate_param_recommendations(data)
    analysis = _generate_strategist_analysis(data)

    # Append recommendations summary to analysis
    if recommendations:
        analysis += "\n\n" + _format_recommendations_applied(recommendations)

    return {
        "analysis": analysis,
        "date": today_str,
        "summary": data["summary"],
        "recommendations": recommendations,
    }


def apply_recommendations(recommendations: list) -> dict:
    """Apply parameter recommendations to strategy_config.json."""
    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
    except Exception:
        config = {}

    changes = []
    for rec in recommendations:
        key = rec.get("strategy_key")
        if not key:
            continue

        if key not in config:
            config[key] = {}

        for param, value in rec.get("changes", {}).items():
            old_val = config[key].get(param)
            config[key][param] = value
            changes.append(f"{STRATEGY_NAMES.get(key, key)}: {param} {old_val} -> {value}")

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    return {"applied": len(changes), "changes": changes}


def get_current_config() -> dict:
    """Read current strategy_config.json."""
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════════════════════
#  Data Collection
# ═══════════════════════════════════════════════════════════════════════════


def _collect_trading_data(today_str: str) -> dict:
    """Gather all trading data from Fyers and auto-trader."""
    orders_raw = _safe_call(fyers_client.get_orderbook)
    trades_raw = _safe_call(fyers_client.get_tradebook)
    positions_raw = _safe_call(fyers_client.get_positions)

    # Parse orders
    order_book = orders_raw.get("orderBook", []) if orders_raw else []
    orders = []
    for o in order_book:
        orders.append({
            "symbol": _clean_sym(o.get("symbol", "")),
            "side": "BUY" if o.get("side") == 1 else "SELL",
            "qty": o.get("qty", 0),
            "filled_qty": o.get("filledQty", 0),
            "product": o.get("productType", ""),
            "limit_price": o.get("limitPrice", 0),
            "traded_price": o.get("tradedPrice", 0),
            "status": _order_status(o.get("status", 0)),
            "message": o.get("message", ""),
            "time": o.get("orderDateTime", ""),
        })

    filled = [o for o in orders if o["status"] == "FILLED"]
    rejected = [o for o in orders if o["status"] == "REJECTED"]
    cancelled = [o for o in orders if o["status"] == "CANCELLED"]
    pending = [o for o in orders if o["status"] == "PENDING"]

    # Parse trades
    trade_book = trades_raw.get("tradeBook", []) if trades_raw else []
    trades = []
    for t in trade_book:
        trades.append({
            "symbol": _clean_sym(t.get("symbol", "")),
            "side": "BUY" if t.get("side") == 1 else "SELL",
            "qty": t.get("tradedQty", 0),
            "price": t.get("tradePrice", 0),
            "value": t.get("tradeValue", 0),
            "product": t.get("productType", ""),
            "time": t.get("orderDateTime", ""),
        })

    # Parse positions
    net_positions = positions_raw.get("netPositions", []) if positions_raw else []
    positions = []
    total_pl = 0
    realized_pl = 0
    unrealized_pl = 0
    for p in net_positions:
        pl = p.get("pl", 0)
        rpl = p.get("realized_profit", 0)
        upl = p.get("unrealized_profit", 0)
        positions.append({
            "symbol": _clean_sym(p.get("symbol", "")),
            "net_qty": p.get("netQty", 0),
            "buy_avg": p.get("buyAvg", 0),
            "sell_avg": p.get("sellAvg", 0),
            "ltp": p.get("ltp", 0),
            "realized_pl": rpl,
            "unrealized_pl": upl,
            "total_pl": pl,
            "product": p.get("productType", ""),
        })
        total_pl += pl
        realized_pl += rpl
        unrealized_pl += upl

    # Auto-trader state
    auto_status = auto_trader.status()
    active_strategies = auto_status.get("strategies", [])
    capital = auto_status.get("capital", 0)
    scan_count = auto_status.get("scan_count", 0)
    order_count = auto_status.get("order_count", 0)
    trade_history = auto_status.get("trade_history", [])
    auto_logs = auto_status.get("logs", [])

    # Per-strategy stats
    strategy_stats = []

    if active_strategies:
        for strat in active_strategies:
            key = strat.get("strategy", "")
            tf = strat.get("timeframe", "")
            name = STRATEGY_NAMES.get(key, key)

            strat_trades = [t for t in trade_history if t.get("strategy") == key]
            strat_positions = []
            for pos in positions:
                for st in strat_trades:
                    if st.get("symbol") == pos["symbol"]:
                        strat_positions.append(pos)
                        break

            strat_pl = sum(p["total_pl"] for p in strat_positions) if strat_positions else 0
            winners = [p for p in strat_positions if p["total_pl"] > 0]
            losers = [p for p in strat_positions if p["total_pl"] < 0]

            trade_metrics = _compute_trade_metrics(strat_trades)
            avg_rr = sum(m["rr_ratio"] for m in trade_metrics) / len(trade_metrics) if trade_metrics else 0
            avg_sl_pct = sum(m["sl_pct"] for m in trade_metrics) / len(trade_metrics) if trade_metrics else 0
            max_loss = min((t.get("pnl", 0) for t in strat_trades), default=0)
            max_win = max((t.get("pnl", 0) for t in strat_trades), default=0)

            strategy_stats.append({
                "key": key,
                "name": name,
                "timeframe": tf,
                "trades": strat_trades,
                "trade_metrics": trade_metrics,
                "positions": strat_positions,
                "total_pl": round(strat_pl, 2),
                "winners": len(winners),
                "losers": len(losers),
                "win_rate": round(len(winners) / len(strat_positions) * 100, 1) if strat_positions else 0,
                "avg_rr": round(avg_rr, 2),
                "avg_sl_pct": round(avg_sl_pct, 2),
                "max_loss": round(max_loss, 2),
                "max_win": round(max_win, 2),
            })

    # Detect issues
    issues = []
    if rejected:
        for r in rejected:
            issues.append({"type": "rejection", "symbol": r["symbol"], "side": r["side"], "message": r["message"]})
    for st in trade_history:
        entry = st.get("entry_price", 0)
        sl = st.get("stop_loss", 0)
        if entry > 0 and sl > 0:
            sl_pct = abs(entry - sl) / entry * 100
            if sl_pct < 0.3:
                issues.append({"type": "tight_sl", "symbol": st["symbol"], "sl_pct": round(sl_pct, 2), "strategy": st.get("strategy", "")})
    rapid_sl = [st for st in trade_history if st.get("status") == "CLOSED" and st.get("pnl", 0) < 0]
    if len(rapid_sl) > 2:
        issues.append({"type": "multiple_sl", "count": len(rapid_sl)})
    zero_scans = sum(1 for log in auto_logs if "0 signals" in log.get("message", "") and "unique" not in log.get("message", ""))
    if zero_scans > 5:
        issues.append({"type": "zero_signals", "count": zero_scans})

    recent_logs = auto_logs[-30:] if auto_logs else []

    return {
        "date": today_str,
        "orders": orders,
        "filled": filled,
        "rejected": rejected,
        "cancelled": cancelled,
        "pending": pending,
        "trades": trades,
        "positions": positions,
        "total_pl": round(total_pl, 2),
        "realized_pl": round(realized_pl, 2),
        "unrealized_pl": round(unrealized_pl, 2),
        "capital": capital,
        "scan_count": scan_count,
        "order_count": order_count,
        "trade_history": trade_history,
        "active_strategies": active_strategies,
        "strategy_stats": strategy_stats,
        "issues": issues,
        "recent_logs": recent_logs,
        "summary": {
            "total_pl": round(total_pl, 2),
            "realized_pl": round(realized_pl, 2),
            "unrealized_pl": round(unrealized_pl, 2),
            "total_orders": len(orders),
            "filled": len(filled),
            "rejected": len(rejected),
            "cancelled": len(cancelled),
            "pending": len(pending),
            "scan_count": scan_count,
            "strategies_active": len(active_strategies),
            "capital": capital,
        },
    }


def _compute_trade_metrics(strat_trades: list) -> list:
    """Compute detailed metrics for a list of strategy trades."""
    trade_metrics = []
    for t in strat_trades:
        entry = t.get("entry_price", 0)
        sl = t.get("stop_loss", 0)
        tgt = t.get("target", 0)
        sl_dist = abs(entry - sl) if entry and sl else 0
        sl_pct = sl_dist / entry * 100 if entry > 0 else 0
        tgt_dist = abs(tgt - entry) if entry and tgt else 0
        rr_ratio = tgt_dist / sl_dist if sl_dist > 0 else 0
        trade_metrics.append({
            **t,
            "sl_distance": round(sl_dist, 2),
            "sl_pct": round(sl_pct, 2),
            "target_distance": round(tgt_dist, 2),
            "rr_ratio": round(rr_ratio, 2),
        })
    return trade_metrics


# ═══════════════════════════════════════════════════════════════════════════
#  Parameter Recommendations Engine
# ═══════════════════════════════════════════════════════════════════════════


def _generate_param_recommendations(data: dict) -> list:
    """Generate concrete parameter change recommendations based on today's performance."""
    recommendations = []

    # Load current config
    try:
        with open(CONFIG_PATH, "r") as f:
            current_config = json.load(f)
    except Exception:
        current_config = {}

    for ss in data["strategy_stats"]:
        key = ss["key"]
        name = ss["name"]
        cfg = current_config.get(key, {})
        current_atr = cfg.get("atr_mult", 1.5)
        current_min_pct = cfg.get("min_pct", 0.005)
        current_tf = cfg.get("preferred_timeframe", "15m")
        current_enabled = cfg.get("enabled", True)

        changes = {}
        reasons = []

        if not ss["trades"]:
            # No trades — no data to recommend changes
            continue

        # ── ATR Multiplier tuning ──
        avg_sl_pct = ss["avg_sl_pct"]
        win_rate = ss["win_rate"]
        losers = ss["losers"]
        winners = ss["winners"]
        total_trades = len(ss["trades"])

        # Tight SLs causing frequent stops
        if avg_sl_pct < 0.5 and losers > winners:
            new_atr = min(round(current_atr + 0.5, 1), 3.0)
            if new_atr != current_atr:
                changes["atr_mult"] = new_atr
                reasons.append(f"SLs too tight (avg {avg_sl_pct:.1f}%) causing frequent stops. Widening ATR mult {current_atr} -> {new_atr}")

        elif avg_sl_pct < 0.5 and losers > 0:
            new_atr = min(round(current_atr + 0.3, 1), 3.0)
            if new_atr != current_atr:
                changes["atr_mult"] = new_atr
                reasons.append(f"SLs tight (avg {avg_sl_pct:.1f}%). Slightly widening ATR mult {current_atr} -> {new_atr}")

        # Very wide SLs risking too much
        elif avg_sl_pct > 3.0:
            new_atr = max(round(current_atr - 0.3, 1), 1.0)
            if new_atr != current_atr:
                changes["atr_mult"] = new_atr
                reasons.append(f"SLs too wide (avg {avg_sl_pct:.1f}%). Tightening ATR mult {current_atr} -> {new_atr}")

        # ── Min SL floor tuning ──
        if avg_sl_pct < 0.3:
            new_min = max(round(current_min_pct + 0.003, 3), 0.005)
            new_min = min(new_min, 0.015)
            if new_min != current_min_pct:
                changes["min_pct"] = new_min
                reasons.append(f"Min SL floor too low. Raising {current_min_pct*100:.1f}% -> {new_min*100:.1f}%")

        # ── R:R analysis ──
        avg_rr = ss["avg_rr"]
        if avg_rr < 1.0 and total_trades >= 2:
            reasons.append(f"R:R below 1.0 ({avg_rr:.1f}x) — risking more than reward. Review target calculation.")

        # ── Win rate based enable/disable ──
        if total_trades >= 3 and win_rate == 0 and losers >= 3:
            changes["enabled"] = False
            reasons.append(f"0% win rate across {total_trades} trades. Disabling until parameters reviewed.")

        elif total_trades >= 5 and win_rate < 25:
            changes["enabled"] = False
            reasons.append(f"Win rate {win_rate:.0f}% across {total_trades} trades. Pausing strategy.")

        # ── Strong performers: keep and maybe tighten for more profit ──
        if win_rate >= 70 and total_trades >= 3 and avg_rr >= 2.0:
            reasons.append(f"STRONG: {win_rate:.0f}% win rate, {avg_rr:.1f}x R:R. Keep current settings.")

        if changes or reasons:
            rec = {
                "strategy_key": key,
                "strategy_name": name,
                "changes": changes,
                "reasons": reasons,
                "current": {
                    "atr_mult": current_atr,
                    "min_pct": current_min_pct,
                    "enabled": current_enabled,
                },
                "performance": {
                    "trades": total_trades,
                    "win_rate": win_rate,
                    "avg_rr": avg_rr,
                    "avg_sl_pct": avg_sl_pct,
                    "pl": ss["total_pl"],
                },
            }
            recommendations.append(rec)

    return recommendations


def _format_recommendations_applied(recommendations: list) -> str:
    """Format recommendations into readable text for the analysis."""
    lines = ["PARAMETER RECOMMENDATIONS", "=" * 60]

    has_changes = any(r["changes"] for r in recommendations)

    if not has_changes:
        lines.append("No parameter changes recommended. Current settings are adequate.")
        for r in recommendations:
            for reason in r["reasons"]:
                lines.append(f"  {r['strategy_name']}: {reason}")
        return "\n".join(lines)

    for rec in recommendations:
        name = rec["strategy_name"]
        lines.append(f"\n  [{name}]")

        for reason in rec["reasons"]:
            lines.append(f"    {reason}")

        if rec["changes"]:
            lines.append(f"    Changes to apply:")
            for param, value in rec["changes"].items():
                old = rec["current"].get(param)
                if param == "min_pct":
                    lines.append(f"      {param}: {old*100:.1f}% -> {value*100:.1f}%")
                elif param == "enabled":
                    lines.append(f"      {param}: {old} -> {value}")
                else:
                    lines.append(f"      {param}: {old} -> {value}")

    lines.append("")
    lines.append("Use 'Apply Recommendations' to update strategy parameters for tomorrow.")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  Strategist Analysis Engine
# ═══════════════════════════════════════════════════════════════════════════


def _generate_strategist_analysis(data: dict) -> str:
    """Generate comprehensive strategist-level analysis from collected data."""
    sections = []

    sections.append(_section_market_verdict(data))
    sections.append(_section_scorecard(data))

    sections.append(_section_strategy_analysis(data))

    sections.append(_section_trade_review(data))
    sections.append(_section_risk_analysis(data))
    sections.append(_section_execution_issues(data))
    sections.append(_section_recommendations(data))
    sections.append(_section_confidence_ratings(data))

    return "\n\n".join(s for s in sections if s)


def _section_market_verdict(data: dict) -> str:
    """Overall market verdict based on aggregate performance."""
    lines = ["MARKET VERDICT", "=" * 60]
    total_pl = data["total_pl"]
    capital = data["capital"]
    filled = data["filled"]
    trades = data["trades"]
    stats = data["strategy_stats"]

    if not trades and not filled:
        # Diagnose why no trades
        if not data["active_strategies"]:
            lines.append("No trades executed — auto-trader was not running today.")
            lines.append("Action: Start auto-trading before 9:15 AM tomorrow with selected strategies.")
        elif data["scan_count"] == 0:
            lines.append("No trades executed — scanner did not run any scans.")
            lines.append("Possible cause: Auto-trader started but no scan cycles completed. Check if data source (yfinance) is responding.")
        else:
            zero_signal_issues = [i for i in data["issues"] if i.get("type") == "zero_signals"]
            if zero_signal_issues:
                lines.append(f"No trades executed — {zero_signal_issues[0]['count']} scans returned zero signals.")
                lines.append("Market was likely flat/range-bound with no setups matching strategy criteria.")
                lines.append("This is normal — the system correctly avoided forcing trades in unsuitable conditions.")
            else:
                lines.append("No trades executed — signals may have been generated but filters prevented order placement.")
                lines.append("Check if capital allocation or position sizing constraints blocked entries.")
    else:
        # Classify the session
        if capital > 0:
            roi = total_pl / capital * 100
            if roi > 1.0:
                lines.append(f"STRONG PROFITABLE SESSION — Net P&L: Rs.{total_pl:+,.2f} (ROI: {roi:+.2f}%)")
                lines.append("Strategies captured momentum effectively. Current parameter settings are well-calibrated.")
            elif roi > 0:
                lines.append(f"MILDLY PROFITABLE SESSION — Net P&L: Rs.{total_pl:+,.2f} (ROI: {roi:+.2f}%)")
                lines.append("Marginal gains — strategies found setups but risk-reward execution could improve.")
            elif roi > -0.5:
                lines.append(f"MARGINAL LOSS SESSION — Net P&L: Rs.{total_pl:+,.2f} (ROI: {roi:+.2f}%)")
                lines.append("Contained losses within acceptable range. SL discipline held. No parameter panic needed.")
            elif roi > -1.5:
                lines.append(f"LOSS SESSION — Net P&L: Rs.{total_pl:+,.2f} (ROI: {roi:+.2f}%)")
                lines.append("Multiple SL hits suggest strategies mismatched today's market character.")
            else:
                lines.append(f"HEAVY LOSS SESSION — Net P&L: Rs.{total_pl:+,.2f} (ROI: {roi:+.2f}%)")
                lines.append("Significant drawdown. Immediate review of active strategies and parameters required.")
        else:
            if total_pl > 0:
                lines.append(f"Profitable session. Net P&L: Rs.{total_pl:+,.2f}")
            elif total_pl < 0:
                lines.append(f"Loss-making session. Net P&L: Rs.{total_pl:+,.2f}")
            else:
                lines.append(f"Breakeven session. Net P&L: Rs.{total_pl:+,.2f}")

        # Winning vs losing strategies
        winning_strats = [s for s in stats if s["total_pl"] > 0]
        losing_strats = [s for s in stats if s["total_pl"] < 0]
        if winning_strats and losing_strats:
            best = max(winning_strats, key=lambda s: s["total_pl"])
            worst = min(losing_strats, key=lambda s: s["total_pl"])
            lines.append(f"Best performer: {best['name']} (Rs.{best['total_pl']:+,.2f}) | Worst: {worst['name']} (Rs.{worst['total_pl']:+,.2f})")

    return "\n".join(lines)


def _section_scorecard(data: dict) -> str:
    """Trading scorecard with key metrics."""
    lines = ["SCORECARD", "=" * 60]
    capital = data["capital"]
    total_pl = data["total_pl"]

    lines.append(f"Date               : {data['date']}")
    lines.append(f"Capital            : Rs.{capital:,.0f}" if capital else "Capital            : Not set (auto-trader not started)")
    lines.append(f"Net P&L            : Rs.{total_pl:+,.2f}")
    lines.append(f"Realised P&L       : Rs.{data['realized_pl']:+,.2f}")
    lines.append(f"Unrealised P&L     : Rs.{data['unrealized_pl']:+,.2f}")

    if capital > 0:
        roi = total_pl / capital * 100
        lines.append(f"ROI                : {roi:+.2f}%")
        max_risk = capital * 0.02 * len(data["trade_history"]) if data["trade_history"] else 0
        if max_risk > 0:
            risk_efficiency = total_pl / max_risk * 100
            lines.append(f"Risk Efficiency    : {risk_efficiency:+.1f}% (P&L vs max risk deployed)")

    lines.append(f"Total Orders       : {len(data['orders'])}")
    lines.append(f"  Filled           : {len(data['filled'])}")
    lines.append(f"  Rejected         : {len(data['rejected'])}")
    lines.append(f"  Cancelled        : {len(data['cancelled'])}")
    lines.append(f"  Pending          : {len(data['pending'])}")

    fill_rate = len(data['filled']) / len(data['orders']) * 100 if data['orders'] else 0
    lines.append(f"Fill Rate          : {fill_rate:.0f}%")
    lines.append(f"Scans Completed    : {data['scan_count']}")
    lines.append(f"Orders by Engine   : {data['order_count']}")
    lines.append(f"Strategies Active  : {len(data['active_strategies'])}")

    if capital > 0 and data['filled']:
        cap_used = sum(o["traded_price"] * o["filled_qty"] for o in data['filled'])
        lines.append(f"Capital Utilised   : Rs.{cap_used:,.0f} ({cap_used/capital*100:.1f}%)")

        if cap_used / capital < 0.3:
            lines.append("  -> Low utilisation. Consider adding more strategies or reducing signal filters.")
        elif cap_used / capital > 0.8:
            lines.append("  -> High utilisation. Concentration risk — consider limiting max positions.")

    return "\n".join(lines)


def _section_strategy_analysis(data: dict) -> str:
    """Detailed per-strategy analysis."""
    lines = ["STRATEGY-BY-STRATEGY ANALYSIS", "=" * 60]

    if not data["strategy_stats"]:
        lines.append("No strategies were active today.")
        return "\n".join(lines)

    for ss in data["strategy_stats"]:
        params = STRATEGY_PARAMS.get(ss["key"], {})
        lines.append(f"\n[{ss['name']}] ({ss['timeframe']})")
        lines.append(f"  Type: {params.get('type', 'unknown')} | Indicators: {params.get('indicators', 'N/A')}")
        lines.append(f"  Trades: {len(ss['trades'])} | Winners: {ss['winners']} | Losers: {ss['losers']}")

        if ss["trades"]:
            lines.append(f"  Win Rate: {ss['win_rate']:.0f}%")
            lines.append(f"  Strategy P&L: Rs.{ss['total_pl']:+,.2f}")
            lines.append(f"  Avg R:R Ratio: {ss['avg_rr']:.1f}x")
            lines.append(f"  Avg SL Distance: {ss['avg_sl_pct']:.1f}%")

            if ss["max_win"] > 0:
                lines.append(f"  Best Trade: Rs.{ss['max_win']:+,.2f}")
            if ss["max_loss"] < 0:
                lines.append(f"  Worst Trade: Rs.{ss['max_loss']:+,.2f}")

            # Verdict
            if ss["win_rate"] >= 60 and ss["avg_rr"] >= 1.5:
                lines.append(f"  VERDICT: EXCELLENT — High win rate + good R:R. Strategy is well-suited to today's market.")
            elif ss["win_rate"] >= 50:
                lines.append(f"  VERDICT: GOOD — Positive edge. Keep running with current parameters.")
            elif ss["win_rate"] >= 40:
                lines.append(f"  VERDICT: AVERAGE — Borderline. Give 2-3 more sessions before tuning.")
            elif len(ss["trades"]) >= 3:
                lines.append(f"  VERDICT: POOR — Win rate below 40% with {len(ss['trades'])} trades. Review parameters or pause.")
            else:
                lines.append(f"  VERDICT: INSUFFICIENT DATA — Only {len(ss['trades'])} trade(s). Need more sessions to judge.")

            # R:R analysis
            if ss["avg_rr"] < 1.0:
                lines.append(f"  WARNING: Avg R:R below 1.0 — risking more than potential reward. Widen target or tighten SL.")
            elif ss["avg_rr"] < 1.5:
                lines.append(f"  NOTE: R:R of {ss['avg_rr']:.1f}x is acceptable but not ideal. Aim for 2:1 minimum.")

            # SL analysis
            if ss["avg_sl_pct"] < 0.5:
                lines.append(f"  WARNING: Very tight SLs (avg {ss['avg_sl_pct']:.1f}%). Increase ATR multiplier from 1.5 to 2.0.")
            elif ss["avg_sl_pct"] > 3.0:
                lines.append(f"  WARNING: Wide SLs (avg {ss['avg_sl_pct']:.1f}%). Risk per trade may exceed 2% capital. Consider tighter ATR multiplier.")

            # Trade details
            for m in ss["trade_metrics"]:
                sym = m.get("symbol", "")
                sig = m.get("signal_type", "")
                entry = m.get("entry_price", 0)
                sl = m.get("stop_loss", 0)
                tgt = m.get("target", 0)
                status = m.get("status", "")
                pnl = m.get("pnl", 0)
                rr = m.get("rr_ratio", 0)
                sl_pct = m.get("sl_pct", 0)
                lines.append(f"    {sig} {sym} @ Rs.{entry:.2f} | SL Rs.{sl:.2f} ({sl_pct:.1f}%) | Tgt Rs.{tgt:.2f} | R:R {rr:.1f} | {status} | Rs.{pnl:+,.2f}")
        else:
            lines.append(f"  No trades placed. Scanner found no qualifying signals on {ss['timeframe']} timeframe.")
            ideal = params.get("ideal_market", "")
            if ideal:
                lines.append(f"  This strategy works best in: {ideal} conditions.")

    return "\n".join(lines)


def _section_trade_review(data: dict) -> str:
    """Review all positions with entry/exit analysis."""
    if not data["positions"]:
        return ""

    lines = ["POSITION REVIEW", "=" * 60]
    for p in data["positions"]:
        sym = p["symbol"]
        lines.append(f"\n  {sym}:")
        lines.append(f"    Net Qty: {p['net_qty']} | Buy Avg: Rs.{p['buy_avg']:.2f} | Sell Avg: Rs.{p['sell_avg']:.2f}")
        lines.append(f"    LTP: Rs.{p['ltp']:.2f} | P&L: Rs.{p['total_pl']:+,.2f}")

        if p["net_qty"] != 0:
            lines.append(f"    STATUS: OPEN — Position still held. Will be squared off at 3:15 PM if not closed.")
        else:
            if p["total_pl"] > 0:
                lines.append(f"    STATUS: CLOSED WITH PROFIT")
            elif p["total_pl"] < 0:
                if p["buy_avg"] > 0 and p["sell_avg"] > 0:
                    if p["sell_avg"] < p["buy_avg"]:
                        lines.append(f"    STATUS: SL HIT — Sold below buy average.")
                    else:
                        lines.append(f"    STATUS: CLOSED WITH LOSS")
                else:
                    lines.append(f"    STATUS: CLOSED WITH LOSS")
            else:
                lines.append(f"    STATUS: BREAKEVEN")

    return "\n".join(lines)


def _section_risk_analysis(data: dict) -> str:
    """Risk management analysis."""
    lines = ["RISK ANALYSIS", "=" * 60]
    capital = data["capital"]
    trade_history = data["trade_history"]

    if not trade_history:
        lines.append("No trades to analyse risk metrics.")
        return "\n".join(lines)

    # Max drawdown in sequence
    cumulative = 0
    peak = 0
    max_dd = 0
    for t in trade_history:
        pnl = t.get("pnl", 0)
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

    lines.append(f"Max Intraday Drawdown : Rs.{max_dd:,.2f}")
    if capital > 0:
        dd_pct = max_dd / capital * 100
        lines.append(f"Drawdown vs Capital  : {dd_pct:.2f}%")
        if dd_pct > 3:
            lines.append(f"  ALERT: Drawdown exceeded 3% of capital. Consider reducing position sizes or number of concurrent strategies.")
        elif dd_pct > 2:
            lines.append(f"  CAUTION: Drawdown approaching 2% threshold. Monitor closely tomorrow.")

    # Consecutive losses
    max_consec_loss = 0
    current_streak = 0
    for t in trade_history:
        if t.get("pnl", 0) < 0:
            current_streak += 1
            max_consec_loss = max(max_consec_loss, current_streak)
        else:
            current_streak = 0

    if max_consec_loss >= 3:
        lines.append(f"Consecutive Losses   : {max_consec_loss} in a row")
        lines.append(f"  ALERT: {max_consec_loss} consecutive SL hits suggests strategies mismatched the market regime.")
        lines.append(f"  Consider pausing the worst-performing strategy and switching to a different timeframe.")
    elif max_consec_loss >= 2:
        lines.append(f"Consecutive Losses   : {max_consec_loss}")
        lines.append(f"  Within normal range. No action needed.")

    # SL distribution
    sl_pcts = []
    for t in trade_history:
        entry = t.get("entry_price", 0)
        sl = t.get("stop_loss", 0)
        if entry > 0 and sl > 0:
            sl_pcts.append(abs(entry - sl) / entry * 100)

    if sl_pcts:
        avg_sl = sum(sl_pcts) / len(sl_pcts)
        min_sl = min(sl_pcts)
        max_sl = max(sl_pcts)
        lines.append(f"SL Distance Range    : {min_sl:.1f}% — {max_sl:.1f}% (Avg: {avg_sl:.1f}%)")

        if min_sl < 0.3:
            lines.append(f"  WARNING: Some SLs are extremely tight ({min_sl:.2f}%). These will get stopped out on normal price noise.")
            lines.append(f"  SUGGESTION: Increase ATR multiplier from 1.5x to 2.0x, or raise minimum floor from 0.5% to 0.8%.")

        if max_sl > 3.0:
            lines.append(f"  WARNING: Some SLs are very wide ({max_sl:.1f}%). Per-trade risk may exceed 2% of capital.")

    return "\n".join(lines)


def _section_execution_issues(data: dict) -> str:
    """Analyse execution problems."""
    issues = data["issues"]
    if not issues:
        return "EXECUTION QUALITY\n" + "=" * 60 + "\nNo execution issues detected. All orders processed cleanly."

    lines = ["EXECUTION ISSUES", "=" * 60]

    rejections = [i for i in issues if i["type"] == "rejection"]
    tight_sls = [i for i in issues if i["type"] == "tight_sl"]
    multi_sl = [i for i in issues if i["type"] == "multiple_sl"]
    zero_sigs = [i for i in issues if i["type"] == "zero_signals"]

    issue_num = 1

    if rejections:
        for r in rejections:
            lines.append(f"\n  {issue_num}. ORDER REJECTED: {r['symbol']} {r['side']}")
            lines.append(f"     Reason: {r['message']}")

            msg = r["message"].lower()
            if "margin" in msg or "fund" in msg:
                lines.append(f"     Root Cause: Insufficient margin. Reduce position size or add funds.")
            elif "quantity" in msg or "lot" in msg:
                lines.append(f"     Root Cause: Invalid quantity. Check lot size constraints for this stock.")
            elif "price" in msg or "tick" in msg:
                lines.append(f"     Root Cause: Price outside tick/circuit limits. Use market orders instead of limit.")
            elif "freeze" in msg:
                lines.append(f"     Root Cause: Order freeze quantity exceeded. Split into smaller orders.")
            else:
                lines.append(f"     Root Cause: Broker-side rejection. Check Fyers order requirements for this symbol.")
            issue_num += 1

    if tight_sls:
        lines.append(f"\n  {issue_num}. TIGHT STOP-LOSSES DETECTED:")
        for ts in tight_sls:
            strat_name = STRATEGY_NAMES.get(ts.get("strategy", ""), ts.get("strategy", ""))
            lines.append(f"     {ts['symbol']} — SL at {ts['sl_pct']:.2f}% ({strat_name})")
        lines.append(f"     Action: Increase ATR multiplier to 2.0x or raise min SL floor to 0.8%.")
        issue_num += 1

    if multi_sl:
        count = multi_sl[0]["count"]
        lines.append(f"\n  {issue_num}. {count} POSITIONS HIT STOP-LOSS")
        lines.append(f"     Market was likely choppy/whipsaw-prone.")
        lines.append(f"     Action: On choppy days, trend-following strategies (EMA Crossover, Triple MA, Supertrend) struggle.")
        lines.append(f"     Consider: Switch to mean-reversion strategies (VWAP Pullback, BB Contra) when market is range-bound.")
        issue_num += 1

    if zero_sigs:
        count = zero_sigs[0]["count"]
        lines.append(f"\n  {issue_num}. {count} SCANS RETURNED ZERO SIGNALS")
        lines.append(f"     Possible causes: (a) Market too flat for entry criteria, (b) Data source issue with yfinance.")
        lines.append(f"     If this persists, check yfinance connectivity and try switching timeframes.")
        issue_num += 1

    return "\n".join(lines)


def _section_recommendations(data: dict) -> str:
    """Actionable recommendations for tomorrow."""
    lines = ["RECOMMENDATIONS FOR TOMORROW", "=" * 60]

    stats = data["strategy_stats"]

    if not stats:
        lines.append("No strategies were active today. Start auto-trading before 9:15 AM tomorrow.")
        lines.append("")
        lines.append("Suggested starter combination:")
        lines.append("  1. Supertrend Power Trend (15m) — strong trend-following")
        lines.append("  2. BB Squeeze Breakout (15m) — catches breakouts")
        lines.append("  3. VWAP Trend-Pullback (5m) — pullback entries in trends")
        return "\n".join(lines)

    # Sort by P&L performance
    sorted_stats = sorted(stats, key=lambda s: s["total_pl"], reverse=True)

    for ss in sorted_stats:
        params = STRATEGY_PARAMS.get(ss["key"], {})
        name = ss["name"]
        tf = ss["timeframe"]

        if not ss["trades"]:
            action = "KEEP"
            reason = "No trades today — insufficient data to judge. Give it more sessions."
            tuning = ""
        elif ss["win_rate"] >= 60 and ss["avg_rr"] >= 1.5:
            action = "KEEP (STRONG)"
            reason = f"Win rate {ss['win_rate']:.0f}% with {ss['avg_rr']:.1f}x R:R. Strategy is performing well."
            tuning = "No parameter changes needed."
        elif ss["win_rate"] >= 50:
            action = "KEEP"
            reason = f"Win rate {ss['win_rate']:.0f}% — positive edge."
            tuning = ""
            if ss["avg_rr"] < 1.5:
                tuning = f"Consider widening target multiplier to improve R:R from {ss['avg_rr']:.1f}x to 2.0x."
        elif ss["win_rate"] >= 35 and len(ss["trades"]) <= 3:
            action = "KEEP (MONITOR)"
            reason = f"Only {len(ss['trades'])} trades — too few to draw conclusions."
            tuning = "Run for 2-3 more sessions before deciding."
        elif ss["losers"] >= 3 and ss["winners"] == 0:
            action = "PAUSE"
            reason = f"Zero winners out of {len(ss['trades'])} trades. Strategy mismatched today's market."
            tuning = _get_tuning_advice(ss)
        elif ss["win_rate"] < 40 and len(ss["trades"]) >= 3:
            action = "REVIEW"
            reason = f"Win rate {ss['win_rate']:.0f}% across {len(ss['trades'])} trades — below profitability threshold."
            tuning = _get_tuning_advice(ss)
        else:
            action = "KEEP (MONITOR)"
            reason = "Mixed results — not enough data to make a strong call."
            tuning = ""

        lines.append(f"\n  {name} ({tf}): {action}")
        lines.append(f"    {reason}")
        if tuning:
            lines.append(f"    Tuning: {tuning}")

    # Cross-strategy advice
    trend_strats = [s for s in stats if STRATEGY_PARAMS.get(s["key"], {}).get("type") == "trend-following"]
    mr_strats = [s for s in stats if STRATEGY_PARAMS.get(s["key"], {}).get("type") == "mean-reversion"]

    trend_pl = sum(s["total_pl"] for s in trend_strats) if trend_strats else 0
    mr_pl = sum(s["total_pl"] for s in mr_strats) if mr_strats else 0

    if trend_strats and mr_strats:
        lines.append(f"\n  REGIME INSIGHT:")
        if trend_pl > mr_pl and trend_pl > 0:
            lines.append(f"    Trend-following (Rs.{trend_pl:+,.2f}) outperformed mean-reversion (Rs.{mr_pl:+,.2f}).")
            lines.append(f"    Market was trending today. Weight towards trend strategies tomorrow if expecting continuation.")
        elif mr_pl > trend_pl and mr_pl > 0:
            lines.append(f"    Mean-reversion (Rs.{mr_pl:+,.2f}) outperformed trend-following (Rs.{trend_pl:+,.2f}).")
            lines.append(f"    Market was range-bound today. If expecting similar conditions, favour VWAP/BB strategies.")
        elif trend_pl < 0 and mr_pl < 0:
            lines.append(f"    Both trend (Rs.{trend_pl:+,.2f}) and mean-reversion (Rs.{mr_pl:+,.2f}) lost money.")
            lines.append(f"    Market was likely whipsaw/choppy. Consider reducing position sizes or sitting out volatile sessions.")

    return "\n".join(lines)


def _get_tuning_advice(ss: dict) -> str:
    """Get specific parameter tuning advice for a strategy."""
    key = ss["key"]
    avg_sl = ss["avg_sl_pct"]
    avg_rr = ss["avg_rr"]
    tf = ss["timeframe"]

    advice = []

    # SL tuning
    if avg_sl < 0.5:
        advice.append("Increase ATR multiplier from 1.5x to 2.0x (SLs too tight).")
    elif avg_sl > 2.5:
        advice.append("Decrease ATR multiplier from 1.5x to 1.2x (SLs too wide, risking too much per trade).")

    # Timeframe advice
    if tf in ("5m", "3m"):
        advice.append(f"Consider moving to 15m timeframe — less noise, fewer false signals on {tf}.")
    elif tf == "15m" and ss["win_rate"] < 35:
        advice.append("Try 30m or 1h timeframe for stronger signal quality.")

    # Strategy-specific
    if key == "play4_supertrend" and ss["losers"] > ss["winners"]:
        advice.append("Supertrend works best in strong trends. On choppy days, it generates false signals. Consider pausing on low-ADX days.")
    elif key == "play1_ema_crossover" and avg_rr < 1.0:
        advice.append("EMA crossover targets may be too conservative. Increase target multiplier to capture more of the trend move.")
    elif key == "play5_bb_squeeze" and ss["losers"] > 2:
        advice.append("BB Squeeze false breakouts — market may not have had genuine volatility expansion. Pair with volume confirmation.")
    elif key == "play6_bb_contra":
        advice.append("BB Contra is a counter-trend strategy — it underperforms in strong trends. Use only when Nifty is range-bound.")
    elif key == "play3_vwap_pullback":
        advice.append("VWAP pullback needs a trending market with clean pullbacks. Ineffective on gap-up/gap-down open days.")

    return " ".join(advice) if advice else "Monitor for 2-3 more sessions before making parameter changes."


def _section_confidence_ratings(data: dict) -> str:
    """Confidence rating for each strategy going into tomorrow."""
    lines = ["CONFIDENCE RATINGS (for tomorrow)", "=" * 60]

    if not data["strategy_stats"]:
        lines.append("No strategies to rate — none were active today.")
        return "\n".join(lines)

    for ss in data["strategy_stats"]:
        name = ss["name"]
        trades = ss["trades"]

        if not trades:
            rating = "LOW"
            reason = "No trades executed. Cannot assess."
        elif len(trades) == 1:
            if ss["total_pl"] > 0:
                rating = "MEDIUM"
                reason = "1 winning trade. Need more data but promising."
            else:
                rating = "LOW"
                reason = "1 losing trade. Insufficient sample."
        elif ss["win_rate"] >= 60 and ss["avg_rr"] >= 1.5:
            rating = "HIGH"
            reason = f"{ss['win_rate']:.0f}% win rate, {ss['avg_rr']:.1f}x R:R. Strong edge confirmed."
        elif ss["win_rate"] >= 50 and ss["avg_rr"] >= 1.0:
            rating = "MEDIUM-HIGH"
            reason = f"Positive edge with decent R:R. Likely to repeat if market conditions hold."
        elif ss["win_rate"] >= 40:
            rating = "MEDIUM"
            reason = f"Borderline win rate. Could go either way. Watch closely."
        elif ss["win_rate"] >= 25 and len(trades) <= 4:
            rating = "MEDIUM-LOW"
            reason = f"Below-average but small sample size. Don't overreact yet."
        else:
            rating = "LOW"
            reason = f"Poor performance ({ss['win_rate']:.0f}% win rate). Needs parameter review before running again."

        lines.append(f"  {name}: {rating} — {reason}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _clean_sym(sym):
    return sym.replace("NSE:", "").replace("-EQ", "")


def _order_status(code):
    status_map = {1: "PENDING", 2: "FILLED", 4: "TRANSIT", 5: "REJECTED", 6: "CANCELLED", 20: "MOD"}
    return status_map.get(code, str(code))


def _safe_call(fn):
    try:
        return fn()
    except Exception:
        return {}
