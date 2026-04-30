# Owner Runbook — When Claude Isn't Available

**Audience:** Owner (Gopi). Written for non-technical use. Phone + browser based wherever possible.

**When to use this:** Claude is offline / unreachable AND something is going wrong with the trading system. If Claude is reachable, ask Claude first.

**Last updated:** 2026-04-30. Verify before live capital starts (~Mon 26 May 2026).

---

## 🚨 EMERGENCY — Stop everything NOW (live capital at risk)

**Symptoms requiring this:**
- You see unexpected losses piling up in TradeJini
- Engine seems to be placing wrong orders
- News breaking that requires you to be flat (war, market halt rumor, broker issue)
- Your gut says "something is very wrong"

**Steps (in order):**

### Step 1 — Flatten ALL positions in TradeJini app/web (5 min)
This is the **most important** action. Do this even if you can't do anything else.

1. Open TradeJini mobile app or login at https://trade.tradejini.com
2. Wife's account: **MER004** (you have credentials — check 1Password / your notes)
3. Go to **Positions** tab
4. For each open position: tap **Square Off** → **Confirm**
5. Go to **Orders** tab → cancel any **Pending** orders
6. **Verify Positions tab is empty.**

This stops the bleeding. The algo can no longer open new trades because there are no live positions to act on, and any pending orders are gone.

### Step 2 — Disable the algo from re-entering (10 min)

**Easy method — via TradeJini directly:**
- Change the wife's TradeJini login password in the TradeJini app/web. The algo loses access immediately. No further trades possible until password is updated in the system. **This is the safest single action.**

**If you also want to stop the AWS server (only if comfortable with web SSH):**
- Login to AWS Console: https://aws.amazon.com (use your AWS account credentials)
- Region: **Asia Pacific (Mumbai)** — top-right region selector
- Go to **EC2** → **Instances** → select instance with IP `3.109.167.163`
- **Instance State** → **Stop instance**
- This kills everything. The algo can't run. Restart later when safe.

### Step 3 — Confirm flat
- Wait 5 minutes. Refresh TradeJini. Confirm Positions tab is still empty and no new orders appeared.
- Take screenshots of empty positions tab as evidence.

### Step 4 — Tell Claude (or whoever is helping)
- Once Claude is back, paste the screenshots and what you saw. Don't restart the system without diagnosis.

---

## 🟡 NON-EMERGENCY — System acting weird but not bleeding

**Symptoms:**
- Morning ping didn't arrive
- EOD report didn't arrive
- Telegram bot stopped responding
- Engine status shows "stopped" or "error" in dashboard

**Steps:**

1. **Don't panic, don't manually trade.** No active loss = no urgent action.
2. **Check whether positions are open.** Login to TradeJini → Positions tab.
   - If positions exist and you're uncomfortable holding them overnight/over-weekend → square them off manually (Step 1 above).
   - If positions exist and you're comfortable holding them → leave them, deal with the bug separately.
3. **Take screenshots of:**
   - TradeJini Positions tab
   - TradeJini Orders tab (today + yesterday)
   - Last Telegram messages from @Successhoneybot
4. **Wait for Claude or message:** `gopirajav@vendasta.com` from a different channel, OR ask Claude when next available.
5. **If urgent and you need to flatten:** do Step 1 of the Emergency section.

---

## 🟢 ROUTINE — Things to glance at daily

| Time (IST) | What to check | What's normal |
|---|---|---|
| 09:20 | Telegram morning ping | "✅ Morning Alive — Swing/Intraday status" |
| 10:30 | (Once added) Intraday-started ping | "✅ Intraday scanning started" |
| 15:30 | Telegram EOD report | "EOD: N trades, ₹X P&L, M open positions" |
| 16:00 | Wife's TradeJini Positions | Matches what EOD report said |

If any of these is missing for 2 days in a row → tell Claude. Don't act unless system is clearly broken.

---

## Reference info

### Account & infrastructure

- **Broker:** TradeJini (account `MER004` — wife's individual account)
- **TradeJini login:** https://trade.tradejini.com
- **AWS Console:** https://aws.amazon.com (region: Asia Pacific Mumbai)
- **EC2 instance IP:** `3.109.167.163`
- **Telegram bot:** `@Successhoneybot` (bot id 8635028451)
- **Owner Telegram chat ID:** 7681408915 (named "Gopi")
- **GitHub repo:** github.com/[your-username]/honeydaalu (deploy auto-runs on push)

### Where to find SSH key (if technical helper needs it)

- `~/Downloads/honeydaalu-key.pem` on Owner's Mac
- Also: `~/Documents/LuckyNavi/honeydaalu-key.pem`
- SSH command: `ssh -i ~/Downloads/honeydaalu-key.pem ubuntu@3.109.167.163`

### Capital limits during stabilization

- Paper engines: ₹8,000 each (no real money)
- Live capital before 26 May 2026: **₹0** (paper only, no real money)
- Live capital after Gate 1 pass: **₹2,000 only** (intentionally tiny)
- Scaling schedule: ₹2k → ₹4k → ₹8k → ₹25k → ₹50k → ₹1L over 6 months

If you ever see live capital exceeding the schedule above without a Gate sign-off, something is wrong. Stop the system.

### What NEVER to do (no matter what)

1. ❌ **Never share TradeJini password / API keys / OTP via Telegram or email or screenshots posted online.** One leak = full account compromise.
2. ❌ **Never disable the system mid-trading-day** unless flattening positions first. Killing it with positions open = positions stay live, no monitoring, can blow up.
3. ❌ **Never manually place orders that contradict the algo's plan.** If you want to close, square off; don't open opposite trades.
4. ❌ **Never add capital outside the Gate schedule.** Even if it's "doing great", don't.
5. ❌ **Never re-enable a stopped system without telling Claude / a technical helper why it was stopped first.** Restart blind = re-create the same crash.

### Who to escalate to (in order)

1. **Claude / AI assistant** — first stop for technical / strategy questions
2. **A technical friend** — if Claude unavailable AND something is bleeding (give them this runbook + SSH key)
3. **TradeJini support** — for account-level issues, login problems, broker-side errors
   - TradeJini support: https://tradejini.com/contact
4. **Your CA** (once retained) — for tax / compliance questions, NOT operational
5. **Don't post on Reddit / Twitter / Slack about specifics.** Privacy + don't telegraph positions.

---

## Drill — practice this BEFORE live capital starts

Before Mon 26 May 2026 (Gate 1 live decision day), do this once with paper trading:

1. ☐ Login to TradeJini wife's account on phone. Confirm credentials work.
2. ☐ Look at Positions / Orders tabs. Get familiar with the layout.
3. ☐ Login to AWS Console. Confirm you can find the EC2 instance.
4. ☐ Test the Telegram chat with @Successhoneybot. Confirm you get notifications.
5. ☐ Read this runbook end to end once.

If any step fails, fix it before live day. Practicing under stress = mistakes.

---

**Owner's job during normal operations is light: 5 minutes a day glancing at notifications + 30 minutes Sunday review + ~30 minutes per Gate decision day. This runbook only matters when normal operations break.**
