"""
TradeJini CubePlus API integration service for LuckyNavi.

Handles authentication, order placement, positions, and live market data.
Provides a unified broker API so all traders use the same interface.

API Docs: https://api.tradejini.com/api-doc/
"""

import os
import json
import math
import time
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

import requests as req

load_dotenv()
logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────

TRADEJINI_API_KEY = os.getenv("TRADEJINI_API_KEY", "")
TRADEJINI_API_SECRET = os.getenv("TRADEJINI_API_SECRET", "")
TRADEJINI_CLIENT_ID = os.getenv("TRADEJINI_CLIENT_ID", "")
TRADEJINI_PASSWORD = os.getenv("TRADEJINI_PASSWORD", "")
TRADEJINI_TOTP_SECRET = os.getenv("TRADEJINI_TOTP_SECRET", "")
TRADEJINI_REDIRECT_URI = os.getenv("TRADEJINI_REDIRECT_URI", "http://localhost:8001/api/broker/callback")

BASE_URL = "https://api.tradejini.com/v2"
TOKEN_FILE = Path(__file__).parent.parent / ".tradejini_token"

# ── Product type mapping (Fyers names → TradeJini names) ─────────────────
# Traders use Fyers-style names; we translate transparently.
PRODUCT_TYPE_MAP = {
    "INTRADAY": "MIS",
    "CNC": "CNC",
    "MARGIN": "NRML",
    "MIS": "MIS",
    "NRML": "NRML",
    "BO": "BO",
    "CO": "CO",
}

# Order type mapping (Fyers numeric → TradeJini string)
ORDER_TYPE_MAP = {
    1: "LIMIT",
    2: "MARKET",
    3: "SL",      # Stop Loss (limit)
    4: "SL-M",    # Stop Loss Market
}

# Side mapping (Fyers numeric → TradeJini string)
SIDE_MAP = {
    1: "BUY",
    -1: "SELL",
}

# ── Token persistence ─────────────────────────────────────────────────────

_access_token: Optional[str] = None
_session: Optional[req.Session] = None


def _save_token(token: str):
    TOKEN_FILE.write_text(token)


def _load_saved_token() -> Optional[str]:
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text().strip()
        return token if token else None
    return None


def _clear_token():
    global _access_token, _session
    _access_token = None
    _session = None
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()


def _get_auth_header() -> dict:
    """Build Authorization header for CubePlus API: Bearer APIkey:accessToken"""
    return {"Authorization": f"Bearer {TRADEJINI_API_KEY}:{_access_token}"}


def _get_session() -> Optional[req.Session]:
    """Get authenticated requests session."""
    global _session, _access_token

    if _session is not None and _access_token:
        return _session

    # Try loading saved token
    saved = _load_saved_token()
    if saved:
        _access_token = saved
        _session = req.Session()
        _session.headers.update({
            "Authorization": f"Bearer {TRADEJINI_API_KEY}:{_access_token}",
            "Content-Type": "application/json",
        })
        return _session

    return None


def _api_get(endpoint: str, params: dict = None) -> dict:
    """Make authenticated GET request to CubePlus API."""
    session = _get_session()
    if session is None:
        return {"error": "Not authenticated"}
    try:
        url = f"{BASE_URL}{endpoint}"
        resp = session.get(url, params=params, timeout=15)
        if resp.status_code == 401:
            _clear_token()
            return {"error": "Session expired — please re-authenticate"}
        resp.raise_for_status()
        return resp.json()
    except req.exceptions.RequestException as e:
        logger.error(f"[Broker] GET {endpoint} failed: {e}")
        return {"error": str(e)}


def _api_post(endpoint: str, data: dict = None) -> dict:
    """Make authenticated POST request to CubePlus API (form-encoded)."""
    session = _get_session()
    if session is None:
        return {"error": "Not authenticated"}
    try:
        url = f"{BASE_URL}{endpoint}"
        # CubePlus expects form-encoded POST (not JSON) for order endpoints
        headers = {
            "Authorization": f"Bearer {TRADEJINI_API_KEY}:{_access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = req.post(url, headers=headers, data=data, timeout=15)
        if resp.status_code == 401:
            _clear_token()
            return {"error": "Session expired — please re-authenticate"}
        resp.raise_for_status()
        return resp.json()
    except req.exceptions.RequestException as e:
        logger.error(f"[Broker] POST {endpoint} failed: {e}")
        return {"error": str(e)}


def _api_put(endpoint: str, data: dict = None) -> dict:
    """Make authenticated PUT request to CubePlus API."""
    session = _get_session()
    if session is None:
        return {"error": "Not authenticated"}
    try:
        url = f"{BASE_URL}{endpoint}"
        resp = session.put(url, json=data, timeout=15)
        if resp.status_code == 401:
            _clear_token()
            return {"error": "Session expired — please re-authenticate"}
        resp.raise_for_status()
        return resp.json()
    except req.exceptions.RequestException as e:
        logger.error(f"[Broker] PUT {endpoint} failed: {e}")
        return {"error": str(e)}


def _api_delete(endpoint: str, params: dict = None) -> dict:
    """Make authenticated DELETE request to CubePlus API."""
    session = _get_session()
    if session is None:
        return {"error": "Not authenticated"}
    try:
        url = f"{BASE_URL}{endpoint}"
        resp = session.delete(url, params=params, timeout=15)
        if resp.status_code == 401:
            _clear_token()
            return {"error": "Session expired — please re-authenticate"}
        resp.raise_for_status()
        return resp.json()
    except req.exceptions.RequestException as e:
        logger.error(f"[Broker] DELETE {endpoint} failed: {e}")
        return {"error": str(e)}


# ── Authentication ─────────────────────────────────────────────────────────


def is_configured() -> bool:
    """Check if TradeJini API credentials are configured."""
    return bool(TRADEJINI_API_KEY) and bool(TRADEJINI_API_SECRET)


def get_auth_url() -> Optional[str]:
    """
    Generate the TradeJini CubePlus OAuth login URL.
    User must visit this URL, log in with TOTP, and get redirected.
    """
    if not is_configured():
        return None

    # CubePlus uses standard OAuth redirect flow
    params = {
        "api_key": TRADEJINI_API_KEY,
        "redirect_url": TRADEJINI_REDIRECT_URI,
        "state": "luckynavi",
    }
    return f"{BASE_URL}/o/authorize?api_key={TRADEJINI_API_KEY}&redirect_url={TRADEJINI_REDIRECT_URI}&state=luckynavi"


def generate_token(auth_code: str) -> dict:
    """
    Exchange auth code for access token.
    Called after OAuth redirect with the authorization code.
    """
    if not is_configured():
        return {"error": "TradeJini API credentials not configured"}

    try:
        resp = req.post(
            f"{BASE_URL}/o/access-token",
            json={
                "api_key": TRADEJINI_API_KEY,
                "api_secret": TRADEJINI_API_SECRET,
                "request_token": auth_code,
            },
            timeout=15,
        )

        data = resp.json()
        token = data.get("access_token") or data.get("data", {}).get("access_token")

        if token:
            _set_token(token)
            # Load ScripMaster data after successful auth
            _load_scripmaster_async()
            return {"status": "ok", "message": "Authenticated successfully"}
        else:
            return {"error": data.get("message", "Token generation failed")}

    except Exception as e:
        return {"error": str(e)}


def _set_token(token: str):
    """Set access token and create session."""
    global _access_token, _session
    _access_token = token
    _save_token(token)
    _session = req.Session()
    _session.headers.update({
        "Authorization": f"Bearer {TRADEJINI_API_KEY}:{_access_token}",
        "Content-Type": "application/json",
    })


def _load_scripmaster_async():
    """ScripMaster not needed — CubePlus Individual mode uses EQT_{SYMBOL}_EQ_NSE format directly."""
    pass


def is_authenticated() -> bool:
    """Check if we have a valid TradeJini session."""
    session = _get_session()
    if session is None:
        return False
    try:
        resp = _api_get("/api/account/details")
        return "error" not in resp and resp.get("status") != "error"
    except Exception:
        _clear_token()
        return False


def logout():
    """Clear TradeJini session."""
    _clear_token()
    return {"status": "ok", "message": "Logged out"}


def headless_login() -> dict:
    """
    Fully automated TradeJini login via individual-token-v2 endpoint.
    Uses password + TOTP for 2FA — zero manual interaction.

    Flow:
      1. Generate TOTP from secret
      2. POST /api-gw/oauth/individual-token-v2 with password + TOTP
      3. Receive access_token

    Requires TRADEJINI_PASSWORD and TRADEJINI_TOTP_SECRET in .env
    """
    import pyotp

    password = TRADEJINI_PASSWORD
    totp_secret = TRADEJINI_TOTP_SECRET

    if not password:
        return {"error": "TRADEJINI_PASSWORD required in .env for auto-login"}

    if not is_configured():
        return {"error": "TRADEJINI_API_KEY and TRADEJINI_API_SECRET not configured"}

    if not totp_secret:
        return {"error": "TRADEJINI_TOTP_SECRET required — 2FA is mandatory for API login"}

    try:
        totp_code = pyotp.TOTP(totp_secret).now()

        logger.info("[Broker] Headless login: sending individual-token-v2 request...")

        resp = req.post(
            f"{BASE_URL}/api-gw/oauth/individual-token-v2",
            headers={
                "Authorization": f"Bearer {TRADEJINI_API_KEY}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "password": password,
                "twoFa": totp_code,
                "twoFaTyp": "totp",
            },
            timeout=15,
        )

        if resp.status_code != 200:
            return {"error": f"Login failed (HTTP {resp.status_code}): {resp.text[:300]}"}

        data = resp.json()
        token = data.get("access_token")
        if token:
            _set_token(token)
            _load_scripmaster_async()
            logger.info("[Broker] Headless login: SUCCESS — access token obtained")
            return {"status": "ok", "message": "Authenticated successfully"}

        return {"error": f"Login failed: {data}"}

    except Exception as e:
        logger.error(f"[Broker] Headless login failed: {e}")
        return {"error": f"Headless login failed: {str(e)}"}


# ── Fyers-compatible accessor (used by options_client.py) ─────────────────

def get_fyers():
    """
    Compatibility shim — returns self-module so callers using
    `fyers = get_fyers(); fyers.quotes(...)` can be gradually migrated.
    Returns None if not authenticated.
    """
    if _get_session() is None:
        return None
    return _BrokerCompat()


class _BrokerCompat:
    """Compatibility wrapper providing Fyers-like method interface."""

    def quotes(self, data: dict = None) -> dict:
        symbols = data.get("symbols", "") if data else ""
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        return get_quotes_raw(symbol_list)

    def get_profile(self) -> dict:
        return get_profile()

    def funds(self) -> dict:
        return get_funds()

    def orderbook(self) -> dict:
        return get_orderbook()

    def positions(self) -> dict:
        return get_positions()

    def holdings(self) -> dict:
        return get_holdings()

    def tradebook(self) -> dict:
        return get_tradebook()

    def place_order(self, data: dict = None) -> dict:
        if not data:
            return {"error": "No order data"}
        return _place_raw_order(data)

    def modify_order(self, data: dict = None) -> dict:
        if not data:
            return {"error": "No data"}
        order_id = data.pop("id", "")
        return modify_order(order_id, **data)

    def cancel_order(self, data: dict = None) -> dict:
        if not data:
            return {"error": "No data"}
        return cancel_order(data.get("id", ""))

    def depth(self, data: dict = None) -> dict:
        symbol = data.get("symbol", "") if data else ""
        return get_market_depth(symbol)


# ── Profile & Funds ────────────────────────────────────────────────────────


def get_profile() -> dict:
    """Get user profile. Returns Fyers-compatible format."""
    result = _api_get("/api/account/details")
    if "error" in result:
        return result

    # Normalize to Fyers-compatible shape
    data = result.get("data", result)
    return {
        "s": "ok",
        "data": {
            "name": data.get("name", data.get("clientName", "")),
            "email": data.get("email", ""),
            "pan": data.get("pan", ""),
            "fy_id": data.get("clientCode", TRADEJINI_CLIENT_ID),
        },
    }


def get_funds() -> dict:
    """Get fund limits. Returns normalized format for all engines."""
    result = _api_get("/api/oms/limits")
    if "error" in result:
        return result

    # TradeJini CubePlus returns: {d: {availMargin, marginUsed, totalCredits, ...}, s: "ok"}
    data = result.get("d", result.get("data", result))

    available = 0
    used = 0
    total = 0
    if isinstance(data, dict):
        available = float(data.get("availMargin", data.get("availCash", 0)))
        used = float(data.get("marginUsed", 0))
        total = float(data.get("totalCredits", available + used))

    return {
        "s": "ok",
        "fund_limit": [
            {"id": 10, "title": "Available Balance", "equityAmount": available},
            {"id": 6, "title": "Used Margin", "equityAmount": used},
            {"id": 1, "title": "Total Balance", "equityAmount": total},
        ],
    }


# ── Segment Check ─────────────────────────────────────────────────────────

def is_nfo_enabled() -> bool:
    """Check if NFO (F&O) segment is enabled on the account."""
    try:
        # Try fetching a quote for a NIFTY option
        from services.scripmaster import is_loaded
        if not is_loaded():
            return False

        # Check if NFO instruments are loaded
        from services.scripmaster import _symbol_to_token
        nfo_count = sum(1 for k in _symbol_to_token if k.startswith("NFO:"))
        if nfo_count > 0:
            return True
    except Exception:
        pass

    # Try placing a small test or checking segments via profile
    try:
        profile = _api_get("/api/account/details")
        exchanges = profile.get("data", {}).get("exchanges", [])
        if isinstance(exchanges, list):
            return "NFO" in exchanges
    except Exception:
        pass

    return False


# ── Orders ─────────────────────────────────────────────────────────────────


def place_order(
    symbol: str,
    qty: int,
    side: int,  # 1=Buy, -1=Sell (Fyers convention)
    order_type: int = 2,  # 1=Limit, 2=Market, 3=SL, 4=SL-M
    product_type: str = "INTRADAY",
    limit_price: float = 0,
    stop_price: float = 0,
    order_tag: str = "equity_intraday",
) -> dict:
    """
    Place an order on TradeJini.
    Accepts Fyers-style parameters and translates to CubePlus API.
    SEBI compliance: order_tag is enriched with Algo ID automatically.
    """
    session = _get_session()
    if session is None:
        return {"error": "Not authenticated"}

    # SEBI compliance: enrich order tag with Algo ID
    from services.sebi_compliance import build_order_tag, log_order_event
    order_tag = build_order_tag(order_tag)
    log_order_event()

    # Format symbol for TradeJini CubePlus
    broker_symbol = format_broker_symbol(symbol)

    # Map to CubePlus field values (lowercase)
    side_map = {1: "buy", -1: "sell"}
    type_map = {1: "limit", 2: "market", 3: "stoplimit", 4: "stopmarket"}
    product_map = {"INTRADAY": "intraday", "CNC": "delivery", "MARGIN": "normal", "DELIVERY": "delivery", "MIS": "intraday"}

    order_data = {
        "symId": broker_symbol,
        "qty": qty,
        "side": side_map.get(side, "buy"),
        "type": type_map.get(order_type, "market"),
        "product": product_map.get(product_type.upper(), "intraday"),
        "validity": "day",
        "discQty": 0,
    }

    if order_type in (1, 3) and limit_price > 0:
        order_data["limitPrice"] = round(limit_price, 2)
    if order_type in (3, 4) and stop_price > 0:
        order_data["trigPrice"] = round(stop_price, 2)

    return _place_order_with_tick_retry(order_data)


def place_bracket_order(
    symbol: str,
    qty: int,
    side: int,
    limit_price: float,
    stop_loss: float,
    target: float,
) -> dict:
    """
    Place an entry order + separate SL-M protective order.
    Same approach as Fyers version: INTRADAY market entry + SL-M.
    """
    session = _get_session()
    if session is None:
        return {"error": "Not authenticated"}

    broker_symbol = format_broker_symbol(symbol)
    return _place_intraday_with_sl(broker_symbol, qty, side, stop_loss, target)


def _place_intraday_with_sl(
    broker_symbol: str,
    qty: int,
    side: int,
    stop_loss: float,
    target: float,
) -> dict:
    """
    Place MIS market entry, then a SL-M protective order.
    Returns combined result with both order IDs.
    """
    parts = broker_symbol.split("_")
    exchange_token = parts[0] if len(parts) >= 2 else broker_symbol
    exchange = parts[1] if len(parts) >= 2 else "NSE"
    tj_side = SIDE_MAP.get(side, "BUY")

    # Step 1: Market entry order
    entry_data = {
        "exchangeName": exchange,
        "exchangeToken": exchange_token,
        "transactionType": tj_side,
        "orderType": "MARKET",
        "productType": "MIS",
        "quantity": qty,
        "price": 0,
        "triggerPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
    }

    _enforce_order_rate_limit()
    entry_resp = _api_post("/api/oms/place-order", entry_data)

    if "error" in entry_resp:
        return {"error": f"Entry order failed: {entry_resp['error']}"}

    entry_order_id = str(
        entry_resp.get("orderId")
        or entry_resp.get("data", {}).get("orderId")
        or entry_resp.get("id", "")
    )

    if not entry_order_id or entry_order_id == "None":
        return {"error": f"Entry order rejected: {entry_resp}"}

    logger.info(f"MIS entry placed: {broker_symbol} (ID: {entry_order_id})")

    # Step 2: SL-M protective order (opposite side)
    sl_side_int = -1 if side == 1 else 1
    sl_side_str = SIDE_MAP.get(sl_side_int)
    if sl_side_int == -1:
        sl_limit = _round_to_tick(stop_loss - max(stop_loss * 0.02, 1))
    else:
        sl_limit = _round_to_tick(stop_loss + max(stop_loss * 0.02, 1))

    sl_data = {
        "exchangeName": exchange,
        "exchangeToken": exchange_token,
        "transactionType": sl_side_str,
        "orderType": "SL-M",
        "productType": "MIS",
        "quantity": qty,
        "price": round(sl_limit, 2),
        "triggerPrice": round(stop_loss, 2),
        "validity": "DAY",
        "disclosedQty": 0,
    }

    _enforce_order_rate_limit()
    sl_resp = _api_post("/api/oms/place-order", sl_data)

    sl_order_id = str(
        sl_resp.get("orderId")
        or sl_resp.get("data", {}).get("orderId")
        or sl_resp.get("id", "")
    )

    if not sl_order_id or sl_order_id == "None" or "error" in sl_resp:
        sl_error = sl_resp.get("message", sl_resp.get("error", str(sl_resp)))
        logger.error(f"SL-M order FAILED for {broker_symbol}: {sl_error}")
        # Cancel entry to avoid unprotected position
        logger.error(f"Cancelling entry {entry_order_id} — SL failed, position unprotected")
        try:
            cancel_order(entry_order_id)
        except Exception:
            pass
        # Try emergency market exit
        try:
            exit_side_str = SIDE_MAP.get(-1 if side == 1 else 1)
            _enforce_order_rate_limit()
            _api_post("/api/oms/place-order", {
                "exchangeName": exchange,
                "exchangeToken": exchange_token,
                "transactionType": exit_side_str,
                "orderType": "MARKET",
                "productType": "MIS",
                "quantity": qty,
                "price": 0,
                "triggerPrice": 0,
                "validity": "DAY",
            })
            logger.info(f"Emergency exit placed for {broker_symbol}")
        except Exception:
            pass
        return {"error": f"SL placement failed: {sl_error}. Entry cancelled/reversed for safety."}

    logger.info(f"SL-M placed: {broker_symbol} SL@{stop_loss} (ID: {sl_order_id})")

    return {
        "s": "ok",
        "id": entry_order_id,
        "order_mode": "INTRADAY_SL",
        "entry_order_id": entry_order_id,
        "sl_order_id": sl_order_id,
        "target_order_id": "",
        "target_price": round(target, 2),
    }


def _place_raw_order(data: dict) -> dict:
    """
    Place order from raw Fyers-format data dict (used by _BrokerCompat).
    Translates Fyers fields to TradeJini CubePlus fields.
    """
    symbol = data.get("symbol", "")
    # If symbol is in Fyers format (NSE:XXX-EQ), extract clean name first
    clean_symbol = symbol.replace("NSE:", "").replace("-EQ", "").replace("NFO:", "")

    broker_sym = format_broker_symbol(clean_symbol) if ":" in symbol or "-EQ" in symbol else symbol
    parts = broker_sym.split("_")
    exchange_token = parts[0] if len(parts) >= 2 else broker_sym
    exchange = parts[1] if len(parts) >= 2 else "NSE"

    side_int = data.get("side", 1)
    order_type_int = data.get("type", 2)

    order_payload = {
        "exchangeName": exchange,
        "exchangeToken": exchange_token,
        "transactionType": SIDE_MAP.get(side_int, "BUY"),
        "orderType": ORDER_TYPE_MAP.get(order_type_int, "MARKET"),
        "productType": PRODUCT_TYPE_MAP.get(data.get("productType", "INTRADAY"), "MIS"),
        "quantity": data.get("qty", 0),
        "price": data.get("limitPrice", 0),
        "triggerPrice": data.get("trigPrice", 0),
        "validity": data.get("validity", "DAY"),
        "disclosedQty": data.get("disclosedQty", 0),
        "orderTag": data.get("orderTag", ""),
    }

    _enforce_order_rate_limit()
    result = _api_post("/api/oms/place-order", order_payload)

    # Normalize response to Fyers format
    order_id = str(result.get("orderId") or result.get("data", {}).get("orderId") or "")
    if order_id and order_id != "None":
        return {"s": "ok", "id": order_id}
    return result


def modify_order(order_id: str, **kwargs) -> dict:
    """Modify an existing order."""
    data = {"orderId": order_id}

    if "qty" in kwargs:
        data["quantity"] = kwargs["qty"]
    if "limitPrice" in kwargs:
        data["price"] = kwargs["limitPrice"]
    if "trigPrice" in kwargs:
        data["triggerPrice"] = kwargs["trigPrice"]
    if "type" in kwargs:
        data["orderType"] = ORDER_TYPE_MAP.get(kwargs["type"], kwargs["type"])

    result = _api_put("/api/oms/modify-order", data)

    # Normalize
    if result.get("status") == "success" or result.get("s") == "ok":
        return {"s": "ok", "id": order_id}
    return result


def cancel_order(order_id: str) -> dict:
    """Cancel an order."""
    result = _api_delete("/api/oms/cancel-order", params={"orderId": order_id})

    # Normalize
    if result.get("status") == "success" or result.get("s") == "ok":
        return {"s": "ok", "id": order_id}
    return result


# ── Order Book & Positions ─────────────────────────────────────────────────


def get_orderbook() -> dict:
    """Get all orders. Returns Fyers-compatible format."""
    result = _api_get("/api/oms/orders")
    if "error" in result:
        return result

    # Normalize to Fyers format
    orders = result.get("data", result.get("orderBook", []))
    if not isinstance(orders, list):
        orders = []

    return {"s": "ok", "orderBook": orders}


def get_positions() -> dict:
    """Get net positions. Returns Fyers-compatible format."""
    result = _api_get("/api/oms/positions")
    if "error" in result:
        return result

    positions = result.get("data", result.get("netPositions", []))
    if not isinstance(positions, list):
        positions = []

    # Normalize field names to Fyers format
    normalized = []
    for pos in positions:
        normalized.append({
            "symbol": pos.get("symbol", pos.get("tradingSymbol", "")),
            "netQty": pos.get("netQty", pos.get("netQuantity", 0)),
            "buyQty": pos.get("buyQty", pos.get("buyQuantity", 0)),
            "sellQty": pos.get("sellQty", pos.get("sellQuantity", 0)),
            "buyAvg": pos.get("buyAvg", pos.get("buyAvgPrice", 0)),
            "sellAvg": pos.get("sellAvg", pos.get("sellAvgPrice", 0)),
            "realized_profit": pos.get("realized_profit", pos.get("realizedProfit", 0)),
            "unrealized_profit": pos.get("unrealized_profit", pos.get("unrealizedProfit", 0)),
            "ltp": pos.get("ltp", pos.get("lastPrice", 0)),
            "productType": pos.get("productType", pos.get("product", "")),
            **pos,  # Keep all original fields too
        })

    return {"s": "ok", "netPositions": normalized}


def get_holdings() -> dict:
    """Get delivery holdings."""
    result = _api_get("/api/oms/holdings")
    if "error" in result:
        return result

    holdings = result.get("data", result.get("holdings", []))
    if not isinstance(holdings, list):
        holdings = []

    return {"s": "ok", "holdings": holdings}


def get_tradebook() -> dict:
    """Get trade book (executed trades)."""
    result = _api_get("/api/oms/trades")
    if "error" in result:
        return result

    trades = result.get("data", result.get("tradeBook", []))
    if not isinstance(trades, list):
        trades = []

    return {"s": "ok", "tradeBook": trades}


# ── Market Data ────────────────────────────────────────────────────────────


def get_quotes(symbols: list[str]) -> dict:
    """
    Get live quotes for symbols.
    Accepts NSE symbols (e.g., ["RELIANCE", "TCS"]) — auto-converts to broker format.
    Returns Fyers-compatible quote format.
    """
    session = _get_session()
    if session is None:
        return {"error": "Not authenticated"}

    # Convert symbols to broker format
    broker_symbols = []
    for s in symbols:
        bs = format_broker_symbol(s)
        broker_symbols.append(bs)

    # Build comma-separated token list for API
    # TradeJini expects: exchangeToken_exchangeName format
    try:
        result = _api_get("/api/market/quote", params={
            "symbols": ",".join(broker_symbols),
            "mode": "LTP",
        })

        if "error" in result:
            return result

        # Normalize to Fyers quote format: {"d": [{"n": symbol, "v": {"lp": price, ...}}]}
        quotes_data = result.get("data", [])
        if not isinstance(quotes_data, list):
            quotes_data = [quotes_data] if quotes_data else []

        fyers_quotes = []
        for i, q in enumerate(quotes_data):
            orig_symbol = symbols[i] if i < len(symbols) else ""
            fyers_symbol = f"NSE:{orig_symbol}-EQ" if ":" not in orig_symbol else orig_symbol

            fyers_quotes.append({
                "n": fyers_symbol,
                "v": {
                    "lp": float(q.get("ltp", q.get("lp", q.get("lastPrice", 0)))),
                    "open_price": float(q.get("open", q.get("open_price", 0))),
                    "high_price": float(q.get("high", q.get("high_price", 0))),
                    "low_price": float(q.get("low", q.get("low_price", 0))),
                    "close_price": float(q.get("close", q.get("close_price", q.get("prevClose", 0)))),
                    "volume": int(q.get("volume", q.get("vol", 0))),
                    "ch": float(q.get("change", q.get("ch", 0))),
                    "chp": float(q.get("changePercent", q.get("chp", 0))),
                },
            })

        return {"s": "ok", "d": fyers_quotes}

    except Exception as e:
        return {"error": str(e)}


def get_quotes_raw(symbols: list[str]) -> dict:
    """
    Get quotes with raw broker symbols (already formatted).
    Used by _BrokerCompat for direct calls.
    """
    try:
        result = _api_get("/api/market/quote", params={
            "symbols": ",".join(symbols),
            "mode": "LTP",
        })
        return result if "error" not in result else {"s": "error", "d": []}
    except Exception as e:
        return {"error": str(e)}


def get_market_depth(symbol: str) -> dict:
    """Get market depth (Level 2 data) for a symbol."""
    broker_symbol = format_broker_symbol(symbol)
    result = _api_get("/api/market/quote", params={
        "symbols": broker_symbol,
        "mode": "FULL",
    })
    return result


# ── Helpers ────────────────────────────────────────────────────────────────


def _round_to_tick(price: float, tick: float = 0.05) -> float:
    """Round price down to nearest tick size."""
    return round(math.floor(price / tick) * tick, 2)


# SEBI: max 10 orders/second. Track timestamps to enforce.
_order_timestamps: list[float] = []
_ORDER_RATE_LIMIT = 8  # stay under 10/sec with safety margin


def _enforce_order_rate_limit():
    """Block if we're approaching 10 orders/second (SEBI limit)."""
    now = time.time()
    while _order_timestamps and now - _order_timestamps[0] > 1.0:
        _order_timestamps.pop(0)
    if len(_order_timestamps) >= _ORDER_RATE_LIMIT:
        sleep_time = 1.0 - (now - _order_timestamps[0])
        if sleep_time > 0:
            logger.info(f"[RateLimit] Throttling order — sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
    _order_timestamps.append(time.time())


def _place_order_with_tick_retry(order_data: dict, max_retries: int = 2) -> dict:
    """
    Place order with retry on tick-size rejection.
    """
    import re

    last_response = {}
    for attempt in range(max_retries + 1):
        _enforce_order_rate_limit()
        response = _api_post("/api/oms/place-order", order_data)

        order_id = str(
            response.get("orderId")
            or response.get("data", {}).get("orderId")
            or response.get("id", "")
        )

        if order_id and order_id != "None":
            return {"s": "ok", "id": order_id}

        msg = str(response.get("message", response.get("error", "")))
        last_response = response

        # Retry on tick size error
        if "tick" in msg.lower() and attempt < max_retries:
            tick_match = re.search(r'tick\s*(?:size)?\s*(\d+\.?\d*)', msg, re.IGNORECASE)
            if tick_match:
                tick = float(tick_match.group(1))
                logger.info(f"Tick correction (attempt {attempt+1}): tick={tick}")
                if order_data.get("trigPrice", 0) > 0:
                    order_data["trigPrice"] = _round_to_tick(order_data["trigPrice"], tick)
                if order_data.get("limitPrice", 0) > 0:
                    order_data["limitPrice"] = _round_to_tick(order_data["limitPrice"], tick)
                continue

        return response

    return last_response


def format_broker_symbol(nse_symbol: str) -> str:
    """
    Convert NSE symbol to TradeJini CubePlus symId format.

    CubePlus format: EQT_{SYMBOL}_EQ_NSE (for equities)
    Example: RELIANCE → EQT_RELIANCE_EQ_NSE
    """
    nse_symbol = nse_symbol.replace(".NS", "")
    # Already in CubePlus format
    if nse_symbol.startswith("EQT_") or nse_symbol.startswith("FUTSTK_") or nse_symbol.startswith("OPTSTK_"):
        return nse_symbol
    # Strip old format if present
    nse_symbol = nse_symbol.replace("NSE:", "").replace("-EQ", "")
    return f"EQT_{nse_symbol}_EQ_NSE"


def nse_from_broker(broker_symbol: str) -> str:
    """Convert TradeJini symId back to plain NSE symbol.
    EQT_RELIANCE_EQ_NSE → RELIANCE
    """
    if broker_symbol.startswith("EQT_") and broker_symbol.endswith("_EQ_NSE"):
        return broker_symbol[4:-7]  # Strip EQT_ prefix and _EQ_NSE suffix
    # Fallback
    parts = broker_symbol.rsplit("_", 1)
    return parts[0] if parts else broker_symbol


# Alias for backward compatibility with format_fyers_symbol references
format_fyers_symbol = format_broker_symbol
nse_from_fyers = nse_from_broker
