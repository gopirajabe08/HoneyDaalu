"""
Algo Specialist Analyser — 6 specialist perspectives on TODAY's trading session.
Each specialist analyses today's data from their domain expertise.
Output format: highlights, lowlights, improvements (no historical data).
"""

import json
import os
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from services import broker_client
from services.auto_trader import auto_trader
from config import INTRADAY_MAX_POSITIONS_CAP as MAX_OPEN_POSITIONS
from services.paper_trader import paper_trader
from services import trade_logger
from config import STRATEGY_TIMEFRAMES

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "strategy_config.json")

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

SPECIALISTS = {
    "strategist": {
        "id": "strategist",
        "name": "Quantitative Trading Strategist",
        "icon": "TrendingUp",
        "color": "orange",
        "description": "Reviews today's strategy performance, win rate, risk-reward, and market alignment. Highlights what worked and what failed.",
    },
    "engineer": {
        "id": "engineer",
        "name": "Algo Systems Engineer",
        "icon": "Cpu",
        "color": "blue",
        "description": "Reviews today's order execution, rejections, BO vs fallback, and system stability.",
    },
    "data_scientist": {
        "id": "data_scientist",
        "name": "Quantitative Data Scientist",
        "icon": "BarChart2",
        "color": "purple",
        "description": "Analyses today's trade data patterns — P&L distribution, duration, edge ratio, and signal quality.",
    },
    "risk_manager": {
        "id": "risk_manager",
        "name": "Risk Management Specialist",
        "icon": "Shield",
        "color": "red",
        "description": "Reviews today's position sizing, SL discipline, drawdown, capital exposure, and worst-case scenarios.",
    },
    "qa_expert": {
        "id": "qa_expert",
        "name": "Strategy Validation Expert",
        "icon": "CheckCircle",
        "color": "green",
        "description": "Validates today's signal correctness — SL/target placement, order modes, exit reasons, and slippage.",
    },
    "performance_analyst": {
        "id": "performance_analyst",
        "name": "Trading Performance Analyst",
        "icon": "Activity",
        "color": "yellow",
        "description": "Reviews today's overall session — P&L, Nifty regime, per-strategy breakdown, and next-session recommendations.",
    },
}


# =====================================================================
#  Public API
# =====================================================================


def get_specialists() -> list[dict]:
    """Return list of all 6 specialists with their metadata."""
    return list(SPECIALISTS.values())


def run_specialist_analysis(specialist_id: str) -> dict:
    """
    Run analysis from a single specialist's perspective — TODAY only.

    Returns:
        {
            "specialist": {...},
            "highlights": ["...", ...],
            "lowlights": ["...", ...],
            "improvements": ["...", ...],
            "metrics": {...},
            "recommendations": [{action, priority, deployable, deploy_key}, ...],
        }
    """
    if specialist_id not in SPECIALISTS:
        return {"error": f"Unknown specialist: {specialist_id}. Valid: {list(SPECIALISTS.keys())}"}

    try:
        data = _collect_data()
    except Exception as e:
        logger.exception(f"[SpecialistAnalyser] Data collection failed: {e}")
        return {
            "specialist": SPECIALISTS[specialist_id],
            "highlights": [],
            "lowlights": [f"Data collection failed: {e}"],
            "improvements": [],
            "metrics": {},
            "recommendations": [],
        }

    dispatch = {
        "strategist": _analyse_strategist,
        "engineer": _analyse_engineer,
        "data_scientist": _analyse_data_scientist,
        "risk_manager": _analyse_risk_manager,
        "qa_expert": _analyse_qa_expert,
        "performance_analyst": _analyse_performance_analyst,
    }

    try:
        result = dispatch[specialist_id](data)
    except Exception as e:
        logger.exception(f"[SpecialistAnalyser] Analysis failed for {specialist_id}: {e}")
        result = {
            "highlights": [],
            "lowlights": [f"Analysis failed: {e}"],
            "improvements": [],
            "metrics": {},
            "recommendations": [],
        }

    result["specialist"] = SPECIALISTS[specialist_id]
    return result


def deploy_recommendation(deploy_key: str) -> dict:
    """
    Execute a specific recommendation identified by deploy_key.

    Supported deploy_keys:
        increase_max_positions / decrease_max_positions
        disable_strategy_<key> / enable_strategy_<key>
        adjust_sl_multiplier_<key>_<up|down>
        adjust_risk_percent_<up|down>

    Returns {"status": "deployed", "change": "..."} or {"error": "..."}.
    """
    try:
        config = _load_config()
    except Exception:
        config = {}

    # ── Max positions (LIVE — takes effect immediately) ──
    if deploy_key == "increase_max_positions":
        old_val = auto_trader.max_open_positions
        new_val = old_val + 1
        if new_val > 8:
            return {"error": "Cannot increase beyond 8 max positions"}
        auto_trader.max_open_positions = new_val
        return {"status": "deployed", "change": f"Max positions: {old_val} -> {new_val}. Active immediately."}

    if deploy_key == "decrease_max_positions":
        old_val = auto_trader.max_open_positions
        new_val = old_val - 1
        if new_val < 1:
            return {"error": "Cannot reduce below 1 max position"}
        auto_trader.max_open_positions = new_val
        return {"status": "deployed", "change": f"Max positions: {old_val} -> {new_val}. Active immediately."}

    # ── Disable / enable strategy ──
    for strat_key in STRATEGY_NAMES:
        if deploy_key == f"disable_strategy_{strat_key}":
            config.setdefault(strat_key, {})["enabled"] = False
            _save_config(config)
            return {"status": "deployed", "change": f"Disabled {STRATEGY_NAMES[strat_key]}. Will be skipped on next scan."}

        if deploy_key == f"enable_strategy_{strat_key}":
            config.setdefault(strat_key, {})["enabled"] = True
            _save_config(config)
            return {"status": "deployed", "change": f"Enabled {STRATEGY_NAMES[strat_key]}. Will be active on next scan."}

    # ── SL multiplier adjustment ──
    for strat_key in STRATEGY_NAMES:
        if deploy_key == f"adjust_sl_multiplier_{strat_key}_up":
            cfg = config.get(strat_key, {})
            current = cfg.get("atr_mult", 1.5)
            new_val = min(round(current + 0.3, 1), 3.5)
            config.setdefault(strat_key, {})["atr_mult"] = new_val
            _save_config(config)
            return {"status": "deployed", "change": f"{STRATEGY_NAMES[strat_key]} ATR multiplier: {current} -> {new_val}"}

        if deploy_key == f"adjust_sl_multiplier_{strat_key}_down":
            cfg = config.get(strat_key, {})
            current = cfg.get("atr_mult", 1.5)
            new_val = max(round(current - 0.3, 1), 0.8)
            config.setdefault(strat_key, {})["atr_mult"] = new_val
            _save_config(config)
            return {"status": "deployed", "change": f"{STRATEGY_NAMES[strat_key]} ATR multiplier: {current} -> {new_val}"}

    # ── Risk percent ──
    if deploy_key == "adjust_risk_percent_up":
        changes = []
        for strat_key in STRATEGY_NAMES:
            cfg = config.get(strat_key, {})
            current = cfg.get("min_pct", 0.005)
            new_val = min(round(current + 0.002, 3), 0.02)
            config.setdefault(strat_key, {})["min_pct"] = new_val
            changes.append(f"{STRATEGY_NAMES[strat_key]}: {current*100:.1f}% -> {new_val*100:.1f}%")
        _save_config(config)
        return {"status": "deployed", "change": "Min SL floor raised: " + "; ".join(changes)}

    if deploy_key == "adjust_risk_percent_down":
        changes = []
        for strat_key in STRATEGY_NAMES:
            cfg = config.get(strat_key, {})
            current = cfg.get("min_pct", 0.005)
            new_val = max(round(current - 0.002, 3), 0.003)
            config.setdefault(strat_key, {})["min_pct"] = new_val
            changes.append(f"{STRATEGY_NAMES[strat_key]}: {current*100:.1f}% -> {new_val*100:.1f}%")
        _save_config(config)
        return {"status": "deployed", "change": "Min SL floor lowered: " + "; ".join(changes)}

    return {"error": f"Unknown deploy_key: {deploy_key}"}


# =====================================================================
#  Data Collection — TODAY ONLY
# =====================================================================


def _collect_data() -> dict:
    """
    Collect today's trading data from all sources.
    No historical data — only what happened today.
    """
    now = datetime.now(IST)
    today_str = now.strftime("%Y-%m-%d")

    # ── Today's trades from trade logger (intraday live only) ──
    all_trades = trade_logger.get_all_trades(days=1)
    today_trades = [t for t in all_trades if t.get("date") == today_str and t.get("source") == "auto"]

    # ── Auto-trader state (intraday live) — filtered to today only ──
    auto_status = auto_trader.status()
    auto_strategies = auto_status.get("strategies", [])
    auto_capital = auto_status.get("capital", 0)
    auto_scan_count = auto_status.get("scan_count", 0)
    auto_order_count = auto_status.get("order_count", 0)
    auto_trade_history = [t for t in auto_status.get("trade_history", [])
                          if (t.get("placed_at") or "")[:10] == today_str]
    auto_active_trades = [t for t in auto_status.get("active_trades", [])
                          if (t.get("placed_at") or "")[:10] == today_str]
    auto_logs = auto_status.get("logs", [])

    # ── Paper-trader state ──
    paper_status = paper_trader.status()
    paper_strategies = paper_status.get("strategies", [])
    paper_capital = paper_status.get("capital", 0)
    paper_scan_count = paper_status.get("scan_count", 0)
    paper_order_count = paper_status.get("order_count", 0)
    paper_trade_history = paper_status.get("trade_history", [])
    paper_active_trades = paper_status.get("active_trades", [])
    paper_logs = paper_status.get("logs", [])

    # ── Broker data (today — graceful if not connected) ──
    positions_raw = _safe_call(broker_client.get_positions)
    orderbook_raw = _safe_call(broker_client.get_orderbook)
    tradebook_raw = _safe_call(broker_client.get_tradebook)

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

    # Parse orderbook
    order_book = orderbook_raw.get("orderBook", []) if orderbook_raw else []
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

    # Parse tradebook
    trade_book = tradebook_raw.get("tradeBook", []) if tradebook_raw else []
    broker_trades = []
    for t in trade_book:
        broker_trades.append({
            "symbol": _clean_sym(t.get("symbol", "")),
            "side": "BUY" if t.get("side") == 1 else "SELL",
            "qty": t.get("tradedQty", 0),
            "price": t.get("tradePrice", 0),
            "value": t.get("tradeValue", 0),
            "product": t.get("productType", ""),
            "time": t.get("orderDateTime", ""),
        })

    # ── Strategy configs ──
    strategy_configs = {}
    try:
        with open(CONFIG_PATH, "r") as f:
            raw_config = json.load(f)
    except Exception:
        raw_config = {}

    for key in STRATEGY_NAMES:
        defaults = {"atr_mult": 1.5, "min_pct": 0.005, "atr_period": 14, "enabled": True, "preferred_timeframe": "15m"}
        cfg = raw_config.get(key, {})
        strategy_configs[key] = {**defaults, **cfg}

    # Detect Nifty regime from auto-trader logs
    nifty_regime = "UNKNOWN"
    for log in reversed(auto_logs):
        msg = log.get("message", "")
        if "Nifty BEARISH" in msg:
            nifty_regime = "BEARISH"
            break
        elif "Nifty BULLISH" in msg:
            nifty_regime = "BULLISH"
            break
        elif "Nifty NEUTRAL" in msg:
            nifty_regime = "NEUTRAL"
            break

    return {
        "today_str": today_str,
        "now": now,
        "nifty_regime": nifty_regime,
        # Today's trades from logger
        "today_trades": today_trades,
        # Auto-trader (live)
        "auto_status": auto_status,
        "auto_strategies": auto_strategies,
        "auto_capital": auto_capital,
        "auto_scan_count": auto_scan_count,
        "auto_order_count": auto_order_count,
        "auto_trade_history": auto_trade_history,
        "auto_active_trades": auto_active_trades,
        "auto_logs": auto_logs,
        # Paper-trader
        "paper_status": paper_status,
        "paper_strategies": paper_strategies,
        "paper_capital": paper_capital,
        "paper_scan_count": paper_scan_count,
        "paper_order_count": paper_order_count,
        "paper_trade_history": paper_trade_history,
        "paper_active_trades": paper_active_trades,
        "paper_logs": paper_logs,
        # Broker data
        "positions": positions,
        "total_pl": round(total_pl, 2),
        "realized_pl": round(realized_pl, 2),
        "unrealized_pl": round(unrealized_pl, 2),
        "orders": orders,
        "filled": filled,
        "rejected": rejected,
        "cancelled": cancelled,
        "pending": pending,
        "broker_trades": broker_trades,
        # Config
        "strategy_configs": strategy_configs,
        "strategy_timeframes": STRATEGY_TIMEFRAMES,
        "max_open_positions": auto_trader.max_open_positions,
    }


# =====================================================================
#  Helper: group today's trades by strategy
# =====================================================================

def _group_by_strategy(trades: list) -> dict:
    """Group trades by strategy key. Returns {strategy_key: {trades, wins, losses, pnl}}."""
    groups = {}
    for t in trades:
        key = t.get("strategy", "unknown")
        if key not in groups:
            groups[key] = {"trades": [], "wins": 0, "losses": 0, "pnl": 0.0}
        g = groups[key]
        g["trades"].append(t)
        pnl = t.get("pnl", 0)
        g["pnl"] += pnl
        if pnl > 0:
            g["wins"] += 1
        elif pnl < 0:
            g["losses"] += 1
    return groups


def _empty_result():
    return {"highlights": [], "lowlights": [], "improvements": [], "metrics": {}, "recommendations": []}


# =====================================================================
#  Specialist: Quantitative Trading Strategist
# =====================================================================


def _analyse_strategist(data: dict) -> dict:
    """How did today's strategies perform against market conditions?"""
    highlights = []
    lowlights = []
    improvements = []
    recommendations = []
    metrics = {}

    # Live trades only (auto-trader)
    all_trades = data["auto_trade_history"] + data["auto_active_trades"]
    closed_trades = [t for t in all_trades if t.get("status") == "CLOSED"]
    nifty = data["nifty_regime"]

    if not all_trades:
        lowlights.append("No trades executed today — either market conditions didn't match or engines weren't running.")
        return {"highlights": highlights, "lowlights": lowlights, "improvements": improvements, "metrics": metrics, "recommendations": recommendations}

    metrics["nifty_regime"] = nifty
    metrics["total_trades"] = len(all_trades)
    metrics["closed_trades"] = len(closed_trades)

    # ── Nifty regime alignment ──
    if nifty == "BEARISH":
        sell_trades = [t for t in all_trades if t.get("signal_type") == "SELL"]
        buy_trades = [t for t in all_trades if t.get("signal_type") == "BUY"]
        if sell_trades and not buy_trades:
            highlights.append(f"Nifty BEARISH — correctly placed only SELL trades ({len(sell_trades)} positions). Trend filter working.")
        elif buy_trades:
            lowlights.append(f"Nifty BEARISH but {len(buy_trades)} BUY trades placed — counter-trend trading.")
    elif nifty == "BULLISH":
        buy_trades = [t for t in all_trades if t.get("signal_type") == "BUY"]
        sell_trades = [t for t in all_trades if t.get("signal_type") == "SELL"]
        if buy_trades and not sell_trades:
            highlights.append(f"Nifty BULLISH — correctly placed only BUY trades ({len(buy_trades)} positions). Trend filter working.")
        elif sell_trades:
            lowlights.append(f"Nifty BULLISH but {len(sell_trades)} SELL trades placed — counter-trend trading.")

    # ── Per-strategy breakdown ──
    strat_groups = _group_by_strategy(closed_trades)
    best_strat = None
    worst_strat = None

    for key, g in strat_groups.items():
        name = STRATEGY_NAMES.get(key, key)
        total = len(g["trades"])
        wins = g["wins"]
        losses = g["losses"]
        pnl = g["pnl"]
        wr = wins / total * 100 if total > 0 else 0

        if total > 0:
            if best_strat is None or pnl > best_strat[1]:
                best_strat = (key, pnl, name, wins, total)
            if worst_strat is None or pnl < worst_strat[1]:
                worst_strat = (key, pnl, name, wins, total)

            if pnl > 0:
                highlights.append(f"{name}: +Rs.{pnl:,.0f} P&L ({wins}/{total} wins, {wr:.0f}% win rate)")
            elif pnl < 0:
                lowlights.append(f"{name}: Rs.{pnl:,.0f} P&L ({wins}/{total} wins, {wr:.0f}% win rate)")

            # R:R check
            avg_win = sum(t.get("pnl", 0) for t in g["trades"] if t.get("pnl", 0) > 0) / max(wins, 1)
            avg_loss = abs(sum(t.get("pnl", 0) for t in g["trades"] if t.get("pnl", 0) < 0) / max(losses, 1))
            if avg_loss > 0:
                actual_rr = avg_win / avg_loss
                if actual_rr < 1.0 and total >= 2:
                    improvements.append(f"{name}: actual R:R is {actual_rr:.1f}:1 (below target). Widen targets or tighten SLs.")

    if best_strat and best_strat[1] > 0:
        metrics["best_strategy"] = best_strat[2]
        metrics["best_pnl"] = round(best_strat[1], 2)
    if worst_strat and worst_strat[1] < 0:
        metrics["worst_strategy"] = worst_strat[2]
        metrics["worst_pnl"] = round(worst_strat[1], 2)
        if worst_strat[3] == 0 and len(strat_groups[worst_strat[0]]["trades"]) >= 2:
            recommendations.append({"action": f"Pause {worst_strat[2]} — 0 wins today",
                                    "priority": "high", "deployable": True, "deploy_key": f"disable_strategy_{worst_strat[0]}"})
            improvements.append(f"Consider pausing {worst_strat[2]} — zero wins today. Market may not suit this strategy type ({STRATEGY_PARAMS.get(worst_strat[0], {}).get('ideal_market', 'unknown')}).")

    # ── Strategy suitability vs market ──
    if nifty == "BEARISH":
        trend_strats = [k for k in strat_groups if STRATEGY_PARAMS.get(k, {}).get("type") == "trend-following"]
        if trend_strats:
            sell_pnl = sum(strat_groups[k]["pnl"] for k in trend_strats)
            if sell_pnl > 0:
                highlights.append(f"Trend-following strategies profitable in bearish market (+Rs.{sell_pnl:,.0f}). Good strategy-market alignment.")
            else:
                lowlights.append(f"Trend-following strategies lost Rs.{abs(sell_pnl):,.0f} despite bearish market. Signal timing may be off.")

    # ── Signal quality from logs ──
    total_signals = 0
    for log in data["auto_logs"]:
        msg = log.get("message", "")
        if "unique signals" in msg:
            try:
                num = int(msg.split(",")[0].split()[-1])
                total_signals = max(total_signals, num)
            except (ValueError, IndexError):
                pass

    orders_placed = data["auto_order_count"]
    if total_signals > 0 and orders_placed > 0:
        conversion = orders_placed / total_signals * 100
        if conversion < 10:
            lowlights.append(f"Low signal conversion: {orders_placed} orders from {total_signals} signals ({conversion:.0f}%). Most signals filtered or slots full.")
        metrics["signal_count"] = total_signals
        metrics["conversion_rate"] = round(conversion, 1)

    # ── Regime-based next session advice ──
    if nifty == "BEARISH":
        improvements.append("Market was BEARISH. For next session if expecting continuation: prioritize Supertrend (SELL), VWAP Pullback (short pullbacks).")
    elif nifty == "BULLISH":
        improvements.append("Market was BULLISH. For next session if expecting continuation: prioritize EMA Crossover + Triple MA (BUY), Supertrend (momentum).")
    else:
        improvements.append("Market was NEUTRAL. Diversify across strategy types — both trend-following and mean-reversion.")

    total_pnl = sum(t.get("pnl", 0) for t in closed_trades)
    metrics["total_pnl"] = round(total_pnl, 2)

    return {"highlights": highlights, "lowlights": lowlights, "improvements": improvements, "metrics": metrics, "recommendations": recommendations}


# =====================================================================
#  Specialist: Algo Systems Engineer
# =====================================================================


def _analyse_engineer(data: dict) -> dict:
    """How did the execution system perform today?"""
    highlights = []
    lowlights = []
    improvements = []
    recommendations = []
    metrics = {}

    orders = data["orders"]
    filled = data["filled"]
    rejected = data["rejected"]
    cancelled = data["cancelled"]
    auto_logs = data["auto_logs"]
    auto_trades = data["auto_trade_history"] + data["auto_active_trades"]

    total_orders = len(orders)
    metrics["total_orders"] = total_orders
    metrics["filled"] = len(filled)
    metrics["rejected"] = len(rejected)

    # ── Order execution ──
    if total_orders > 0:
        fill_rate = len(filled) / total_orders * 100
        reject_rate = len(rejected) / total_orders * 100
        metrics["fill_rate"] = round(fill_rate, 1)

        if fill_rate >= 80:
            highlights.append(f"Order fill rate: {fill_rate:.0f}% ({len(filled)}/{total_orders} filled)")
        if reject_rate > 20:
            lowlights.append(f"High rejection rate: {reject_rate:.0f}% ({len(rejected)}/{total_orders} rejected)")
        elif rejected:
            lowlights.append(f"{len(rejected)} order(s) rejected")
    elif data["auto_status"].get("is_running"):
        lowlights.append("Auto-trader running but 0 orders placed today. Slots may be full or no signals passed filters.")

    # ── Rejection breakdown ──
    if rejected:
        rejection_reasons = defaultdict(list)
        for r in rejected:
            msg = r["message"].lower()
            if "tick" in msg or "price" in msg:
                rejection_reasons["tick_size"].append(r)
            elif "margin" in msg or "fund" in msg:
                rejection_reasons["margin"].append(r)
            else:
                rejection_reasons["other"].append(r)

        for reason, rej_list in rejection_reasons.items():
            if reason == "margin":
                lowlights.append(f"{len(rej_list)} orders rejected due to insufficient margin")
                improvements.append("Increase broker funds or reduce capital per trade to avoid margin rejections.")
            elif reason == "tick_size":
                highlights.append(f"{len(rej_list)} tick-size rejections handled by auto-retry mechanism")

    # ── BO vs INTRADAY_SL ──
    bo_count = sum(1 for t in auto_trades if t.get("order_mode") == "BO")
    sl_count = sum(1 for t in auto_trades if t.get("order_mode") == "INTRADAY_SL")
    total_mode = bo_count + sl_count
    if total_mode > 0:
        metrics["bo_orders"] = bo_count
        metrics["intraday_sl_orders"] = sl_count
        if sl_count > bo_count:
            highlights.append(f"INTRADAY_SL fallback handled {sl_count}/{total_mode} orders correctly (BO rejected by broker for equity)")
        elif bo_count > 0:
            highlights.append(f"{bo_count}/{total_mode} orders placed as Bracket Orders (BO)")

    # ── System stability ──
    error_logs = [l for l in auto_logs if l.get("level") == "ERROR"]
    warn_logs = [l for l in auto_logs if l.get("level") == "WARN"]
    restore_logs = [l for l in auto_logs if l.get("level") == "RESTORE"]

    if not error_logs:
        highlights.append("Zero errors in auto-trader logs — system stable")
    else:
        lowlights.append(f"{len(error_logs)} errors in auto-trader logs today")
        for el in error_logs[-3:]:
            lowlights.append(f"  ERROR: {el.get('message', '')[:100]}")
        improvements.append("Investigate auto-trader errors — check broker auth, network, and order parameters.")

    if restore_logs:
        lowlights.append(f"{len(restore_logs)} auto-trader restart(s) detected today")
        improvements.append("Multiple restarts indicate server instability. Check if backend crashed or was manually restarted.")

    # ── Scan performance ──
    auto_scans = data["auto_scan_count"]
    metrics["auto_scans"] = auto_scans

    if auto_scans > 0:
        highlights.append(f"Live auto-trader completed {auto_scans} scan(s) today (on-demand mode)")

    return {"highlights": highlights, "lowlights": lowlights, "improvements": improvements, "metrics": metrics, "recommendations": recommendations}


# =====================================================================
#  Specialist: Quantitative Data Scientist
# =====================================================================


def _analyse_data_scientist(data: dict) -> dict:
    """What do today's numbers tell us?"""
    highlights = []
    lowlights = []
    improvements = []
    recommendations = []
    metrics = {}

    # Live closed trades only (auto-trader)
    all_closed = [t for t in data["auto_trade_history"] if t.get("status") == "CLOSED"]

    if not all_closed:
        lowlights.append("No closed trades today for statistical analysis.")
        return {"highlights": highlights, "lowlights": lowlights, "improvements": improvements, "metrics": metrics, "recommendations": recommendations}

    pnl_values = [t.get("pnl", 0) for t in all_closed]
    wins = [p for p in pnl_values if p > 0]
    losses = [p for p in pnl_values if p < 0]

    total = len(pnl_values)
    win_rate = len(wins) / total * 100 if total > 0 else 0
    total_pnl = sum(pnl_values)
    mean_pnl = total_pnl / total

    metrics["total_closed"] = total
    metrics["win_rate"] = round(win_rate, 1)
    metrics["mean_pnl"] = round(mean_pnl, 2)
    metrics["total_pnl"] = round(total_pnl, 2)

    # ── Win rate ──
    if win_rate >= 50:
        highlights.append(f"Win rate: {win_rate:.0f}% ({len(wins)}W / {len(losses)}L out of {total} trades)")
    else:
        lowlights.append(f"Win rate below 50%: {win_rate:.0f}% ({len(wins)}W / {len(losses)}L out of {total} trades)")

    # ── Edge ratio ──
    if wins and losses:
        avg_win = sum(wins) / len(wins)
        avg_loss = abs(sum(losses) / len(losses))
        edge_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        metrics["avg_win"] = round(avg_win, 2)
        metrics["avg_loss"] = round(avg_loss, 2)
        metrics["edge_ratio"] = round(edge_ratio, 2)

        if edge_ratio >= 1.5:
            highlights.append(f"Strong edge ratio: {edge_ratio:.1f}:1 (avg win Rs.{avg_win:,.0f} vs avg loss Rs.{avg_loss:,.0f})")
        elif edge_ratio >= 1.0:
            highlights.append(f"Positive edge ratio: {edge_ratio:.1f}:1")
        else:
            lowlights.append(f"Losses larger than wins: edge ratio {edge_ratio:.1f}:1 (avg loss Rs.{avg_loss:,.0f} > avg win Rs.{avg_win:,.0f})")
            improvements.append("Tighten SLs or widen targets to improve edge ratio above 1.0.")
            recommendations.append({"action": "Tighten SL floor to reduce average loss size",
                                    "priority": "medium", "deployable": True, "deploy_key": "adjust_risk_percent_down"})

    # ── Expectancy ──
    if mean_pnl > 0:
        highlights.append(f"Positive expectancy: Rs.{mean_pnl:+,.0f} per trade (total Rs.{total_pnl:+,.0f})")
    elif mean_pnl < 0:
        lowlights.append(f"Negative expectancy: Rs.{mean_pnl:+,.0f} per trade (total Rs.{total_pnl:+,.0f})")
        improvements.append("System lost money on average per trade. Review which strategy is dragging performance.")

    # ── Trade duration ──
    durations = []
    for t in all_closed:
        placed = t.get("placed_at", "")
        closed = t.get("closed_at", "")
        if placed and closed:
            try:
                dur_min = (datetime.fromisoformat(closed) - datetime.fromisoformat(placed)).total_seconds() / 60
                if dur_min > 0:
                    durations.append(dur_min)
            except (ValueError, TypeError):
                pass

    if durations:
        avg_dur = sum(durations) / len(durations)
        metrics["avg_duration_min"] = round(avg_dur, 1)

        quick_exits = [d for d in durations if d < 15]
        if quick_exits and len(quick_exits) > total * 0.5:
            lowlights.append(f"{len(quick_exits)}/{total} trades exited in <15 min — SLs may be too tight or market too volatile")
            improvements.append("Widen ATR multiplier to give trades more room and reduce premature stop-outs.")
            recommendations.append({"action": "Widen SL by increasing ATR multiplier",
                                    "priority": "medium", "deployable": True, "deploy_key": "adjust_risk_percent_up"})
        else:
            highlights.append(f"Average trade duration: {avg_dur:.0f} minutes")

    # ── Consecutive losses ──
    max_consec_loss = 0
    current_streak = 0
    for pnl in pnl_values:
        if pnl < 0:
            current_streak += 1
            max_consec_loss = max(max_consec_loss, current_streak)
        else:
            current_streak = 0

    metrics["max_consecutive_losses"] = max_consec_loss
    if max_consec_loss >= 3:
        lowlights.append(f"Max consecutive losses today: {max_consec_loss} in a row")
        improvements.append("Consider reducing max positions during losing streaks to limit damage.")
    elif max_consec_loss <= 1 and total >= 3:
        highlights.append("No significant losing streaks today — losses well distributed")

    # ── BUY vs SELL direction ──
    buy_trades = [t for t in all_closed if t.get("signal_type") == "BUY"]
    sell_trades = [t for t in all_closed if t.get("signal_type") == "SELL"]
    if buy_trades and sell_trades:
        buy_pnl = sum(t.get("pnl", 0) for t in buy_trades)
        sell_pnl = sum(t.get("pnl", 0) for t in sell_trades)
        if sell_pnl > buy_pnl and sell_pnl > 0:
            highlights.append(f"SELL signals outperformed: Rs.{sell_pnl:+,.0f} vs BUY Rs.{buy_pnl:+,.0f}")
        elif buy_pnl > sell_pnl and buy_pnl > 0:
            highlights.append(f"BUY signals outperformed: Rs.{buy_pnl:+,.0f} vs SELL Rs.{sell_pnl:+,.0f}")
        metrics["buy_pnl"] = round(buy_pnl, 2)
        metrics["sell_pnl"] = round(sell_pnl, 2)

    return {"highlights": highlights, "lowlights": lowlights, "improvements": improvements, "metrics": metrics, "recommendations": recommendations}


# =====================================================================
#  Specialist: Risk Management Specialist
# =====================================================================


def _analyse_risk_manager(data: dict) -> dict:
    """How well was risk managed today?"""
    highlights = []
    lowlights = []
    improvements = []
    recommendations = []
    metrics = {}

    all_trades = data["auto_trade_history"] + data["auto_active_trades"]
    capital = data["auto_capital"]
    positions = data["positions"]
    active_trades = data["auto_active_trades"]
    max_pos = data["max_open_positions"]

    if not all_trades and not positions:
        lowlights.append("No trades or positions today for risk analysis.")
        return {"highlights": highlights, "lowlights": lowlights, "improvements": improvements, "metrics": metrics, "recommendations": recommendations}

    # ── Risk per trade ──
    risk_pcts = []
    for t in all_trades:
        entry = t.get("entry_price", 0)
        sl = t.get("stop_loss", 0)
        qty = t.get("quantity", 0)
        if entry > 0 and sl > 0 and qty > 0 and capital > 0:
            risk_amount = abs(entry - sl) * qty
            risk_pcts.append(risk_amount / capital * 100)

    if risk_pcts:
        avg_risk = sum(risk_pcts) / len(risk_pcts)
        max_risk = max(risk_pcts)
        metrics["avg_risk_pct"] = round(avg_risk, 2)
        metrics["max_risk_pct"] = round(max_risk, 2)

        if avg_risk <= 2.2:
            highlights.append(f"Risk per trade within 2% target: avg {avg_risk:.1f}% of capital")
        elif avg_risk <= 3.0:
            lowlights.append(f"Risk per trade slightly elevated: avg {avg_risk:.1f}% (target: 2%)")
            improvements.append("Tighten position sizing to bring risk back to 2% target.")
        else:
            lowlights.append(f"Risk per trade too high: avg {avg_risk:.1f}% (target: 2%)")
            recommendations.append({"action": "Lower ATR multiplier to reduce per-trade risk",
                                    "priority": "high", "deployable": True, "deploy_key": "adjust_risk_percent_down"})

        if max_risk > 4.0:
            lowlights.append(f"Worst single trade risked {max_risk:.1f}% of capital — dangerously high")

    # ── SL distance ──
    sl_pcts = []
    for t in all_trades:
        entry = t.get("entry_price", 0)
        sl = t.get("stop_loss", 0)
        if entry > 0 and sl > 0:
            sl_pcts.append(abs(entry - sl) / entry * 100)

    if sl_pcts:
        avg_sl = sum(sl_pcts) / len(sl_pcts)
        metrics["avg_sl_distance_pct"] = round(avg_sl, 2)

        tight_count = sum(1 for s in sl_pcts if s < 0.3)
        wide_count = sum(1 for s in sl_pcts if s > 3.0)

        if tight_count > 0:
            lowlights.append(f"{tight_count} trades with extremely tight SL (<0.3%) — likely stopped by noise")
            improvements.append("Increase ATR multiplier for strategies with very tight SLs.")
        if wide_count > 0:
            lowlights.append(f"{wide_count} trades with wide SL (>3.0%) — excessive risk per trade")
        if tight_count == 0 and wide_count == 0:
            highlights.append(f"SL distances healthy: avg {avg_sl:.1f}% from entry")

    # ── Worst case (all active SLs hit) ──
    if active_trades and capital > 0:
        worst_case_loss = 0
        for t in active_trades:
            entry = t.get("entry_price", 0)
            sl = t.get("stop_loss", 0)
            qty = t.get("quantity", 0)
            if entry > 0 and sl > 0 and qty > 0:
                worst_case_loss += abs(entry - sl) * qty

        if worst_case_loss > 0:
            wc_pct = worst_case_loss / capital * 100
            metrics["worst_case_pct"] = round(wc_pct, 1)

            if wc_pct > 8:
                lowlights.append(f"Worst case if all {len(active_trades)} SLs hit: Rs.{worst_case_loss:,.0f} ({wc_pct:.1f}% of capital)")
                recommendations.append({"action": f"Reduce max positions from {max_pos} to {max(max_pos - 1, 2)}",
                                        "priority": "high", "deployable": True, "deploy_key": "decrease_max_positions"})
            elif wc_pct > 5:
                lowlights.append(f"Worst case: Rs.{worst_case_loss:,.0f} ({wc_pct:.1f}% of capital) if all active SLs hit")
            else:
                highlights.append(f"Max risk exposure: {wc_pct:.1f}% of capital — within acceptable limits")

    # ── Capital utilization ──
    open_positions = [p for p in positions if p["net_qty"] != 0 and p["product"] in ("INTRADAY", "BO")]
    if open_positions and capital > 0:
        total_deployed = sum(abs(p["net_qty"]) * p.get("ltp", p.get("buy_avg", 0)) for p in open_positions)
        utilization = total_deployed / capital * 100
        metrics["capital_utilization"] = round(utilization, 1)

        if utilization > 80:
            lowlights.append(f"Capital utilization high: {utilization:.0f}% deployed")
        else:
            highlights.append(f"Capital utilization: {utilization:.0f}% — room for additional positions")

    # ── Intraday drawdown ──
    closed = [t for t in all_trades if t.get("status") == "CLOSED"]
    if closed:
        cumulative = 0
        peak = 0
        max_dd = 0
        for t in closed:
            cumulative += t.get("pnl", 0)
            peak = max(peak, cumulative)
            max_dd = max(max_dd, peak - cumulative)

        if max_dd > 0 and capital > 0:
            dd_pct = max_dd / capital * 100
            metrics["intraday_drawdown"] = round(max_dd, 2)
            if dd_pct > 3:
                lowlights.append(f"Intraday drawdown: Rs.{max_dd:,.0f} ({dd_pct:.1f}% of capital)")
            else:
                highlights.append(f"Intraday drawdown contained: Rs.{max_dd:,.0f} ({dd_pct:.1f}%)")

    return {"highlights": highlights, "lowlights": lowlights, "improvements": improvements, "metrics": metrics, "recommendations": recommendations}


# =====================================================================
#  Specialist: Strategy Validation Expert
# =====================================================================


def _analyse_qa_expert(data: dict) -> dict:
    """Were today's signals and executions correct?"""
    highlights = []
    lowlights = []
    improvements = []
    recommendations = []
    metrics = {}

    all_trades = data["auto_trade_history"] + data["auto_active_trades"]
    orders = data["orders"]
    broker_trades = data["broker_trades"]
    strategy_configs = data["strategy_configs"]
    active_strategies = data["auto_strategies"]

    if not all_trades and not orders:
        lowlights.append("No trades or orders today for validation.")
        return {"highlights": highlights, "lowlights": lowlights, "improvements": improvements, "metrics": metrics, "recommendations": recommendations}

    # ── SL/Target placement validation ──
    sl_issues = 0
    target_issues = 0
    for t in all_trades:
        entry = t.get("entry_price", 0)
        sl = t.get("stop_loss", 0)
        target = t.get("target", 0)
        signal_type = t.get("signal_type", "")

        if entry > 0 and sl > 0:
            if signal_type == "BUY" and sl >= entry:
                sl_issues += 1
            elif signal_type == "SELL" and sl <= entry:
                sl_issues += 1

        if entry > 0 and target > 0:
            if signal_type == "BUY" and target <= entry:
                target_issues += 1
            elif signal_type == "SELL" and target >= entry:
                target_issues += 1

    if sl_issues == 0 and all_trades:
        highlights.append(f"All {len(all_trades)} trades have correctly placed SL (below entry for BUY, above for SELL)")
    elif sl_issues > 0:
        lowlights.append(f"{sl_issues} trades with INVALID SL placement — critical logic bug")
        improvements.append("Fix SL calculation in affected strategy — SL must be below entry for BUY and above for SELL.")

    if target_issues > 0:
        lowlights.append(f"{target_issues} trades with INVALID target placement")
    elif all_trades:
        highlights.append("All target prices correctly placed")

    # ── Exit reason distribution ──
    exit_reasons = defaultdict(int)
    for t in all_trades:
        reason = t.get("exit_reason", "")
        if reason:
            exit_reasons[reason] += 1

    if exit_reasons:
        sl_hits = exit_reasons.get("SL_HIT", 0)
        target_hits = exit_reasons.get("TARGET_HIT", 0)
        square_offs = exit_reasons.get("SQUARE_OFF", 0)
        metrics["exit_reasons"] = dict(exit_reasons)

        if sl_hits + target_hits > 0:
            target_rate = target_hits / (sl_hits + target_hits) * 100
            metrics["target_hit_rate"] = round(target_rate, 1)

            if target_rate >= 50:
                highlights.append(f"Target hit rate: {target_rate:.0f}% ({target_hits} targets vs {sl_hits} SLs)")
            else:
                lowlights.append(f"Low target hit rate: {target_rate:.0f}% ({target_hits} targets vs {sl_hits} SLs)")

        if square_offs > 0:
            lowlights.append(f"{square_offs} trades closed by 3:15 PM square-off (didn't hit SL or target)")
            improvements.append("Trades not resolving before square-off suggests R:R targets may be too ambitious or entry timing is late.")

    # ── Signal direction check ──
    buy_count = sum(1 for t in all_trades if t.get("signal_type") == "BUY")
    sell_count = sum(1 for t in all_trades if t.get("signal_type") == "SELL")
    metrics["buy_signals"] = buy_count
    metrics["sell_signals"] = sell_count

    if buy_count > 0 and sell_count > 0:
        highlights.append(f"Bidirectional signals active: {buy_count} BUY + {sell_count} SELL")
    elif buy_count > 0 and sell_count == 0:
        highlights.append(f"Only BUY signals today ({buy_count}) — consistent with Nifty trend filter in bullish market")
    elif sell_count > 0 and buy_count == 0:
        highlights.append(f"Only SELL signals today ({sell_count}) — consistent with Nifty trend filter in bearish market")

    # ── Slippage (signal entry vs actual fill) ──
    if broker_trades and all_trades:
        matched_slippage = []
        for bt in broker_trades:
            for t in all_trades:
                if bt["symbol"] == t.get("symbol", "") and bt["side"] == t.get("signal_type", ""):
                    signal_entry = t.get("entry_price", 0)
                    actual_fill = bt.get("price", 0)
                    if signal_entry > 0 and actual_fill > 0:
                        slip_pct = abs(actual_fill - signal_entry) / signal_entry * 100
                        matched_slippage.append(slip_pct)
                        break

        if matched_slippage:
            avg_slip = sum(matched_slippage) / len(matched_slippage)
            metrics["avg_slippage_pct"] = round(avg_slip, 3)
            if avg_slip < 0.1:
                highlights.append(f"Minimal slippage: avg {avg_slip:.3f}% across {len(matched_slippage)} fills")
            elif avg_slip > 0.3:
                lowlights.append(f"High slippage: avg {avg_slip:.2f}% — eating into profits")
                improvements.append("Consider using limit orders or trading more liquid stocks to reduce slippage.")

    # ── Config validation ──
    active_keys = [s.get("strategy") for s in active_strategies]
    for key in STRATEGY_NAMES:
        cfg = strategy_configs.get(key, {})
        if not cfg.get("enabled", True) and key in active_keys:
            lowlights.append(f"{STRATEGY_NAMES[key]} is disabled in config but running — config may not be reloaded")

    return {"highlights": highlights, "lowlights": lowlights, "improvements": improvements, "metrics": metrics, "recommendations": recommendations}


# =====================================================================
#  Specialist: Trading Performance Analyst
# =====================================================================


def _analyse_performance_analyst(data: dict) -> dict:
    """Overall session verdict — how did today go?"""
    highlights = []
    lowlights = []
    improvements = []
    recommendations = []
    metrics = {}

    nifty = data["nifty_regime"]

    # ── Live performance only ──
    live_closed = [t for t in data["auto_trade_history"] if t.get("status") == "CLOSED"]
    live_open = data["auto_active_trades"]
    live_pnl = data["total_pl"]  # from broker (source of truth)
    live_realized = data["realized_pl"]
    live_unrealized = data["unrealized_pl"]

    metrics["nifty_regime"] = nifty
    metrics["live_realized_pl"] = round(live_realized, 2)
    metrics["live_unrealized_pl"] = round(live_unrealized, 2)
    metrics["live_total_pl"] = round(live_pnl, 2)
    metrics["live_trades"] = len(live_closed) + len(live_open)

    if live_realized > 0:
        highlights.append(f"Realized P&L: +Rs.{live_realized:,.0f}")
    elif live_realized < 0:
        lowlights.append(f"Realized P&L: Rs.{live_realized:,.0f}")

    if live_open:
        if live_unrealized > 0:
            highlights.append(f"{len(live_open)} open position(s) with +Rs.{live_unrealized:,.0f} unrealized profit")
        elif live_unrealized < 0:
            lowlights.append(f"{len(live_open)} open position(s) with Rs.{live_unrealized:,.0f} unrealized loss")

    # ── Per-strategy breakdown (live only) ──
    strat_groups = _group_by_strategy(live_closed)

    if strat_groups:
        for key, g in sorted(strat_groups.items(), key=lambda x: x[1]["pnl"], reverse=True):
            name = STRATEGY_NAMES.get(key, key)
            total = len(g["trades"])
            wr = g["wins"] / total * 100 if total > 0 else 0
            pnl = g["pnl"]

            if pnl > 0:
                highlights.append(f"{name}: +Rs.{pnl:,.0f} | {g['wins']}W/{g['losses']}L ({wr:.0f}%)")
            elif pnl < 0:
                lowlights.append(f"{name}: Rs.{pnl:,.0f} | {g['wins']}W/{g['losses']}L ({wr:.0f}%)")

    # ── Market regime assessment ──
    if nifty != "UNKNOWN":
        highlights.append(f"Market regime: Nifty {nifty} — trend filter correctly applied")

    # ── Scan efficiency ──
    auto_scans = data["auto_scan_count"]
    auto_orders = data["auto_order_count"]

    if auto_scans > 0:
        metrics["live_scan_to_order"] = f"{auto_orders} orders from {auto_scans} scans"

    # ── Session verdict ──
    if live_realized > 0:
        highlights.append(f"Session verdict: PROFITABLE day (+Rs.{live_realized:,.0f} realized)")
    elif live_realized < 0:
        lowlights.append(f"Session verdict: LOSING day (Rs.{live_realized:,.0f} realized)")
    elif not live_closed:
        lowlights.append("Session verdict: No closed trades yet")

    # ── Next session improvements ──
    if strat_groups:
        worst_key = min(strat_groups.keys(), key=lambda k: strat_groups[k]["pnl"])
        worst_g = strat_groups[worst_key]
        worst_name = STRATEGY_NAMES.get(worst_key, worst_key)
        if worst_g["pnl"] < 0 and worst_g["wins"] == 0 and len(worst_g["trades"]) >= 2:
            improvements.append(f"Pause {worst_name} for next session — 0 wins, Rs.{worst_g['pnl']:,.0f} loss today.")
            recommendations.append({"action": f"Disable {worst_name}",
                                    "priority": "high", "deployable": True, "deploy_key": f"disable_strategy_{worst_key}"})

        best_key = max(strat_groups.keys(), key=lambda k: strat_groups[k]["pnl"])
        best_g = strat_groups[best_key]
        best_name = STRATEGY_NAMES.get(best_key, best_key)
        if best_g["pnl"] > 0:
            improvements.append(f"Keep {best_name} — best performer today (+Rs.{best_g['pnl']:,.0f}).")

    # Regime-based advice
    if nifty == "BEARISH":
        improvements.append("Market was BEARISH. If expecting continuation tomorrow: prioritize Supertrend (SELL signals), VWAP short pullbacks.")
    elif nifty == "BULLISH":
        improvements.append("Market was BULLISH. If expecting continuation: prioritize EMA Crossover, Triple MA (BUY signals).")
    else:
        improvements.append("Market was NEUTRAL. Diversify across strategy types for next session.")

    return {"highlights": highlights, "lowlights": lowlights, "improvements": improvements, "metrics": metrics, "recommendations": recommendations}


# =====================================================================
#  Helpers
# =====================================================================


def _safe_call(fn):
    """Call a function, returning {} on any error."""
    try:
        return fn()
    except Exception:
        return {}


def _clean_sym(sym: str) -> str:
    return sym.replace("NSE:", "").replace("-EQ", "")


def _order_status(code) -> str:
    status_map = {1: "PENDING", 2: "FILLED", 4: "TRANSIT", 5: "REJECTED", 6: "CANCELLED", 20: "MOD"}
    return status_map.get(code, str(code))


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
