#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# Securely update .env on EC2 (credentials never go in git)
#
# Usage from your Mac:
#   bash deploy/update-env.sh <elastic-ip> <path-to-key.pem>
#
# Example:
#   bash deploy/update-env.sh 13.235.100.50 ~/Downloads/Honeydaalu-key.pem
# ═══════════════════════════════════════════════════════════════════════

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: bash deploy/update-env.sh <elastic-ip> <path-to-key.pem>"
    exit 1
fi

EC2_IP="$1"
PEM_KEY="$2"
LOCAL_ENV="backend/.env"

if [ ! -f "$LOCAL_ENV" ]; then
    echo "Error: $LOCAL_ENV not found. Run from project root."
    exit 1
fi

echo "Uploading .env to EC2 at $EC2_IP..."
scp -i "$PEM_KEY" "$LOCAL_ENV" ubuntu@"$EC2_IP":/tmp/.env.upload
ssh -i "$PEM_KEY" ubuntu@"$EC2_IP" "
    sudo mv /tmp/.env.upload /opt/luckynavi/app/backend/.env
    sudo chown luckynavi:luckynavi /opt/luckynavi/app/backend/.env
    sudo chmod 600 /opt/luckynavi/app/backend/.env
    echo '.env updated on server'
"
echo "Done. Credentials updated securely."
