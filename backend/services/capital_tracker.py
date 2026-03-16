"""
Capital tracker — tracks starting capital, fund additions/withdrawals.
Combined with daily P&L, gives capital_start and capital_end for each trading day.
"""

import json
import os
import logging
from datetime import datetime, timezone, timedelta
from threading import Lock

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
LEDGER_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".capital_ledger.json")

_lock = Lock()


def _load_ledger() -> dict:
    try:
        if os.path.exists(LEDGER_FILE):
            with open(LEDGER_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"[CapitalTracker] Failed to load ledger: {e}")
    return {"initial_capital": 0, "transactions": []}


def _save_ledger(ledger: dict):
    try:
        with open(LEDGER_FILE, "w") as f:
            json.dump(ledger, f, indent=2, default=str)
    except Exception as e:
        logger.warning(f"[CapitalTracker] Failed to save ledger: {e}")


def set_initial_capital(amount: float, source: str = "live") -> dict:
    """Set the initial/starting capital for a source (live or paper)."""
    with _lock:
        ledger = _load_ledger()
        key = f"initial_capital_{source}"
        ledger[key] = round(amount, 2)
        _save_ledger(ledger)
    return {"status": "ok", "source": source, "initial_capital": round(amount, 2)}


def get_initial_capital(source: str = "live") -> float:
    ledger = _load_ledger()
    key = f"initial_capital_{source}"
    return ledger.get(key, ledger.get("initial_capital", 0))


def add_transaction(amount: float, txn_type: str, source: str = "live", note: str = "") -> dict:
    """
    Record a fund addition or withdrawal.

    Args:
        amount: positive number
        txn_type: "add" or "withdraw"
        source: "live" or "paper"
        note: optional description
    """
    if amount <= 0:
        return {"error": "Amount must be positive"}
    if txn_type not in ("add", "withdraw"):
        return {"error": "Type must be 'add' or 'withdraw'"}

    entry = {
        "date": datetime.now(IST).strftime("%Y-%m-%d"),
        "timestamp": datetime.now(IST).isoformat(),
        "type": txn_type,
        "amount": round(amount, 2),
        "source": source,
        "note": note,
    }

    with _lock:
        ledger = _load_ledger()
        if "transactions" not in ledger:
            ledger["transactions"] = []
        ledger["transactions"].append(entry)
        _save_ledger(ledger)

    return {"status": "ok", **entry}


def delete_transaction(index: int, source: str = "live") -> dict:
    """Delete a transaction by index (within the filtered source list)."""
    with _lock:
        ledger = _load_ledger()
        txns = ledger.get("transactions", [])
        # Find the nth transaction matching source
        source_indices = [i for i, t in enumerate(txns) if t.get("source") == source]
        if index < 0 or index >= len(source_indices):
            return {"error": "Invalid transaction index"}
        actual_idx = source_indices[index]
        removed = txns.pop(actual_idx)
        _save_ledger(ledger)
    return {"status": "ok", "removed": removed}


def get_transactions(source: str = "live") -> list[dict]:
    ledger = _load_ledger()
    txns = ledger.get("transactions", [])
    return [t for t in txns if t.get("source") == source]


def get_daily_capital(daily_pnl_rows: list[dict], source: str = "live") -> list[dict]:
    """
    Enrich daily P&L rows with capital_start, capital_end, fund_added, fund_withdrawn.

    Args:
        daily_pnl_rows: sorted list of {date, net_pnl, ...} from daily-pnl endpoint
        source: "live" or "paper"

    Returns:
        Same rows with added capital fields.
    """
    initial = get_initial_capital(source)
    txns = get_transactions(source)

    # Group transactions by date
    txn_by_date = {}
    for t in txns:
        d = t.get("date", "")
        if d not in txn_by_date:
            txn_by_date[d] = {"added": 0, "withdrawn": 0}
        if t["type"] == "add":
            txn_by_date[d]["added"] += t["amount"]
        else:
            txn_by_date[d]["withdrawn"] += t["amount"]

    running_capital = initial
    for row in daily_pnl_rows:
        date = row["date"]
        fund = txn_by_date.get(date, {"added": 0, "withdrawn": 0})

        row["capital_start"] = round(running_capital, 2)
        row["fund_added"] = round(fund["added"], 2)
        row["fund_withdrawn"] = round(fund["withdrawn"], 2)

        # End of day = start + net P&L + funds added - funds withdrawn
        net_pnl = row.get("net_pnl", row.get("total_pnl", 0))
        running_capital = running_capital + net_pnl + fund["added"] - fund["withdrawn"]
        row["capital_end"] = round(running_capital, 2)

    return daily_pnl_rows
