# IntraTrading — AWS Migration Guide

## SEBI-Compliant Algo Trading Server with Static IP

**Version:** 1.0 | **Date:** March 26, 2026
**Author:** Claude (Fund Manager + Engineer)

---

## Table of Contents

1. Why AWS? (SEBI Compliance)
2. Architecture Overview
3. Cost Breakdown
4. Prerequisites
5. Phase 1: AWS Account Setup
6. Phase 2: Launch EC2 Instance
7. Phase 3: Elastic IP (Static IP)
8. Phase 4: Connect to Your Server
9. Phase 5: Server Setup (Automated)
10. Phase 6: Upload Credentials
11. Phase 7: Fyers Configuration
12. Phase 8: GitHub Repository Setup
13. Phase 9: GitHub Actions CI/CD Pipeline
14. Phase 10: First Deployment Test
15. Phase 11: Health Check
16. Phase 12: Daily Operations
17. Deployment Workflow (How Changes Go Live)
18. Troubleshooting
19. Security Checklist
20. Monthly Maintenance

---

## 1. Why AWS? (SEBI Compliance)

**SEBI Regulation (2023-2024):** All algorithmic trading orders must originate from a
whitelisted static IP address. Brokers (including Fyers) are required to verify and register
the IP address of any automated trading system.

**Current Problem:** Your Mac at home uses a dynamic IP from your ISP. This IP changes
periodically, which means:
- Fyers cannot permanently whitelist your IP
- Your algo orders may get rejected if IP changes
- You are not SEBI compliant

**Solution:** AWS EC2 instance with an Elastic IP (static, permanent public IP) in the
Mumbai region. This IP never changes. You register it once with Fyers, and all algo orders
originate from this whitelisted IP.

---

## 2. Architecture Overview

```
YOUR MAC (Development)
    │
    │  git push (code changes)
    ▼
GITHUB (Code Repository)
    │
    │  GitHub Actions (automatic)
    ▼
AWS EC2 — Mumbai Region
    │
    ├── Elastic IP: xx.xx.xx.xx (static, registered with Fyers)
    ├── Backend: FastAPI on port 8001
    ├── Frontend: Nginx serves static files on port 80
    ├── Systemd: Auto-manages backend process
    ├── Cron: Starts backend at 9:00 AM IST (Mon-Fri)
    │
    ▼
FYERS API → NSE (Trades execute)
```

**Key Principle:** You NEVER log into the server to edit code. All changes go through
GitHub. The server pulls the latest code automatically.

---

## 3. Cost Breakdown

| Item | Monthly Cost | Notes |
|------|-------------|-------|
| EC2 t3.small (2 vCPU, 2GB RAM) | ₹1,100 | Mumbai region, on-demand |
| Elastic IP | ₹0 | Free while attached to running instance |
| EBS Storage (20 GB gp3) | ₹160 | SSD storage |
| Data Transfer | ₹0-100 | Minimal for API calls |
| **TOTAL** | **~₹1,300/month** | |

**Cost optimization:** You can use a t3.micro (₹550/month) initially. If the system needs
more memory for scanning 500 stocks, upgrade to t3.small.

**Free Tier:** If this is a new AWS account, t3.micro is free for 12 months (750 hours/month).

---

## 4. Prerequisites

Before starting, ensure you have:

- [ ] Email address for AWS account
- [ ] Credit/Debit card (AWS requires payment method, charges only what you use)
- [ ] PAN card (AWS India requires PAN for billing)
- [ ] Your Fyers credentials (APP_ID, SECRET_KEY, TOTP_SECRET, PIN)
- [ ] Your Telegram bot token and chat ID
- [ ] GitHub account (free at github.com)
- [ ] Terminal app on your Mac (already have it)

---

## 5. Phase 1: AWS Account Setup

### Step 5.1: Create AWS Account

1. Open browser → go to **https://aws.amazon.com**
2. Click **"Create an AWS Account"**
3. Enter your email address and choose an account name (e.g., "IntraTrading")
4. Verify your email with the OTP sent
5. Set a strong root password

### Step 5.2: Contact Information

1. Select **"Personal"** account type
2. Fill in your name, phone number, address
3. Enter PAN number when asked

### Step 5.3: Payment Method

1. Add your credit/debit card
2. AWS will charge ₹2 for verification (refunded)
3. This card will be billed monthly for usage (~₹1,300/month)

### Step 5.4: Identity Verification

1. Enter your phone number
2. AWS will call or SMS you with a verification code
3. Enter the code

### Step 5.5: Select Support Plan

1. Choose **"Basic Support — Free"**
2. Click "Complete sign up"

### Step 5.6: Sign In

1. Go to **https://console.aws.amazon.com**
2. Sign in with your email and password
3. You are now in the AWS Console

---

## 6. Phase 2: Launch EC2 Instance

### Step 6.1: Select Mumbai Region

1. In the top-right corner of the AWS Console, you'll see a region name (e.g., "N. Virginia")
2. Click it and select **"Asia Pacific (Mumbai) ap-south-1"**
3. This is critical — Mumbai region gives lowest latency to NSE

### Step 6.2: Navigate to EC2

1. In the search bar at the top, type **"EC2"**
2. Click **"EC2"** from the results
3. You'll see the EC2 Dashboard

### Step 6.3: Launch Instance

1. Click the orange **"Launch instance"** button

2. **Name:** Enter `IntraTrading-Server`

3. **Application and OS Images (AMI):**
   - Select **"Ubuntu"**
   - Choose **"Ubuntu Server 24.04 LTS (HVM), SSD Volume Type"**
   - Architecture: **64-bit (x86)**

4. **Instance type:**
   - Select **"t3.small"** (2 vCPU, 2 GB RAM)
   - If budget is tight, use **"t3.micro"** (1 vCPU, 1 GB RAM, free tier eligible)

5. **Key pair (login):**
   - Click **"Create new key pair"**
   - Key pair name: `intratrading-key`
   - Key pair type: **RSA**
   - Private key file format: **.pem**
   - Click **"Create key pair"**
   - **IMPORTANT:** A file `intratrading-key.pem` will download. SAVE THIS FILE.
     Move it to a safe location: `~/Documents/AWS/intratrading-key.pem`
   - **You CANNOT download this file again.** If you lose it, you lose access to your server.

6. **Network settings:**
   - Click **"Edit"**
   - VPC: Keep default
   - Subnet: Keep default (any Mumbai AZ)
   - Auto-assign public IP: **Enable**
   - **Security group:** Create new security group
     - Security group name: `IntraTrading-SG`
     - Description: `IntraTrading algo trading server`
     - Add the following rules:

   | Type | Port | Source | Description |
   |------|------|--------|-------------|
   | SSH | 22 | My IP | SSH access from your IP |
   | HTTP | 80 | 0.0.0.0/0 | Web dashboard |
   | HTTPS | 443 | 0.0.0.0/0 | Secure web dashboard |
   | Custom TCP | 8001 | 0.0.0.0/0 | Backend API (temporary, remove after nginx setup) |

7. **Configure storage:**
   - Size: **20 GiB**
   - Volume type: **gp3**
   - Delete on termination: **Yes** (checked)

8. **Summary:**
   - Review all settings
   - Number of instances: **1**
   - Click **"Launch instance"**

9. You'll see "Success! Instance is launching."
   - Click **"View all instances"**
   - Wait for Instance State to show **"Running"** and Status Checks to show **"2/2 checks passed"**
   - This takes 1-2 minutes

### Step 6.4: Note Your Instance ID

1. Click on your instance
2. Note the **Instance ID** (e.g., `i-0abc123def456`)
3. Note the **Public IPv4 address** (temporary — we'll replace with Elastic IP)

---

## 7. Phase 3: Elastic IP (Static IP)

### Step 7.1: Allocate Elastic IP

1. In the left sidebar of EC2, click **"Elastic IPs"** (under Network & Security)
2. Click **"Allocate Elastic IP address"**
3. Network Border Group: Keep default (ap-south-1)
4. Click **"Allocate"**
5. You'll see a new Elastic IP (e.g., `13.235.100.50`)
6. **Write this IP down — this is your permanent static IP**

### Step 7.2: Associate with Instance

1. Select the Elastic IP you just created
2. Click **Actions → "Associate Elastic IP address"**
3. Resource type: **Instance**
4. Instance: Select your `IntraTrading-Server` instance
5. Click **"Associate"**

### Step 7.3: Verify

1. Go back to EC2 → Instances
2. Click your instance
3. The **Public IPv4 address** should now show your Elastic IP
4. This IP will NEVER change (unless you release it)

**IMPORTANT:** An Elastic IP is free ONLY while associated with a RUNNING instance.
If you stop the instance, you'll be charged ~₹300/month for the idle Elastic IP.
Solution: Don't stop the instance. The backend auto-shuts down at 3:45 PM and auto-starts
at 9:00 AM via cron — the instance stays running but uses minimal CPU when idle.

---

## 8. Phase 4: Connect to Your Server

### Step 8.1: Set Key Permissions

Open Terminal on your Mac and run:

```bash
# Move the key file to a safe location
mkdir -p ~/Documents/AWS
mv ~/Downloads/intratrading-key.pem ~/Documents/AWS/

# Set permissions (required by SSH)
chmod 400 ~/Documents/AWS/intratrading-key.pem
```

### Step 8.2: SSH into the Server

```bash
ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP
```

Replace `YOUR_ELASTIC_IP` with your actual Elastic IP (e.g., `13.235.100.50`).

You should see:
```
Welcome to Ubuntu 24.04 LTS
ubuntu@ip-172-31-xx-xx:~$
```

**You are now connected to your AWS server.**

### Step 8.3: Create a Shortcut (Optional)

Add this to your Mac's `~/.zshrc` for easy access:

```bash
echo 'alias it-server="ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP"' >> ~/.zshrc
source ~/.zshrc
```

Now you can type `it-server` to connect.

---

## 9. Phase 5: Server Setup (Automated)

### Step 9.1: Upload and Run Setup Script

From your Mac (NOT from SSH), run:

```bash
cd "/Users/vgopiraja/Documents/MY Applications/IntraTrading"

# Upload the setup script to the server
scp -i ~/Documents/AWS/intratrading-key.pem \
    deploy/setup-server.sh \
    ubuntu@YOUR_ELASTIC_IP:/tmp/setup-server.sh

# SSH in and run it
ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP \
    'sudo bash /tmp/setup-server.sh'
```

This script automatically installs:
- Python 3.12 with venv
- Node.js 20 (for frontend build)
- Nginx (reverse proxy)
- All pip and npm dependencies
- Systemd service for auto-management
- Cron job for 9:00 AM auto-start
- UFW firewall
- Log rotation

**This takes about 5-10 minutes.** Wait for it to complete.

### Step 9.2: Verify Setup

```bash
ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP

# Check Python
/opt/intratrading/app/backend/venv/bin/python --version
# Should show: Python 3.12.x

# Check Nginx
sudo systemctl status nginx
# Should show: active (running)

# Check service exists
sudo systemctl status intratrading-backend
# Should show: inactive (dead) — hasn't been started yet
```

---

## 10. Phase 6: Upload Credentials

**Credentials (.env file) NEVER go in Git.** Upload them directly and securely.

### Step 10.1: Upload .env

From your Mac:

```bash
cd "/Users/vgopiraja/Documents/MY Applications/IntraTrading"
bash deploy/update-env.sh YOUR_ELASTIC_IP ~/Documents/AWS/intratrading-key.pem
```

This securely copies your local `backend/.env` to the server with proper permissions (600).

### Step 10.2: Verify .env on Server

```bash
ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP

# Check file exists and has correct permissions
ls -la /opt/intratrading/app/backend/.env
# Should show: -rw------- intratrading intratrading ... .env

# Verify contents (check, don't share)
sudo -u intratrading cat /opt/intratrading/app/backend/.env
# Should show your FYERS_APP_ID, SECRET_KEY, TOTP_SECRET, etc.
```

---

## 11. Phase 7: Fyers Configuration

### Step 11.1: Register Static IP with Fyers

1. Login to **Fyers Dashboard**: https://myapi.fyers.in/dashboard
2. Go to your app settings
3. Find **"Allowed IPs"** or **"Whitelisted IPs"**
4. Add your Elastic IP: `YOUR_ELASTIC_IP`
5. Save

### Step 11.2: Update OAuth Redirect URI

1. In Fyers Dashboard, find your app's **Redirect URI**
2. Change it from:
   ```
   http://localhost:8001/api/fyers/callback
   ```
   To:
   ```
   http://YOUR_ELASTIC_IP:8001/api/fyers/callback
   ```
3. Save

### Step 11.3: Update Backend Config

On the server, update the Fyers redirect URI:

```bash
ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP

sudo -u intratrading nano /opt/intratrading/app/backend/.env
```

Make sure `FYERS_REDIRECT_URI` points to the Elastic IP:
```
FYERS_REDIRECT_URI=http://YOUR_ELASTIC_IP:8001/api/fyers/callback
```

### Step 11.4: Register IP for F&O Segment

Since your Options and Futures segments are now active on Fyers:
1. Check if Fyers requires separate IP registration for NFO/MCX segments
2. If yes, register the same Elastic IP for all segments

---

## 12. Phase 8: GitHub Repository Setup

### Step 12.1: Create GitHub Repository

1. Go to **https://github.com** and sign in
2. Click **"+"** → **"New repository"**
3. Repository name: `IntraTrading`
4. Visibility: **Private** (important — your trading code is proprietary)
5. Do NOT initialize with README (we'll push existing code)
6. Click **"Create repository"**

### Step 12.2: Push Existing Code

From your Mac:

```bash
cd "/Users/vgopiraja/Documents/MY Applications/IntraTrading"

# Initialize git (if not already)
git init

# Add GitHub as remote
git remote add origin https://github.com/YOUR_USERNAME/IntraTrading.git

# Make sure .gitignore is proper (already updated)
# Verify no secrets will be committed
git status

# Add all files
git add -A

# Commit
git commit -m "Initial push: IntraTrading algo trading platform"

# Push
git push -u origin main
```

### Step 12.3: Verify on GitHub

1. Go to `https://github.com/YOUR_USERNAME/IntraTrading`
2. Verify the code is there
3. Verify `.env` is NOT in the repo (check .gitignore is working)

---

## 13. Phase 9: GitHub Actions CI/CD Pipeline

### Step 13.1: Generate SSH Key for GitHub Actions

The CI/CD pipeline needs to SSH into your EC2 instance. We'll use your existing key.

### Step 13.2: Add GitHub Secrets

1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**

Add these two secrets:

| Secret Name | Value |
|-------------|-------|
| `EC2_HOST` | Your Elastic IP (e.g., `13.235.100.50`) |
| `EC2_SSH_KEY` | The ENTIRE contents of your `intratrading-key.pem` file |

To get the key contents:
```bash
cat ~/Documents/AWS/intratrading-key.pem
```
Copy everything (including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----`) and paste as the secret value.

### Step 13.3: Verify Workflow File

The file `.github/workflows/deploy.yml` is already created. It triggers on every push to
the `main` branch and runs `deploy/deploy.sh` on the EC2 server.

### Step 13.4: Set Up Deploy Key on EC2

The EC2 server needs to pull from your private GitHub repo:

```bash
ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP

# Generate SSH key for the intratrading user
sudo -u intratrading ssh-keygen -t ed25519 -C "intratrading@ec2" -f /home/intratrading/.ssh/id_ed25519 -N ""

# Show the public key
sudo cat /home/intratrading/.ssh/id_ed25519.pub
```

Copy the output. Then:

1. Go to GitHub repo → **Settings** → **Deploy keys**
2. Click **"Add deploy key"**
3. Title: `EC2 Server`
4. Key: Paste the public key
5. Allow write access: **No** (read-only is sufficient)
6. Click **"Add key"**

### Step 13.5: Configure Git on EC2

```bash
ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP

# Set the remote URL to use SSH
sudo -u intratrading git -C /opt/intratrading/app remote set-url origin git@github.com:YOUR_USERNAME/IntraTrading.git

# Test connection
sudo -u intratrading ssh -T git@github.com
# Should show: "Hi YOUR_USERNAME! You've successfully authenticated"
```

---

## 14. Phase 10: First Deployment Test

### Step 14.1: Manual Start

```bash
ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP

# Start the backend
sudo systemctl start intratrading-backend

# Check status
sudo systemctl status intratrading-backend

# Watch logs
tail -f /var/log/intratrading/backend.log
```

You should see:
```
[Startup] Attempting fresh TOTP login...
[Startup] Fyers connected: YOUR_NAME (attempt 1)
[AutoStart] Starting engines...
```

### Step 14.2: Test from Browser

Open in your browser:
```
http://YOUR_ELASTIC_IP
```

You should see the IntraTrading dashboard.

### Step 14.3: Test API

```bash
curl http://YOUR_ELASTIC_IP:8001/api/strategies
curl http://YOUR_ELASTIC_IP:8001/api/fyers/status
curl http://YOUR_ELASTIC_IP:8001/api/market-status
```

### Step 14.4: Stop the Backend

Since today (Mar 26) is a holiday:
```bash
sudo systemctl stop intratrading-backend
```

### Step 14.5: Test Auto-Deploy

From your Mac, make a small change and push:

```bash
cd "/Users/vgopiraja/Documents/MY Applications/IntraTrading"
git add -A
git commit -m "Test: verify CI/CD pipeline"
git push origin main
```

Go to GitHub → Actions tab → you should see the deploy workflow running.
After ~60 seconds, the code will be updated on the server.

---

## 15. Phase 11: Health Check

### Step 15.1: Run Health Check from Mac

```bash
cd "/Users/vgopiraja/Documents/MY Applications/IntraTrading"
bash deploy/health-check.sh YOUR_ELASTIC_IP
```

Expected output:
```
═══ IntraTrading Health Check (YOUR_ELASTIC_IP) ═══

1. Backend reachable: ✅ (HTTP 200)
2. Fyers connection: ✅ Connected
3. Market status: OPEN | Next: Square-off at 3:15 PM
4. Equity Live: RUNNING | Trades: 2 | P&L: ₹815.00
5. Options Live: RUNNING | Positions: 1
6. BTST Live: RUNNING | Trades: 0

═══ Health Check Complete ═══
```

---

## 16. Phase 12: Daily Operations

### What Happens Automatically (No Action Needed)

| Time (IST) | Event | How |
|------------|-------|-----|
| 9:00 AM | Backend starts | Cron job |
| 9:10 AM | Fyers TOTP login | Auto on startup |
| 9:15 AM | Market opens | Engines start |
| 9:30 AM | Morning brief | Telegram notification |
| 10:00 AM | Options scan begins | Auto |
| 10:30 AM | Equity scan begins | Auto |
| 1:00 PM | Half-day summary | Telegram notification |
| 1:50 PM | BTST engine starts | Deferred start |
| 2:00 PM | BTST scan + buy | Auto |
| 3:15 PM | Equity square-off | Auto |
| 3:20 PM | All intraday closed | Auto |
| 3:45 PM | Day-end summary | Telegram notification |
| 3:45 PM | Backend shuts down | Auto-shutdown |

### What You Do

1. **Morning:** Check Telegram for morning brief
2. **During day:** Check Telegram for trade alerts
3. **Evening:** Check Telegram for day-end summary
4. **If needed:** Run health check from Mac

### If Something Goes Wrong

```bash
# Check logs
ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP
tail -100 /var/log/intratrading/backend.log

# Restart backend
sudo systemctl restart intratrading-backend

# Check if backend is running
sudo systemctl status intratrading-backend
```

---

## 17. Deployment Workflow (How Changes Go Live)

### The Golden Rule: Never Edit Code on the Server

All changes follow this flow:

```
1. Edit code on your Mac (with Claude)
2. Test locally if possible
3. git add + git commit + git push
4. GitHub Actions automatically deploys to EC2
5. If backend is running, it restarts with new code
6. If backend is off (after hours), code updates silently — next startup uses new code
```

### Example: Claude Makes a Strategy Change

```bash
# Claude edits files on your Mac
# Then you (or Claude) push:
cd "/Users/vgopiraja/Documents/MY Applications/IntraTrading"
git add -A
git commit -m "Strategy: tighten play8 SL for high VIX"
git push origin main

# GitHub Actions deploys automatically
# If market is open, backend restarts with new code
# If market is closed, code waits for next startup
```

### Updating Credentials

Credentials (.env) NEVER go through GitHub:

```bash
# Edit .env locally on your Mac
# Then upload directly:
bash deploy/update-env.sh YOUR_ELASTIC_IP ~/Documents/AWS/intratrading-key.pem
```

---

## 18. Troubleshooting

### Problem: Cannot SSH into server

```bash
# Check your IP hasn't changed (security group allows "My IP" only)
curl ifconfig.me
# If your IP changed, update the Security Group in AWS Console:
# EC2 → Security Groups → IntraTrading-SG → Edit Inbound Rules → Update SSH source
```

### Problem: Backend won't start

```bash
ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP
# Check logs for errors
sudo journalctl -u intratrading-backend -n 100
tail -100 /var/log/intratrading/backend.log

# Common fixes:
# 1. .env missing or incorrect
sudo -u intratrading cat /opt/intratrading/app/backend/.env

# 2. Dependency issue
cd /opt/intratrading/app/backend
sudo -u intratrading ./venv/bin/pip install -r requirements.txt

# 3. Port already in use
sudo lsof -i :8001
```

### Problem: Fyers login fails

```bash
# Check if the Elastic IP is whitelisted in Fyers
# Check if redirect URI is correct in Fyers dashboard
# Check TOTP secret is correct in .env

# Test manually:
ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP
cd /opt/intratrading/app/backend
sudo -u intratrading ./venv/bin/python -c "
from services.fyers_client import headless_login
result = headless_login()
print(result)
"
```

### Problem: GitHub Actions deploy fails

1. Go to GitHub → Actions → click the failed workflow
2. Check the error message
3. Common issues:
   - SSH key incorrect in GitHub Secrets
   - EC2 security group blocks GitHub's IP on port 22
   - Fix: Change SSH rule source from "My IP" to "0.0.0.0/0" (less secure but works)
   - Better: Add GitHub's IP ranges to security group

### Problem: No trades being placed

```bash
# Check engine status
curl http://YOUR_ELASTIC_IP:8001/api/auto/status | python3 -m json.tool
curl http://YOUR_ELASTIC_IP:8001/api/options/auto/status | python3 -m json.tool

# Check scan logs
tail -200 /var/log/intratrading/backend.log | grep -i "scan\|signal\|order"
```

---

## 19. Security Checklist

- [ ] `.env` file has 600 permissions (owner read/write only)
- [ ] `.pem` key file stored safely on Mac, not in cloud storage
- [ ] GitHub repository is **Private**
- [ ] SSH access restricted to "My IP" in security group
- [ ] No credentials in git history (check with `git log --all --full-history -- '*.env'`)
- [ ] Fyers API key has IP restriction enabled
- [ ] UFW firewall enabled on server
- [ ] Regular OS updates: `sudo apt update && sudo apt upgrade`

---

## 20. Monthly Maintenance

### Weekly (Every Friday)

1. Check AWS bill: https://console.aws.amazon.com/billing
2. Run health check: `bash deploy/health-check.sh YOUR_ELASTIC_IP`

### Monthly

1. Update server OS:
   ```bash
   ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP
   sudo apt update && sudo apt upgrade -y
   ```

2. Check disk space:
   ```bash
   df -h /
   # If >80% full, clean old logs:
   sudo find /var/log/intratrading -name "*.log.*.gz" -mtime +30 -delete
   ```

3. Review trading performance and adjust strategies as needed

4. Check if Fyers IP whitelist is still active

---

## Quick Reference Card

| Task | Command |
|------|---------|
| SSH into server | `ssh -i ~/Documents/AWS/intratrading-key.pem ubuntu@YOUR_ELASTIC_IP` |
| Start backend | `sudo systemctl start intratrading-backend` |
| Stop backend | `sudo systemctl stop intratrading-backend` |
| Check status | `sudo systemctl status intratrading-backend` |
| View logs | `tail -f /var/log/intratrading/backend.log` |
| Deploy code | `git push origin main` (auto-deploys via GitHub Actions) |
| Upload .env | `bash deploy/update-env.sh IP KEY` |
| Health check | `bash deploy/health-check.sh YOUR_ELASTIC_IP` |
| Update OS | `sudo apt update && sudo apt upgrade -y` |

---

**Document End**

Replace `YOUR_ELASTIC_IP` and `YOUR_USERNAME` with your actual values throughout this guide.

For support, ask Claude in the next session.
