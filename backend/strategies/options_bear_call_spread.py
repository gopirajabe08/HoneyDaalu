"""
Bear Call Spread — Sell lower strike CE + Buy higher strike CE (credit spread).
Used when conviction is mildly bearish. HIGH PROBABILITY strategy.
Profits when underlying stays below the sold call strike.
"""

from typing import Optional

from config import OPTIONS_STRIKE_INTERVAL
from strategies.options_base import OptionsBaseStrategy


class BearCallSpread(OptionsBaseStrategy):
    name = "Bear Call Spread"
    description = "Sell OTM CE + Buy further OTM CE. Credit spread for mildly bearish conviction. High probability."
    spread_type = "bear_call_spread"
    strategy_type = "credit"
    win_rate_estimate = "~65-70% (credit spread, profits from time decay)"

    def select_strikes(self, chain: dict, atm_strike: int, underlying: str, params: dict) -> Optional[list[dict]]:
        """
        Select strikes for bear call spread.
        Sell CE at ATM + interval (slightly OTM), Buy CE at ATM + (otm_offset+1) * interval (further OTM).
        """
        interval = OPTIONS_STRIKE_INTERVAL.get(underlying, 50)
        otm_offset = params.get("otm_offset", 2)

        sell_strike = atm_strike + interval  # 1 strike OTM
        buy_strike = atm_strike + ((otm_offset + 1) * interval)  # Further OTM protection

        # Validate both strikes exist in chain
        if sell_strike not in chain or buy_strike not in chain:
            return None

        sell_data = chain[sell_strike]
        buy_data = chain[buy_strike]

        sell_premium = sell_data.get("ce_ltp", 0)
        buy_premium = buy_data.get("ce_ltp", 0)

        # Sell premium must be higher (it's closer to ATM)
        if sell_premium <= 0 or buy_premium <= 0:
            return None
        if buy_premium >= sell_premium:
            return None  # No credit possible

        return [
            {
                "symbol": sell_data["ce_symbol"],
                "strike": sell_strike,
                "option_type": "CE",
                "side": -1,
                "price": sell_premium,
            },
            {
                "symbol": buy_data["ce_symbol"],
                "strike": buy_strike,
                "option_type": "CE",
                "side": 1,
                "price": buy_premium,
            },
        ]

    def calculate_payoff(self, legs: list[dict], lot_size: int) -> dict:
        """
        Bear Call Spread payoff:
        - Max profit = net credit * lot_size
        - Max loss = (buy_strike - sell_strike - net_credit) * lot_size
        - Breakeven = sell_strike + net_credit
        """
        sell_leg = next(l for l in legs if l["side"] == -1)
        buy_leg = next(l for l in legs if l["side"] == 1)

        net_credit = sell_leg["price"] - buy_leg["price"]
        strike_width = buy_leg["strike"] - sell_leg["strike"]

        max_reward = round(net_credit * lot_size, 2)
        max_risk = round((strike_width - net_credit) * lot_size, 2)
        breakeven = round(sell_leg["strike"] + net_credit, 2)

        rr_ratio = f"1:{round(max_reward / max_risk, 2)}" if max_risk > 0 else "N/A"

        return {
            "max_risk": max_risk,
            "max_reward": max_reward,
            "breakeven": breakeven,
            "risk_reward_ratio": rr_ratio,
        }
