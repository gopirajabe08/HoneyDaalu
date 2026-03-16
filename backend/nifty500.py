"""
Nifty 500 stock list with NSE symbols.
These symbols are used with .NS suffix for yfinance.
Update this list periodically from NSE website.
"""

NIFTY_500 = [
    # ── Nifty 50 ──
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
    "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "HCLTECH",
    "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN",
    "BAJFINANCE", "BAJAJFINSV", "NESTLEIND", "ULTRACEMCO", "WIPRO",
    "NTPC", "POWERGRID", "ONGC", "JSWSTEEL", "TATAMOTORS", "TATASTEEL",
    "ADANIENT", "ADANIPORTS", "TECHM", "HDFCLIFE", "SBILIFE",
    "DIVISLAB", "DRREDDY", "CIPLA", "GRASIM", "INDUSINDBK",
    "EICHERMOT", "HEROMOTOCO", "BAJAJ-AUTO", "BRITANNIA", "APOLLOHOSP",
    "COALINDIA", "BPCL", "HINDALCO", "TATACONSUM", "M&M", "LTF",

    # ── Nifty Next 50 ──
    "DMART", "GODREJCP", "MARICO", "DABUR", "PIDILITIND", "BERGERPAINTS",
    "HAVELLS", "VOLTAS", "PAGEIND", "MUTHOOTFIN", "CHOLAFIN",
    "LICHSGFIN", "PFC", "RECLTD", "IRFC", "CANBK", "BANKBARODA",
    "PNB", "INDIANB", "IDFCFIRSTB", "FEDERALBNK", "BANDHANBNK",
    "AUBANK", "YESBANK", "IDBI", "NAUKRI", "ZOMATO",
    "IRCTC", "TRENT", "VBL", "UBL", "COLPAL",
    "HINDPETRO", "GAIL", "MRF", "BOSCHLTD", "SIEMENS", "ABB",
    "CUMMINSIND", "BEL", "HAL", "BHEL", "CONCOR", "SAIL", "NMDC",
    "NATIONALUM", "HINDCOPPER", "IOC", "VEDL", "SHRIRAMFIN",

    # ── IT & Technology ──
    "TATAELXSI", "LTTS", "PERSISTENT", "COFORGE", "MPHASIS", "LTIM",
    "HAPPSTMNDS", "MASTEK", "ZENSAR", "SONATSOFTW", "BSOFT",
    "KPITTECH", "INTELLECT", "NEWGEN", "OFSS", "AFFLE",
    "LATENTVIEW", "TANLA", "ROUTE",

    # ── Pharma & Healthcare ──
    "SYNGENE", "BIOCON", "LALPATHLAB", "METROPOLIS", "IPCALAB",
    "LAURUSLABS", "GRANULES", "NATCOPHARM", "GLENMARK", "ALKEM",
    "TORNTPHARM", "AUROPHARMA", "LUPIN", "ABBOTINDIA",
    "JBCHEPHARM", "AJANTPHARM", "MAXHEALTH", "FORTIS",
    "MEDANTA", "STAR",

    # ── Banking & Finance ──
    "CUB", "KARURVYSYA", "SUNDARMFIN",
    "ABCAPITAL", "BAJAJHLDNG", "MANAPPURAM",
    "ICICIPRULI", "HDFCAMC", "NIPPONIND", "SBICARD",
    "ICICIGI", "STARHEALTH", "KFINTECH", "CAMS", "CDSL",
    "BSE", "MCX", "ANGELONE", "MOTILALOFS",
    "AAVAS", "HOMEFIRST", "CANFINHOME", "HUDCO", "IREDA",
    "EQUITASBNK", "UJJIVANSFB", "POONAWALLA",

    # ── Auto & Auto Ancillary ──
    "MOTHERSON", "BHARATFORG", "EXIDEIND", "AMARAJABAT",
    "BALKRISIND", "APOLLOTYRE", "CEATLTD", "TVSMTR", "ASHOKLEY",
    "ESCORTS", "TVSMOTOR", "SONACOMS",

    # ── Metals & Mining ──
    "APLAPOLLO", "MOIL", "RATNAMANI", "JINDALSAW",
    "WELCORP", "JSWENERGY",

    # ── Infrastructure & Construction ──
    "GMRINFRA", "IRB", "KNRCON", "PNCINFRA",
    "NCC", "NBCC", "ENGINERSIN", "RVNL", "RAILTEL",

    # ── Capital Goods & Engineering ──
    "THERMAX", "ELGIEQUIP", "GRINDWELL",
    "SCHAEFFLER", "TIMKEN", "SKFIND", "DIXON", "KAYNES",
    "POLYCAB", "KEI", "FINOLEX", "AMBER",

    # ── Consumer Goods ──
    "GILLETTE", "PGHH", "MCDOWELL-N", "RADICO", "UNITDSPR",
    "GODFRYPHLP", "JUBLFOOD", "DEVYANI", "WESTLIFE",
    "TATAPOWER", "CESC", "TORNTPOWER", "NHPC", "SJVN", "IEX",

    # ── Chemicals ──
    "SRF", "ATUL", "FINEORG", "NAVINFLUOR", "DEEPAKNTR",
    "FLUOROCHEM", "TATACHEM", "ALKYLAMINE", "GALAXYSURF",
    "PIIND", "UPL", "SUMICHEM", "BASF", "NOCIL",
    "CLEAN", "GNFC", "GSFC", "CHAMBLFERT",

    # ── Cement & Building Materials ──
    "SHREECEM", "AMBUJACEM", "ACC", "RAMCOCEM", "DALBHARAT",
    "JKCEMENT", "JKLAKSHMI", "STARCEMENT",
    "CERA", "KAJARIA", "ASTRAL", "SUPREMEIND",

    # ── Telecom & Media ──
    "IDEA", "HFCL",
    "SUNTV", "PVRINOX", "ZEEL", "SAREGAMA", "TATACOMM",

    # ── Real Estate ──
    "DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "BRIGADE",
    "PHOENIXLTD", "SOBHA", "MAHLIFE",

    # ── Textiles & Apparel ──
    "TRENT", "ABFRL", "MANYAVAR", "CAMPUS", "RELAXO",
    "BATA", "METROBRAND", "RAYMOND", "ARVIND",

    # ── Energy & Power ──
    "ADANIGREEN", "ADANIPOWER", "TATAPOWER", "NHPC", "SJVN",
    "PGEL", "JSWENERGY",

    # ── Hospitality & Travel ──
    "INDHOTEL", "LEMON", "CHALET", "EIH",

    # ── Miscellaneous ──
    "INDIGOPNTS", "VGUARD", "SYMPHONY", "BLUESTARLT",
    "CROMPTON", "WHIRLPOOL", "GRSE", "COCHINSHIP", "MAZAGON",
    "BDL", "SOLARINDS", "LTFOODS", "KRBL",

    # ── Sugar ──
    "BALRAMCHIN", "RENUKA", "DWARIKESH", "TRIVENI", "EID",

    # ── Defence ──
    "HAL", "BEL", "BDL", "MAZAGON", "COCHINSHIP", "GRSE",

    # ── PSU Banks ──
    "SBIN", "BANKBARODA", "PNB", "CANBK", "UNIONBANK",
    "INDIANB", "IOB", "CENTRALBK", "MAHABANK", "IDBI",

    # ── Fertilizers ──
    "CHAMBLFERT", "GNFC", "GSFC", "RCF", "NFL", "DEEPAKFERT",

    # ── Additional Nifty 500 ──
    "INDIGO", "DELHIVERY", "POLICYBZR", "PAYTM", "CARTRADE",
    "NYKAA", "ZOMATO", "PATANJALI", "MAPMYINDIA",
    "DOMS", "JYOTHYLAB", "EMAMILTD", "ZYDUSLIFE",
    "TORNTPHARM", "SANOFI", "GLAXO", "PFIZER",
    "SHRIRAMFIN", "CENTRALBK", "AIAENG", "CARBORUNIV",
    "VIPIND", "LAXMIMACH", "HONAUT", "3MINDIA",
    "HATSUN", "TTML", "BAYERCROP", "FIVESTAR",
    "JBMA", "GRINFRA", "JIOFIN", "JIOFINANCE",
    "SBILIFE", "HDFCLIFE", "ICICIPRULI",
]


def get_nifty500_symbols():
    """Return deduplicated Nifty 500 symbols."""
    seen = set()
    unique = []
    for s in NIFTY_500:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def get_yfinance_symbol(nse_symbol: str) -> str:
    """Convert NSE symbol to yfinance format."""
    return f"{nse_symbol}.NS"
