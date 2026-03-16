"""
Long Straddle — Buy ATM CE + Buy ATM PE (debit spread).
Used when conviction is high volatility (VIX > 20).
Profits when underlying makes a large move in either direction.
"""

from typing import Optional

from config import OPTIONS_STRIKE_INTERVAL
from strategies.options_base import OptionsBaseStrategy


class LongStraddle(OptionsBaseStrategy):
    name = "Long Straddle"
    description = "Buy ATM CE + Buy ATM PE. Debit strategy for high volatility. Profits from large moves in either direction."
    spread_type = "long_straddle"
    strategy_type = "debit"
    win_rate_estimate = "~35-40% (needs significant move, but unlimited upside)"

    def select_strikes(self, chain: dict, atm_strike: int, underlying: str, params: dict) -> Optional[list[dict]]:
        """
        Select strikes for long straddle.
        Buy CE at ATM, Buy PE at ATM.
        """
        if atm_strike not in chain:
            return None

        atm_data = chain[atm_strike]

        ce_premium = atm_data.get("ce_ltp", 0)
        pe_premium = atm_data.get("pe_ltp", 0)

        if ce_premium <= 0 or pe_premium <= 0:
            return None

        return [
            {
                "symbol": atm_data["ce_symbol"],
                "strike": atm_strike,
                "option_type": "CE",
                "side": 1,
                "price": ce_premium,
            },
            {
                "symbol": atm_data["pe_symbol"],
                "strike": atm_strike,
                "option_type": "PE",
                "side": 1,
                "price": pe_premium,
            },
        ]

    def calculate_payoff(self, legs: list[dict], lot_size: int) -> dict:
        """
        Long Straddle payoff:
        - Max loss = total premium paid * lot_size (both CE + PE decay to zero)
        - Max profit = unlimited (theoretically)
        - Two breakevens: ATM - total_premium, ATM + total_premium
        """
        ce_leg = next(l for l in legs if l["option_type"] == "CE")
        pe_leg = next(l for l in legs if l["option_type"] == "PE")

        total_premium = ce_leg["price"] + pe_leg["price"]
        atm_strike = ce_leg["strike"]  # Both are at ATM

        max_risk = round(total_premium * lot_size, 2)
        # Max reward is theoretically unlimited; use 3x premium as a practical estimate
        max_reward_estimate = round(total_premium * 3 * lot_size, 2)

        lower_be = round(atm_strike - total_premium, 2)
        upper_be = round(atm_strike + total_premium, 2)

        rr_ratio = "1:unlimited"

        return {
            "max_risk": max_risk,
            "max_reward": max_reward_estimate,
            "breakeven": [lower_be, upper_be],
            "risk_reward_ratio": rr_ratio,
        }

    def check_exit(self, entry: dict, current_leg_prices: dict, params: dict) -> Optional[dict]:
        """
        Custom exit for long straddle.
        Exit at profit_target_pct of total premium paid, or stop_loss_mult of premium.
        """
        legs = entry.get("legs", [])
        lot_size = entry.get("lot_size", 75)

        # Total premium paid at entry
        total_premium_paid = sum(l["price"] for l in legs)

        # Current total value of both legs
        current_total = 0.0
        for leg in legs:
            sym = leg["symbol"]
            current_price = current_leg_prices.get(sym, leg["price"])
            current_total += current_price

        # P&L per unit = current_value - premium_paid (we bought both legs)
        pnl_per_unit = current_total - total_premium_paid

        profit_target_pct = params.get("profit_target_pct", 0.30)
        stop_loss_mult = params.get("stop_loss_mult", 0.50)

        # Profit target: current value exceeds entry by profit_target_pct
        if total_premium_paid > 0 and pnl_per_unit >= total_premium_paid * profit_target_pct:
            return {"exit": True, "reason": "PROFIT_TARGET", "pnl_per_unit": round(pnl_per_unit, 2)}

        # Stop loss: value dropped by stop_loss_mult of premium paid
        if total_premium_paid > 0 and pnl_per_unit <= -(total_premium_paid * stop_loss_mult):
            return {"exit": True, "reason": "STOP_LOSS", "pnl_per_unit": round(pnl_per_unit, 2)}

        return None
