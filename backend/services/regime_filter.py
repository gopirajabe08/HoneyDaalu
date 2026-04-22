"""
4-gate regime filter for the regime-filtered equity intraday engine.

Usage:
    from services.regime_filter import should_trade_long_today

    allow, reason, detail = should_trade_long_today()
    if not allow:
        log_skip(reason)
        return

Gate spec (from 2026-04-22 autonomous-task brief):

    1. Gap gate — NIFTY open > prev close - 0.3%
    2. Fear gate — India VIX < 20
    3. Trend gate — today's NIFTY spot > NIFTY close 3 trading days ago
    4. Flash crash — NIFTY intraday > -1% from open (re-check before every entry)

Gates 1-3 are evaluated once per day (first call after 9:15 AM IST) and cached.
Gate 4 is re-evaluated on every call.

All data via yfinance (^NSEI, ^INDIAVIX). No broker auth required.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from utils.time_utils import now_ist

logger = logging.getLogger(__name__)

# Thresholds (locked in per spec; tuning requires owner approval)
GAP_FLOOR_PCT = -0.3
VIX_CEILING = 20.0
TREND_LOOKBACK_DAYS = 3
FLASH_CRASH_FLOOR_PCT = -1.0


@dataclass
class DailyGateSnapshot:
    """Evaluated once per day at ~9:30 AM IST and cached."""
    trading_date: date
    gap_pct: float
    gap_ok: bool
    vix: float
    vix_ok: bool
    trend_change: float
    trend_ok: bool
    computed_at: datetime
    error: Optional[str] = None

    @property
    def all_static_gates_ok(self) -> bool:
        return self.gap_ok and self.vix_ok and self.trend_ok


@dataclass
class FilterResult:
    """Return value of should_trade_long_today()."""
    allow: bool
    reason: str
    gap_pct: float = 0.0
    vix: float = 0.0
    trend_change: float = 0.0
    flash_pct: float = 0.0
    detail: dict = field(default_factory=dict)


_daily_snapshot: Optional[DailyGateSnapshot] = None
_daily_lock = threading.Lock()


def _fetch_daily_gates() -> DailyGateSnapshot:
    """Fetch NIFTY + VIX daily data and evaluate the 3 static gates."""
    today = now_ist().date()
    try:
        nifty = yf.Ticker("^NSEI").history(period="10d", interval="1d")
        vix = yf.Ticker("^INDIAVIX").history(period="10d", interval="1d")

        if nifty is None or nifty.empty or vix is None or vix.empty:
            raise RuntimeError("yfinance returned empty data for ^NSEI or ^INDIAVIX")

        nifty = nifty.copy()
        nifty.index = nifty.index.tz_localize(None).normalize()
        vix = vix.copy()
        vix.index = vix.index.tz_localize(None).normalize()

        today_ts = pd.Timestamp(today)
        if today_ts in nifty.index:
            row = nifty.loc[today_ts]
        else:
            row = nifty.iloc[-1]
            logger.warning(
                f"[RegimeFilter] Today ({today}) missing in ^NSEI; using last row {row.name.date()}"
            )

        # Prev close = row immediately before today's row in the daily series
        today_idx = nifty.index.get_loc(row.name)
        if today_idx == 0:
            raise RuntimeError("Not enough NIFTY history for prev_close")
        prev_close = float(nifty["Close"].iloc[today_idx - 1])
        lookback_idx = today_idx - TREND_LOOKBACK_DAYS
        if lookback_idx < 0:
            raise RuntimeError(f"Not enough NIFTY history for {TREND_LOOKBACK_DAYS}-day lookback")
        lookback_close = float(nifty["Close"].iloc[lookback_idx])

        open_px = float(row["Open"])
        today_close = float(row["Close"])
        gap_pct = (open_px - prev_close) / prev_close * 100
        trend_change = today_close - lookback_close
        gap_ok = gap_pct >= GAP_FLOOR_PCT
        trend_ok = today_close > lookback_close

        # VIX: use today's row if present, else latest
        if today_ts in vix.index:
            vix_val = float(vix.loc[today_ts, "Close"])
        else:
            vix_val = float(vix["Close"].iloc[-1])
        vix_ok = vix_val < VIX_CEILING

        return DailyGateSnapshot(
            trading_date=today,
            gap_pct=gap_pct,
            gap_ok=gap_ok,
            vix=vix_val,
            vix_ok=vix_ok,
            trend_change=trend_change,
            trend_ok=trend_ok,
            computed_at=now_ist(),
        )

    except Exception as e:
        logger.exception(f"[RegimeFilter] Daily gate fetch failed: {e}")
        return DailyGateSnapshot(
            trading_date=today,
            gap_pct=0.0,
            gap_ok=False,
            vix=0.0,
            vix_ok=False,
            trend_change=0.0,
            trend_ok=False,
            computed_at=now_ist(),
            error=str(e),
        )


def _get_daily_gates() -> DailyGateSnapshot:
    """Thread-safe cached daily-gates accessor."""
    global _daily_snapshot
    today = now_ist().date()
    with _daily_lock:
        if _daily_snapshot is None or _daily_snapshot.trading_date != today:
            _daily_snapshot = _fetch_daily_gates()
        return _daily_snapshot


def _check_flash_crash() -> tuple[bool, float]:
    """Re-evaluated before every entry. Returns (ok, intraday_pct)."""
    try:
        nifty_intra = yf.Ticker("^NSEI").history(period="1d", interval="5m")
        if nifty_intra is None or nifty_intra.empty:
            return False, 0.0
        open_px = float(nifty_intra["Open"].iloc[0])
        current_px = float(nifty_intra["Close"].iloc[-1])
        pct = (current_px - open_px) / open_px * 100 if open_px > 0 else 0.0
        return pct >= FLASH_CRASH_FLOOR_PCT, pct
    except Exception as e:
        logger.warning(f"[RegimeFilter] Flash-crash check failed, defaulting to block: {e}")
        return False, 0.0


def should_trade_long_today() -> FilterResult:
    """Main entry point. Returns FilterResult with allow/reason/gate values."""
    snap = _get_daily_gates()
    if snap.error:
        return FilterResult(
            allow=False,
            reason=f"data error: {snap.error}",
            detail={"gate": "data_fetch", "error": snap.error},
        )

    if not snap.gap_ok:
        return FilterResult(
            allow=False,
            reason=f"gap {snap.gap_pct:+.2f}% below floor {GAP_FLOOR_PCT:+.1f}%",
            gap_pct=snap.gap_pct, vix=snap.vix, trend_change=snap.trend_change,
            detail={"gate": "gap", "threshold": GAP_FLOOR_PCT},
        )
    if not snap.vix_ok:
        return FilterResult(
            allow=False,
            reason=f"VIX {snap.vix:.2f} >= ceiling {VIX_CEILING:.1f}",
            gap_pct=snap.gap_pct, vix=snap.vix, trend_change=snap.trend_change,
            detail={"gate": "vix", "threshold": VIX_CEILING},
        )
    if not snap.trend_ok:
        return FilterResult(
            allow=False,
            reason=f"trend down {snap.trend_change:+.2f} vs {TREND_LOOKBACK_DAYS}d ago",
            gap_pct=snap.gap_pct, vix=snap.vix, trend_change=snap.trend_change,
            detail={"gate": "trend", "lookback_days": TREND_LOOKBACK_DAYS},
        )

    flash_ok, flash_pct = _check_flash_crash()
    if not flash_ok:
        return FilterResult(
            allow=False,
            reason=f"flash crash {flash_pct:+.2f}% <= floor {FLASH_CRASH_FLOOR_PCT:+.1f}%",
            gap_pct=snap.gap_pct, vix=snap.vix, trend_change=snap.trend_change,
            flash_pct=flash_pct,
            detail={"gate": "flash", "threshold": FLASH_CRASH_FLOOR_PCT},
        )

    return FilterResult(
        allow=True,
        reason="all 4 gates passed",
        gap_pct=snap.gap_pct, vix=snap.vix, trend_change=snap.trend_change,
        flash_pct=flash_pct,
        detail={
            "gap_pct": snap.gap_pct, "vix": snap.vix,
            "trend_change": snap.trend_change, "flash_pct": flash_pct,
        },
    )


def reset_cache() -> None:
    """Test helper — forces re-evaluation of daily gates on next call."""
    global _daily_snapshot
    with _daily_lock:
        _daily_snapshot = None
