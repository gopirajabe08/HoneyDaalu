"""
Research Analyst — Corporate Action Filter for LuckyNavi.

Fetches today's corporate actions from NSE and returns a list of
stock symbols that should be EXCLUDED from intraday scanning.

Stocks with dividends, splits, rights, and similar corporate events
experience abnormal price behaviour and gaps that break technical signals.
These are excluded for the day they go ex-date.

Usage:
    from services.research_analyst import get_excluded_stocks
    excluded = get_excluded_stocks()
    # Pass to scanner — skip these symbols
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import json

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# NSE corporate actions API
_NSE_CORP_ACTIONS_URL = (
    "https://www.nseindia.com/api/corporates/corporateActions"
    "?index=equities&from_date={from_date}&to_date={to_date}"
)

# NSE requires browser-like headers to avoid 403
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

# Corporate action types that should trigger exclusion
_EXCLUDE_PURPOSES = {
    "dividend",
    "interim dividend",
    "final dividend",
    "bonus",
    "stock split",
    "rights",
    "buyback",
    "amalgamation",
    "merger",
    "demerger",
    "special dividend",
    "capital reduction",
}

# Simple in-process cache: refresh at most once per day
_cache: dict[str, list] = {}  # {"YYYY-MM-DD": [symbol, ...]}
_cache_time: float = 0


def get_excluded_stocks() -> list[str]:
    """
    Return a list of NSE equity symbols to EXCLUDE from scanning today.

    Fetches NSE corporate actions for today. Symbols whose ex-date is today
    are returned. The list is cached for the trading day.

    Returns:
        List of symbol strings (e.g. ["HDFCBANK", "RELIANCE"]).
        Returns [] on any fetch error (fail-open: don't block trading).
    """
    global _cache, _cache_time

    today_str = datetime.now(IST).strftime("%Y-%m-%d")

    # Return cached result if fresh (within 4 hours)
    if today_str in _cache and (time.time() - _cache_time) < 14400:
        return _cache[today_str]

    try:
        excluded = _fetch_excluded_today(today_str)
        _cache = {today_str: excluded}
        _cache_time = time.time()
        if excluded:
            logger.info(f"[ResearchAnalyst] {len(excluded)} stocks excluded today (corporate actions): {', '.join(excluded[:10])}{'...' if len(excluded)>10 else ''}")
        else:
            logger.info("[ResearchAnalyst] No corporate actions today — no exclusions")
        return excluded
    except Exception as e:
        logger.warning(f"[ResearchAnalyst] Failed to fetch corporate actions: {e} — proceeding with no exclusions")
        return []


def _fetch_excluded_today(today_str: str) -> list[str]:
    """
    Fetch NSE corporate actions for today and return symbols with ex-date = today.

    NSE API date format: DD-MM-YYYY
    """
    # Convert YYYY-MM-DD → DD-MM-YYYY for NSE API
    parts = today_str.split("-")
    nse_date = f"{parts[2]}-{parts[1]}-{parts[0]}"

    url = _NSE_CORP_ACTIONS_URL.format(from_date=nse_date, to_date=nse_date)
    logger.debug(f"[ResearchAnalyst] Fetching: {url}")

    # NSE requires session cookies — must hit homepage first
    import requests as _req
    s = _req.Session()
    s.headers.update(_HEADERS)
    s.get("https://www.nseindia.com", timeout=10)
    resp = s.get(url, timeout=15)
    resp.raise_for_status()
    raw = resp.text

    data = json.loads(raw)

    # Response is a list of dicts OR {"data": [...]}
    if isinstance(data, dict):
        items = data.get("data", [])
    elif isinstance(data, list):
        items = data
    else:
        return []

    excluded = set()
    for item in items:
        purpose = (item.get("purpose", "") or "").lower().strip()
        symbol = (item.get("symbol", "") or "").upper().strip()
        ex_date_raw = (item.get("exDate", "") or item.get("ex_date", "") or "").strip()

        if not symbol:
            continue

        # Check if ex-date matches today
        # NSE returns dates as "DD-MMM-YYYY" (e.g. "13-APR-2026") or "YYYY-MM-DD"
        ex_date_matches = _ex_date_is_today(ex_date_raw, today_str)
        if not ex_date_matches:
            continue

        # Check if the purpose warrants exclusion
        if any(excl in purpose for excl in _EXCLUDE_PURPOSES):
            excluded.add(symbol)
            logger.debug(f"[ResearchAnalyst] Excluding {symbol}: {purpose} (ex-date {ex_date_raw})")

    return sorted(excluded)


def _ex_date_is_today(ex_date_raw: str, today_str: str) -> bool:
    """
    Parse NSE ex-date string and check if it matches today.

    NSE uses mixed formats: "13-APR-2026", "2026-04-13", "13/04/2026".
    """
    if not ex_date_raw:
        return False

    ex_clean = ex_date_raw.strip().upper()

    # Try DD-MMM-YYYY (most common NSE format)
    try:
        dt = datetime.strptime(ex_clean, "%d-%b-%Y")
        return dt.strftime("%Y-%m-%d") == today_str
    except ValueError:
        pass

    # Try YYYY-MM-DD
    try:
        dt = datetime.strptime(ex_clean, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d") == today_str
    except ValueError:
        pass

    # Try DD/MM/YYYY
    try:
        dt = datetime.strptime(ex_clean, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d") == today_str
    except ValueError:
        pass

    # Try DD-MM-YYYY
    try:
        dt = datetime.strptime(ex_clean, "%d-%m-%Y")
        return dt.strftime("%Y-%m-%d") == today_str
    except ValueError:
        pass

    return False
