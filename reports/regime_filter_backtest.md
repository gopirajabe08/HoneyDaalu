# Regime Filter Backtest — Mar 1 to Apr 22, 2026

Autonomous Phase 1 of the regime-filtered equity intraday engine. Validates the 4-gate filter against historical NIFTY + India VIX data from yfinance, cross-referenced to IntraTrading's Fyers P&L on 3 known days.

**Thresholds (from spec):**
- Gap gate: NIFTY open ≥ prev close × (1 + -0.003) (i.e. gap-down ≤ 0.3%)
- Fear gate: India VIX < 20.0
- Trend gate: today's close > close 3 trading days ago
- Flash crash gate: intraday low ≥ open × (1 + -0.01)

**Data source:** yfinance ^NSEI (daily), ^INDIAVIX (daily close). Flash-crash gate uses daily low vs open as a one-shot backtest proxy; live engine will re-evaluate intraday before every entry.

## Summary

- Trading days in window: **33**
- Allowed (all 4 gates pass): **7** (21.2%)
- Blocked (≥ 1 gate fails): **26** (78.8%)
- Success criterion (Phase 3): block rate > 20%. Current backtest block rate: **78.8%** → PASS

## Ground-truth validation (vs IntraTrading Fyers P&L)

| Date | Actual P&L | Filter expected | Filter result | Verdict |
|---|---|---|---|---|
| 2026-03-12 | +₹1,362 (3W/1L) | ALLOW | BLOCK (gap, vix, trend) | ❌ |
| 2026-03-13 | +₹1,707 (8W/1L) | ALLOW | BLOCK (gap, vix, trend, flash) | ❌ |
| 2026-03-24 | -₹6,095 (disaster) | BLOCK | BLOCK (vix, trend, flash) | ✅ |

**❌ Ground truth mismatch — Phase 2 deploy HELD pending owner decision.**

### Tuning-wall analysis (spec-allowed: ±0.1% gap, ±2 VIX)

| Day | as-spec | max-relax (gap≥-0.4%, VIX<22) | residual blocker |
|---|---|---|---|
| 2026-03-12 | BLOCK(gap,vix,trend) | BLOCK(gap,trend) | gap,trend |
| 2026-03-13 | BLOCK(gap,vix,trend,flash) | BLOCK(gap,vix,trend,flash) | gap,vix,trend,flash |
| 2026-03-24 | BLOCK(vix,trend,flash) | BLOCK(vix,trend,flash) | none |

**Residual trend-gate failure on Mar 12/13 cannot be tuned away with the spec-allowed knobs.** Those days occurred inside a clear NIFTY downtrend (close on Mar 12 was -1.6% from the 3-day lookback; on Mar 13 it was -4.6%). The IntraTrading engine happened to profit on them via stock-specific moves, but broad-market regime was unambiguously bearish. The filter correctly classifies these as bad-regime days.

### Owner decision needed

1. **Deploy as-spec anyway** (recommended, Trading Specialist + Quant verified). The filter's purpose is to block bearish-regime days; Mar 12/13 were profitable outliers despite bearish regime, not examples of the filter failing. 60 days of live paper data will tell us definitively whether the filter's expectation holds.
2. **Expand tuning authority** (e.g. replace 3-day trend gate with a 5-day or drop it entirely). Breaks spec; needs explicit go-ahead.
3. **Rethink hypothesis** — Mar 12/13 edge may be stock-specific (catalysts, earnings). Regime filter alone wouldn't capture it.
4. **Kill project** — if the filter's expected behaviour doesn't match the ground truth, the whole approach may be wrong.

## Day-by-day

| Date | Gap% | VIX | Trend | Flash% | Allow? | Fail |
|---|---|---|---|---|---|---|
| 2026-03-02 | -2.06% | 17.13 | flat/down | -0.23% | 🔴 | gap,trend |
| 2026-03-04 | -1.92% | 21.14 | flat/down | -0.34% | 🔴 | gap,vix,trend |
| 2026-03-05 | +0.55% | 17.86 | flat/down | -0.35% | 🔴 | trend |
| 2026-03-06 | -0.44% | 19.88 | flat/down | -0.98% | 🔴 | gap,trend |
| 2026-03-09 | -2.38% | 23.36 | flat/down | -0.71% | 🔴 | gap,vix,trend |
| 2026-03-10 | +1.05% | 18.91 | flat/down | -0.83% | 🔴 | trend |
| 2026-03-11 | -0.12% | 21.06 | flat/down | -1.64% | 🔴 | vix,trend,flash |
| 2026-03-12 | -0.80% | 21.52 | flat/down | -0.50% | 🔴 | gap,vix,trend |
| 2026-03-13 | -0.75% | 22.65 | flat/down | -1.49% | 🔴 | gap,vix,trend,flash |
| 2026-03-16 | -0.15% | 21.60 | flat/down | -0.70% | 🔴 | vix,trend |
| 2026-03-17 | +0.36% | 19.79 | flat/down | -0.62% | 🔴 | trend |
| 2026-03-18 | +0.22% | 18.72 | up | -0.06% | 🟢 | — |
| 2026-03-19 | -2.44% | 22.80 | flat/down | -1.15% | 🔴 | gap,vix,trend,flash |
| 2026-03-20 | +0.47% | 22.81 | flat/down | -0.18% | 🔴 | vix,trend |
| 2026-03-23 | -1.26% | 26.73 | flat/down | -1.55% | 🔴 | gap,vix,trend,flash |
| 2026-03-24 | +1.62% | 24.74 | flat/down | -1.11% | 🔴 | vix,trend,flash |
| 2026-03-25 | +0.66% | 24.64 | up | -0.01% | 🔴 | vix |
| 2026-03-27 | -0.57% | 26.80 | up | -1.59% | 🔴 | gap,vix,flash |
| 2026-03-30 | -1.18% | 27.89 | flat/down | -1.18% | 🔴 | gap,vix,trend,flash |
| 2026-04-01 | +2.54% | 25.01 | flat/down | -1.22% | 🔴 | vix,trend,flash |
| 2026-04-02 | -1.31% | 25.52 | flat/down | -0.90% | 🔴 | gap,vix,trend |
| 2026-04-06 | +0.30% | 25.47 | up | -1.04% | 🔴 | vix,flash |
| 2026-04-07 | -0.56% | 24.70 | up | -0.52% | 🔴 | gap,vix |
| 2026-04-08 | +3.16% | 19.70 | up | -0.11% | 🟢 | — |
| 2026-04-09 | -0.37% | 20.43 | up | -0.95% | 🔴 | gap,vix |
| 2026-04-10 | +0.44% | 18.85 | up | -0.10% | 🟢 | — |
| 2026-04-13 | -1.92% | 20.50 | flat/down | -0.14% | 🔴 | gap,vix,trend |
| 2026-04-15 | +1.35% | 18.67 | up | -0.07% | 🟢 | — |
| 2026-04-16 | +0.64% | 18.09 | up | -1.16% | 🔴 | flash |
| 2026-04-17 | -0.13% | 17.21 | up | -0.29% | 🟢 | — |
| 2026-04-20 | +0.16% | 18.79 | up | -0.62% | 🟢 | — |
| 2026-04-21 | +0.04% | 17.53 | up | -0.08% | 🟢 | — |
| 2026-04-22 | -0.43% | 18.30 | up | -0.48% | 🔴 | gap |

## Gate failure distribution (blocked days)

| Gate | Days failing |
|---|---|
| gap | 15 |
| vix | 19 |
| trend | 19 |
| flash | 10 |

## Notes + caveats

- **Backtest data is daily-bar.** The 9:30 AM VIX and gap values are approximated by the daily open/close; live filter will use the 9:15-9:30 AM 15-min bar.
- **Flash-crash** is one-shot in backtest (daily low vs open). In production the gate is re-evaluated before every entry, so fewer intraday-reversal days may trigger it live.
- **Trend gate uses trading-day lookback**, not calendar days — consistent with spec.
- **Ground-truth P&L figures** (Mar 12/13/24) are from IntraTrading Fyers system, referenced only to validate filter directionality. No IntraTrading code or data was touched.
