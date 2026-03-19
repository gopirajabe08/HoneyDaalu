"""
Play #9: Gap Analysis (Gap & Go / Gap Fill)
────────────────────────────────────────────
Timeframe : 15m

"Gaps reveal overnight conviction. Whether they hold or fill
 tells you everything about the day's direction."

Two modes based on gap behavior:

GAP & GO (Continuation):
  Setup: Stock gaps up/down > 1% from previous close
  Entry conditions (Gap Up → BUY):
    1. Today's open > previous close * 1.01 (gap up > 1%)
    2. First 2 candles (30 min) hold above previous close (gap not filling)
    3. Price breaks above the high of first 2 candles
    4. Volume on breakout candle > 1.3x SMA20
    5. Entry: close of breakout candle

  Entry conditions (Gap Down → SELL):
    1. Today's open < previous close * 0.99 (gap down > 1%)
    2. First 2 candles hold below previous close
    3. Price breaks below the low of first 2 candles
    4. Volume on breakout candle > 1.3x SMA20
    5. Entry: close of breakout candle

GAP FILL (Reversal):
  Setup: Stock gaps but starts filling
  Entry conditions (Gap Up but Filling → SELL):
    1. Today's open > previous close * 1.01 (gap up > 1%)
    2. Within first 4 candles (1 hour), price drops below gap midpoint
       (midpoint = (today_open + prev_close) / 2)
    3. Bearish candle pattern (strong red body > 50% of range)
    4. Volume confirmation > 1.3x SMA20
    5. Entry: close of fill candle

  Entry conditions (Gap Down but Filling → BUY):
    1. Today's open < previous close * 0.99
    2. Within first 4 candles, price rises above gap midpoint
    3. Bullish candle pattern
    4. Volume confirmation > 1.3x SMA20

Risk Management:
  Gap & Go:
    - SL: Below first 2 candles' low (BUY) or above high (SELL)
    - Target: 1:2 R:R

  Gap Fill:
    - SL: Beyond the gap extreme (today's open for gap up fill)
    - Target: Previous close (full gap fill)
"""

import pandas as pd
from typing import Optional

from .base import (
    BaseStrategy,
    body_size,
    candle_range,
    is_bullish_candle,
    is_bearish_candle,
    get_strategy_config,
    calc_sma,
)

_KEY = "play9_gap_analysis"


class GapAnalysis(BaseStrategy):
    name = "Gap Analysis (Gap & Go / Gap Fill)"
    description = (
        "Detects gap up/down > 1% and trades continuation (Gap & Go) "
        "if the gap holds or reversal (Gap Fill) if it starts closing."
    )
    category = "Intraday Precision (Session Trading)"
    indicators = ["Gap % (prev close vs open)", "SMA20 Volume", "Candle body ratio"]
    timeframes = ["15m"]
    long_setup = (
        "Gap & Go BUY: gap up > 1%, first 2 candles hold above prev close, "
        "price breaks above first-2-candle high with volume > 1.3x SMA20. "
        "Gap Fill BUY: gap down > 1%, within first 4 candles price rises above "
        "gap midpoint with bullish body and volume confirmation."
    )
    short_setup = (
        "Gap & Go SELL: gap down > 1%, first 2 candles hold below prev close, "
        "price breaks below first-2-candle low with volume > 1.3x SMA20. "
        "Gap Fill SELL: gap up > 1%, within first 4 candles price drops below "
        "gap midpoint with bearish body and volume confirmation."
    )
    exit_rules = "Gap & Go: 1:2 R:R target. Gap Fill: target = previous close (full gap fill)."
    stop_loss_rules = (
        "Gap & Go: opposite side of first-2-candle range (min 1.2% floor). "
        "Gap Fill: beyond the gap extreme (today's open) with 1.2% floor."
    )

    def scan(self, df: pd.DataFrame, symbol: str, **kwargs) -> Optional[dict]:
        # Need at least 5 candles of today's data + previous day data
        if len(df) < 6:
            return None

        df = df.copy()

        # Filter to trading session only (exclude pre-market 9:00-9:15)
        try:
            if hasattr(df.index, 'time'):
                from datetime import time as dtime
                session_mask = df.index.time >= dtime(9, 15)
                df = df[session_mask]
                if len(df) < 6:
                    return None
        except Exception:
            pass

        # ── Identify previous close ──
        # For intraday 15m data, detect day boundaries via date change
        if hasattr(df.index, 'date'):
            dates = pd.Series(df.index.date, index=df.index)
        else:
            dates = pd.Series(pd.to_datetime(df.index).date, index=df.index)

        unique_dates = dates.unique()

        if len(unique_dates) < 2:
            # Only one day of data — cannot compute previous close
            return None

        today = unique_dates[-1]
        today_mask = dates == today
        prev_mask = dates == unique_dates[-2]

        today_df = df[today_mask]
        prev_df = df[prev_mask]

        if len(prev_df) == 0 or len(today_df) < 5:
            return None

        prev_close = prev_df["Close"].iloc[-1]
        today_open = today_df["Open"].iloc[0]

        # ── Detect gap direction and magnitude ──
        gap_pct = (today_open - prev_close) / prev_close

        if abs(gap_pct) < 0.01:
            # Gap < 1%, no signal
            return None

        gap_up = gap_pct > 0
        gap_midpoint = (today_open + prev_close) / 2

        # ── First 2 candles (opening range) stats ──
        first2_high = max(today_df["High"].iloc[0], today_df["High"].iloc[1])
        first2_low = min(today_df["Low"].iloc[0], today_df["Low"].iloc[1])

        # ── Volume SMA20 for confirmation ──
        vol_sma = None
        if len(df) >= 20:
            vol_sma = df["Volume"].rolling(20).mean()

        # ── Try Gap & Go first, then Gap Fill ──
        signal = self._check_gap_and_go(
            df, today_df, symbol, prev_close, today_open,
            gap_up, first2_high, first2_low, vol_sma,
        )
        if signal:
            return signal

        signal = self._check_gap_fill(
            df, today_df, symbol, prev_close, today_open,
            gap_up, gap_midpoint, vol_sma,
        )
        return signal

    # ──────────────────────────────────────────────────────────────────────
    #  GAP & GO (Continuation)
    # ──────────────────────────────────────────────────────────────────────

    def _check_gap_and_go(
        self, df: pd.DataFrame, today_df: pd.DataFrame, symbol: str,
        prev_close: float, today_open: float, gap_up: bool,
        first2_high: float, first2_low: float,
        vol_sma: Optional[pd.Series],
    ) -> Optional[dict]:

        if gap_up:
            return self._gap_go_long(
                df, today_df, symbol, prev_close, today_open,
                first2_high, first2_low, vol_sma,
            )
        else:
            return self._gap_go_short(
                df, today_df, symbol, prev_close, today_open,
                first2_high, first2_low, vol_sma,
            )

    def _gap_go_long(
        self, df: pd.DataFrame, today_df: pd.DataFrame, symbol: str,
        prev_close: float, today_open: float,
        first2_high: float, first2_low: float,
        vol_sma: Optional[pd.Series],
    ) -> Optional[dict]:
        """Gap Up → BUY continuation: gap holds, price breaks above first-2 high."""

        # Condition: first 2 candles hold above previous close (gap not filling)
        if first2_low < prev_close:
            return None

        # Look for breakout candle (after first 2) — check last two completed
        for idx in [-1, -2]:
            actual_idx = len(today_df) + idx
            if actual_idx < 2:
                continue

            candle = today_df.iloc[idx]

            # Price breaks above first-2-candle high
            if candle["Close"] <= first2_high:
                continue

            # Strong candle: body > 50% of range
            c_range = candle_range(candle)
            if c_range == 0:
                continue
            if body_size(candle) / c_range < 0.50:
                continue

            # Must be bullish
            if not is_bullish_candle(candle):
                continue

            # Volume confirmation > 1.3x SMA20
            if vol_sma is not None and len(vol_sma) >= 20:
                candle_global_idx = today_df.index[actual_idx]
                sma_val = vol_sma.loc[candle_global_idx]
                if pd.notna(sma_val) and candle["Volume"] < sma_val * 1.3:
                    continue

            # ── Entry & Risk Management ──
            entry = round(candle["Close"], 2)

            # SL = below first 2 candles' low
            sl = first2_low

            # SL floor: at least 1.2% from entry
            cfg = get_strategy_config(_KEY)
            min_pct = cfg.get("min_pct", 0.012)
            min_sl_distance = entry * min_pct
            if entry - sl < min_sl_distance:
                sl = round(entry - min_sl_distance, 2)

            sl = round(sl, 2)
            risk = entry - sl
            if risk <= 0:
                return None

            # Target: 1:2 R:R
            target1 = round(entry + risk * 2, 2)
            target2 = round(entry + risk * 3, 2)

            return {
                "symbol": symbol,
                "signal_type": "BUY",
                "entry_price": entry,
                "stop_loss": sl,
                "target_1": target1,
                "target_2": target2,
                "risk": round(risk, 2),
                "reward": round(risk * 2, 2),
                "risk_reward_ratio": "1:2",
                "current_price": round(df.iloc[-1]["Close"], 2),
                "strategy": _KEY,
            }

        return None

    def _gap_go_short(
        self, df: pd.DataFrame, today_df: pd.DataFrame, symbol: str,
        prev_close: float, today_open: float,
        first2_high: float, first2_low: float,
        vol_sma: Optional[pd.Series],
    ) -> Optional[dict]:
        """Gap Down → SELL continuation: gap holds, price breaks below first-2 low."""

        # Condition: first 2 candles hold below previous close (gap not filling)
        if first2_high > prev_close:
            return None

        # Look for breakout candle (after first 2) — check last two completed
        for idx in [-1, -2]:
            actual_idx = len(today_df) + idx
            if actual_idx < 2:
                continue

            candle = today_df.iloc[idx]

            # Price breaks below first-2-candle low
            if candle["Close"] >= first2_low:
                continue

            # Strong candle: body > 50% of range
            c_range = candle_range(candle)
            if c_range == 0:
                continue
            if body_size(candle) / c_range < 0.50:
                continue

            # Must be bearish
            if not is_bearish_candle(candle):
                continue

            # Volume confirmation > 1.3x SMA20
            if vol_sma is not None and len(vol_sma) >= 20:
                candle_global_idx = today_df.index[actual_idx]
                sma_val = vol_sma.loc[candle_global_idx]
                if pd.notna(sma_val) and candle["Volume"] < sma_val * 1.3:
                    continue

            # ── Entry & Risk Management ──
            entry = round(candle["Close"], 2)

            # SL = above first 2 candles' high
            sl = first2_high

            # SL floor: at least 1.2% from entry
            cfg = get_strategy_config(_KEY)
            min_pct = cfg.get("min_pct", 0.012)
            min_sl_distance = entry * min_pct
            if sl - entry < min_sl_distance:
                sl = round(entry + min_sl_distance, 2)

            sl = round(sl, 2)
            risk = sl - entry
            if risk <= 0:
                return None

            # Target: 1:2 R:R
            target1 = round(entry - risk * 2, 2)
            target2 = round(entry - risk * 3, 2)

            return {
                "symbol": symbol,
                "signal_type": "SELL",
                "entry_price": entry,
                "stop_loss": sl,
                "target_1": target1,
                "target_2": target2,
                "risk": round(risk, 2),
                "reward": round(risk * 2, 2),
                "risk_reward_ratio": "1:2",
                "current_price": round(df.iloc[-1]["Close"], 2),
                "strategy": _KEY,
            }

        return None

    # ──────────────────────────────────────────────────────────────────────
    #  GAP FILL (Reversal)
    # ──────────────────────────────────────────────────────────────────────

    def _check_gap_fill(
        self, df: pd.DataFrame, today_df: pd.DataFrame, symbol: str,
        prev_close: float, today_open: float, gap_up: bool,
        gap_midpoint: float, vol_sma: Optional[pd.Series],
    ) -> Optional[dict]:

        if gap_up:
            return self._gap_fill_short(
                df, today_df, symbol, prev_close, today_open,
                gap_midpoint, vol_sma,
            )
        else:
            return self._gap_fill_long(
                df, today_df, symbol, prev_close, today_open,
                gap_midpoint, vol_sma,
            )

    def _gap_fill_short(
        self, df: pd.DataFrame, today_df: pd.DataFrame, symbol: str,
        prev_close: float, today_open: float,
        gap_midpoint: float, vol_sma: Optional[pd.Series],
    ) -> Optional[dict]:
        """Gap Up but Filling → SELL: price drops below gap midpoint within first 4 candles."""

        # Check candles within the first 4 (indices 0-3)
        check_limit = min(4, len(today_df))

        # Look for the fill candle — check last two completed candles that are within limit
        for idx in [-1, -2]:
            actual_idx = len(today_df) + idx
            if actual_idx < 0 or actual_idx >= check_limit:
                continue

            candle = today_df.iloc[actual_idx]

            # Price drops below gap midpoint
            if candle["Close"] >= gap_midpoint:
                continue

            # Bearish candle: strong red body > 50% of range
            c_range = candle_range(candle)
            if c_range == 0:
                continue
            if body_size(candle) / c_range < 0.50:
                continue
            if not is_bearish_candle(candle):
                continue

            # Volume confirmation > 1.3x SMA20
            if vol_sma is not None and len(vol_sma) >= 20:
                candle_global_idx = today_df.index[actual_idx]
                sma_val = vol_sma.loc[candle_global_idx]
                if pd.notna(sma_val) and candle["Volume"] < sma_val * 1.3:
                    continue

            # ── Entry & Risk Management ──
            entry = round(candle["Close"], 2)

            # SL = beyond the gap extreme (today's open for gap up fill)
            sl = round(today_open, 2)

            # SL floor: at least 1.2% from entry
            cfg = get_strategy_config(_KEY)
            min_pct = cfg.get("min_pct", 0.012)
            min_sl_distance = entry * min_pct
            if sl - entry < min_sl_distance:
                sl = round(entry + min_sl_distance, 2)

            sl = round(sl, 2)
            risk = sl - entry
            if risk <= 0:
                return None

            # Target: previous close (full gap fill)
            target1 = round(prev_close, 2)
            reward = entry - target1
            if reward <= 0:
                return None

            # target2: extend beyond prev close by same risk distance
            target2 = round(target1 - risk, 2)

            return {
                "symbol": symbol,
                "signal_type": "SELL",
                "entry_price": entry,
                "stop_loss": sl,
                "target_1": target1,
                "target_2": target2,
                "risk": round(risk, 2),
                "reward": round(reward, 2),
                "risk_reward_ratio": f"1:{round(reward / risk, 1) if risk > 0 else 0}",
                "current_price": round(df.iloc[-1]["Close"], 2),
                "strategy": _KEY,
            }

        return None

    def _gap_fill_long(
        self, df: pd.DataFrame, today_df: pd.DataFrame, symbol: str,
        prev_close: float, today_open: float,
        gap_midpoint: float, vol_sma: Optional[pd.Series],
    ) -> Optional[dict]:
        """Gap Down but Filling → BUY: price rises above gap midpoint within first 4 candles."""

        # Check candles within the first 4 (indices 0-3)
        check_limit = min(4, len(today_df))

        # Look for the fill candle — check last two completed candles that are within limit
        for idx in [-1, -2]:
            actual_idx = len(today_df) + idx
            if actual_idx < 0 or actual_idx >= check_limit:
                continue

            candle = today_df.iloc[actual_idx]

            # Price rises above gap midpoint
            if candle["Close"] <= gap_midpoint:
                continue

            # Bullish candle: strong green body > 50% of range
            c_range = candle_range(candle)
            if c_range == 0:
                continue
            if body_size(candle) / c_range < 0.50:
                continue
            if not is_bullish_candle(candle):
                continue

            # Volume confirmation > 1.3x SMA20
            if vol_sma is not None and len(vol_sma) >= 20:
                candle_global_idx = today_df.index[actual_idx]
                sma_val = vol_sma.loc[candle_global_idx]
                if pd.notna(sma_val) and candle["Volume"] < sma_val * 1.3:
                    continue

            # ── Entry & Risk Management ──
            entry = round(candle["Close"], 2)

            # SL = beyond the gap extreme (today's open for gap down fill)
            sl = round(today_open, 2)

            # SL floor: at least 1.2% from entry
            cfg = get_strategy_config(_KEY)
            min_pct = cfg.get("min_pct", 0.012)
            min_sl_distance = entry * min_pct
            if entry - sl < min_sl_distance:
                sl = round(entry - min_sl_distance, 2)

            sl = round(sl, 2)
            risk = entry - sl
            if risk <= 0:
                return None

            # Target: previous close (full gap fill)
            target1 = round(prev_close, 2)
            reward = target1 - entry
            if reward <= 0:
                return None

            # target2: extend beyond prev close by same risk distance
            target2 = round(target1 + risk, 2)

            return {
                "symbol": symbol,
                "signal_type": "BUY",
                "entry_price": entry,
                "stop_loss": sl,
                "target_1": target1,
                "target_2": target2,
                "risk": round(risk, 2),
                "reward": round(reward, 2),
                "risk_reward_ratio": f"1:{round(reward / risk, 1) if risk > 0 else 0}",
                "current_price": round(df.iloc[-1]["Close"], 2),
                "strategy": _KEY,
            }

        return None
