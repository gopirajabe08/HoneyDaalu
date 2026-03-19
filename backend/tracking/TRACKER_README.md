# Strategy Attribution Tracker

## Purpose
This tracking system ensures data-driven decision making for all strategy parameter changes.
Claude MUST reference these files before making ANY trading-related code changes.

## File Structure
```
backend/tracking/
├── strategy_registry.json    — Master registry of ALL strategy parameters
├── changelog.json            — Every parameter change with date + reason + data
├── TRACKER_README.md         — This file (instructions for Claude)
└── daily/
    └── YYYY-MM-DD.json       — Auto-generated daily performance reports
```

## Rules for Claude (ANY conversation, ANY session)

### Before Making ANY Strategy/Trading Changes:
1. Read `strategy_registry.json` — know current parameter values
2. Read last 3 daily reports in `daily/` — understand recent performance
3. Read `changelog.json` — know what was already changed and why
4. Identify the specific problem with DATA (not intuition)
5. Log the proposed change in `changelog.json` FIRST
6. Only then modify the actual strategy code
7. Update `strategy_registry.json` with new values

### After Market Close Each Day:
1. Fetch today's trade data from API endpoints
2. Generate `daily/YYYY-MM-DD.json` report
3. Compare with previous days — spot trends
4. Update `strategy_registry.json` performance_notes if needed

### Parameter Change Protocol:
```json
{
  "date": "YYYY-MM-DD",
  "file": "backend/strategies/play4_supertrend.py",
  "parameter": "atr_multiplier",
  "before": 1.5,
  "after": 2.5,
  "reason": "5 of 12 SL hits in last 5 days were within normal noise range (< 1% from entry). Increasing to 2.5x gives trades room to breathe.",
  "data_backing": "Daily reports 03-14 to 03-18: avg time-to-SL = 28 min, avg SL distance = 0.9%",
  "expected_impact": "Reduce premature SL hits by ~50%, accept slightly larger losses on true reversals",
  "rollback_trigger": "If win rate drops below 40% over next 5 days, revert to 1.5x"
}
```

### Key API Endpoints for Data Collection:
- `GET /api/trades/history?days=1&source=paper` — today's paper trades
- `GET /api/trades/history?days=1&source=auto` — today's live trades
- `GET /api/paper/status` — intraday paper engine status + logs
- `GET /api/auto/status` — intraday live engine status
- `GET /api/swing/status` — swing live status
- `GET /api/swing-paper/status` — swing paper status
- `GET /api/options/paper/status` — options paper status
- `GET /api/futures/paper/status` — futures paper status
- `GET /api/futures/swing-paper/status` — futures swing paper status
- `GET /api/market/status` — market open/close
- `GET /api/regime` — current equity regime detection

## Never Do:
- Change parameters without logging in changelog.json
- Trust a single day's data — need 3-5 days minimum
- Make multiple parameter changes simultaneously (can't attribute results)
- Delete daily reports (they're the historical record)
- Change parameters during market hours (wait for square-off)
