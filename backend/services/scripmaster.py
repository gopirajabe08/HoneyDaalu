"""
ScripMaster data loader for TradeJini CubePlus API.

TradeJini uses exchange tokens (e.g., 22_NSE) instead of symbol names.
This module downloads and caches the ScripMaster instrument master file,
providing fast lookups between NSE symbols and exchange tokens.
"""

import os
import json
import time
import logging
import threading
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── Cache paths ──────────────────────────────────────────────────────────
CACHE_DIR = Path(__file__).parent.parent / ".scripmaster_cache"
CACHE_FILE_NSE = CACHE_DIR / "nse_instruments.json"
CACHE_FILE_NFO = CACHE_DIR / "nfo_instruments.json"
CACHE_EXPIRY_HOURS = 16  # Refresh daily (before next trading day)

# ── In-memory lookups ────────────────────────────────────────────────────
_symbol_to_token: dict = {}   # {"NSE:RELIANCE": "2885", "NFO:NIFTY...": "12345"}
_token_to_symbol: dict = {}   # {"2885_NSE": "RELIANCE", "12345_NFO": "NIFTY..."}
_instruments: dict = {}        # Full instrument data by token
_lock = threading.Lock()
_loaded = False


def _ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _is_cache_fresh(cache_file: Path) -> bool:
    """Check if cache file exists and is less than CACHE_EXPIRY_HOURS old."""
    if not cache_file.exists():
        return False
    age_hours = (time.time() - cache_file.stat().st_mtime) / 3600
    return age_hours < CACHE_EXPIRY_HOURS


def download_scripmaster(access_token: str, api_key: str, exchange: str = "NSE") -> list:
    """
    Download ScripMaster (instrument master) from TradeJini CubePlus API.

    Args:
        access_token: Valid CubePlus access token
        api_key: TradeJini API key
        exchange: Exchange segment (NSE, NFO, BSE, BFO, CDS, MCX)

    Returns:
        List of instrument dicts with fields: excToken, symbol, name, series, etc.
    """
    _ensure_cache_dir()
    cache_file = CACHE_DIR / f"{exchange.lower()}_instruments.json"

    # Return cached if fresh
    if _is_cache_fresh(cache_file):
        try:
            with open(cache_file) as f:
                data = json.load(f)
            logger.info(f"[ScripMaster] Loaded {len(data)} {exchange} instruments from cache")
            return data
        except Exception:
            pass

    # Download from API
    try:
        headers = {
            "Authorization": f"Bearer {api_key}:{access_token}",
            "Content-Type": "application/json",
        }
        url = f"https://api.tradejini.com/v2/api/market/scrip-master?exchangeName={exchange}"
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, list) and len(data) > 0:
            # Cache for reuse
            with open(cache_file, "w") as f:
                json.dump(data, f)
            logger.info(f"[ScripMaster] Downloaded {len(data)} {exchange} instruments")
            return data
        else:
            logger.warning(f"[ScripMaster] Empty response for {exchange}: {str(data)[:200]}")
            return []
    except Exception as e:
        logger.error(f"[ScripMaster] Failed to download {exchange}: {e}")
        # Try returning stale cache
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return []


def load_instruments(access_token: str, api_key: str, exchanges: list = None):
    """
    Load ScripMaster data for specified exchanges into memory.
    Call this once after authentication succeeds.

    Args:
        access_token: Valid CubePlus access token
        api_key: TradeJini API key
        exchanges: List of exchanges to load (default: NSE, NFO)
    """
    global _symbol_to_token, _token_to_symbol, _instruments, _loaded

    if exchanges is None:
        exchanges = ["NSE", "NFO"]

    with _lock:
        _symbol_to_token.clear()
        _token_to_symbol.clear()
        _instruments.clear()

        for exchange in exchanges:
            instruments = download_scripmaster(access_token, api_key, exchange)

            for inst in instruments:
                exc_token = str(inst.get("excToken", ""))
                symbol = inst.get("symbol", "")
                series = inst.get("series", "")
                name = inst.get("name", "")

                if not exc_token or not symbol:
                    continue

                # Build lookup keys
                broker_symbol = f"{exc_token}_{exchange}"

                # For NSE equity (EQ series), map plain symbol
                if exchange == "NSE" and series in ("EQ", "BE"):
                    _symbol_to_token[f"NSE:{symbol}"] = exc_token
                    _token_to_symbol[broker_symbol] = symbol
                elif exchange == "NFO":
                    # Options/Futures: store full symbol for lookup
                    _symbol_to_token[f"NFO:{symbol}"] = exc_token
                    _token_to_symbol[broker_symbol] = symbol

                _instruments[broker_symbol] = inst

        _loaded = True
        total = len(_symbol_to_token)
        logger.info(f"[ScripMaster] Loaded {total} instruments into memory ({', '.join(exchanges)})")


def is_loaded() -> bool:
    """Check if ScripMaster data is loaded in memory."""
    return _loaded


def get_exchange_token(symbol: str, exchange: str = "NSE") -> Optional[str]:
    """
    Get exchange token for a symbol.

    Args:
        symbol: Plain symbol (e.g., "RELIANCE") or exchange-prefixed ("NSE:RELIANCE")
        exchange: Exchange segment (NSE, NFO)

    Returns:
        Exchange token string, or None if not found
    """
    if not _loaded:
        logger.warning("[ScripMaster] Data not loaded - call load_instruments() first")
        return None

    # Try with exchange prefix
    key = f"{exchange}:{symbol}" if ":" not in symbol else symbol
    token = _symbol_to_token.get(key)
    if token:
        return token

    # Try without exchange prefix
    for k, v in _symbol_to_token.items():
        if k.endswith(f":{symbol}"):
            return v

    return None


def get_symbol_from_token(token: str, exchange: str = "NSE") -> Optional[str]:
    """
    Get plain symbol from an exchange token.

    Args:
        token: Exchange token (e.g., "2885")
        exchange: Exchange segment

    Returns:
        Plain symbol string (e.g., "RELIANCE"), or None
    """
    broker_symbol = f"{token}_{exchange}"
    return _token_to_symbol.get(broker_symbol)


def build_broker_symbol(nse_symbol: str) -> str:
    """
    Convert NSE symbol to TradeJini broker format: exchangeToken_exchangeName

    Args:
        nse_symbol: Plain NSE symbol (e.g., "RELIANCE")

    Returns:
        Broker symbol (e.g., "2885_NSE"), or original symbol if token not found
    """
    # Clean input
    clean = nse_symbol.replace(".NS", "").replace("NSE:", "").replace("-EQ", "")
    token = get_exchange_token(clean, "NSE")
    if token:
        return f"{token}_NSE"

    logger.warning(f"[ScripMaster] No exchange token found for {clean} — using symbol as-is")
    return f"{clean}_NSE"


def nse_from_broker(broker_symbol: str) -> str:
    """
    Convert TradeJini broker symbol back to plain NSE symbol.

    Args:
        broker_symbol: Broker format (e.g., "2885_NSE")

    Returns:
        Plain symbol (e.g., "RELIANCE")
    """
    symbol = _token_to_symbol.get(broker_symbol)
    if symbol:
        return symbol

    # Fallback: strip exchange suffix
    parts = broker_symbol.rsplit("_", 1)
    return parts[0] if parts else broker_symbol


def get_instrument(token: str, exchange: str = "NSE") -> Optional[dict]:
    """Get full instrument data by exchange token."""
    return _instruments.get(f"{token}_{exchange}")


def build_option_symbol(underlying: str, expiry_str: str, strike: int, option_type: str) -> Optional[str]:
    """
    Build TradeJini option symbol and get its exchange token.

    Args:
        underlying: "NIFTY" or "BANKNIFTY"
        expiry_str: Expiry in YYMMDD format (e.g., "260402")
        strike: Strike price (e.g., 23500)
        option_type: "CE" or "PE"

    Returns:
        Broker symbol (exchangeToken_NFO) or None if not found
    """
    # TradeJini option symbol format varies - search in loaded instruments
    # Common patterns: "NIFTY 02APR2026 CE 23500", "NIFTY26APR23500CE"
    search_terms = [
        f"{underlying}{expiry_str}{strike}{option_type}",
        f"{underlying} {expiry_str} {option_type} {strike}",
    ]

    for key, token in _symbol_to_token.items():
        if key.startswith("NFO:"):
            sym = key[4:]  # Remove "NFO:" prefix
            for term in search_terms:
                if term in sym.replace(" ", ""):
                    return f"{token}_NFO"

    logger.warning(f"[ScripMaster] Option not found: {underlying} {expiry_str} {strike} {option_type}")
    return None


def build_futures_symbol(symbol: str, expiry_str: str) -> Optional[str]:
    """
    Build TradeJini futures symbol and get its exchange token.

    Args:
        symbol: Underlying (e.g., "NIFTY", "RELIANCE")
        expiry_str: Expiry in YYMMDD or YYMMMFUT format

    Returns:
        Broker symbol (exchangeToken_NFO) or None if not found
    """
    search_terms = [
        f"{symbol}{expiry_str}FUT",
        f"{symbol} {expiry_str} FUT",
    ]

    for key, token in _symbol_to_token.items():
        if key.startswith("NFO:"):
            sym = key[4:]
            for term in search_terms:
                if term in sym.replace(" ", ""):
                    return f"{token}_NFO"

    logger.warning(f"[ScripMaster] Futures not found: {symbol} {expiry_str}")
    return None


def search_instruments(query: str, exchange: str = None, limit: int = 20) -> list:
    """
    Search instruments by name/symbol substring.

    Args:
        query: Search string
        exchange: Optional exchange filter
        limit: Max results

    Returns:
        List of matching instrument dicts
    """
    results = []
    query_upper = query.upper()

    for broker_sym, inst in _instruments.items():
        if exchange and not broker_sym.endswith(f"_{exchange}"):
            continue
        symbol = inst.get("symbol", "")
        name = inst.get("name", "")
        if query_upper in symbol.upper() or query_upper in name.upper():
            results.append(inst)
            if len(results) >= limit:
                break

    return results
