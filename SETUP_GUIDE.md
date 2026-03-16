# SmartAlgo — Setup Guide

## If your laptop dies / new machine setup

### Step 1: Install prerequisites

```bash
# Install Homebrew (Mac)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.13+
brew install python@3.13

# Install Node.js 20+
brew install node

# Install Git
brew install git
```

### Step 2: Clone the repo

```bash
cd ~/Documents
git clone https://github.com/gopirajabe08/SmartAlgo.git
cd SmartAlgo
```

### Step 3: Setup Backend

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt

# Create .env file with your Fyers credentials
cat > .env << 'EOF'
FYERS_APP_ID=your_app_id_here
FYERS_SECRET_KEY=your_secret_key_here
FYERS_REDIRECT_URI=http://localhost:8001/api/fyers/callback
FYERS_TOTP_SECRET=your_totp_secret_here
FYERS_PIN=your_pin_here
FYERS_CLIENT_ID=your_client_id_here
EOF

# Edit .env with your actual Fyers credentials
# Get them from: https://myapi.fyers.in/dashboard
nano .env

cd ..
```

### Step 4: Setup Frontend

```bash
cd frontend
npm install
cd ..
```

### Step 5: Setup Mobile (optional — for Android APK)

```bash
cd mobile
npm install

# Install Android SDK (for APK build)
brew install --cask android-commandlinetools

# Build APK
cd android
./gradlew assembleRelease
# APK at: android/app/build/outputs/apk/release/app-release.apk

cd ../..
```

### Step 6: Start the application

```bash
# Terminal 1 — Backend
cd backend && source venv/bin/activate && python main.py

# Terminal 2 — Frontend
cd frontend && npm run dev
```

### Step 7: Access the app

- **Web**: http://localhost:3000
- **Backend API**: http://localhost:8001
- **Login to Fyers** from the Dashboard sidebar before trading

---

## Daily Trading Routine

### Morning setup

```bash
# Start backend
cd SmartAlgo/backend && source venv/bin/activate && python main.py &

# Start frontend
cd SmartAlgo/frontend && npm run dev &

# Prevent Mac sleep (if closing lid)
caffeinate -d -i -s &
```

### Start engines

| Time | Engine | Capital | Mode |
|---|---|---|---|
| **9:50 AM** | Options Intraday Paper | ₹25K | Auto regime |
| **11:50 AM** | Equity Intraday Paper | ₹75K | Auto regime |
| **11:50 AM** | Equity Swing Paper | ₹50K | Manual (Play 1,2,5,6) |
| **11:50 AM** | Futures Intraday Paper | ₹1L | Auto regime |
| **11:50 AM** | Futures Swing Paper | ₹1L | Manual (all 4) |

### Auto square-off

- Options: **3:00 PM**
- Equity + Futures: **3:15 PM**
- Swing positions carry overnight

---

## Key files to backup separately

These are NOT in git (contain secrets/data):

| File | Contains | How to backup |
|---|---|---|
| `backend/.env` | Fyers API credentials | Save in password manager |
| `backend/.fyers_token` | Session token (expires daily) | No backup needed |
| `backend/.trade_history.json` | All trade records | Copy to Google Drive weekly |
| `backend/*_state.json` | Engine state files | Recreated each day |

---

## Architecture overview

```
SmartAlgo/
├── backend/                    # FastAPI + Python
│   ├── main.py                 # 96 API endpoints
│   ├── config.py               # All configuration
│   ├── services/
│   │   ├── auto_trader.py      # Equity intraday live
│   │   ├── paper_trader.py     # Equity intraday paper
│   │   ├── swing_trader.py     # Equity swing live
│   │   ├── options_*.py        # 4 options engines
│   │   ├── futures_*.py        # 4 futures engines
│   │   ├── equity_regime.py    # Equity auto strategy selection
│   │   ├── market_regime.py    # Options regime (VIX+PCR+intraday)
│   │   ├── futures_regime.py   # Futures regime (OI+trend+VIX)
│   │   ├── fyers_client.py     # Fyers API wrapper
│   │   └── scanner.py          # Stock scanner (Nifty 500)
│   ├── strategies/
│   │   ├── play1-6_*.py        # 6 equity strategies
│   │   ├── options_*.py        # 6 options spread strategies
│   │   └── futures_*.py        # 4 futures strategies
│   └── fno_stocks.py           # ~180 F&O stocks with lot sizes
├── frontend/                   # React + Vite + Tailwind
│   └── src/components/         # All UI pages
├── mobile/                     # React Native + Expo
│   └── app/(tabs)/             # Mobile tab screens
└── SETUP_GUIDE.md              # This file
```

## Risk controls

| Control | Equity | Options | Futures |
|---|---|---|---|
| SL floor | 1.2% min | Spread-based | 1.2% min |
| Daily loss limit | 5% | 5% | 5% |
| Exchange SL-M | ✓ (live) | — | ✓ (live) |
| Max orders/scan | 2 | — | — |
| Loss cooldown | — | 30 min | — |
| VIX filter | 5m→15m if >18 | Regime adapts | Regime adapts |
| Order verification | ✓ (live) | — | — |
| Liquidity filter | — | — | ✓ |

## Ports

| Service | Port |
|---|---|
| Backend API | 8001 |
| Frontend dev | 3000 |
| Fyers callback | 8001 (same as backend) |
