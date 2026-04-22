"""
Nifty 50 + Nifty Next 50 = NIFTY 100 constituents used as the hard universe
for the regime-filtered equity intraday engine.

Sourced from NSE constituents as of Apr 2026, matching the first two sections
of nifty500.py (which is the broader scanner universe).

yfinance suffix = ".NS"; broker-side symbols (TradeJini) resolve via
format_broker_symbol() → EQT_{SYM}_EQ_NSE.
"""

NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
    "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "HCLTECH",
    "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN",
    "BAJFINANCE", "BAJAJFINSV", "NESTLEIND", "ULTRACEMCO", "WIPRO",
    "NTPC", "POWERGRID", "ONGC", "JSWSTEEL", "TATAMOTORS", "TATASTEEL",
    "ADANIENT", "ADANIPORTS", "TECHM", "HDFCLIFE", "SBILIFE",
    "DRREDDY", "CIPLA", "GRASIM", "INDUSINDBK",
    "EICHERMOT", "HEROMOTOCO", "BAJAJ-AUTO", "BRITANNIA", "APOLLOHOSP",
    "COALINDIA", "BPCL", "HINDALCO", "TATACONSUM", "M&M", "LTF",
    "TRENT", "SHRIRAMFIN",
]

NIFTY_NEXT_50 = [
    "DMART", "GODREJCP", "MARICO", "DABUR", "PIDILITIND", "BERGERPAINTS",
    "HAVELLS", "VOLTAS", "PAGEIND", "MUTHOOTFIN", "CHOLAFIN",
    "LICHSGFIN", "PFC", "RECLTD", "IRFC", "CANBK", "BANKBARODA",
    "PNB", "INDIANB", "IDFCFIRSTB", "FEDERALBNK", "BANDHANBNK",
    "AUBANK", "NAUKRI", "ZOMATO", "IRCTC", "VBL", "UBL", "COLPAL",
    "HINDPETRO", "GAIL", "MRF", "BOSCHLTD", "SIEMENS", "ABB",
    "CUMMINSIND", "BEL", "HAL", "CONCOR", "SAIL", "NMDC",
    "IOC", "VEDL", "ICICIPRULI", "HDFCAMC", "SBICARD", "ICICIGI",
    "LTIM", "TORNTPHARM", "DIVISLAB",
]

NIFTY_100 = NIFTY_50 + NIFTY_NEXT_50

# Sanity-check: exactly 100 unique names
assert len(NIFTY_100) == 100, f"Expected 100 symbols, got {len(NIFTY_100)}"
assert len(set(NIFTY_100)) == 100, "NIFTY_100 has duplicates"

NIFTY_100_SET = frozenset(NIFTY_100)


def is_in_nifty100(symbol: str) -> bool:
    """Symbol may come in as 'RELIANCE', 'NSE:RELIANCE-EQ', or 'EQT_RELIANCE_EQ_NSE'.
    Normalise and check membership."""
    if not symbol:
        return False
    s = symbol.strip().upper()
    s = s.replace("NSE:", "").replace("-EQ", "")
    if s.startswith("EQT_") and s.endswith("_EQ_NSE"):
        s = s[4:-7]
    return s in NIFTY_100_SET
