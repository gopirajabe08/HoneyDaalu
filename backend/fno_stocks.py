"""
NSE F&O stock list with lot sizes.
~180 stocks approved for futures & options trading.
Update periodically from: https://www.nseindia.com/products/content/derivatives/equities/fo_underlying_home.htm
Lot sizes from: https://www.nseindia.com/products/content/derivatives/equities/contract.htm
"""

# Symbol → lot size mapping for NSE F&O stocks
FNO_STOCKS = {
    # ── Nifty 50 F&O Stocks ──
    "RELIANCE": 250,
    "TCS": 175,
    "HDFCBANK": 550,
    "INFY": 400,
    "ICICIBANK": 700,
    "HINDUNILVR": 300,
    "SBIN": 750,
    "BHARTIARTL": 475,
    "ITC": 1600,
    "KOTAKBANK": 400,
    "LT": 150,
    "HCLTECH": 350,
    "AXISBANK": 625,
    "ASIANPAINT": 300,
    "MARUTI": 75,
    "SUNPHARMA": 350,
    "TITAN": 175,
    "BAJFINANCE": 125,
    "BAJAJFINSV": 500,
    "NESTLEIND": 25,
    "ULTRACEMCO": 50,
    "WIPRO": 1500,
    "NTPC": 2250,
    "POWERGRID": 2700,
    "ONGC": 3575,
    "JSWSTEEL": 675,
    "TATAMOTORS": 1425,
    "TATASTEEL": 5500,
    "ADANIENT": 250,
    "ADANIPORTS": 625,
    "TECHM": 600,
    "HDFCLIFE": 1100,
    "SBILIFE": 375,
    "DIVISLAB": 125,
    "DRREDDY": 125,
    "CIPLA": 650,
    "GRASIM": 275,
    "INDUSINDBK": 500,
    "EICHERMOT": 175,
    "HEROMOTOCO": 150,
    "BAJAJ-AUTO": 125,
    "BRITANNIA": 100,
    "APOLLOHOSP": 125,
    "COALINDIA": 1700,
    "BPCL": 1800,
    "HINDALCO": 1075,
    "TATACONSUM": 575,
    "M&M": 350,

    # ── Nifty Next 50 F&O ──
    "DMART": 200,
    "GODREJCP": 500,
    "MARICO": 1200,
    "DABUR": 1250,
    "PIDILITIND": 250,
    "HAVELLS": 500,
    "VOLTAS": 400,
    "PAGEIND": 15,
    "MUTHOOTFIN": 300,
    "CHOLAFIN": 625,
    "LICHSGFIN": 1000,
    "PFC": 1500,
    "RECLTD": 1500,
    "CANBK": 5400,
    "BANKBARODA": 2925,
    "PNB": 6000,
    "IDFCFIRSTB": 7500,
    "FEDERALBNK": 5000,
    "BANDHANBNK": 2600,
    "AUBANK": 1000,
    "NAUKRI": 75,
    "ZOMATO": 3750,
    "IRCTC": 500,
    "TRENT": 250,
    "VBL": 600,
    "UBL": 350,
    "COLPAL": 200,
    "HINDPETRO": 1350,
    "GAIL": 3100,
    "MRF": 5,
    "BOSCHLTD": 25,
    "SIEMENS": 75,
    "ABB": 125,
    "CUMMINSIND": 200,
    "BEL": 3000,
    "HAL": 150,
    "BHEL": 4500,
    "SAIL": 5500,
    "NMDC": 3350,
    "NATIONALUM": 3750,
    "HINDCOPPER": 2175,
    "VEDL": 1550,
    "SHRIRAMFIN": 250,

    # ── Banking & Finance F&O ──
    "MANAPPURAM": 3000,
    "IBULHSGFIN": 2300,
    "L&TFH": 3574,
    "SBICARD": 800,
    "EXIDEIND": 1800,
    "ABCAPITAL": 5400,

    # ── Auto & Manufacturing F&O ──
    "ASHOKLEY": 3200,
    "BALKRISIND": 200,
    "TVSMOTOR": 250,
    "MOTHERSON": 5000,
    "MGL": 400,
    "ESCORTS": 200,
    "TATAELXSI": 100,

    # ── Pharma & Healthcare F&O ──
    "BIOCON": 2300,
    "AUROPHARMA": 450,
    "LUPIN": 550,
    "TORNTPHARM": 250,
    "ALKEM": 150,
    "IPCALAB": 450,
    "LAURUSLABS": 1000,
    "ABBOTINDIA": 25,

    # ── IT & Software F&O ──
    "MPHASIS": 275,
    "COFORGE": 100,
    "LTTS": 100,
    "PERSISTENT": 150,

    # ── Metals & Mining F&O ──
    "JINDALSTEL": 750,
    "APLAPOLLO": 350,
    "JSWENERGY": 1150,

    # ── Oil & Gas / Energy F&O ──
    "PETRONET": 3000,
    "IGL": 1350,
    "GUJGASLTD": 1250,
    "ADANIGREEN": 450,
    "TATAPOWER": 1875,
    "NHPC": 7500,
    "ADANIENSOL": 150,

    # Note: NTPC and POWERGRID already listed in Nifty 50 section above

    # ── Cement / Building Materials F&O ──
    "AMBUJACEM": 900,
    "DALBHARAT": 275,
    "RAMCOCEM": 500,
    "SHREECEM": 25,
    "ACC": 300,

    # ── Consumer / FMCG F&O ──
    "MCDOWELL-N": 1250,
    "INDIAMART": 375,
    "NYKAA": 3700,
    "TATACOMM": 250,
    "CROMPTON": 1300,
    "WHIRLPOOL": 400,
    "BATAINDIA": 550,
    "DIXON": 100,

    # ── Chemicals / Specialty F&O ──
    "DEEPAKNTR": 250,
    "ATUL": 75,
    "PIIND": 150,
    "SYNGENE": 650,
    "COROMANDEL": 350,
    "NAVINFLUOR": 150,
    "CLEAN": 400,

    # ── Infrastructure / Industrials F&O ──
    "LALPATHLAB": 200,
    "MAXHEALTH": 700,
    "POLYCAB": 100,
    "HONAUT": 15,
    "ASTRAL": 300,
    "OBEROIRLTY": 475,
    "GODREJPROP": 225,
    "DLF": 825,
    "LODHA": 750,
    "PHOENIXLTD": 375,
    "PRESTIGE": 400,
    "LTIM": 150,
    "ZYDUSLIFE": 650,
    "MANKIND": 300,
    "ICICIGI": 400,
    "ICICIPRULI": 1050,
    "ABFRL": 1700,
    "INDHOTEL": 1000,
    "METROPOLIS": 250,
    "PVRINOX": 325,
    "CONCOR": 1000,
    "IOC": 4350,
    "IDEA": 50000,
    "GMRINFRA": 7500,
    "IRFC": 7500,
    "INDUSTOWER": 1650,
    "INDIGO": 200,
    "OFSS": 100,
    "MCX": 200,
    "CANFINHOME": 575,
    "CUB": 3500,
    "GNFC": 800,
    "GRANULES": 1600,
    "GSPL": 1625,
    "IDBI": 5000,
}


def get_fno_symbols() -> list[str]:
    """Return list of all F&O stock symbols."""
    return list(FNO_STOCKS.keys())


def get_lot_size(symbol: str) -> int:
    """Return lot size for a given symbol. Returns 0 if not found."""
    return FNO_STOCKS.get(symbol, 0)


def get_fno_stocks_with_lots() -> dict[str, int]:
    """Return the full symbol → lot_size mapping."""
    return dict(FNO_STOCKS)
