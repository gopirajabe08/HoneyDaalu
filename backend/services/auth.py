"""
Authentication service for IntraTrading web portal.

Email OTP authentication via Telegram delivery + JWT tokens.
Single-user system: only AUTH_EMAIL from .env can log in.

Security:
  - 6-digit numeric OTP with 5-minute expiry
  - Max 3 OTP requests per 10 minutes (rate limited)
  - JWT tokens with 24-hour expiry
  - Only whitelisted email allowed
"""

import os
import time
import random
import logging
import threading
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────
AUTH_EMAIL = os.getenv("AUTH_EMAIL", "").strip().lower()
JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "")

if not JWT_SECRET:
    logger.warning("[Auth] AUTH_JWT_SECRET not set in .env — generating random secret (will invalidate on restart)")
    JWT_SECRET = os.urandom(32).hex()

# ── OTP Storage (in-memory) ──────────────────────────────────────────
# Structure: { email: { "otp": "123456", "expires": timestamp, "attempts": 0 } }
_otp_store: dict = {}
_otp_lock = threading.Lock()

# Rate limiting: { email: [timestamp, timestamp, ...] }
_rate_store: dict = {}
_rate_lock = threading.Lock()

OTP_EXPIRY_SECONDS = 300        # 5 minutes
OTP_LENGTH = 6
MAX_OTP_REQUESTS = 3
RATE_WINDOW_SECONDS = 600       # 10 minutes
MAX_VERIFY_ATTEMPTS = 5         # Max wrong OTP attempts before lockout
JWT_EXPIRY_HOURS = 24


def _generate_otp() -> str:
    """Generate a cryptographically random 6-digit OTP."""
    return str(random.SystemRandom().randint(100000, 999999))


def _is_rate_limited(email: str) -> bool:
    """Check if email has exceeded max OTP requests in the rate window."""
    now = time.time()
    with _rate_lock:
        if email not in _rate_store:
            _rate_store[email] = []

        # Purge old timestamps
        cutoff = now - RATE_WINDOW_SECONDS
        _rate_store[email] = [ts for ts in _rate_store[email] if ts > cutoff]

        if len(_rate_store[email]) >= MAX_OTP_REQUESTS:
            return True

        _rate_store[email].append(now)
        return False


def _is_email_allowed(email: str) -> bool:
    """Check if this email is the configured AUTH_EMAIL."""
    if not AUTH_EMAIL:
        logger.error("[Auth] AUTH_EMAIL not configured in .env")
        return False
    return email.strip().lower() == AUTH_EMAIL


def request_otp(email: str) -> dict:
    """
    Generate OTP and send via Telegram.
    Returns {"status": "otp_sent"} or {"error": "..."}.
    """
    email = email.strip().lower()

    # Validate email is allowed
    if not _is_email_allowed(email):
        # Don't reveal whether the email exists or not (security)
        logger.warning(f"[Auth] OTP request for unauthorized email: {email}")
        # Still return success to prevent email enumeration
        return {"status": "otp_sent"}

    # Rate limit check
    if _is_rate_limited(email):
        remaining = RATE_WINDOW_SECONDS
        with _rate_lock:
            if email in _rate_store and _rate_store[email]:
                oldest = _rate_store[email][0]
                remaining = int(oldest + RATE_WINDOW_SECONDS - time.time())
        return {"error": f"Too many OTP requests. Try again in {remaining} seconds."}

    # Generate OTP
    otp = _generate_otp()
    expires = time.time() + OTP_EXPIRY_SECONDS

    with _otp_lock:
        _otp_store[email] = {
            "otp": otp,
            "expires": expires,
            "attempts": 0,
        }

    # Send via Telegram
    try:
        from services import telegram_notify
        telegram_notify.send(
            f"🔐 <b>IntraTrading Login OTP</b>\n\n"
            f"Your OTP: <code>{otp}</code>\n\n"
            f"Valid for 5 minutes.\n"
            f"If you didn't request this, ignore it."
        )
        logger.info(f"[Auth] OTP sent to Telegram for {email}")
    except Exception as e:
        logger.error(f"[Auth] Failed to send OTP via Telegram: {e}")
        return {"error": "Failed to send OTP. Check Telegram configuration."}

    return {"status": "otp_sent"}


def verify_otp(email: str, otp: str) -> dict:
    """
    Verify OTP and return JWT token if valid.
    Returns {"token": "jwt..."} or {"error": "..."}.
    """
    email = email.strip().lower()

    # Check email is allowed
    if not _is_email_allowed(email):
        return {"error": "Invalid credentials"}

    with _otp_lock:
        stored = _otp_store.get(email)

        if not stored:
            return {"error": "No OTP requested. Please request a new OTP."}

        # Check expiry
        if time.time() > stored["expires"]:
            del _otp_store[email]
            return {"error": "OTP expired. Please request a new one."}

        # Check attempts
        if stored["attempts"] >= MAX_VERIFY_ATTEMPTS:
            del _otp_store[email]
            return {"error": "Too many failed attempts. Request a new OTP."}

        # Verify OTP
        if stored["otp"] != otp.strip():
            stored["attempts"] += 1
            remaining = MAX_VERIFY_ATTEMPTS - stored["attempts"]
            return {"error": f"Invalid OTP. {remaining} attempts remaining."}

        # OTP valid — clean up
        del _otp_store[email]

    # Generate JWT
    token = _create_jwt(email)
    logger.info(f"[Auth] Login successful for {email}")

    # Notify via Telegram
    try:
        from services import telegram_notify
        telegram_notify.send(
            f"✅ <b>Login Successful</b>\n\n"
            f"IntraTrading portal accessed.\n"
            f"Session valid for 24 hours."
        )
    except Exception:
        pass

    return {"token": token, "email": email}


def _create_jwt(email: str) -> str:
    """Create a JWT token with 24-hour expiry."""
    import jwt

    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
        "iss": "intratrading",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(token: str) -> dict:
    """
    Verify a JWT token.
    Returns {"valid": True, "email": "..."} or {"valid": False, "error": "..."}.
    """
    import jwt

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], issuer="intratrading")
        email = payload.get("sub", "")

        if not _is_email_allowed(email):
            return {"valid": False, "error": "Unauthorized email"}

        return {"valid": True, "email": email}

    except jwt.ExpiredSignatureError:
        return {"valid": False, "error": "Token expired"}
    except jwt.InvalidTokenError as e:
        return {"valid": False, "error": f"Invalid token: {e}"}
