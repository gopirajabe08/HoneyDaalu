"""
Walk-forward backtest module v2 — addresses the 9 audit failures from
2026-05-04 Backtest Validator Role 16 audit.

REPLACES backtest_with_charges.py for any decision affecting live capital.

Design goals (per audit):
1. Next-bar-open execution (no same-bar-close look-ahead)
2. Walk-forward train/test splits (no in-sample-only)
3. Full Indian retail cost model (brokerage + STT + GST + DP + stamp + SEBI)
4. Multi-regime testing (12+ months of data)
5. Sample size enforcement (n>=100 per strategy claim)
6. Distribution analysis (lottery profile detection)
7. Parameter sensitivity (test +/-10% around each hard-coded value)
8. Realistic slippage (0.1-0.3% by liquidity tier)
9. Survivorship-aware universe (delisted stocks acknowledged)

Sub-modules:
  data.py        — historical data acquisition + caching
  cost_model.py  — Indian retail full charge model
  walk_forward.py — rolling train/test engine
  strategies.py  — adopted strategies (play1, play2) ported with no look-ahead
  audit.py       — 9 adversarial checks
  cli.py         — main entry point

Status 2026-05-06: skeleton + cost_model + data layer.
Target completion: Mon 18 May 2026 (Day 14 of 20-day plan).
"""
__version__ = "2.0.0-alpha"
