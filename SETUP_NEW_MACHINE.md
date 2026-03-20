# Setup Guide — New Machine (Mac or Windows)

## Prerequisites (both platforms)
- Python 3.11+
- Node.js 18+
- Git
- Claude Code CLI: `npm install -g @anthropic-ai/claude-code`

---

## Mac Setup

### 1. Clone Repo
```bash
cd ~/Documents
git clone https://gopirajabe08:<TOKEN>@github.com/gopirajabe08/SmartAlgo.git IntraTrading
```

### 2. Backend Setup
```bash
cd IntraTrading/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Frontend Setup
```bash
cd ../frontend
npm install
```

### 4. Credentials
Create `IntraTrading/backend/.env`:
```
FYERS_APP_ID=<your-app-id>
FYERS_SECRET_KEY=<your-secret>
FYERS_REDIRECT_URI=http://localhost:8001/api/fyers/callback
FY_ID=<your-fyers-id>
FY_PIN=<your-pin>
FY_TOTP_KEY=<your-totp-key>
```

### 5. Claude Memory
Copy from current Mac:
```bash
cp -r ~/.claude/projects/-Users-vgopiraja-Documents-MY-Applications-IntraTrading/ \
      ~/.claude/projects/<new-sanitized-path>/
```
(Adjust target path based on where you cloned the project)

### 6. Start
```bash
cd IntraTrading/backend && source venv/bin/activate && python main.py &
cd ../frontend && npm run dev &
```
Open: http://localhost:3000
(Fyers auto-connects, all engines auto-start)

### 7. Prevent Sleep
```bash
caffeinate -d -i -s &
```

---

## Windows Setup

### 1. Install Prerequisites
- Python: https://python.org/downloads (check "Add to PATH")
- Node.js: https://nodejs.org (LTS version)
- Git: https://git-scm.com/download/win

### 2. Clone Repo (PowerShell)
```powershell
cd C:\Users\<username>\Documents
git clone https://gopirajabe08:<TOKEN>@github.com/gopirajabe08/SmartAlgo.git IntraTrading
```

### 3. Backend Setup
```powershell
cd IntraTrading\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Frontend Setup
```powershell
cd ..\frontend
npm install
```

### 5. Credentials
Create `IntraTrading\backend\.env` (same contents as Mac step 4)

### 6. Claude Memory
Copy from Mac:
```
Source: ~/.claude/projects/-Users-vgopiraja-Documents-MY-Applications-IntraTrading/memory/
Target: C:\Users\<username>\.claude\projects\-C-Users-<username>-Documents-IntraTrading\memory\
```
Create folder if needed:
```powershell
mkdir C:\Users\<username>\.claude\projects\-C-Users-<username>-Documents-IntraTrading\memory
```

### 7. Start (two terminals)
Terminal 1:
```powershell
cd IntraTrading\backend
venv\Scripts\activate
python main.py
```
Terminal 2:
```powershell
cd IntraTrading\frontend
npm run dev
```
Open: http://localhost:3000

### 8. Prevent Sleep
```
Settings → System → Power → Screen timeout: Never
Settings → System → Power → Sleep: Never
```
Or: `powercfg /change standby-timeout-ac 0`

---

## Verify Everything Works

After starting:
1. http://localhost:3000 loads dashboard ✓
2. System Brain shows regime + VIX ✓
3. All 6 paper engines auto-start ✓
4. Fyers shows "Connected" ✓
5. Live engines start based on capital ✓
6. Tracker sidebar shows daily reports ✓
7. Type "regime" in Claude CLI — shows all 3 ✓

---

## Files NOT in Git (must copy manually)

| File | Purpose |
|------|---------|
| `backend/.env` | Fyers credentials |
| `backend/.fyers_token` | Auto-generated on login |
| `~/.claude/projects/*/` | Claude memory files |
| `backend/tracking/daily/` | Daily reports (optional) |

Everything else is in GitHub.
