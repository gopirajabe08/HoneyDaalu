"""
Bull Call Spread — Buy lower strike CE + Sell higher strike CE (debit spread).
Used when conviction is strongly bullish.
Profits when underlying moves up above the lower strike + net debit.
"""

from typing import Optional

from config import OPTIONS_STRIKE_INTERVAL
from strategies.options_base import OptionsBaseStrategy


class BullCallSpread(OptionsBaseStrategy):
    name = "Bull Call Spread"
    description = "Buy ITM/ATM CE + Sell OTM CE. Debit spread for strongly bullish conviction."
    spread_type = "bull_call_spread"
    strategy_type = "debit"
    win_rate_estimate = "~45-50% (directional, needs move up)"

    def select_strikes(self, chain: dict, atm_strike: int, underlying: str, params: dict) -> Optional[list[dict]]:
        """
        Select strikes for bull call spread.
        Buy CE at ATM, Sell CE at ATM + (otm_offset * interval).
        """
        interval = OPTIONS_STRIKE_INTERVAL.get(underlying, 50)
        otm_offset = params.get("otm_offset", 2)

        buy_strike = atm_strike
        sell_strike = atm_strike + (otm_offset * interval)

        # Validate both strikes exist in chain
        if buy_strike not in chain or sell_strike not in chain:
            return None

        buy_data = chain[buy_strike]
        sell_data = chain[sell_strike]

        buy_premium = buy_data.get("ce_ltp", 0)
        sell_premium = sell_data.get("ce_ltp", 0)

        # Need valid premiums and sell must be cheaper than buy (it's OTM)
        if buy_premium <= 0 or sell_premium <= 0:
            return None
        if sell_premium >= buy_premium:
            return None  # No debit possible, invalid setup

        return [
            {
                "symbol": buy_data["ce_symbol"],
                "strike": buy_strike,
                "option_type": "CE",
                "side": 1,
                "price": buy_premium,
            },
            {
                "symbol": sell_data["ce_symbol"],
                "strike": sell_strike,
                "option_type": "CE",
                "side": -1,
                "price": sell_premium,
            },
        ]

    def calculate_payoff(self, legs: list[dict], lot_size: int) -> dict:
        """
        Bull Call Spread payoff:
        - Max loss = net debit * lot_size
        - Max profit = (sell_strike - buy_strike - net_debit) * lot_size
        - Breakeven = buy_strike + net_debit
        """
        buy_leg = next(l for l in legs if l["side"] == 1)
        sell_leg = next(l for l in legs if l["side"] == -1)

        net_debit = buy_leg["price"] - sell_leg["price"]
        strike_width = sell_leg["strike"] - buy_leg["strike"]

        max_risk = round(net_debit * lot_size, 2)
        max_reward = round((strike_width - net_debit) * lot_size, 2)
        breakeven = round(buy_leg["strike"] + net_debit, 2)


        rr_ratio = f"1:{round(max_reward / max_risk, 2)}" if max_risk > 0 else "N/A"

        return {
            "max_risk": max_risk,
            "max_reward": max_reward,
            "breakeven": breakeven,
            "risk_reward_ratio": rr_ratio,
        }
