"""
Options Scanner — scans NIFTY/BANKNIFTY for spread trade setups.

Reads the current market regime (via market_regime.detect_regime), selects the
recommended options strategy, fetches the live option chain from the broker, and
returns fully formed spread signals (legs, strikes, premiums, max risk/reward).
Supports both intraday (weekly expiry) and swing (monthly expiry) modes.
"""

import time
import logging
from datetime import datetime, timezone, timedelta

from services.options_client import get_option_chain, get_nearest_expiry
from services.market_regime import detect_regime
from strategies.options_registry import OPTIONS_STRATEGY_MAP, REGIME_STRATEGY_MAP
from config import (
    OPTIONS_STRATEGY_PARAMS, OPTIONS_EXPIRY_PREFERENCE,
    OPTIONS_MAX_BID_ASK_SPREAD_PCT, OPTIONS_SKIP_EXPIRY_DAY,
)

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


def scan_options(underlying: str, capital: float, mode: str = "intraday") -> dict:
    """
    Scan for options spread setups on a given underlying.

    1. Detect market regime
    2. Map regime -> candidate strategies
    3. Fetch option chain
    4. For each candidate: call strategy.scan()
    5. Filter by risk:reward
    6. Return sorted signals (credit spreads first)
    """
    start_time = time.time()

    # Fix 3: Skip weekly expiry day for intraday (gamma risk)
    if mode == "intraday" and OPTIONS_SKIP_EXPIRY_DAY:
        try:
            _, expiry_date = get_nearest_expiry(underlying, "weekly")
            today = datetime.now(IST).date()
            if today == expiry_date:
                logger.info(f"[OptionsScanner] Skipping {underlying} — today is expiry day (gamma risk)")
                return {
                    "underlying": underlying,
                    "regime": {},
                    "signals": [],
                    "scan_time_seconds": 0,
                    "strategies_checked": 0,
                    "mode": mode,
                    "skipped_reason": "expiry_day",
                }
        except Exception as e:
            logger.warning(f"[OptionsScanner] Expiry day check failed: {e} — proceeding with scan")

    # Detect regime
    regime = detect_regime(underlying)
    conviction = regime.get("conviction", "neutral")

    # Get candidate strategies from regime
    candidate_ids = REGIME_STRATEGY_MAP.get(conviction, ["iron_condor"])

    # Also include credit spread strategies always (they're high probability)
    credit_strategies = ["bull_put_spread", "bear_call_spread", "iron_condor"]
    all_candidates = list(dict.fromkeys(candidate_ids + credit_strategies))

    # P1-002: Block iron condor when VIX > 16 (too much movement risk)
    vix = regime.get("components", {}).get("vix", 0)
    if vix > 16 and "iron_condor" in all_candidates:
        all_candidates.remove("iron_condor")
        logger.info(f"[OptionsScanner] Iron condor blocked — VIX={vix:.1f} > 16")

    # Fetch option chain
    expiry_pref = "monthly" if mode == "swing" else OPTIONS_EXPIRY_PREFERENCE
    chain_data = get_option_chain(underlying, expiry_pref)
    if "error" in chain_data:
        return {"error": chain_data["error"], "underlying": underlying, "signals": []}

    # Scan each strategy
    signals = []
    for strat_id in all_candidates:
        strategy = OPTIONS_STRATEGY_MAP.get(strat_id)
        if not strategy:
            continue
        params = OPTIONS_STRATEGY_PARAMS.get(strat_id, {})
        try:
            signal = strategy.scan(chain_data, regime, underlying, params)
        except Exception as e:
            logger.warning(f"[OptionsScanner] Strategy {strat_id} scan error: {e}")
            continue
        if signal:
            # Check capital sufficiency
            max_risk = signal.get("max_risk", 0)
            if max_risk > capital * 0.1:  # Don't risk more than 10% of capital per trade
                logger.info(f"[OptionsScanner] {strat_id} skipped — max_risk {max_risk} exceeds 10% of capital {capital}")
                continue

            # Fix 2: Bid-ask spread filter — skip signals with wide spreads
            legs = signal.get("legs", [])
            wide_spread = False
            max_spread_pct = 0.0
            chain = chain_data.get("chain", {})
            for leg in legs:
                strike = leg.get("strike", 0)
                option_type = leg.get("option_type", "")
                strike_data = chain.get(strike, {})
                if option_type == "CE":
                    bid = strike_data.get("ce_bid", 0)
                    ask = strike_data.get("ce_ask", 0)
                else:
                    bid = strike_data.get("pe_bid", 0)
                    ask = strike_data.get("pe_ask", 0)

                mid = (bid + ask) / 2 if (bid + ask) > 0 else 0
                spread_pct = ((ask - bid) / mid * 100) if mid > 0 else 100

                if spread_pct > max_spread_pct:
                    max_spread_pct = spread_pct

                if spread_pct > OPTIONS_MAX_BID_ASK_SPREAD_PCT:
                    symbol = leg.get("symbol", "")
                    logger.info(f"[OptionsScanner] {strat_id} skipped — {symbol} bid-ask spread "
                                f"{spread_pct:.1f}% > {OPTIONS_MAX_BID_ASK_SPREAD_PCT}% (bid={bid}, ask={ask})")
                    wide_spread = True
                    break

            if wide_spread:
                continue

            signal["max_bid_ask_spread_pct"] = round(max_spread_pct, 2)
            signal["regime"] = conviction
            signal["strategy_id"] = strat_id
            signals.append(signal)

    # Sort: credit spreads first, then by risk:reward
    def sort_key(s):
        is_credit = 1 if s.get("strategy_type") == "credit" else 0
        max_reward = s.get("max_reward", 0)
        max_risk = max(s.get("max_risk", 1), 1)
        return (is_credit, max_reward / max_risk)

    signals.sort(key=sort_key, reverse=True)

    elapsed = round(time.time() - start_time, 2)

    return {
        "underlying": underlying,
        "regime": regime,
        "signals": signals,
        "scan_time_seconds": elapsed,
        "strategies_checked": len(all_candidates),
        "mode": mode,
    }
