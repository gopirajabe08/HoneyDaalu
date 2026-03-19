"""
Futures Strategy Registry — maps strategy IDs to instances
and provides OI sentiment → strategy filtering rules.
"""

from strategies.futures_volume_breakout import FuturesVolumeBreakout
from strategies.futures_candlestick_reversal import FuturesCandlestickReversal
from strategies.futures_mean_reversion import FuturesMeanReversion
from strategies.futures_ema_rsi_pullback import FuturesEmaRsiPullback
from strategies.play4_supertrend import SupertrendPowerTrend
from strategies.play7_orb import ORBBreakout
from strategies.play8_rsi_divergence import RSIDivergence
from strategies.play9_gap_analysis import GapAnalysis

# ── Strategy instances ─────────────────────────────────────────────────────

FUTURES_STRATEGY_MAP = {
    "futures_volume_breakout": FuturesVolumeBreakout(),
    "futures_candlestick_reversal": FuturesCandlestickReversal(),
    "futures_mean_reversion": FuturesMeanReversion(),
    "futures_ema_rsi_pullback": FuturesEmaRsiPullback(),
    # Equity strategies adapted for futures (same candle logic, applied to F&O stocks)
    "play4_supertrend": SupertrendPowerTrend(),
    "play7_orb": ORBBreakout(),
    "play8_rsi_divergence": RSIDivergence(),
    "play9_gap_analysis": GapAnalysis(),
}

# ── OI Sentiment → Strategy filtering rules ────────────────────────────────
# Which strategies are allowed to fire for each OI sentiment.
# If a stock's OI sentiment is "long_buildup", only these strategies can produce BUY signals.

OI_STRATEGY_RULES = {
    "long_buildup": {
        "futures_volume_breakout": "BUY",
        "futures_ema_rsi_pullback": "BUY",
        "futures_candlestick_reversal": "BUY",
        "futures_mean_reversion": "BUY",
        "play4_supertrend": "BOTH",
        "play7_orb": "BOTH",
        "play8_rsi_divergence": "BOTH",
        "play9_gap_analysis": "BOTH",
    },
    "short_covering": {
        "futures_volume_breakout": "BUY",
        "futures_candlestick_reversal": "BUY",
        "futures_mean_reversion": "BUY",
        "futures_ema_rsi_pullback": "BUY",
        "play4_supertrend": "BOTH",
        "play7_orb": "BOTH",
        "play8_rsi_divergence": "BOTH",
        "play9_gap_analysis": "BOTH",
    },
    "short_buildup": {
        "futures_volume_breakout": "SELL",
        "futures_ema_rsi_pullback": "SELL",
        "futures_candlestick_reversal": "SELL",
        "futures_mean_reversion": "SELL",
        "play4_supertrend": "BOTH",
        "play7_orb": "BOTH",
        "play8_rsi_divergence": "BOTH",
        "play9_gap_analysis": "BOTH",
    },
    "long_unwinding": {
        "futures_volume_breakout": "SELL",
        "futures_candlestick_reversal": "SELL",
        "futures_mean_reversion": "SELL",
        "futures_ema_rsi_pullback": "SELL",
        "play4_supertrend": "BOTH",
        "play7_orb": "BOTH",
        "play8_rsi_divergence": "BOTH",
        "play9_gap_analysis": "BOTH",
    },
}

# ── Timeframe mapping ──────────────────────────────────────────────────────

FUTURES_STRATEGY_TIMEFRAMES = {
    "futures_volume_breakout": ["15m", "1h"],
    "futures_candlestick_reversal": ["15m", "1h"],
    "futures_mean_reversion": ["1h", "1d"],
    "futures_ema_rsi_pullback": ["15m", "1h"],
    "play4_supertrend": ["15m"],
    "play7_orb": ["15m"],
    "play8_rsi_divergence": ["15m"],
    "play9_gap_analysis": ["15m"],
}

FUTURES_SWING_STRATEGY_TIMEFRAMES = {
    "futures_volume_breakout": ["1h", "1d"],
    "futures_candlestick_reversal": ["1h", "1d"],
    "futures_mean_reversion": ["1d"],
    "futures_ema_rsi_pullback": ["1h", "1d"],
    "play4_supertrend": ["1h", "1d"],
    "play8_rsi_divergence": ["1h", "1d"],
}


def get_strategy(strategy_id: str):
    """Get a strategy instance by ID."""
    return FUTURES_STRATEGY_MAP.get(strategy_id)


def get_all_strategies() -> list[dict]:
    """Return info dicts for all registered futures strategies."""
    return [
        {"id": sid, **strategy.info()}
        for sid, strategy in FUTURES_STRATEGY_MAP.items()
    ]


def get_strategy_info(strategy_id: str) -> dict:
    """Get detailed info for a single strategy."""
    strategy = FUTURES_STRATEGY_MAP.get(strategy_id)
    if strategy is None:
        return {"error": f"Unknown strategy: {strategy_id}"}
    return {"id": strategy_id, **strategy.info()}
