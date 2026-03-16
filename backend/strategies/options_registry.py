"""
Options Strategy Registry — maps strategy IDs to instances
and provides regime-to-strategy recommendation lookup.
"""

from strategies.options_bull_call_spread import BullCallSpread
from strategies.options_bull_put_spread import BullPutSpread
from strategies.options_bear_call_spread import BearCallSpread
from strategies.options_bear_put_spread import BearPutSpread
from strategies.options_iron_condor import IronCondor
from strategies.options_long_straddle import LongStraddle

# ── Strategy instances ─────────────────────────────────────────────────────

OPTIONS_STRATEGY_MAP = {
    "bull_call_spread": BullCallSpread(),
    "bull_put_spread": BullPutSpread(),
    "bear_call_spread": BearCallSpread(),
    "bear_put_spread": BearPutSpread(),
    "iron_condor": IronCondor(),
    "long_straddle": LongStraddle(),
}

# ── Regime to strategy mapping ─────────────────────────────────────────────

REGIME_STRATEGY_MAP = {
    "strongly_bullish": ["bull_call_spread"],
    "mildly_bullish": ["bull_put_spread"],
    "neutral": ["iron_condor"],
    "mildly_bearish": ["bear_call_spread"],
    "strongly_bearish": ["bear_put_spread"],
    "high_volatility": ["long_straddle"],
}


def get_strategy(strategy_id: str):
    """Get a strategy instance by ID."""
    return OPTIONS_STRATEGY_MAP.get(strategy_id)


def get_all_strategies() -> list[dict]:
    """Return info dicts for all registered options strategies."""
    return [
        {"id": sid, **strategy.info()}
        for sid, strategy in OPTIONS_STRATEGY_MAP.items()
    ]


def get_strategies_for_regime(conviction: str) -> list:
    """
    Get strategy instances recommended for a given market regime conviction.

    Args:
        conviction: one of "strongly_bullish", "mildly_bullish", "neutral",
                    "mildly_bearish", "strongly_bearish", "high_volatility"

    Returns:
        list of (strategy_id, strategy_instance) tuples
    """
    strategy_ids = REGIME_STRATEGY_MAP.get(conviction, ["iron_condor"])
    result = []
    for sid in strategy_ids:
        instance = OPTIONS_STRATEGY_MAP.get(sid)
        if instance is not None:
            result.append((sid, instance))
    return result


def get_strategy_info(strategy_id: str) -> dict:
    """Get detailed info for a single strategy."""
    strategy = OPTIONS_STRATEGY_MAP.get(strategy_id)
    if strategy is None:
        return {"error": f"Unknown strategy: {strategy_id}"}
    return {"id": strategy_id, **strategy.info()}
