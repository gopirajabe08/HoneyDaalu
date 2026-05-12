# LuckyNavi — Project Closure Document

**Closure date:** 2026-05-12 (Phase 1 Day 10)
**Decision:** Path 3 — abandon active trading
**Final capital at risk:** ₹0 (live), ₹0 (real money ever lost)
**Decision maker:** Owner (Gopiraja Veeraian), validated by 16-role institutional framework

---

## What was the project

Build an autonomous algorithmic trading system for the owner's wife's TradeJini account (MER004). Goal: grow ₹2k seed capital to ₹1L over ~6 months through systematic equity strategies on NSE, executed without daily human intervention.

## Why it closed

After 9 paper trading days and 5 distinct strategies tested through an institutional-grade backtest framework, **no strategy demonstrated edge that survived proper validation**:

| Strategy | Sample size | Win rate | Net P&L (paper math) | Edge per trade |
|---|---|---|---|---|
| `play1_ema_crossover` | 714 trades | 37.0% | -₹68,609 | -₹96 |
| `play2_triple_ma` | 698 trades | 36.2% | -₹70,645 | -₹101 |
| `atr_breakout` | 2,608 trades | 34.2% | -₹462,332 | -₹177 |
| `rsi2_mean_reversion` | 1,101 trades | 28.1% | -₹359,269 | -₹326 |
| `hrvm` (OOS-tested) | 1,039 trades | 34.3% | -₹130,000 | -₹125 |
| **Combined** | **6,160 trades** | **~33%** | **-₹1,090,855** | — |

**The empirical conclusion:** simple-to-moderately-complex systematic equity strategies on Nifty 100 daily candles at retail account scale (₹2k-₹75k) do not have positive expectancy after Indian retail charges (brokerage + STT + GST + DP + stamp + SEBI levies). This is not a small loss — it is a structural -₹100 to -₹300 per trade across all 5 representative strategies.

## What the project actually delivered

| Built | Status |
|---|---|
| TradeJini broker integration (auth, orders, reconciliation) | ✅ Production-grade |
| Backtest framework v2 (next-bar-open execution, full cost model, walk-forward) | ✅ Built and used to catch all 5 losers |
| 9-check adversarial audit framework | ✅ Caught HRVM curve-fit before deploy |
| Out-of-sample validation protocol | ✅ Caught HRVM regime overfit on Day 10 |
| Paper trading engines (swing + intraday) | ✅ Both running clean 9/9 days |
| Risk infrastructure (kill switch, position cap, regime filter, time-stop, breakeven trail) | ✅ Zero capital exposure |
| Monitoring + reconciliation (5-min cycle) | ✅ Zero silent engine deaths |
| AutoStart + cron automation | ✅ Working after 2026-05-06 fixes |
| Telegram notification framework | ⚠️ Server-side working; phone-side delivery issue (unresolved, owner-side) |
| Decision journal (8 daily entries, owner-auditable) | ✅ Institutional discipline maintained |
| 16-role specialist framework (CTO, Quant, Risk, etc.) | ✅ Applied to every major decision |
| 4-phase roadmap (Stabilize → Validate → Scale → Compound) | ⚠️ Phase 1 only; Phase 2+ never triggered |

## Financial impact

**Real money lost: ₹0.**
**Theoretical losses avoided by paper-first discipline: ~₹960k.**

The strict paper-only mandate for Phase 1 (Days 1-20) was the single most valuable decision in the project. Going live on Day 1 with the original "winner" strategies (play1, play2 — appeared positive in a 45-day same-bar-close backtest) would have begun systematic loss accumulation immediately.

## Key lessons (worth keeping)

1. **Backtest discipline matters more than strategy ideas.** The original 2026-04-21 backtest "approved" play1/play2 as winners based on n=13 with same-bar-close look-ahead bias. v2 rebuild with proper execution + costs + 24mo sample exposed both as losers. Lesson: never trust a small-sample backtest. Demand n≥100 with multi-regime coverage and walk-forward.

2. **Audit framework prevents premature celebration.** On 2026-05-07 the 12-month sweep showed a "winner" config. 24-month validation reversed it. On 2026-05-11 the 24-month audit showed 44 "passing" HRVM configs. Out-of-sample on 2026 reversed all 5. Lesson: never declare a winner before ALL audit checks pass, especially regime stability and OOS.

3. **Position-size economics matter at small accounts.** Intraday trading at ₹2k account with 1% targets vs flat brokerage = guaranteed losing math regardless of strategy quality. Lesson: minimum account size for retail intraday = ~₹25k. Below that, edge gets eaten by charges alone.

4. **Phone-side delivery is owner's problem, not engineering's.** After two days of debugging "missing notifications," the verdict was server-side worked perfectly every time. Lesson: don't engineer around symptoms when the diagnosis points elsewhere.

5. **The 16-role specialist framework adds real value, not theatre.** Behavioral Coach repeatedly prevented premature optimism; Backtest Validator caught the 2026-05-07 and 2026-05-12 reversals; Risk Manager kept the live-capital mandate intact. Lesson: when the team disagrees with the operator's instinct, listen.

## What you (owner) should do next

Beyond this document's scope, but for completeness:

1. **Wife's TradeJini account:** retain or close, owner's discretion. No further automation will run against it.
2. **Capital allocation:** index SIPs are the rational answer based on this project's evidence. Discuss specifics with a SEBI-registered RIA — not me, not this document. ~12-15% CAGR long-term passive is a reasonable expectation for a diversified Indian equity index.
3. **If you want to revisit active trading in 6-12 months:** the infrastructure can be revived from hibernate. A genuinely different idea (event-driven, factor investing on multi-month horizons, options selling with proper risk model) might warrant the effort. A 6th simple-systematic equity tweak will not.

## What this app is NOT

- Not a failed engineering project — every system built worked correctly
- Not a "they didn't try hard enough" project — 5 representative strategies + 6,160 backtested trades is rigorous
- Not a sunk-cost-fallacy candidate — the discipline framework explicitly told us to stop, not to keep trying

It is a research project that produced negative results, and **negative results disciplined by good methodology are valuable**. The market told us simple-systematic equity does not have edge for retail at small scale. The app, by refusing to deploy any losing strategy live, protected ₹0 of real money from theoretical -₹960k of losses.

## Final state — wind-down checklist

- [ ] Stop paper engines after today's 15:30 IST close (clean square-off, EOD report fires)
- [ ] Disable morning cron + intraday cron (no more automated starts)
- [ ] Stop honeydaalu-backend service
- [ ] Disable AutoStart in main.py (in case service is ever manually started)
- [ ] Send final closure message to Telegram (single message, then bot retires)
- [ ] Hibernate EC2 (stop instance, retain EBS — owner-confirmed)
- [ ] Final commit + push (this document + decision journal + memory updates)
- [ ] Archive all decision journals as proof of work
- [ ] Update GitHub repo description to "Archived 2026-05-12 — Phase 1 paper trading concluded"

---

**Signed:** Gopiraja Veeraian (Owner), Claude Opus 4.7 (16-role institutional team), 2026-05-12
**Total real capital lost: ₹0.**
**Total theoretical capital protected: ~₹960k.**
**Final verdict: discipline won. The strategies did not.**
