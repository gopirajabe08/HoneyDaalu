"""
Indian retail trading full cost model — addresses Audit Check 4 FAIL
("Cost realism: missing 5-8% of actual charges").

Old backtest_with_charges.py covered: brokerage + STT + 0.03% generic exchange.
This module adds: GST(18%) + DP charges + separate buy-stamp + SEBI fee.

Reference rates from Zerodha/TradeJini standard schedule (early 2026).
Owner should verify against actual TradeJini contract notes monthly.
"""
from __future__ import annotations
from dataclasses import dataclass


# ── Base rate constants (TradeJini retail equity, early 2026) ──
BROKERAGE_FLAT_CAP = 20.0           # ₹20/leg max
BROKERAGE_RATE_INTRADAY = 0.0003    # 0.03% intraday
BROKERAGE_RATE_DELIVERY = 0.0       # ₹0 for delivery (buy/sell) — discount broker

STT_RATE_INTRADAY_SELL = 0.00025    # 0.025% on sell side intraday
STT_RATE_DELIVERY = 0.001           # 0.1% on both buy and sell delivery

EXCHANGE_RATE_NSE = 0.0000325       # 0.00325% per leg (NSE transaction fee)
SEBI_RATE = 0.000001                # ₹10 per crore = 0.000001
STAMP_DUTY_BUY_INTRADAY = 0.00003   # 0.003% on buy side only intraday
STAMP_DUTY_BUY_DELIVERY = 0.00015   # 0.015% on buy side only delivery

GST_RATE = 0.18                     # 18% GST on brokerage + exchange + SEBI

# DP charges only apply on delivery sells (when shares move from demat)
DP_CHARGE_PER_SCRIP_SELL = 13.5     # ₹13.5/scrip for delivery sell
DP_GST_RATE = 0.18                  # GST on DP charge


@dataclass
class TradeCharges:
    """Itemized charges for one round-trip trade."""
    brokerage: float
    stt: float
    exchange: float
    sebi: float
    stamp: float
    gst: float          # On brokerage + exchange + SEBI
    dp_charge: float    # Only delivery sells
    total: float

    def __str__(self) -> str:
        return (
            f"brok=₹{self.brokerage:.2f} stt=₹{self.stt:.2f} exch=₹{self.exchange:.2f} "
            f"sebi=₹{self.sebi:.2f} stamp=₹{self.stamp:.2f} gst=₹{self.gst:.2f} "
            f"dp=₹{self.dp_charge:.2f} | TOTAL=₹{self.total:.2f}"
        )


def compute_round_trip(
    qty: int,
    entry_price: float,
    exit_price: float,
    is_intraday: bool,
) -> TradeCharges:
    """
    Compute full charges for a complete round-trip trade.

    Args:
        qty: number of shares
        entry_price: buy/short price
        exit_price: sell/cover price
        is_intraday: True if MIS/intraday (no DP), False if delivery (DP applies)

    Returns:
        TradeCharges with itemized + total

    Notes on Indian retail model (verified against TradeJini schedule):
    - Brokerage: 0.03% intraday (capped ₹20/leg), ₹0 delivery
    - STT: 0.025% sell-only intraday, 0.1% both sides delivery
    - NSE transaction: 0.00325% per leg
    - SEBI: ₹10/crore both sides
    - Stamp duty: buy-side only (0.003% intraday, 0.015% delivery)
    - GST: 18% on (brokerage + exchange + SEBI)
    - DP: ₹13.5+GST per scrip on delivery sell only
    """
    buy_turnover = qty * entry_price
    sell_turnover = qty * exit_price
    total_turnover = buy_turnover + sell_turnover

    # Brokerage (per leg, capped)
    if is_intraday:
        brok_buy = min(BROKERAGE_FLAT_CAP, buy_turnover * BROKERAGE_RATE_INTRADAY)
        brok_sell = min(BROKERAGE_FLAT_CAP, sell_turnover * BROKERAGE_RATE_INTRADAY)
    else:
        brok_buy = buy_turnover * BROKERAGE_RATE_DELIVERY
        brok_sell = sell_turnover * BROKERAGE_RATE_DELIVERY
    brokerage = brok_buy + brok_sell

    # STT
    if is_intraday:
        stt = sell_turnover * STT_RATE_INTRADAY_SELL
    else:
        stt = total_turnover * STT_RATE_DELIVERY

    # Exchange transaction fees (per leg)
    exchange = total_turnover * EXCHANGE_RATE_NSE

    # SEBI
    sebi = total_turnover * SEBI_RATE

    # Stamp duty (buy side only)
    if is_intraday:
        stamp = buy_turnover * STAMP_DUTY_BUY_INTRADAY
    else:
        stamp = buy_turnover * STAMP_DUTY_BUY_DELIVERY

    # GST on brokerage + exchange + SEBI
    gst = (brokerage + exchange + sebi) * GST_RATE

    # DP charges (delivery sell only)
    if is_intraday:
        dp_charge = 0.0
    else:
        dp_charge = DP_CHARGE_PER_SCRIP_SELL * (1 + DP_GST_RATE)

    total = round(brokerage + stt + exchange + sebi + stamp + gst + dp_charge, 2)

    return TradeCharges(
        brokerage=round(brokerage, 2),
        stt=round(stt, 2),
        exchange=round(exchange, 2),
        sebi=round(sebi, 2),
        stamp=round(stamp, 2),
        gst=round(gst, 2),
        dp_charge=round(dp_charge, 2),
        total=total,
    )


def compute_realistic_slippage(entry_price: float, liquidity_tier: str = "large_cap") -> float:
    """
    Realistic slippage estimate by liquidity tier.

    Based on Pillar 2 of NSE Trading Specialist (Role 12) framework.

    Args:
        entry_price: signal entry price
        liquidity_tier: "large_cap" (Nifty 50), "mid_cap" (Nifty 100), "small_cap" (rest)

    Returns:
        Slippage in absolute price units (subtract from BUY entry / add to SELL entry).
    """
    rates = {
        "large_cap": 0.001,   # 0.1% — RELIANCE, TCS, etc.
        "mid_cap": 0.002,     # 0.2% — Nifty 100-500
        "small_cap": 0.004,   # 0.4% — beyond Nifty 500
    }
    rate = rates.get(liquidity_tier, 0.002)
    return entry_price * rate


# ── Sanity check / self-test ──
if __name__ == "__main__":
    # Example: ₹10,000 BUY at ₹500, exit at ₹510, intraday
    print("=== Intraday round-trip example ===")
    qty = 20
    entry, exit_p = 500.0, 510.0
    c = compute_round_trip(qty, entry, exit_p, is_intraday=True)
    gross = (exit_p - entry) * qty
    print(f"Gross: ₹{gross:.2f}")
    print(c)
    print(f"Net: ₹{gross - c.total:.2f}")
    print()

    print("=== Delivery (swing) round-trip example ===")
    c2 = compute_round_trip(qty, entry, exit_p, is_intraday=False)
    print(c2)
    print(f"Net: ₹{gross - c2.total:.2f}")
    print()

    print("=== Slippage ===")
    print(f"Large-cap @ ₹500: ₹{compute_realistic_slippage(500, 'large_cap'):.2f}")
    print(f"Mid-cap @ ₹500: ₹{compute_realistic_slippage(500, 'mid_cap'):.2f}")
    print(f"Small-cap @ ₹500: ₹{compute_realistic_slippage(500, 'small_cap'):.2f}")
