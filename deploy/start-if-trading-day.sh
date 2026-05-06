#!/bin/bash
# ── Start HoneyDaalu only on trading days ──
# Called by cron at 9:00 AM IST (3:30 AM UTC) Mon-Fri.
# Skips NSE holidays by checking backend/config.py's NSE_HOLIDAYS dict.

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

APP_DIR="/opt/honeydaalu/app"
LOG="/var/log/honeydaalu/cron.log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG")" 2>/dev/null || true

TODAY=$(TZ="Asia/Kolkata" date +%Y-%m-%d)

echo "[$TODAY] Cron script started" >> "$LOG"

# Check if today is an NSE holiday using the same config the backend uses
IS_HOLIDAY=$("$APP_DIR/backend/venv/bin/python3" -c "
import sys
sys.path.insert(0, '$APP_DIR/backend')
from config import NSE_HOLIDAYS
today = '$TODAY'
if today in NSE_HOLIDAYS:
    print(NSE_HOLIDAYS[today])
else:
    print('')
" 2>> "$LOG")

if [ $? -ne 0 ]; then
    echo "[$TODAY] ERROR: Holiday check Python script failed" >> "$LOG"
fi

if [ -n "$IS_HOLIDAY" ]; then
    echo "[$TODAY] Skipping start — NSE holiday: $IS_HOLIDAY" >> "$LOG"
    exit 0
fi

# 2026-05-06 — Use `restart` not `start`. systemd's `start` is a no-op
# when service is already running, so AutoStart logic in main.py never
# re-fires. That left engines silently dead today after backend was
# accidentally left running overnight from yesterday's bot token swap.
# `restart` is idempotent: starts if stopped, restarts if running.
# Pre-market timing (09:00 IST, 15 min before market opens) means no
# active trades to disturb. State-persistence fix (paper_trader.py +
# swing_paper_trader.py) preserves any data across the restart.
echo "[$TODAY] Trading day — restarting HoneyDaalu backend (forces AutoStart re-fire)" >> "$LOG"
/usr/bin/sudo /usr/bin/systemctl restart honeydaalu-backend >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
    echo "[$TODAY] Service restarted successfully — AutoStart will re-fire" >> "$LOG"
else
    echo "[$TODAY] ERROR: Failed to restart service" >> "$LOG"
fi
