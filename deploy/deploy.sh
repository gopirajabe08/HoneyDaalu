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
if git diff HEAD~1 --name-only | grep -q "frontend/"; then
    log "Frontend changed — rebuilding..."
    cd "$APP_DIR/frontend"
    npm install --silent
    npm run build
    log "Frontend built"
else
    log "No frontend changes — skipping build"
fi

# ── Restart backend ONLY if it's currently running ──
# Don't start it outside market hours — the cron handles that
if systemctl is-active --quiet honeydaalu-backend; then
    log "Backend is running — restarting with new code..."
    sudo systemctl restart honeydaalu-backend
    sleep 3
    if systemctl is-active --quiet honeydaalu-backend; then
        log "Backend restarted successfully"
    else
        log "ERROR: Backend failed to start after deploy!"
        log "Check: journalctl -u honeydaalu-backend -n 50"
    fi
else
    log "Backend is not running (market closed) — code updated, will start at 9:00 AM"
fi

log "═══ Deploy complete ═══"
