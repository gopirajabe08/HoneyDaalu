"""
Central configuration for LuckyNavi.

All tunable parameters live here — time windows, position limits, intervals,
price filters, strategy settings, and options config. Traders import from
this module rather than hard-coding values.
"""

# ── General ──────────────────────────────────────────────────────────────────

# Default capital in INR
DEFAULT_CAPITAL = 100000

# ── NSE Trading Holidays ────────────────────────────────────────────────────
# Weekday holidays when NSE is closed (excludes Sat/Sun — already handled).
# Update annually from: https://www.nseindia.com/resources/exchange-communication-holidays

NSE_HOLIDAYS = {
    # 2025
    "2025-02-26": "Maha Shivaratri",
    "2025-03-14": "Holi",
    "2025-03-31": "Id-ul-Fitr (Ramzan Eid)",
    "2025-04-10": "Mahavir Jayanti",
    "2025-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
    "2025-04-18": "Good Friday",
    "2025-05-01": "Maharashtra Day",
    "2025-08-15": "Independence Day",
    "2025-08-27": "Ganesh Chaturthi",
    "2025-10-02": "Mahatma Gandhi Jayanti / Dasara",
    "2025-10-21": "Diwali-Laxmi Pujan",
    "2025-10-22": "Diwali-Balipratipada",
    "2025-11-05": "Guru Nanak Jayanti",
    "2025-12-25": "Christmas",
    # 2026
    "2026-01-26": "Republic Day",
    "2026-03-03": "Holi",
    "2026-03-26": "Ram Navami",
    "2026-03-31": "Mahavir Jayanti",
    "2026-04-03": "Good Friday",
    "2026-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
    "2026-05-01": "Maharashtra Day",
    "2026-05-28": "Bakri Id / Eid ul-Adha",
    "2026-06-26": "Muharram",
    "2026-09-14": "Ganesh Chaturthi",
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-20": "Dasara",
    "2026-11-10": "Diwali-Balipratipada",
    "2026-11-24": "Guru Nanak Jayanti",
    "2026-12-25": "Christmas",
}

# ── Intraday Trading Time Windows (IST) ──────────────────────────────────────
# Previously hard-coded in auto_trader.py and paper_trader.py

INTRADAY_ORDER_START_HOUR, INTRADAY_ORDER_START_MIN = 10, 30   # 10:30 AM — start placing orders
INTRADAY_ORDER_CUTOFF_HOUR, INTRADAY_ORDER_CUTOFF_MIN = 13, 30  # 1:30 PM — stop placing new orders (need 1.75h for trade to develop)
INTRADAY_SQUAREOFF_HOUR, INTRADAY_SQUAREOFF_MIN = 15, 20       # 3:20 PM — square off (before broker auto-square at 3:25)
INTRADAY_MARKET_CLOSE_HOUR, INTRADAY_MARKET_CLOSE_MIN = 15, 30 # 3:30 PM — market closes

# ── Intraday Position Limits ─────────────────────────────────────────────────

INTRADAY_CAPITAL_PER_POSITION = 25000  # Full capital on 1 best trade (Phase 1)
INTRADAY_MIN_POSITIONS = 1
INTRADAY_MAX_POSITIONS_CAP = 1        # Only 1 position — pick the BEST signal, full conviction
INTRADAY_PAPER_MAX_POSITIONS = 10     # paper: more positions for testing
INTRADAY_POSITION_CHECK_INTERVAL = 20  # seconds between LTP checks (reduced from 60s for faster reaction)

# Timeframe options per strategy (intraday only)
STRATEGY_TIMEFRAMES = {
    "play1_ema_crossover": ["5m", "15m"],
    "play2_triple_ma": ["15m"],
    "play3_vwap_pullback": ["5m"],
    "play4_supertrend": ["5m", "15m"],
    "play5_bb_squeeze": ["15m"],
    "play6_bb_contra": ["5m", "15m"],
    "play7_orb": ["15m"],                  # ORB needs 15m (first 2 candles = 30min range)
    "play8_rsi_divergence": ["15m"],       # RSI divergence on 15m for intraday
    "play9_gap_analysis": ["15m"],         # Gap analysis needs 15m (first 2-4 candles for gap detection)
    "play10_momentum_rank": ["15m"],       # Momentum ranking on 15m intraday
}

# Swing trading timeframes (positions carry over days)
SWING_STRATEGY_TIMEFRAMES = {
    "play1_ema_crossover": ["1h", "1d"],
    "play2_triple_ma": ["1h", "1d"],
    "play4_supertrend": ["1d"],
    "play5_bb_squeeze": ["1d"],
    "play6_bb_contra": ["1d"],
    "play8_rsi_divergence": ["1h", "1d"],  # RSI divergence works well on daily for swing
}

# Swing trading settings
SWING_SCAN_INTERVAL_SECONDS = 4 * 60 * 60  # 4 hours default
SWING_MAX_POSITIONS = 1       # live: only 1 open position at a time
SWING_PAPER_MAX_POSITIONS = 5  # paper: more positions to test strategies

# ── BTST (Buy Today Sell Tomorrow) Trading Time Windows ──────────────────────
BTST_ORDER_START_HOUR, BTST_ORDER_START_MIN = 14, 0    # 2:00 PM — buy late afternoon when momentum is confirmed
BTST_ORDER_CUTOFF_HOUR, BTST_ORDER_CUTOFF_MIN = 15, 15  # 3:15 PM — last entry before market close
BTST_POSITION_CHECK_INTERVAL = 60  # seconds

BTST_CAPITAL_PER_POSITION = 25000
BTST_MIN_POSITIONS = 1
BTST_MAX_POSITIONS = 2  # Conservative — holds overnight
BTST_PAPER_MAX_POSITIONS = 4

BTST_EXIT_PROFIT_TARGET_PCT = 2.0   # Exit at +2% profit next day
BTST_EXIT_LOSS_LIMIT_PCT = 1.5      # Exit at -1.5% loss next day
BTST_MAX_HOLD_DAYS = 2              # Force exit after 2 trading days

BTST_STRATEGY_TIMEFRAMES = {
    "play1_ema_crossover": ["1d"],
    "play4_supertrend": ["1d"],
    "play5_bb_squeeze": ["1d"],
    "play6_bb_contra": ["1d"],
    "play8_rsi_divergence": ["1h", "1d"],
    "play10_momentum_rank": ["1d"],
}

# Price range filter — skip stocks outside this range
# Keeps position sizing meaningful and reduces brokerage impact
INTRADAY_MIN_PRICE = 50   # ₹50 minimum (skip penny stocks)
INTRADAY_MAX_PRICE = 5000 # ₹5,000 maximum (skip extreme-priced, low-qty trades)
SWING_MIN_PRICE = 100     # ₹100 minimum (skip penny stocks)
SWING_MAX_PRICE = 1500    # ₹1,500 maximum (skip high-priced, low-qty trades)

# Daily scheduled scan times (IST) for swing trading with 1d candles
# Morning: 9:20 AM — uses yesterday's completed daily candle → place orders at open
# EOD: 3:35 PM — uses today's just-completed daily candle → identify signals for tomorrow
SWING_DAILY_SCAN_TIMES = [(9, 20), (15, 35)]

# yfinance period for each interval
INTERVAL_PERIOD_MAP = {
    # "3m": removed — yfinance no longer supports 3m interval

    "5m": "30d",
    "15m": "30d",
    "30m": "30d",
    "1h": "60d",
    "1d": "200d",
}

# Minimum candles required for each strategy
MIN_CANDLES = {
    "play1_ema_crossover": 55,    # need 50 SMA
    "play2_triple_ma": 210,       # need 200 SMA
    "play3_vwap_pullback": 15,
    "play4_supertrend": 25,
    "play5_bb_squeeze": 30,
    "play6_bb_contra": 210,       # need 200 SMA
}

# VWAP time filter (IST)
VWAP_MARKET_OPEN_OFFSET_MIN = 15   # trade 15 min after open
VWAP_MARKET_CLOSE_OFFSET_MIN = 60  # stop 1 hour before close

# ── Options Trading Config ─────────────────────────────────────────────────

OPTIONS_UNDERLYINGS = ["NIFTY", "BANKNIFTY"]

OPTIONS_LOT_SIZES = {
    "NIFTY": 65,       # Updated Mar 2026 (was 25, broker min lot = 65)
    "BANKNIFTY": 30,    # Updated Mar 2026 (was 15, broker min lot = 30)
}

# Broker symbol prefixes for options
OPTIONS_SYMBOL_PREFIX = {
    "NIFTY": "NSE:NIFTY",
    "BANKNIFTY": "NSE:BANKNIFTY",
}

# Index symbols for fetching spot price
OPTIONS_INDEX_SYMBOLS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
}

# Strike interval (gap between consecutive strikes)
OPTIONS_STRIKE_INTERVAL = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
}

OPTIONS_DEFAULT_CAPITAL = 200000
OPTIONS_CAPITAL_PER_POSITION = 20000  # ~₹20K per spread (auto-calculates max positions from capital)
OPTIONS_MIN_POSITIONS = 1
OPTIONS_MAX_POSITIONS_CAP = 4         # hard cap per underlying
OPTIONS_MAX_POSITIONS = 3  # default fallback per underlying
OPTIONS_EXPIRY_PREFERENCE = "weekly"  # weekly for intraday, monthly for swing

# Options time cutoffs (IST)
OPTIONS_ORDER_START_HOUR, OPTIONS_ORDER_START_MIN = 10, 0  # 10:00 AM
OPTIONS_ORDER_CUTOFF_HOUR, OPTIONS_ORDER_CUTOFF_MIN = 14, 0  # 2:00 PM
OPTIONS_SQUAREOFF_HOUR, OPTIONS_SQUAREOFF_MIN = 15, 0  # 3:00 PM (before 3:15 intraday)
OPTIONS_POSITION_CHECK_INTERVAL = 15  # seconds
OPTIONS_DAILY_LOSS_LIMIT_PCT = 5.0  # Stop opening new positions if daily realized loss exceeds this % of capital
OPTIONS_MAX_BID_ASK_SPREAD_PCT = 5.0  # Skip options with bid-ask spread wider than this %
OPTIONS_SKIP_EXPIRY_DAY = False  # Disabled — trade every day including expiry. Use wider SL on expiry days instead.

# Swing options
OPTIONS_SWING_MAX_POSITIONS = 2
OPTIONS_SWING_SCAN_INTERVAL_SECONDS = 4 * 60 * 60  # 4 hours
OPTIONS_SWING_EXIT_DAYS_BEFORE_EXPIRY = 2

# Strategy parameters
OPTIONS_STRATEGY_PARAMS = {
    "bull_call_spread": {"otm_offset": 2, "profit_target_pct": 0.50, "stop_loss_mult": 1.0},
    "bull_put_spread": {"otm_offset": 2, "profit_target_pct": 0.50, "stop_loss_mult": 1.0},
    "bear_call_spread": {"otm_offset": 2, "profit_target_pct": 0.50, "stop_loss_mult": 1.0},
    "bear_put_spread": {"otm_offset": 2, "profit_target_pct": 0.50, "stop_loss_mult": 1.0},
    "iron_condor": {"otm_offset": 3, "profit_target_pct": 0.50, "stop_loss_mult": 1.0},
    "long_straddle": {"profit_target_pct": 0.30, "stop_loss_mult": 0.50},
}

# ── Futures Trading Config ────────────────────────────────────────────────

# Intraday time windows (same as equity by default)
FUTURES_ORDER_START_HOUR, FUTURES_ORDER_START_MIN = 11, 0    # 11:00 AM
FUTURES_ORDER_CUTOFF_HOUR, FUTURES_ORDER_CUTOFF_MIN = 14, 0  # 2:00 PM
FUTURES_SQUAREOFF_HOUR, FUTURES_SQUAREOFF_MIN = 15, 15       # 3:15 PM

# Position limits
FUTURES_MAX_POSITIONS_CAP = 4         # hard cap for live intraday
FUTURES_PAPER_MAX_POSITIONS = 8       # paper: more positions for testing
FUTURES_POSITION_CHECK_INTERVAL = 60  # seconds between LTP checks

# Margin assumption
# Overnight (MARGIN product): ~15-20% SPAN + exposure
# Intraday (INTRADAY product): brokers offer ~50% of normal ≈ 8-12%
FUTURES_MARGIN_PCT_INTRADAY = 0.10  # 10% for intraday (MIS/INTRADAY)
FUTURES_MARGIN_PCT_OVERNIGHT = 0.20  # 20% for swing (MARGIN)

# Risk per trade (% of capital)
# Conservative: 2-3% (institutional), Moderate: 5% (default), Aggressive: 10% (small capital)
FUTURES_RISK_PER_TRADE_PCT = 0.02  # 2% conservative — reduced from 5% to limit per-trade exposure

# Daily loss circuit breaker — stop engine if daily realized loss exceeds this % of capital
FUTURES_DAILY_LOSS_LIMIT_PCT = 5.0

# Liquidity filters — skip futures contracts with low OI/volume
FUTURES_MIN_OI = 1000         # minimum open interest (in shares, not lots)
FUTURES_MIN_DAILY_VOLUME = 10000  # minimum daily volume — lowered from 50K to include more liquid stocks

# Square-off retry
FUTURES_SQUAREOFF_MAX_RETRIES = 3

# Swing futures
FUTURES_SWING_MAX_POSITIONS = 2
FUTURES_SWING_PAPER_MAX_POSITIONS = 5
FUTURES_SWING_SCAN_INTERVAL_SECONDS = 4 * 60 * 60  # 4 hours
FUTURES_SWING_EXIT_DAYS_BEFORE_EXPIRY = 2  # close 2 days before expiry

# ── VIX-Adjusted SL Multipliers ──────────────────────────────────────────
# In high VIX, intraday noise is larger → fixed ATR SL gets hit more often.
# Widen SL (and target) proportionally to avoid premature exits.
VIX_SL_ADJUSTMENTS = {
    "low": {"threshold": 14, "atr_mult": 2.0},      # Low VIX: tighter SL ok
    "normal": {"threshold": 18, "atr_mult": 2.5},    # Normal
    "elevated": {"threshold": 22, "atr_mult": 3.0},  # Elevated: wider SL
    "high": {"threshold": 99, "atr_mult": 3.5},      # High VIX: widest SL
}

# ── Phase 1 Test Mode ──────────────────────────────────────────────────────
# Friday: 2 shares (prove partial exit + 3-order model)
# Monday: full qty (best day 58% win rate)
PHASE1_TEST_MODE = True   # Still testing 3-order model
PHASE1_TEST_QTY = 2       # 2 shares: proves partial exit + minimal risk

# ── Day-of-Week Strategy Adjustment ──────────────────────────────────────
# Research: Monday 58% win, Tuesday 39%, Wednesday 54%, Thursday 44%, Friday 44%
# 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday
DAY_CONFIDENCE = {
    0: 1.0,    # Monday — BEST day, full confidence
    1: 0.5,    # Tuesday — WORST day, very selective
    2: 0.8,    # Wednesday — decent
    3: 0.6,    # Thursday — expiry day, cautious
    4: 0.6,    # Friday — weak, cautious
}
