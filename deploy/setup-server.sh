#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# IntraTrading — AWS EC2 Server Setup (run ONCE on fresh Ubuntu 24.04)
#
# Usage: ssh -i key.pem ubuntu@<elastic-ip> 'bash -s' < setup-server.sh
# ═══════════════════════════════════════════════════════════════════════

set -e

echo "═══ IntraTrading Server Setup ═══"

# ── System packages ──
sudo apt-get update -y
sudo apt-get install -y \
    python3.12 python3.12-venv python3-pip \
    nginx certbot python3-certbot-nginx \
    git curl jq unzip htop \
    build-essential libffi-dev libssl-dev

# ── Create app user ──
sudo useradd -m -s /bin/bash intratrading 2>/dev/null || true
sudo mkdir -p /opt/intratrading
sudo chown intratrading:intratrading /opt/intratrading

# ── Clone repo (first time) or pull (subsequent) ──
if [ ! -d /opt/intratrading/app/.git ]; then
    echo "Cloning repository..."
    sudo -u intratrading git clone https://github.com/YOUR_USERNAME/IntraTrading.git /opt/intratrading/app
else
    echo "Repository exists — pulling latest..."
    sudo -u intratrading git -C /opt/intratrading/app pull origin main
fi

# ── Backend: Python venv + dependencies ──
cd /opt/intratrading/app/backend
sudo -u intratrading python3.12 -m venv venv
sudo -u intratrading ./venv/bin/pip install --upgrade pip
sudo -u intratrading ./venv/bin/pip install -r requirements.txt

# ── Frontend: Build static files ──
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
cd /opt/intratrading/app/frontend
sudo -u intratrading npm install
sudo -u intratrading npm run build

# ── Create .env placeholder ──
if [ ! -f /opt/intratrading/app/backend/.env ]; then
    cat > /tmp/env_template << 'ENVEOF'
# Fyers Credentials (fill in)
FYERS_APP_ID=
FYERS_SECRET_KEY=
FYERS_TOTP_SECRET=
FYERS_PIN=

# Telegram Notifications
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ENVEOF
    sudo mv /tmp/env_template /opt/intratrading/app/backend/.env
    sudo chown intratrading:intratrading /opt/intratrading/app/backend/.env
    sudo chmod 600 /opt/intratrading/app/backend/.env
    echo "⚠️  Fill in /opt/intratrading/app/backend/.env with your credentials!"
fi

# ── Systemd service: Backend ──
sudo tee /etc/systemd/system/intratrading-backend.service > /dev/null << 'EOF'
[Unit]
Description=IntraTrading Backend (FastAPI)
After=network.target

[Service]
Type=simple
User=intratrading
Group=intratrading
WorkingDirectory=/opt/intratrading/app/backend
ExecStart=/opt/intratrading/app/backend/venv/bin/python main.py
Restart=no
RestartSec=10
Environment=PYTHONUNBUFFERED=1

# Don't auto-restart — the app has its own lifecycle (auto-shutdown at 3:45 PM)
# Restart=no prevents the crash loop that caused 400+ Telegram messages

StandardOutput=append:/var/log/intratrading/backend.log
StandardError=append:/var/log/intratrading/backend.log

[Install]
WantedBy=multi-user.target
EOF

# ── Log directory ──
sudo mkdir -p /var/log/intratrading
sudo chown intratrading:intratrading /var/log/intratrading

# ── Logrotate ──
sudo tee /etc/logrotate.d/intratrading > /dev/null << 'EOF'
/var/log/intratrading/*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
    copytruncate
}
EOF

# ── Nginx reverse proxy ──
sudo tee /etc/nginx/sites-available/intratrading > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    # ── Security Headers ──
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' http://localhost:8001" always;

    # ── Block sensitive paths ──
    location ~ /\.env { deny all; return 404; }
    location ~ /\.git { deny all; return 404; }
    location ~ /\.pem { deny all; return 404; }
    location ~ \.json$ {
        # Allow API JSON responses but block direct state/config file access
        try_files $uri @backend;
    }

    # ── Rate limiting for auth endpoints ──
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;

    # Frontend (built static files)
    location / {
        root /opt/intratrading/app/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Auth endpoints — rate limited
    location /api/auth/ {
        limit_req zone=auth burst=3 nodelay;
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    location @backend {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/intratrading /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# ── Cron: Auto-start backend at 9:00 AM IST (Mon-Fri, skips NSE holidays) ──
# AWS uses UTC. IST = UTC+5:30. So 9:00 AM IST = 3:30 AM UTC.
# The start script checks NSE_HOLIDAYS from backend/config.py before starting.
chmod +x /opt/intratrading/app/deploy/start-if-trading-day.sh
sudo -u intratrading crontab -l 2>/dev/null | grep -v intratrading > /tmp/crontab_clean || true
echo "30 3 * * 1-5 /opt/intratrading/app/deploy/start-if-trading-day.sh" >> /tmp/crontab_clean
sudo -u intratrading crontab /tmp/crontab_clean
rm /tmp/crontab_clean

# ── Enable services ──
sudo systemctl daemon-reload
sudo systemctl enable nginx

# ── Firewall (UFW) ──
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (nginx)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw --force enable

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  IntraTrading Server Setup COMPLETE"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  Next steps:"
echo "  1. Fill in /opt/intratrading/app/backend/.env"
echo "  2. Test: sudo systemctl start intratrading-backend"
echo "  3. Check: sudo systemctl status intratrading-backend"
echo "  4. Logs: tail -f /var/log/intratrading/backend.log"
echo "  5. Register Elastic IP with Fyers"
echo ""
