"""
Iron Condor — Bull Put Spread + Bear Call Spread combined (credit spread).
Used when conviction is neutral / range-bound. HIGH PROBABILITY strategy.
Profits when underlying stays within a range between the two sold strikes.
"""

from typing import Optional

from config import OPTIONS_STRIKE_INTERVAL
from strategies.options_base import OptionsBaseStrategy


class IronCondor(OptionsBaseStrategy):
    name = "Iron Condor"
    description = "Sell OTM PE + Buy further OTM PE + Sell OTM CE + Buy further OTM CE. Credit spread for neutral conviction. High probability."
    spread_type = "iron_condor"
    strategy_type = "credit"
    win_rate_estimate = "~70-75% (wide range, double credit, profits from time decay)"

    def select_strikes(self, chain: dict, atm_strike: int, underlying: str, params: dict) -> Optional[list[dict]]:
        """
        Select strikes for iron condor.
        Put side (bull put): Sell PE at ATM - otm_offset*interval, Buy PE one strike below.
        Call side (bear call): Sell CE at ATM + otm_offset*interval, Buy CE one strike above.
        """
        interval = OPTIONS_STRIKE_INTERVAL.get(underlying, 50)
        otm_offset = params.get("otm_offset", 3)

        # Put side (bull put spread)
        put_sell_strike = atm_strike - (otm_offset * interval)
        put_buy_strike = put_sell_strike - interval

        # Call side (bear call spread)
        call_sell_strike = atm_strike + (otm_offset * interval)
        call_buy_strike = call_sell_strike + interval

        # Validate all strikes exist in chain
        required = [put_sell_strike, put_buy_strike, call_sell_strike, call_buy_strike]
        for s in required:
            if s not in chain:
                return None

        put_sell_data = chain[put_sell_strike]
        put_buy_data = chain[put_buy_strike]
        call_sell_data = chain[call_sell_strike]
        call_buy_data = chain[call_buy_strike]

        put_sell_premium = put_sell_data.get("pe_ltp", 0)
        put_buy_premium = put_buy_data.get("pe_ltp", 0)
        call_sell_premium = call_sell_data.get("ce_ltp", 0)
        call_buy_premium = call_buy_data.get("ce_ltp", 0)

        # All premiums must be positive
        if any(p <= 0 for p in [put_sell_premium, put_buy_premium, call_sell_premium, call_buy_premium]):
            return None

        # Sold strikes must have higher premium than bought strikes
        if put_buy_premium >= put_sell_premium:
            return None
        if call_buy_premium >= call_sell_premium:
            return None

        return [
            # Bull Put Spread (put side)
            {
                "symbol": put_sell_data["pe_symbol"],
                "strike": put_sell_strike,
                "option_type": "PE",
                "side": -1,
                "price": put_sell_premium,
            },
            {
                "symbol": put_buy_data["pe_symbol"],
                "strike": put_buy_strike,
                "option_type": "PE",
                "side": 1,
                "price": put_buy_premium,
            },
            # Bear Call Spread (call side)
            {
                "symbol": call_sell_data["ce_symbol"],
                "strike": call_sell_strike,
                "option_type": "CE",
                "side": -1,
                "price": call_sell_premium,
            },
            {
                "symbol": call_buy_data["ce_symbol"],
                "strike": call_buy_strike,
                "option_type": "CE",
                "side": 1,
                "price": call_buy_premium,
            },
        ]

    def calculate_payoff(self, legs: list[dict], lot_size: int) -> dict:
        """
        Iron Condor payoff:
        - Max profit = total net credit * lot_size
        - Max loss = (strike_width - total_net_credit) * lot_size
          (strike_width is the wider of the two spreads, typically equal)
        - Two breakevens: put_sell - net_credit_put_side, call_sell + net_credit_call_side
        """
        # Separate put and call legs
        put_sell = None
        put_buy = None
        call_sell = None
        call_buy = None

        for leg in legs:
            if leg["option_type"] == "PE" and leg["side"] == -1:
                put_sell = leg
            elif leg["option_type"] == "PE" and leg["side"] == 1:
                put_buy = leg
            elif leg["option_type"] == "CE" and leg["side"] == -1:
                call_sell = leg
            elif leg["option_type"] == "CE" and leg["side"] == 1:
                call_buy = leg

        if not all([put_sell, put_buy, call_sell, call_buy]):
            return {"max_risk": 0, "max_reward": 0, "breakeven": [], "risk_reward_ratio": "N/A"}

        # Net credit from each side
        put_credit = put_sell["price"] - put_buy["price"]
        call_credit = call_sell["price"] - call_buy["price"]
        total_credit = put_credit + call_credit

        # Strike widths
        put_width = put_sell["strike"] - put_buy["strike"]
        call_width = call_buy["strike"] - call_sell["strike"]
        max_width = max(put_width, call_width)

        max_reward = round(total_credit * lot_size, 2)
        max_risk = round((max_width - total_credit) * lot_size, 2)

        # Breakevens
        lower_be = round(put_sell["strike"] - total_credit, 2)
        upper_be = round(call_sell["strike"] + total_credit, 2)

        rr_ratio = f"1:{round(max_reward / max_risk, 2)}" if max_risk > 0 else "N/A"

        return {
            "max_risk": max_risk,
            "max_reward": max_reward,
            "breakeven": [lower_be, upper_be],
            "risk_reward_ratio": rr_ratio,
        }
