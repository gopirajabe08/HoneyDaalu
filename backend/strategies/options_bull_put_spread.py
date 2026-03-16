"""
Bull Put Spread — Sell higher strike PE + Buy lower strike PE (credit spread).
Used when conviction is mildly bullish. HIGH PROBABILITY strategy.
Profits when underlying stays above the sold put strike.
"""

from typing import Optional

from config import OPTIONS_STRIKE_INTERVAL
from strategies.options_base import OptionsBaseStrategy


class BullPutSpread(OptionsBaseStrategy):
    name = "Bull Put Spread"
    description = "Sell OTM PE + Buy further OTM PE. Credit spread for mildly bullish conviction. High probability."
    spread_type = "bull_put_spread"
    strategy_type = "credit"
    win_rate_estimate = "~65-70% (credit spread, profits from time decay)"

    def select_strikes(self, chain: dict, atm_strike: int, underlying: str, params: dict) -> Optional[list[dict]]:
        """
        Select strikes for bull put spread.
        Sell PE at ATM - interval (slightly OTM), Buy PE at ATM - (otm_offset+1) * interval (further OTM).
        """
        interval = OPTIONS_STRIKE_INTERVAL.get(underlying, 50)
        otm_offset = params.get("otm_offset", 2)

        sell_strike = atm_strike - interval  # 1 strike OTM
        buy_strike = atm_strike - ((otm_offset + 1) * interval)  # Further OTM protection

        # Validate both strikes exist in chain
        if sell_strike not in chain or buy_strike not in chain:
            return None

        sell_data = chain[sell_strike]
        buy_data = chain[buy_strike]

        sell_premium = sell_data.get("pe_ltp", 0)
        buy_premium = buy_data.get("pe_ltp", 0)

        # Sell premium must be higher (it's closer to ATM)
        if sell_premium <= 0 or buy_premium <= 0:
            return None
        if buy_premium >= sell_premium:
            return None  # No credit possible

        return [
            {
                "symbol": sell_data["pe_symbol"],
                "strike": sell_strike,
                "option_type": "PE",
                "side": -1,
                "price": sell_premium,
            },
            {
                "symbol": buy_data["pe_symbol"],
                "strike": buy_strike,
                "option_type": "PE",
                "side": 1,
                "price": buy_premium,
            },
        ]

    def calculate_payoff(self, legs: list[dict], lot_size: int) -> dict:
        """
        Bull Put Spread payoff:
        - Max profit = net credit * lot_size
        - Max loss = (sell_strike - buy_strike - net_credit) * lot_size
        - Breakeven = sell_strike - net_credit
        """
        sell_leg = next(l for l in legs if l["side"] == -1)
        buy_leg = next(l for l in legs if l["side"] == 1)

        net_credit = sell_leg["price"] - buy_leg["price"]
        strike_width = sell_leg["strike"] - buy_leg["strike"]

        max_reward = round(net_credit * lot_size, 2)
        max_risk = round((strike_width - net_credit) * lot_size, 2)
        breakeven = round(sell_leg["strike"] - net_credit, 2)

        rr_ratio = f"1:{round(max_reward / max_risk, 2)}" if max_risk > 0 else "N/A"

        return {
            "max_risk": max_risk,
            "max_reward": max_reward,
            "breakeven": breakeven,
            "risk_reward_ratio": rr_ratio,
        }
