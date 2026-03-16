"""
Base class for all options spread strategies.
Each strategy selects strikes, calculates payoff, generates entry signals, and checks exits.
"""

from abc import ABC, abstractmethod
from typing import Optional


class OptionsBaseStrategy(ABC):
    """Base class for options spread strategies."""

    name: str = ""
    description: str = ""
    spread_type: str = ""  # "bull_call"|"bull_put"|"bear_call"|"bear_put"|"iron_condor"|"long_straddle"
    strategy_type: str = ""  # "credit" or "debit"
    win_rate_estimate: str = ""

    @abstractmethod
    def select_strikes(self, chain: dict, atm_strike: int, underlying: str, params: dict) -> Optional[list[dict]]:
        """
        Select strikes for the spread from option chain data.

        Args:
            chain: option chain dict with strike data
            atm_strike: current ATM strike
            underlying: "NIFTY" or "BANKNIFTY"
            params: strategy parameters from config

        Returns:
            list of leg dicts or None if no valid setup.
            Each leg: {"symbol": str, "strike": int, "option_type": "CE"|"PE", "side": 1(BUY)|-1(SELL), "price": float}
        """
        pass

    @abstractmethod
    def calculate_payoff(self, legs: list[dict], lot_size: int) -> dict:
        """
        Calculate max risk, max reward, breakeven for the spread.

        Returns:
            {"max_risk": float, "max_reward": float, "breakeven": float|list, "risk_reward_ratio": str}
        """
        pass

    def scan(self, chain_data: dict, regime: dict, underlying: str, params: dict) -> Optional[dict]:
        """
        Check if this strategy has a valid setup.

        Returns signal dict or None.
        """
        chain = chain_data.get("chain", {})
        atm = chain_data.get("atm_strike", 0)
        lot_size = chain_data.get("lot_size", 75)

        if not chain or atm == 0:
            return None

        legs = self.select_strikes(chain, atm, underlying, params)
        if legs is None:
            return None

        # Verify all legs have valid prices
        for leg in legs:
            if leg.get("price", 0) <= 0:
                return None

        # Add qty to each leg (lot_size)
        for leg in legs:
            leg["qty"] = lot_size

        payoff = self.calculate_payoff(legs, lot_size)
        if payoff.get("max_risk", 0) <= 0:
            return None

        # Calculate net premium (positive = credit received, negative = debit paid)
        net_premium = 0.0
        for leg in legs:
            if leg["side"] == -1:  # SELL
                net_premium += leg["price"]
            else:  # BUY
                net_premium -= leg["price"]

        return {
            "strategy": self.spread_type,
            "strategy_name": self.name,
            "underlying": underlying,
            "legs": legs,
            "net_premium": round(net_premium, 2),
            "net_premium_per_lot": round(net_premium * lot_size, 2),
            "max_risk": payoff["max_risk"],
            "max_reward": payoff["max_reward"],
            "breakeven": payoff["breakeven"],
            "risk_reward_ratio": payoff["risk_reward_ratio"],
            "lot_size": lot_size,
            "expiry": chain_data.get("expiry", ""),
            "expiry_date": chain_data.get("expiry_date", ""),
            "days_to_expiry": chain_data.get("days_to_expiry", 0),
            "spot_price": chain_data.get("spot_price", 0),
            "atm_strike": atm,
            "strategy_type": self.strategy_type,
        }

    def check_exit(self, entry: dict, current_leg_prices: dict, params: dict) -> Optional[dict]:
        """
        Check exit conditions for an open position.

        Args:
            entry: the original entry signal/trade dict
            current_leg_prices: {"symbol": current_ltp} for each leg
            params: strategy parameters

        Returns:
            {"exit": True, "reason": str} or None if no exit.
        """
        net_premium_entry = entry.get("net_premium", 0)
        legs = entry.get("legs", [])
        lot_size = entry.get("lot_size", 75)

        # Calculate current net premium
        current_net = 0.0
        for leg in legs:
            sym = leg["symbol"]
            current_price = current_leg_prices.get(sym, leg["price"])
            if leg["side"] == -1:  # SELL
                current_net += current_price
            else:  # BUY
                current_net -= current_price

        # For credit spreads: profit when current_net < net_premium_entry (premiums decay)
        # For debit spreads: profit when current_net > net_premium_entry (premiums increase)

        if self.strategy_type == "credit":
            # We collected premium. Current position value = net_premium_entry - current_net
            pnl_per_unit = net_premium_entry - current_net
            max_reward = entry.get("max_reward", 0) / lot_size if lot_size > 0 else 0
            max_risk = entry.get("max_risk", 0) / lot_size if lot_size > 0 else 0
        else:
            # We paid premium. Current position value = current_net - net_premium_entry
            pnl_per_unit = current_net - net_premium_entry
            max_reward = entry.get("max_reward", 0) / lot_size if lot_size > 0 else 0
            max_risk = entry.get("max_risk", 0) / lot_size if lot_size > 0 else 0

        profit_target_pct = params.get("profit_target_pct", 0.50)
        stop_loss_mult = params.get("stop_loss_mult", 1.5)

        # Profit target: exit at X% of max reward
        if max_reward > 0 and pnl_per_unit >= max_reward * profit_target_pct:
            return {"exit": True, "reason": "PROFIT_TARGET", "pnl_per_unit": round(pnl_per_unit, 2)}

        # Stop loss: exit if loss exceeds multiplier of premium received/paid
        if max_risk > 0 and pnl_per_unit <= -max_risk * stop_loss_mult:
            return {"exit": True, "reason": "STOP_LOSS", "pnl_per_unit": round(pnl_per_unit, 2)}

        return None

    def info(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "spread_type": self.spread_type,
            "strategy_type": self.strategy_type,
            "win_rate_estimate": self.win_rate_estimate,
        }
