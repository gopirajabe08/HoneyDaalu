#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# LuckyNavi — AWS EC2 Server Setup (run ONCE on fresh Ubuntu 24.04)
#
# Usage: ssh -i key.pem ubuntu@<elastic-ip> 'bash -s' < setup-server.sh
# ═══════════════════════════════════════════════════════════════════════

set -e

echo "═══ LuckyNavi Server Setup ═══"

# ── System packages ──
sudo apt-get update -y
sudo apt-get install -y \
    python3.12 python3.12-venv python3-pip \
    nginx certbot python3-certbot-nginx \
    git curl jq unzip htop \
    build-essential libffi-dev libssl-dev

# ── Create app user ──
sudo useradd -m -s /bin/bash luckynavi 2>/dev/null || true
sudo mkdir -p /opt/luckynavi
sudo chown luckynavi:luckynavi /opt/luckynavi

# ── Clone repo (first time) or pull (subsequent) ──
if [ ! -d /opt/luckynavi/app/.git ]; then
    echo "Cloning repository..."
    sudo -u luckynavi git clone https://github.com/gopirajabe08/HoneyDaalu.git /opt/luckynavi/app
else
    echo "Repository exists — pulling latest..."
    sudo -u luckynavi git -C /opt/luckynavi/app pull origin main
fi

# ── Backend: Python venv + dependencies ──
cd /opt/luckynavi/app/backend
sudo -u luckynavi python3.12 -m venv venv
sudo -u luckynavi ./venv/bin/pip install --upgrade pip
sudo -u luckynavi ./venv/bin/pip install -r requirements.txt

# ── Frontend: Build static files ──
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
cd /opt/luckynavi/app/frontend
sudo -u luckynavi npm install
sudo -u luckynavi npm run build

# ── Create .env placeholder ──
if [ ! -f /opt/luckynavi/app/backend/.env ]; then
    cat > /tmp/env_template << 'ENVEOF'
# TradeJini CubePlus API Credentials (fill in)
TRADEJINI_API_KEY=
TRADEJINI_API_SECRET=
TRADEJINI_TOTP_SECRET=
TRADEJINI_CLIENT_ID=

# JWT Secret for frontend auth
JWT_SECRET=
ENVEOF
    sudo mv /tmp/env_template /opt/luckynavi/app/backend/.env
    sudo chown luckynavi:luckynavi /opt/luckynavi/app/backend/.env
    sudo chmod 600 /opt/luckynavi/app/backend/.env
    echo "WARNING: Fill in /opt/luckynavi/app/backend/.env with your credentials!"
fi

# ── Systemd service: Backend ──
sudo tee /etc/systemd/system/luckynavi-backend.service > /dev/null << 'EOF'
[Unit]
Description=LuckyNavi Backend (FastAPI)
After=network.target

[Service]
Type=simple
User=luckynavi
Group=luckynavi
WorkingDirectory=/opt/luckynavi/app/backend
ExecStart=/opt/luckynavi/app/backend/venv/bin/python main.py
Restart=no
RestartSec=10
Environment=PYTHONUNBUFFERED=1

# Don't auto-restart — the app has its own lifecycle (auto-shutdown at 3:45 PM)
# Restart=no prevents crash loops

StandardOutput=append:/var/log/luckynavi/backend.log
StandardError=append:/var/log/luckynavi/backend.log

[Install]
WantedBy=multi-user.target
EOF

# ── Log directory ──
sudo mkdir -p /var/log/luckynavi
sudo chown luckynavi:luckynavi /var/log/luckynavi

# ── Logrotate ──
sudo tee /etc/logrotate.d/luckynavi > /dev/null << 'EOF'
/var/log/luckynavi/*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
    copytruncate
}
EOF

# ── Nginx reverse proxy ──
sudo tee /etc/nginx/sites-available/luckynavi > /dev/null << 'EOF'
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
        root /opt/luckynavi/app/frontend/dist;
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

sudo ln -sf /etc/nginx/sites-available/luckynavi /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# ── Cron: Auto-start backend at 9:00 AM IST (Mon-Fri, skips NSE holidays) ──
# AWS uses UTC. IST = UTC+5:30. So 9:00 AM IST = 3:30 AM UTC.
chmod +x /opt/luckynavi/app/deploy/start-if-trading-day.sh
sudo -u luckynavi crontab -l 2>/dev/null | grep -v luckynavi > /tmp/crontab_clean || true
echo "30 3 * * 1-5 /opt/luckynavi/app/deploy/start-if-trading-day.sh" >> /tmp/crontab_clean
sudo -u luckynavi crontab /tmp/crontab_clean
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
echo "  LuckyNavi Server Setup COMPLETE"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "  Next steps:"
echo "  1. Fill in /opt/luckynavi/app/backend/.env"
echo "  2. Test: sudo systemctl start luckynavi-backend"
echo "  3. Check: sudo systemctl status luckynavi-backend"
echo "  4. Logs: tail -f /var/log/luckynavi/backend.log"
echo "  5. Register Elastic IP with TradeJini for IP whitelisting"
echo ""
