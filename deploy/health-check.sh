#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# Health check — run from Mac to verify EC2 is working
#
# Usage: bash deploy/health-check.sh <elastic-ip>
# ═══════════════════════════════════════════════════════════════════════

IP="${1:-localhost}"
API="http://$IP:8001"

echo "═══ HoneyDaalu Health Check ($IP) ═══"
echo ""

# 1. Server reachable?
echo -n "1. Backend reachable: "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/strategies" --connect-timeout 5 2>/dev/null)
if [ "$STATUS" = "200" ]; then
    echo "OK (HTTP $STATUS)"
else
    echo "FAIL (HTTP $STATUS — server may be down)"
    exit 1
fi

# 2. TradeJini connected?
echo -n "2. TradeJini connection: "
BROKER=$(curl -s "$API/api/broker/status" --connect-timeout 5 2>/dev/null)
if echo "$BROKER" | grep -q '"authenticated":true'; then
    echo "OK Connected"
else
    echo "FAIL Not connected"
fi

# 3. Market status
echo -n "3. Market status: "
MARKET=$(curl -s "$API/api/market/status" --connect-timeout 5 2>/dev/null)
echo "$MARKET" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f\"{'OPEN' if d.get('is_open') else 'CLOSED'} | Next: {d.get('next_event', 'N/A')}\")
except: print('Could not parse')
" 2>/dev/null || echo "?"

# 4. Equity Live status
echo -n "4. Equity Live: "
AUTO=$(curl -s "$API/api/auto/status" --connect-timeout 5 2>/dev/null)
echo "$AUTO" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f\"{'RUNNING' if d.get('is_running') else 'STOPPED'} | Trades: {d.get('order_count', 0)} | P&L: Rs.{d.get('total_pnl', 0):,.2f}\")
except: print('Could not parse')
" 2>/dev/null || echo "?"

# 5. Options Live status
echo -n "5. Options Live: "
OPT=$(curl -s "$API/api/options/auto/status" --connect-timeout 5 2>/dev/null)
echo "$OPT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f\"{'RUNNING' if d.get('is_running') else 'STOPPED'} | Positions: {len(d.get('active_positions', []))}\")
except: print('Could not parse')
" 2>/dev/null || echo "?"

# 6. Futures Live status
echo -n "6. Futures Live: "
FUT=$(curl -s "$API/api/futures/auto/status" --connect-timeout 5 2>/dev/null)
echo "$FUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f\"{'RUNNING' if d.get('is_running') else 'STOPPED'} | Positions: {len(d.get('active_positions', []))}\")
except: print('Could not parse')
" 2>/dev/null || echo "?"

# 7. BTST status
echo -n "7. BTST Live: "
BTST=$(curl -s "$API/api/btst/status" --connect-timeout 5 2>/dev/null)
echo "$BTST" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f\"{'RUNNING' if d.get('is_running') else 'STOPPED'} | Trades: {d.get('order_count', 0)}\")
except: print('Could not parse')
" 2>/dev/null || echo "?"

echo ""
echo "═══ Health Check Complete ═══"
