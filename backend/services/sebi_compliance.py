"""
SEBI Algo Trading Compliance Module for LuckyNavi.

Implements requirements from SEBI circular SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/0000013
"Safer participation of retail investors in Algorithmic trading"
Effective: April 1, 2026.

Key requirements:
  1. Unique Strategy ID (Algo ID) on every algorithmic order
  2. Static IP whitelisting with broker
  3. Orders Per Second (OPS) limit: 10/sec/exchange
  4. Two-Factor Authentication (TOTP) mandatory for every API session
  5. Broker as Principal — all algos registered through broker

This module manages strategy-to-algo-ID mapping and compliance tagging.
"""

import logging
import json
import os
import time
import threading
from typing import Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# ── Audit Log ─────────────────────────────────────────────────────────────
# Every order placed is written to a daily file: backend/tracking/audit/YYYY-MM-DD.jsonl
# One JSON line per order (JSONL format — easy to tail/grep).

_audit_lock = threading.Lock()


def _audit_log_path() -> str:
    """Return today's audit log file path, creating directory if needed."""
    today = datetime.now(IST).strftime("%Y-%m-%d")
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tracking", "audit")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"{today}.jsonl")


def audit_order(order_data: dict, outcome: str = "placed", extra: str = ""):
    """
    Write an audit log entry for every order placed.

    Args:
        order_data: The order parameters dict sent to the broker.
        outcome: 'placed', 'rejected', 'cancelled', 'filled', 'error'
        extra: Optional context string (e.g. strategy, reason for rejection).
    """
    try:
        entry = {
            "ts": datetime.now(IST).isoformat(),
            "outcome": outcome,
            "symbol": order_data.get("symbol", ""),
            "side": order_data.get("side", ""),
            "qty": order_data.get("qty", order_data.get("quantity", "")),
            "price": order_data.get("limitPrice", order_data.get("limit_price", order_data.get("entry_price", ""))),
            "order_type": order_data.get("orderType", order_data.get("order_type", "")),
            "product": order_data.get("productType", order_data.get("product_type", "")),
            "tag": order_data.get("orderTag", order_data.get("order_tag", "")),
            "strategy": order_data.get("strategy", ""),
            "extra": extra,
        }
        line = json.dumps(entry, default=str)
        path = _audit_log_path()
        with _audit_lock:
            with open(path, "a") as f:
                f.write(line + "\n")
    except Exception as e:
        logger.warning(f"[SEBI] Audit log write failed: {e}")


def verify_rate_limit_before_order() -> tuple[bool, str]:
    """
    Check current OPS before placing an order.

    Returns:
        (ok_to_proceed, reason) — if False, caller should not place the order.
    """
    stats = get_ops_stats()
    current_ops = stats["current_ops"]
    safety_limit = stats["safety_limit"]  # 8/sec

    if current_ops >= safety_limit:
        msg = f"Rate limit: {current_ops} orders/sec >= safety limit {safety_limit}/sec — hold order"
        logger.warning(f"[SEBI] {msg}")
        return False, msg

    # Log the upcoming order event
    log_order_event()
    return True, "OK"

# ── Strategy ID Registry ──────────────────────────────────────────────────
# Maps internal strategy keys to exchange-provided Algo IDs.
# These IDs must be obtained from TradeJini after registering each strategy
# with the exchange. Until registered, we use descriptive tags.
#
# Format: "LNAV-{category}-{number}" (LuckyNavi prefix)
# After exchange registration, replace with actual exchange algo IDs.

STRATEGY_ALGO_IDS = {
    # Equity intraday strategies
    "play1_ema_crossover": "LNAV-EQ-001",
    "play2_triple_ma": "LNAV-EQ-002",
    "play3_vwap_pullback": "LNAV-EQ-003",
    "play4_supertrend": "LNAV-EQ-004",
    "play5_bb_squeeze": "LNAV-EQ-005",
    "play6_bb_contra": "LNAV-EQ-006",
    "play7_orb": "LNAV-EQ-007",
    "play8_rsi_divergence": "LNAV-EQ-008",
    "play9_gap_analysis": "LNAV-EQ-009",
    "play10_momentum_rank": "LNAV-EQ-010",

    # Options spread strategies
    "bull_call_spread": "LNAV-OPT-001",
    "bull_put_spread": "LNAV-OPT-002",
    "bear_call_spread": "LNAV-OPT-003",
    "bear_put_spread": "LNAV-OPT-004",
    "iron_condor": "LNAV-OPT-005",
    "long_straddle": "LNAV-OPT-006",

    # Futures strategies
    "fut_ema_rsi_pullback": "LNAV-FUT-001",
    "fut_volume_breakout": "LNAV-FUT-002",
    "fut_mean_reversion": "LNAV-FUT-003",
    "fut_candlestick_reversal": "LNAV-FUT-004",

    # Special order types
    "equity_intraday": "LNAV-EQ-GEN",
    "equity_swing": "LNAV-EQ-SWG",
    "equity_btst": "LNAV-EQ-BTST",
    "options_intraday": "LNAV-OPT-GEN",
    "options_swing": "LNAV-OPT-SWG",
    "futures_intraday": "LNAV-FUT-GEN",
    "futures_swing": "LNAV-FUT-SWG",
    "manual": "LNAV-MANUAL",
    "squareoff": "LNAV-SQOFF",
    "sl_order": "LNAV-SL",
    "emergency_exit": "LNAV-EMRG",
}

# Reverse lookup for validation
_VALID_ALGO_IDS = set(STRATEGY_ALGO_IDS.values())


def get_algo_id(strategy_key: str) -> str:
    """
    Get the SEBI-compliant Algo ID for a given strategy.

    Args:
        strategy_key: Internal strategy identifier (e.g., "play1_ema_crossover")

    Returns:
        Algo ID string to include in the order tag.
        Returns a generic fallback if strategy is not registered.
    """
    algo_id = STRATEGY_ALGO_IDS.get(strategy_key)

    if not algo_id:
        # Fallback: use generic category tag
        if "options" in strategy_key or "spread" in strategy_key:
            algo_id = "LNAV-OPT-GEN"
        elif "fut" in strategy_key:
            algo_id = "LNAV-FUT-GEN"
        else:
            algo_id = "LNAV-EQ-GEN"
        logger.warning(f"[SEBI] No Algo ID registered for strategy '{strategy_key}' — using fallback: {algo_id}")

    return algo_id


def build_order_tag(strategy_key: str, extra: str = "") -> str:
    """
    Build a SEBI-compliant order tag combining the Algo ID with optional context.

    Format: "ALGO_ID|extra_info" (max 20 chars for most brokers)

    Args:
        strategy_key: Strategy identifier
        extra: Optional extra context (e.g., "entry", "sl", "target")

    Returns:
        Order tag string
    """
    algo_id = get_algo_id(strategy_key)

    if extra:
        tag = f"{algo_id}|{extra}"
    else:
        tag = algo_id

    # Most brokers limit order tag length (TradeJini: check docs, typically 20-50 chars)
    return tag[:50]


def validate_order_compliance(order_data: dict) -> tuple[bool, str]:
    """
    Validate that an order meets SEBI compliance requirements.

    Checks:
      1. Order has a strategy/algo tag
      2. OPS rate is within limits (checked separately by broker_client)
      3. 2FA session is active (checked by broker_client.is_authenticated)

    Args:
        order_data: Order parameters dict

    Returns:
        (is_compliant, reason) tuple
    """
    order_tag = order_data.get("orderTag", order_data.get("order_tag", ""))

    if not order_tag:
        return False, "Missing order tag — SEBI requires algo ID on every order"

    # Check if tag contains a recognized algo ID prefix
    if not order_tag.startswith("LNAV-"):
        logger.warning(f"[SEBI] Order tag '{order_tag}' does not have LNAV- prefix")
        # Don't block — legacy tags are allowed during transition

    return True, "OK"


# ── OPS Monitoring ────────────────────────────────────────────────────────
# SEBI limit: 10 orders per second per exchange per client.
# Primary enforcement is in broker_client._enforce_order_rate_limit() (set to 8/sec).
# This module provides monitoring and alerting.

_ops_log: list[dict] = []  # [{timestamp, exchange, count}]


def log_order_event(exchange: str = "NSE"):
    """Log an order event for OPS monitoring."""
    import time
    now = time.time()

    # Keep only last 60 seconds of data
    cutoff = now - 60
    while _ops_log and _ops_log[0]["timestamp"] < cutoff:
        _ops_log.pop(0)

    _ops_log.append({"timestamp": now, "exchange": exchange, "count": 1})


def get_ops_stats() -> dict:
    """
    Get current OPS statistics for monitoring dashboard.

    Returns:
        {
            "current_ops": float,  # Orders per second (last 1s)
            "peak_ops": float,     # Peak OPS in last 60s
            "total_60s": int,      # Total orders in last 60s
            "compliant": bool,     # Under SEBI limit?
        }
    """
    import time
    now = time.time()

    # Current OPS (last 1 second)
    recent = [e for e in _ops_log if now - e["timestamp"] <= 1.0]
    current_ops = len(recent)

    # Peak OPS in last 60 seconds (sliding 1-second windows)
    peak_ops = 0
    for i in range(60):
        window_start = now - i - 1
        window_end = now - i
        window_count = sum(1 for e in _ops_log if window_start <= e["timestamp"] < window_end)
        peak_ops = max(peak_ops, window_count)

    total_60s = len(_ops_log)

    return {
        "current_ops": current_ops,
        "peak_ops": peak_ops,
        "total_60s": total_60s,
        "compliant": peak_ops < 10,
        "sebi_limit": 10,
        "safety_limit": 8,
    }


# ── Compliance Summary ────────────────────────────────────────────────────

def get_compliance_status() -> dict:
    """
    Get overall SEBI compliance status for the system.

    Returns dashboard-ready compliance summary.
    """
    ops = get_ops_stats()

    return {
        "strategy_ids": {
            "status": "configured",
            "total_strategies": len(STRATEGY_ALGO_IDS),
            "note": "Replace LNAV-* prefixes with exchange-issued IDs after registration",
        },
        "ops_limit": {
            "status": "compliant" if ops["compliant"] else "warning",
            "current": ops["current_ops"],
            "peak": ops["peak_ops"],
            "limit": 10,
            "safety_margin": 8,
        },
        "two_factor_auth": {
            "status": "enforced",
            "method": "TOTP",
            "note": "TradeJini requires TOTP for every API session",
        },
        "static_ip": {
            "status": "pending_setup",
            "note": "Register 1-2 static IPv4 addresses with TradeJini",
        },
        "algo_registration": {
            "status": "pending",
            "note": "Register strategies with exchange through TradeJini broker portal",
        },
    }
