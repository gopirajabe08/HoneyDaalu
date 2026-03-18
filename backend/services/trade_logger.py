"""
Persistent trade logger — accumulates all completed trades across days.
Both auto-trader and paper-trader write here when trades close.
Provides per-strategy success percentage and stats.
"""

import json
import os
import logging
from datetime import datetime, timezone, timedelta
from threading import Lock

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".trade_history.json")

_lock = Lock()


def _load_history() -> list[dict]:
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"[TradeLogger] Failed to load history: {e}")
    return []


def _save_history(history: list[dict]):
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2, default=str)
    except Exception as e:
        logger.warning(f"[TradeLogger] Failed to save history: {e}")


def log_trade(trade: dict, source: str = "auto"):
    """
    Append a completed trade to persistent history.
    Called by auto_trader and paper_trader when a trade closes.

    Args:
        trade: trade dict with symbol, strategy, pnl, entry_price, etc.
        source: "auto" or "paper"
    """
    entry = {
        "symbol": trade.get("symbol", ""),
        "strategy": trade.get("strategy", ""),
        "timeframe": trade.get("timeframe", ""),
        "signal_type": trade.get("signal_type", ""),
        "side": trade.get("side", 0),
        "entry_price": trade.get("entry_price", 0),
        "exit_price": trade.get("exit_price", trade.get("ltp", 0)),
        "stop_loss": trade.get("stop_loss", 0),
        "target": trade.get("target", 0),
        "quantity": trade.get("quantity", 0),
        "pnl": round(trade.get("pnl", 0), 2),
        "exit_reason": trade.get("exit_reason", ""),
        "risk_reward_ratio": trade.get("risk_reward_ratio", ""),
        "capital_required": trade.get("capital_required", 0),
        "placed_at": trade.get("placed_at", ""),
        "closed_at": trade.get("closed_at", ""),
        "date": datetime.now(IST).strftime("%Y-%m-%d"),
        "source": source,
    }

    # Options-specific fields (present only for options trades)
    if trade.get("legs") is not None:
        entry["legs"] = trade.get("legs", [])
    if trade.get("spread_type"):
        entry["spread_type"] = trade["spread_type"]
    if trade.get("net_premium") is not None:
        entry["net_premium"] = round(trade.get("net_premium", 0), 2)
    if trade.get("net_premium_per_lot") is not None:
        entry["net_premium_per_lot"] = round(trade.get("net_premium_per_lot", 0), 2)
    if trade.get("underlying"):
        entry["underlying"] = trade["underlying"]
    if trade.get("expiry"):
        entry["expiry"] = trade["expiry"]
    if trade.get("lot_size"):
        entry["lot_size"] = trade["lot_size"]
    if trade.get("max_risk") is not None:
        entry["max_risk"] = round(trade.get("max_risk", 0), 2)
    if trade.get("max_reward") is not None:
        entry["max_reward"] = round(trade.get("max_reward", 0), 2)
    if trade.get("strategy_type"):
        entry["strategy_type"] = trade["strategy_type"]

    with _lock:
        history = _load_history()

        # Dedup: skip if identical trade already logged (same symbol, source, placed_at)
        for existing in reversed(history[-50:]):  # check last 50 for performance
            if (existing.get("symbol") == entry["symbol"]
                    and existing.get("source") == entry["source"]
                    and existing.get("placed_at") == entry["placed_at"]):
                logger.info(f"[TradeLogger] Skipping duplicate: {entry['symbol']} {entry['source']} placed_at={entry['placed_at']}")
                return

        history.append(entry)
        _save_history(history)

    logger.info(f"[TradeLogger] Logged {source} trade: {entry['symbol']} {entry['strategy']} P&L=₹{entry['pnl']}")


def log_trades_batch(trades: list[dict], source: str = "auto"):
    """Log multiple trades at once (e.g. during square-off)."""
    if not trades:
        return
    with _lock:
        history = _load_history()
        # Build dedup set from recent history
        existing_keys = {
            (t.get("symbol"), t.get("source"), t.get("placed_at"))
            for t in history[-100:]
        }
        logged_count = 0
        for trade in trades:
            entry = {
                "symbol": trade.get("symbol", ""),
                "strategy": trade.get("strategy", ""),
                "timeframe": trade.get("timeframe", ""),
                "signal_type": trade.get("signal_type", ""),
                "side": trade.get("side", 0),
                "entry_price": trade.get("entry_price", 0),
                "exit_price": trade.get("exit_price", trade.get("ltp", 0)),
                "stop_loss": trade.get("stop_loss", 0),
                "target": trade.get("target", 0),
                "quantity": trade.get("quantity", 0),
                "pnl": round(trade.get("pnl", 0), 2),
                "exit_reason": trade.get("exit_reason", ""),
                "risk_reward_ratio": trade.get("risk_reward_ratio", ""),
                "capital_required": trade.get("capital_required", 0),
                "placed_at": trade.get("placed_at", ""),
                "closed_at": trade.get("closed_at", ""),
                "date": datetime.now(IST).strftime("%Y-%m-%d"),
                "source": source,
            }
            # Options-specific fields (present only for options trades)
            if trade.get("legs") is not None:
                entry["legs"] = trade.get("legs", [])
            if trade.get("spread_type"):
                entry["spread_type"] = trade["spread_type"]
            if trade.get("net_premium") is not None:
                entry["net_premium"] = round(trade.get("net_premium", 0), 2)
            if trade.get("net_premium_per_lot") is not None:
                entry["net_premium_per_lot"] = round(trade.get("net_premium_per_lot", 0), 2)
            if trade.get("underlying"):
                entry["underlying"] = trade["underlying"]
            if trade.get("expiry"):
                entry["expiry"] = trade["expiry"]
            if trade.get("lot_size"):
                entry["lot_size"] = trade["lot_size"]
            if trade.get("max_risk") is not None:
                entry["max_risk"] = round(trade.get("max_risk", 0), 2)
            if trade.get("max_reward") is not None:
                entry["max_reward"] = round(trade.get("max_reward", 0), 2)
            if trade.get("strategy_type"):
                entry["strategy_type"] = trade["strategy_type"]

            # Dedup check
            key = (entry["symbol"], entry["source"], entry["placed_at"])
            if key in existing_keys:
                continue
            existing_keys.add(key)
            history.append(entry)
            logged_count += 1
        _save_history(history)
    logger.info(f"[TradeLogger] Logged {logged_count}/{len(trades)} {source} trades in batch (deduped)")


def get_strategy_stats(source_filter: str = None) -> dict:
    """
    Compute per-strategy success stats from historical trades.

    Args:
        source_filter: "live" for auto/swing only, "paper" for paper only, None for all.
    Returns dict keyed by strategy_id with wins, losses, pnl, win_rate, etc.
    """
    history = _load_history()

    if source_filter == "live":
        history = [t for t in history if t.get("source") in ("auto", "swing")]
    elif source_filter == "paper":
        history = [t for t in history if t.get("source") in ("paper", "swing_paper")]
    elif source_filter == "auto":
        history = [t for t in history if t.get("source") == "auto"]
    elif source_filter == "swing":
        history = [t for t in history if t.get("source") == "swing"]
    elif source_filter == "options_live":
        history = [t for t in history if t.get("source") in ("options_auto", "options_swing")]
    elif source_filter == "options_paper":
        history = [t for t in history if t.get("source") in ("options_paper", "options_swing_paper")]

    stats = {}
    for t in history:
        key = t.get("strategy", "unknown")
        if not key:
            key = "unknown"
        if key not in stats:
            stats[key] = {
                "strategy": key,
                "total": 0,
                "wins": 0,
                "losses": 0,
                "flat": 0,
                "total_pnl": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "best_trade": 0.0,
                "worst_trade": 0.0,
                "auto_trades": 0,
                "paper_trades": 0,
                "dates_active": set(),
            }

        s = stats[key]
        pnl = t.get("pnl", 0)
        s["total"] += 1
        s["total_pnl"] += pnl

        if pnl > 0:
            s["wins"] += 1
            s["gross_profit"] += pnl
        elif pnl < 0:
            s["losses"] += 1
            s["gross_loss"] += pnl
        else:
            s["flat"] += 1

        if pnl > s["best_trade"]:
            s["best_trade"] = pnl
        if pnl < s["worst_trade"]:
            s["worst_trade"] = pnl

        if t.get("source") == "paper":
            s["paper_trades"] += 1
        else:
            s["auto_trades"] += 1

        date = t.get("date", "")
        if date:
            s["dates_active"].add(date)

    # Compute derived fields
    result = {}
    for key, s in stats.items():
        closed = s["wins"] + s["losses"] + s["flat"]
        result[key] = {
            "strategy": key,
            "total": s["total"],
            "wins": s["wins"],
            "losses": s["losses"],
            "flat": s["flat"],
            "win_rate": round((s["wins"] / closed) * 100, 1) if closed > 0 else 0,
            "total_pnl": round(s["total_pnl"], 2),
            "gross_profit": round(s["gross_profit"], 2),
            "gross_loss": round(s["gross_loss"], 2),
            "avg_pnl": round(s["total_pnl"] / s["total"], 2) if s["total"] > 0 else 0,
            "avg_win": round(s["gross_profit"] / s["wins"], 2) if s["wins"] > 0 else 0,
            "avg_loss": round(s["gross_loss"] / s["losses"], 2) if s["losses"] > 0 else 0,
            "profit_factor": round(s["gross_profit"] / abs(s["gross_loss"]), 2) if s["gross_loss"] < 0 else 0,
            "best_trade": round(s["best_trade"], 2),
            "worst_trade": round(s["worst_trade"], 2),
            "auto_trades": s["auto_trades"],
            "paper_trades": s["paper_trades"],
            "days_traded": len(s["dates_active"]),
        }

    return result


def get_all_trades(days: int = 30) -> list[dict]:
    """Get all trades from the last N days. days=1 means today only."""
    history = _load_history()
    if days <= 0:
        return history

    if days == 1:
        today = datetime.now(IST).strftime("%Y-%m-%d")
        return [t for t in history if t.get("date", "") == today]

    cutoff = (datetime.now(IST) - timedelta(days=days)).strftime("%Y-%m-%d")
    return [t for t in history if t.get("date", "") >= cutoff]
