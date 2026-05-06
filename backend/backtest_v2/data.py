"""
Historical data acquisition + caching for backtest_v2.

Addresses Audit Check 5 (regime overfitting) by enabling 12+ months of data
across multiple market regimes — old backtest used only 45 days.

Strategy:
- yfinance for daily OHLCV (free, reliable for NSE equities)
- Local Parquet cache to avoid re-fetching (huge speedup on iteration)
- Cache invalidation: re-fetch if cache > 7 days old or explicit force
- Graceful failure: log + skip symbols that fail to fetch
"""
from __future__ import annotations
import logging
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL_DAYS = 7


def _cache_path(symbol: str, period: str, interval: str) -> Path:
    safe = symbol.replace(".", "_").replace("/", "_")
    return CACHE_DIR / f"{safe}_{period}_{interval}.pkl"


def _is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < timedelta(days=CACHE_TTL_DAYS)


def fetch_one(
    symbol: str,
    period: str = "12mo",
    interval: str = "1d",
    use_cache: bool = True,
) -> pd.DataFrame | None:
    """
    Fetch OHLCV for one symbol. Returns None on failure.

    Args:
        symbol: NSE symbol without ".NS" (e.g. "RELIANCE")
        period: yfinance period string ("12mo", "2y", "6mo", etc.)
        interval: candle interval ("1d", "15m", "1h")
        use_cache: read from local cache if fresh

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
        Index: Date (timezone-aware where supported)
    """
    cache = _cache_path(symbol, period, interval)
    if use_cache and _is_cache_fresh(cache):
        try:
            return pd.read_pickle(cache)
        except Exception as e:
            logger.warning(f"[data] cache read failed for {symbol}: {e}; refetching")

    yf_symbol = f"{symbol}.NS"
    try:
        df = yf.Ticker(yf_symbol).history(period=period, interval=interval)
    except Exception as e:
        logger.warning(f"[data] yfinance fetch failed for {symbol}: {e}")
        return None

    if df is None or df.empty:
        logger.warning(f"[data] empty result for {symbol}")
        return None

    # Normalize: keep only OHLCV columns
    keep = ["Open", "High", "Low", "Close", "Volume"]
    df = df[[c for c in keep if c in df.columns]].copy()

    if len(df) < 30:
        logger.warning(f"[data] insufficient bars ({len(df)}) for {symbol}")
        return None

    try:
        df.to_pickle(cache)
    except Exception as e:
        logger.warning(f"[data] cache write failed for {symbol}: {e}")

    return df


def fetch_universe(
    symbols: list[str],
    period: str = "12mo",
    interval: str = "1d",
    use_cache: bool = True,
) -> dict[str, pd.DataFrame]:
    """
    Batch fetch a list of symbols. Skips failed symbols.

    Returns dict: symbol -> DataFrame.
    """
    out = {}
    for i, sym in enumerate(symbols):
        df = fetch_one(sym, period=period, interval=interval, use_cache=use_cache)
        if df is not None:
            out[sym] = df
        if (i + 1) % 25 == 0:
            logger.info(f"[data] fetched {i + 1}/{len(symbols)}")
    logger.info(f"[data] universe ready: {len(out)}/{len(symbols)} symbols")
    return out


def clear_cache():
    """Wipe local cache (for testing / forced refetch)."""
    for f in CACHE_DIR.glob("*.pkl"):
        f.unlink()


# ── .gitignore: don't commit cached data ──
GITIGNORE = CACHE_DIR / ".gitignore"
if not GITIGNORE.exists():
    GITIGNORE.write_text("*\n!.gitignore\n")


# ── Self-test ──
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sym = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    df = fetch_one(sym, period="12mo", interval="1d", use_cache=True)
    if df is None:
        print(f"FAIL: no data for {sym}")
        sys.exit(1)
    print(f"=== {sym} 12mo daily ===")
    print(f"bars: {len(df)} | first: {df.index[0]} | last: {df.index[-1]}")
    print(df.tail(3))
