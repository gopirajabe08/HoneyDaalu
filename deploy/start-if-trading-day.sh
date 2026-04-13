#!/bin/bash
# ── Start LuckyNavi only on trading days ──
# Called by cron at 9:00 AM IST (3:30 AM UTC) Mon-Fri.
# Skips NSE holidays by checking backend/config.py's NSE_HOLIDAYS dict.

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

APP_DIR="/opt/luckynavi/app"
LOG="/var/log/luckynavi/cron.log"

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

echo "[$TODAY] Trading day — starting LuckyNavi backend" >> "$LOG"
/usr/bin/sudo /usr/bin/systemctl start luckynavi-backend >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
    echo "[$TODAY] Service started successfully" >> "$LOG"
else
    echo "[$TODAY] ERROR: Failed to start service" >> "$LOG"
fi
