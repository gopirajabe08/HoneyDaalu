"""
Fyers API integration service.
Handles authentication, order placement, positions, and live market data.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from fyers_apiv3 import fyersModel

load_dotenv()
logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────

FYERS_APP_ID = os.getenv("FYERS_APP_ID", "")
FYERS_SECRET_KEY = os.getenv("FYERS_SECRET_KEY", "")
FYERS_REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI", "http://localhost:8001/api/fyers/callback")

TOKEN_FILE = Path(__file__).parent.parent / ".fyers_token"

# ── Token persistence ─────────────────────────────────────────────────────

_access_token: Optional[str] = None
_fyers_instance: Optional[fyersModel.FyersModel] = None


def _save_token(token: str):
    TOKEN_FILE.write_text(token)


def _load_saved_token() -> Optional[str]:
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text().strip()
        return token if token else None
    return None


def _clear_token():
    global _access_token, _fyers_instance
    _access_token = None
    _fyers_instance = None
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()


# ── Authentication ─────────────────────────────────────────────────────────


def is_configured() -> bool:
    """Check if Fyers API credentials are configured."""
    return bool(FYERS_APP_ID) and bool(FYERS_SECRET_KEY)


def get_auth_url() -> Optional[str]:
    """Generate the Fyers OAuth2 login URL."""
    if not is_configured():
        return None

    session = fyersModel.SessionModel(
        client_id=FYERS_APP_ID,
        secret_key=FYERS_SECRET_KEY,
        redirect_uri=FYERS_REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code",
    )
    return session.generate_authcode()


def generate_token(auth_code: str) -> dict:
    """Exchange auth code for access token."""
    if not is_configured():
        return {"error": "Fyers API credentials not configured"}

    try:
        session = fyersModel.SessionModel(
            client_id=FYERS_APP_ID,
            secret_key=FYERS_SECRET_KEY,
            redirect_uri=FYERS_REDIRECT_URI,
            response_type="code",
            grant_type="authorization_code",
        )
        session.set_token(auth_code)
        response = session.generate_token()

        if response.get("s") == "ok" or "access_token" in response:
            token = response["access_token"]
            _set_token(token)
            return {"status": "ok", "message": "Authenticated successfully"}
        else:
            return {"error": response.get("message", "Token generation failed")}
    except Exception as e:
        return {"error": str(e)}


def _set_token(token: str):
    global _access_token, _fyers_instance
    _access_token = token
    _save_token(token)
    _fyers_instance = fyersModel.FyersModel(
        client_id=FYERS_APP_ID,
        token=token,
        is_async=False,
        log_path="",
    )


def get_fyers() -> Optional[fyersModel.FyersModel]:
    """Get authenticated Fyers instance."""
    global _fyers_instance, _access_token

    if _fyers_instance is not None:
        return _fyers_instance

    # Try loading saved token
    saved = _load_saved_token()
    if saved:
        _set_token(saved)
        return _fyers_instance

    return None


def is_authenticated() -> bool:
    """Check if we have a valid Fyers session."""
    fyers = get_fyers()
    if fyers is None:
        return False
    try:
        profile = fyers.get_profile()
        return profile.get("s") == "ok"
    except Exception:
        _clear_token()
        return False


def logout():
    """Clear Fyers session."""
    _clear_token()
    return {"status": "ok", "message": "Logged out"}


def headless_login() -> dict:
    """
    Fully automated Fyers login using TOTP — zero manual interaction.
    Requires FYERS_FY_ID, FYERS_PIN, FYERS_TOTP_SECRET in .env
    """
    import hashlib
    import requests as req
    import pyotp
    from urllib.parse import urlparse, parse_qs

    fy_id = os.getenv("FYERS_FY_ID", "")
    pin = os.getenv("FYERS_PIN", "")
    totp_secret = os.getenv("FYERS_TOTP_SECRET", "")

    if not all([fy_id, pin, totp_secret]):
        return {"error": "FYERS_FY_ID, FYERS_PIN, FYERS_TOTP_SECRET required in .env for auto-login"}

    if not is_configured():
        return {"error": "FYERS_APP_ID and FYERS_SECRET_KEY not configured"}

    try:
        # Step 1: Initiate login
        r1 = req.post(
            "https://api-t2.fyers.in/vagator/v2/send_login_otp",
            json={"fy_id": fy_id, "app_id": "2"},
        )
        if r1.status_code != 200:
            return {"error": f"Login initiation failed: {r1.text}"}
        request_key = r1.json().get("request_key")
        if not request_key:
            return {"error": f"No request_key received: {r1.json()}"}

        # Step 2: Verify TOTP
        totp = pyotp.TOTP(totp_secret).now()
        r2 = req.post(
            "https://api-t2.fyers.in/vagator/v2/verify_otp",
            json={"request_key": request_key, "otp": totp},
        )
        if r2.status_code != 200:
            return {"error": f"TOTP verification failed: {r2.text}"}
        request_key = r2.json().get("request_key")
        if not request_key:
            return {"error": f"TOTP rejected: {r2.json()}"}

        # Step 3: Verify PIN (raw string, not hashed)
        r3 = req.post(
            "https://api-t2.fyers.in/vagator/v2/verify_pin",
            json={"request_key": request_key, "identity_type": "pin", "identifier": str(pin)},
        )
        if r3.status_code != 200:
            return {"error": f"PIN verification failed: {r3.text}"}
        access_token = r3.json().get("data", {}).get("access_token")
        if not access_token:
            return {"error": f"No access_token from PIN step: {r3.json()}"}

        # Step 4: Exchange for auth_code (app_id without -100 suffix)
        app_id_short = FYERS_APP_ID.split("-")[0] if "-" in FYERS_APP_ID else FYERS_APP_ID
        r4 = req.post(
            "https://api-t1.fyers.in/api/v3/token",
            json={
                "fyers_id": fy_id,
                "app_id": app_id_short,
                "redirect_uri": FYERS_REDIRECT_URI,
                "appType": "100",
                "code_challenge": "",
                "state": "abcdefg",
                "scope": "",
                "nonce": "",
                "response_type": "code",
                "create_cookie": True,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        url_str = r4.json().get("Url", "")
        if not url_str:
            return {"error": f"No auth URL in response: {r4.json()}"}
        auth_code = parse_qs(urlparse(url_str).query).get("auth_code", [None])[0]
        if not auth_code:
            return {"error": f"No auth_code in redirect URL: {url_str}"}

        # Step 5: Exchange auth_code for final access token
        return generate_token(auth_code)

    except Exception as e:
        logger.error(f"Headless login failed: {e}")
        return {"error": f"Headless login failed: {str(e)}"}


# ── Profile & Funds ────────────────────────────────────────────────────────


def get_profile() -> dict:
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}
    try:
        return fyers.get_profile()
    except Exception as e:
        return {"error": str(e)}


def get_funds() -> dict:
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}
    try:
        return fyers.funds()
    except Exception as e:
        return {"error": str(e)}


# ── Segment Check ─────────────────────────────────────────────────────────

def is_nfo_enabled() -> bool:
    """Check if NFO (F&O) segment is enabled on the Fyers account.

    Detection methods (in order):
    1. Try getting a quote for a NIFTY option — if data returns, NFO is active.
    2. Check orderbook for NFO rejection messages — definitive NO.
    3. Check orderbook for any FILLED NFO order — definitive YES.
    """
    fyers = get_fyers()
    if fyers is None:
        return False

    # Method 1: Try getting a NIFTY option quote (fastest proof)
    try:
        from services.options_client import get_nearest_expiry, get_atm_strike
        expiry_str, _ = get_nearest_expiry("NIFTY", "weekly")
        # Use a round ATM strike (estimate from NIFTY ~23000-24000 range)
        test_symbol = f"NSE:NIFTY{expiry_str}23500CE"
        res = fyers.quotes(data={"symbols": test_symbol})
        quotes = res.get("d", [])
        for q in quotes:
            v = q.get("v", {})
            if isinstance(v, dict) and (v.get("lp", 0) > 0 or v.get("close_price", 0) > 0):
                return True  # Got a valid option quote — NFO is active
    except Exception:
        pass

    # Method 2: Check orderbook for NFO rejection or filled orders
    try:
        orders = fyers.orderbook()
        order_book = orders.get("orderBook", [])

        for o in order_book:
            msg = (o.get("message") or "").lower()
            if "nfo not enabled" in msg or "exchange nfo not enabled" in msg:
                return False

        for o in order_book:
            symbol = o.get("symbol", "")
            if o.get("status") == 2 and ("NIFTY" in symbol or "BANKNIFTY" in symbol) and ("CE" in symbol or "PE" in symbol):
                return True
    except Exception:
        pass

    # No definitive answer — default False (safe)
    return False


# ── Orders ─────────────────────────────────────────────────────────────────


def place_order(
    symbol: str,
    qty: int,
    side: int,  # 1=Buy, -1=Sell
    order_type: int = 2,  # 1=Limit, 2=Market, 3=SL, 4=SL-M
    product_type: str = "INTRADAY",
    limit_price: float = 0,
    stop_price: float = 0,
) -> dict:
    """
    Place an order on Fyers.

    Args:
        symbol: NSE symbol (e.g., "RELIANCE"). Auto-formatted to "NSE:RELIANCE-EQ".
        qty: Quantity
        side: 1 for Buy, -1 for Sell
        order_type: 1=Limit, 2=Market, 3=SL, 4=SL-M
        product_type: "INTRADAY" or "CNC" or "MARGIN"
        limit_price: Limit price (for Limit/SL orders)
        stop_price: Stop/trigger price (for SL/SL-M orders)
    """
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}

    # Format symbol for Fyers: NSE:SYMBOL-EQ
    fyers_symbol = format_fyers_symbol(symbol)

    # Fyers requires limitPrice > 0 for SL-M (type 4) orders, and:
    #   SELL SL-M: limitPrice < stopPrice
    #   BUY SL-M:  limitPrice > stopPrice
    # Since SL-M fills at market once triggered, limitPrice is just for validation.
    # Use a small offset and round to tick size (0.05) to satisfy Fyers.
    effective_limit = limit_price
    if order_type == 4 and effective_limit == 0 and stop_price > 0:
        if side == -1:  # SELL SL-M: limit below trigger
            effective_limit = _round_to_tick(stop_price - max(stop_price * 0.02, 1))
        else:  # BUY SL-M: limit above trigger
            effective_limit = _round_to_tick(stop_price + max(stop_price * 0.02, 1))

    data = {
        "symbol": fyers_symbol,
        "qty": qty,
        "type": order_type,
        "side": side,
        "productType": product_type,
        "limitPrice": effective_limit,
        "stopPrice": stop_price,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
    }

    return _place_order_with_tick_retry(fyers, data)


def place_bracket_order(
    symbol: str,
    qty: int,
    side: int,
    limit_price: float,
    stop_loss: float,
    target: float,
) -> dict:
    """
    Place a bracket order (entry + SL + target).
    Tries BO product type first. If BO fails (not supported by Fyers for
    equity), falls back to INTRADAY market entry + separate SL-M order.

    Returns dict with:
      - order_mode: "BO" or "INTRADAY_SL"
      - id / entry_order_id: entry order ID
      - sl_order_id: stop-loss order ID (only for INTRADAY_SL mode)
    """
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}

    fyers_symbol = format_fyers_symbol(symbol)

    # Always use INTRADAY + SL-M (not Bracket Order)
    # BO splits exits into multiple partial fills = extra ₹20/fill charges
    # INTRADAY+SL = 1 entry + 1 SL = 2 orders max = ₹40 vs ₹100+ for BO
    return _place_intraday_with_sl(fyers, fyers_symbol, qty, side, stop_loss, target)


def _place_intraday_with_sl(
    fyers,
    fyers_symbol: str,
    qty: int,
    side: int,
    stop_loss: float,
    target: float,
) -> dict:
    """
    Fallback: place INTRADAY market entry, then a SL-M protective order.
    Returns combined result with both order IDs.
    """
    # Step 1: Market entry order
    entry_data = {
        "symbol": fyers_symbol,
        "qty": qty,
        "type": 2,  # Market order
        "side": side,
        "productType": "INTRADAY",
        "limitPrice": 0,
        "stopPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
    }

    try:
        entry_resp = fyers.place_order(data=entry_data)
    except Exception as e:
        return {"error": f"Entry order failed: {e}"}

    if entry_resp.get("s") != "ok" and "id" not in entry_resp:
        return {"error": f"Entry order rejected: {entry_resp.get('message', str(entry_resp))}"}

    entry_order_id = entry_resp.get("id", entry_resp.get("order_id", ""))
    logger.info(f"INTRADAY entry placed: {fyers_symbol} (ID: {entry_order_id})")

    # Step 2: SL-M (stop loss market) protective order — opposite side
    sl_side = -1 if side == 1 else 1  # opposite direction
    # Fyers SL-M: SELL needs limitPrice < stopPrice, BUY needs limitPrice > stopPrice
    if sl_side == -1:
        sl_limit = _round_to_tick(stop_loss - max(stop_loss * 0.02, 1))
    else:
        sl_limit = _round_to_tick(stop_loss + max(stop_loss * 0.02, 1))
    sl_data = {
        "symbol": fyers_symbol,
        "qty": qty,
        "type": 4,  # SL-M (stop loss market)
        "side": sl_side,
        "productType": "INTRADAY",
        "limitPrice": sl_limit,
        "stopPrice": round(stop_loss, 2),
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
    }

    sl_order_id = ""
    sl_resp = _place_order_with_tick_retry(fyers, sl_data)
    if sl_resp.get("s") == "ok" or "id" in sl_resp:
        sl_order_id = sl_resp.get("id", sl_resp.get("order_id", ""))
        logger.info(f"SL-M order placed: {fyers_symbol} SL@{sl_data['stopPrice']} (ID: {sl_order_id})")
    else:
        logger.error(f"SL-M order FAILED for {fyers_symbol}: {sl_resp.get('message', sl_resp.get('error', str(sl_resp)))}")

    # Target: NO order on Fyers — auto-trader monitors LTP and exits at market
    # Benefits: saves ₹20/trade brokerage, no orphaned target orders, trailing SL is smarter
    # Safety: SL-M on Fyers protects downside, trailing SL locks profits, Fyers auto-square at 3:25 PM

    return {
        "s": "ok",
        "id": entry_order_id,
        "order_mode": "INTRADAY_SL",
        "entry_order_id": entry_order_id,
        "sl_order_id": sl_order_id,
        "target_order_id": "",  # No target order — monitored by auto-trader
        "target_price": round(target, 2),
    }


def modify_order(order_id: str, **kwargs) -> dict:
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}
    try:
        data = {"id": order_id, **kwargs}
        return fyers.modify_order(data=data)
    except Exception as e:
        return {"error": str(e)}


def cancel_order(order_id: str) -> dict:
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}
    try:
        return fyers.cancel_order(data={"id": order_id})
    except Exception as e:
        return {"error": str(e)}


# ── Order Book & Positions ─────────────────────────────────────────────────


def get_orderbook() -> dict:
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}
    try:
        return fyers.orderbook()
    except Exception as e:
        return {"error": str(e)}


def get_positions() -> dict:
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}
    try:
        return fyers.positions()
    except Exception as e:
        return {"error": str(e)}


def get_holdings() -> dict:
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}
    try:
        return fyers.holdings()
    except Exception as e:
        return {"error": str(e)}


def get_tradebook() -> dict:
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}
    try:
        return fyers.tradebook()
    except Exception as e:
        return {"error": str(e)}


# ── Market Data ────────────────────────────────────────────────────────────


def get_quotes(symbols: list[str]) -> dict:
    """Get live quotes for symbols."""
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}

    fyers_symbols = [format_fyers_symbol(s) for s in symbols]
    try:
        return fyers.quotes(data={"symbols": ",".join(fyers_symbols)})
    except Exception as e:
        return {"error": str(e)}


def get_market_depth(symbol: str) -> dict:
    """Get market depth (Level 2 data) for a symbol."""
    fyers = get_fyers()
    if fyers is None:
        return {"error": "Not authenticated"}
    try:
        return fyers.depth(data={"symbol": format_fyers_symbol(symbol), "ohlcv_flag": 1})
    except Exception as e:
        return {"error": str(e)}


# ── Helpers ────────────────────────────────────────────────────────────────


def _round_to_tick(price: float, tick: float = 0.05) -> float:
    """Round price down to nearest tick size."""
    import math
    return round(math.floor(price / tick) * tick, 2)


def _place_order_with_tick_retry(fyers, data: dict, max_retries: int = 2) -> dict:
    """
    Place an order via Fyers, retrying with corrected tick-size rounding
    if the order is rejected due to tick-size validation.

    Fyers stocks have varying tick sizes (0.05, 0.10, 0.50) and the API
    returns the required tick size in the error message.
    """
    import re

    last_response = {}
    for attempt in range(max_retries + 1):
        try:
            response = fyers.place_order(data=data)
            if response.get("s") == "ok" or "id" in response:
                return response

            msg = response.get("message", "")
            code = response.get("code", 0)
            last_response = response

            # Categorise common rejection reasons for better diagnostics
            msg_lower = msg.lower()
            if "insufficient" in msg_lower or "margin" in msg_lower:
                logger.warning(f"[Fyers] Order rejected — insufficient margin: {msg}")
            elif "circuit" in msg_lower or "frozen" in msg_lower:
                logger.warning(f"[Fyers] Order rejected — stock at circuit/frozen: {msg}")
            elif "banned" in msg_lower or "ban period" in msg_lower:
                logger.warning(f"[Fyers] Order rejected — SEBI F&O ban: {msg}")
            elif "tick size" not in msg_lower:
                # Log non-tick-size rejections (tick-size is retried below)
                logger.warning(f"[Fyers] Order rejected: {msg} (code: {code})")

            # Parse tick size from error: "StopPrice not a multiple of tick size 0.1000"
            if "tick size" in msg.lower() and attempt < max_retries:
                tick_match = re.search(r'tick size (\d+\.?\d*)', msg)
                if tick_match:
                    tick = float(tick_match.group(1))
                    logger.info(f"Tick size correction (attempt {attempt+1}): tick={tick} for {data.get('symbol', '')}")
                    if data.get("stopPrice", 0) > 0:
                        data["stopPrice"] = _round_to_tick(data["stopPrice"], tick)
                    if data.get("limitPrice", 0) > 0:
                        data["limitPrice"] = _round_to_tick(data["limitPrice"], tick)
                    continue

            return response
        except Exception as e:
            return {"error": str(e)}

    return last_response


def format_fyers_symbol(nse_symbol: str) -> str:
    """Convert NSE symbol to Fyers format: NSE:SYMBOL-EQ"""
    nse_symbol = nse_symbol.replace(".NS", "")
    if nse_symbol.startswith("NSE:"):
        return nse_symbol
    return f"NSE:{nse_symbol}-EQ"


def nse_from_fyers(fyers_symbol: str) -> str:
    """Convert Fyers symbol back to plain NSE symbol."""
    return fyers_symbol.replace("NSE:", "").replace("-EQ", "")
