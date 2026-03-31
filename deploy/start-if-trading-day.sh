#!/bin/bash
# ── Start IntraTrading only on trading days ──
# Called by cron at 9:00 AM IST (3:30 AM UTC) Mon-Fri.
# Skips NSE holidays by checking backend/config.py's NSE_HOLIDAYS dict.

APP_DIR="/opt/intratrading/app"
LOG="/var/log/intratrading/cron.log"

TODAY=$(TZ="Asia/Kolkata" date +%Y-%m-%d)

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
")

if [ -n "$IS_HOLIDAY" ]; then
    echo "[$TODAY] Skipping start — NSE holiday: $IS_HOLIDAY" >> "$LOG"
    exit 0
fi

echo "[$TODAY] Trading day — starting IntraTrading backend" >> "$LOG"
sudo systemctl start intratrading-backend
