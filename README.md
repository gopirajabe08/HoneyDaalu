# IntraTrading

Intraday and swing algo-trading platform for the Indian stock market (NSE).
Scans the Nifty 500 universe with six technical-analysis strategies from the
*Technical Indicator Playbook*, plus six options spread strategies driven by a
real-time market-regime detector. Trades are placed via the Fyers API; a
full-featured paper-trading mode mirrors every rule without risking capital.

## Architecture

```
┌──────────────────────────────┐      ┌────────────────────────────────┐
│  Frontend (React + Vite)     │ HTTP │  Backend (FastAPI)             │
│  Port 3000                   │◄────►│  Port 8001                     │
│  Tailwind CSS                │      │  yfinance · Fyers SDK          │
└──────────────────────────────┘      └────────────────────────────────┘
```

- **Backend** — Python FastAPI server. Handles strategy scanning, order
  management, position monitoring, trade logging, EOD analysis, and
  specialist review.
- **Frontend** — React SPA built with Vite and styled with Tailwind CSS.
  Provides dashboards for intraday, swing, and options trading with
  live/paper mode toggles, real-time logs, and daily performance stats.

## Project Structure

```
IntraTrading/
├── backend/
│   ├── main.py                     # FastAPI app — all API routes
│   ├── config.py                   # Central configuration (times, limits, params)
│   ├── nifty500.py                 # Nifty 500 stock list provider
│   ├── strategies/
│   │   ├── base.py                 # Base class + indicator helpers
│   │   ├── play1_ema_crossover.py  # Play #1: EMA-EMA Crossover
│   │   ├── play2_triple_ma.py      # Play #2: Triple MA Trend Filter
│   │   ├── play3_vwap_pullback.py  # Play #3: VWAP Intraday Pullback
│   │   ├── play4_supertrend.py     # Play #4: Supertrend Power Trend
│   │   ├── play5_bb_squeeze.py     # Play #5: BB Squeeze Breakout
│   │   ├── play6_bb_contra.py      # Play #6: BB Contra Mean Reversion
│   │   ├── options_base.py         # Options spread base class
│   │   ├── options_registry.py     # Strategy ID → instance + regime map
│   │   ├── options_bull_call_spread.py
│   │   ├── options_bull_put_spread.py
│   │   ├── options_bear_call_spread.py
│   │   ├── options_bear_put_spread.py
│   │   ├── options_iron_condor.py
│   │   └── options_long_straddle.py
│   ├── services/
│   │   ├── fyers_client.py         # Fyers OAuth + order/position API
│   │   ├── market_data.py          # yfinance OHLCV fetcher
│   │   ├── scanner.py              # Nifty 500 strategy scanner
│   │   ├── auto_trader.py          # Live intraday auto-trader
│   │   ├── paper_trader.py         # Paper intraday auto-trader
│   │   ├── swing_trader.py         # Live swing trader
│   │   ├── swing_paper_trader.py   # Paper swing trader
│   │   ├── options_auto_trader.py  # Live options intraday trader
│   │   ├── options_paper_trader.py # Paper options intraday trader
│   │   ├── options_swing_trader.py # Live options swing trader
│   │   ├── options_swing_paper_trader.py
│   │   ├── options_client.py       # Option chain + VIX via Fyers
│   │   ├── options_scanner.py      # Regime-based options scanner
│   │   ├── market_regime.py        # VIX/PCR/trend regime detector
│   │   ├── trade_logger.py         # Persistent JSON trade log
│   │   ├── eod_analyser.py         # End-of-day analysis engine
│   │   ├── specialist_analyser.py  # 6-specialist day review
│   │   └── backtester.py           # Historical backtest runner
│   ├── models/                     # Pydantic request/response models
│   ├── utils/                      # Shared utilities
│   ├── strategy_config.json        # Runtime strategy overrides
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                 # Root component + routing
│   │   ├── components/             # All page/widget components
│   │   ├── data/                   # Static mock data (strategy metadata)
│   │   ├── services/
│   │   │   ├── api.js              # Barrel re-export of all API calls
│   │   │   └── api/                # Split API modules
│   │   │       ├── base.js         # API_BASE + shared fetch helper
│   │   │       ├── market.js       # Market status, strategies, scan
│   │   │       ├── fyers.js        # Fyers auth, orders, positions
│   │   │       ├── trading.js      # Auto/paper/swing start/stop/status
│   │   │       ├── options.js      # Options trading endpoints
│   │   │       └── analysis.js     # EOD, specialist, backtest
│   │   └── utils/
│   │       ├── constants.js        # Shared constants (LOG_COLORS, etc.)
│   │       └── formatters.js       # Currency + display formatters
│   ├── index.html
│   ├── tailwind.config.js
│   └── package.json
└── README.md
```

## Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # macOS/Linux
pip install -r requirements.txt

# Create .env with Fyers credentials
cat > .env << 'EOF'
FYERS_APP_ID=<your-app-id>
FYERS_SECRET_KEY=<your-secret-key>
EOF

uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev                     # starts on port 3000
```

## Equity Strategies (Playbook)

| # | Name | Indicators | Timeframes |
|---|------|-----------|------------|
| 1 | EMA-EMA Crossover | 9 EMA / 21 EMA / 50 SMA filter | 5m, 15m (intraday) · 1h, 1d (swing) |
| 2 | Triple MA Trend Filter | 20 EMA / 50 SMA / 200 SMA | 15m (intraday) · 1h, 1d (swing) |
| 3 | VWAP Intraday Pullback | Session VWAP | 5m (intraday only) |
| 4 | Supertrend Power Trend | ATR 10, Mult 3 + 20 EMA | 5m, 15m (intraday only) |
| 5 | BB Squeeze Breakout | BB(20,2) | 15m (intraday) · 1d (swing) |
| 6 | BB Contra Mean Reversion | BB(20,2) + 200 SMA | 5m, 15m (intraday) · 1d (swing) |

## Options Strategies

| Strategy | Type | Regime |
|----------|------|--------|
| Bull Call Spread | Debit | Strongly/Mildly Bullish |
| Bull Put Spread | Credit | Mildly Bullish |
| Bear Call Spread | Credit | Mildly Bearish |
| Bear Put Spread | Debit | Strongly/Mildly Bearish |
| Iron Condor | Credit | Neutral / Range-bound |
| Long Straddle | Debit | High Volatility |

Strategy selection is automatic based on a real-time market regime detector
that combines India VIX, PCR (put-call ratio), and Nifty trend.

## API Endpoints

### Market & Strategies
- `GET /api/market/status` — market open/closed status
- `GET /api/strategies` — list all 6 equity strategies
- `GET /api/scan/{strategy_id}?timeframe=15m&capital=100000` — scan Nifty 500

### Fyers Integration
- `GET /api/fyers/status` — connection status
- `GET /api/fyers/login` — OAuth login URL
- `GET /api/fyers/callback` — OAuth callback
- `POST /api/fyers/order` — place market order
- `POST /api/fyers/order/bracket` — place bracket order
- `GET /api/fyers/positions` — open positions
- `GET /api/fyers/orders` — order book
- `GET /api/fyers/funds` — available funds

### Equity Trading
- `POST /api/auto/start` — start live intraday auto-trader
- `POST /api/auto/stop` — stop live intraday auto-trader
- `GET /api/auto/status` — live intraday status + logs
- `POST /api/paper/start` — start paper intraday trader
- `POST /api/paper/stop` / `GET /api/paper/status`
- `POST /api/swing/start` / `stop` / `GET /api/swing/status`
- `POST /api/swing-paper/start` / `stop` / `GET /api/swing-paper/status`

### Options Trading
- `GET /api/options/strategies` — list 6 options strategies
- `GET /api/options/regime?underlying=NIFTY` — market regime
- `GET /api/options/scan/{underlying}` — scan for spreads
- `GET /api/options/chain/{underlying}` — option chain
- `POST /api/options/auto/start` / `stop` / `GET status`
- `POST /api/options/paper/start` / `stop` / `GET status`
- `POST /api/options/swing/start` / `stop` / `GET status`
- `POST /api/options/swing-paper/start` / `stop` / `GET status`

### Analysis
- `GET /api/trades/history?days=30&source=auto` — trade history
- `GET /api/trades/daily-pnl?days=30` — daily P&L breakdown
- `GET /api/strategy/stats?source=auto` — per-strategy win rates
- `POST /api/backtest` — run historical backtest
- `POST /api/eod/analyse` — end-of-day analysis
- `POST /api/specialist/{id}/analyse` — specialist day review
- `POST /api/specialist/deploy` — deploy a recommendation

## Configuration

All tunable parameters are centralized in `backend/config.py`:

- **Time windows** — order start (12:00 PM), cutoff (2:00 PM), square-off (3:15 PM)
- **Position limits** — intraday live: 4, paper: 10, swing live: 1, paper: 5
- **Price filters** — intraday: 50-5000, swing: 100-1500
- **Scan intervals** — intraday on-demand, swing scheduled (9:20 AM + 3:35 PM for daily)
- **Options** — lot sizes, strike intervals, expiry preference, max positions, strategy parameters

Runtime overrides are stored in `backend/strategy_config.json` and can be
deployed via the specialist/EOD analysis endpoints.

## Key Design Decisions

- **Singleton traders** — each trader (auto, paper, swing, options) is a
  module-level singleton. Only one instance runs at a time; state survives
  across API calls without a database.
- **State persistence** — active positions and trade history are persisted to
  JSON files so the trader can resume after a server restart.
- **IST timezone** — all time logic uses `UTC+05:30` explicitly. Market hours,
  scan schedules, and log timestamps are in IST.
- **On-demand scanning** — intraday traders scan only when a position slot
  opens (not on a fixed timer), reducing yfinance API calls.
- **Live/paper parity** — paper traders execute the exact same code paths as
  live traders; only the order-placement step is simulated.
- **2% risk per trade** — position sizing calculates quantity so that the
  distance from entry to stop-loss represents 2% of capital.
