#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# HoneyDaalu — Deploy script (runs on EC2 server)
#
# Called by GitHub Actions on every push to main.
# Can also be run manually: ssh -i key.pem ubuntu@<ip> 'bash /opt/honeydaalu/deploy.sh'
# ═══════════════════════════════════════════════════════════════════════

set -e

APP_DIR="/opt/honeydaalu/app"
LOG="/var/log/honeydaalu/deploy.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"
}

log "═══ Deploy started ═══"

# ── Pull latest code ──
cd "$APP_DIR"
git fetch origin main
git reset --hard origin/main
log "Code updated to $(git rev-parse --short HEAD)"

# ── Backend dependencies (only if requirements changed) ──
cd "$APP_DIR/backend"
if git diff HEAD~1 --name-only | grep -q "requirements.txt"; then
    log "requirements.txt changed — installing dependencies..."
    ./venv/bin/pip install -r requirements.txt --quiet
else
    log "No dependency changes — skipping pip install"
fi

# ── Frontend build (only if frontend changed) ──
# Nginx serves from /opt/honeydaalu/frontend/dist (NOT $APP_DIR/frontend/dist).
# After building, sync the output to the nginx doc root.
NGINX_FRONTEND_DIR="/opt/honeydaalu/frontend/dist"
if git diff HEAD~1 --name-only | grep -q "frontend/"; then
    log "Frontend changed — rebuilding..."
    cd "$APP_DIR/frontend"
    npm install --silent
    npm run build
    log "Frontend built — syncing to $NGINX_FRONTEND_DIR"
    sudo mkdir -p "$NGINX_FRONTEND_DIR"
    sudo rsync -a --delete "$APP_DIR/frontend/dist/" "$NGINX_FRONTEND_DIR/"
    log "Frontend deployed to nginx root"
else
    log "No frontend changes — skipping build"
fi

# ── Restart backend ONLY during market hours (9:00-15:45 IST) ──
HOUR=$(TZ="Asia/Kolkata" date +%H)
MIN=$(TZ="Asia/Kolkata" date +%M)
IST_TIME="${HOUR}${MIN}"

if [ "$IST_TIME" -ge "0900" ] && [ "$IST_TIME" -le "1545" ] && systemctl is-active --quiet honeydaalu-backend; then
    log "Market hours + backend running — restarting with new code..."
    sudo systemctl restart honeydaalu-backend
    sleep 3
    if systemctl is-active --quiet honeydaalu-backend; then
        log "Backend restarted successfully"
    else
        log "ERROR: Backend failed to start after deploy!"
    fi
else
    log "Outside market hours — code updated, NO restart. Next start at 9:00 AM."
    # Stop the service if it's running after hours (shouldn't be)
    if systemctl is-active --quiet honeydaalu-backend && [ "$IST_TIME" -gt "1545" ]; then
        log "Stopping backend (after market hours)..."
        sudo systemctl stop honeydaalu-backend
    fi
fi

log "═══ Deploy complete ═══"
