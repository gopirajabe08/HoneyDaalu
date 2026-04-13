"""
Telegram notification service for LuckyNavi.

3-Tier notification system:
  TIER 1 — ALERT: Money at risk. Always send. (flash crash, disconnect, margin)
  TIER 2 — TRADE: Money in/out. Per event. (entry, exit, BTST)
  TIER 3 — SUMMARY: Daily scorecard. 3 per day. (morning, half-day, day-end)

Rate-limited to 30 msgs per 10 min to prevent spam in crash loops.
"""
import os
import logging
import threading
import time as _time_mod
from urllib.request import urlopen, Request
from urllib.parse import quote
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

_enabled = bool(BOT_TOKEN) and bool(CHAT_ID)

# Rate limiting: max 30 messages per 10-minute window
_MAX_MESSAGES_PER_WINDOW = 30
_WINDOW_SECONDS = 600
_send_timestamps: list[float] = []
_rate_lock = threading.Lock()

# Track broker disconnect time to suppress brief hiccups (<5 min)
_broker_disconnect_time: float = 0


def _is_rate_limited() -> bool:
    now = _time_mod.time()
    with _rate_lock:
        cutoff = now - _WINDOW_SECONDS
        while _send_timestamps and _send_timestamps[0] < cutoff:
            _send_timestamps.pop(0)
        if len(_send_timestamps) >= _MAX_MESSAGES_PER_WINDOW:
            return True
        _send_timestamps.append(now)
        return False


def _send_async(text: str):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = f"chat_id={CHAT_ID}&text={quote(text)}&parse_mode=HTML".encode()
        req = Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        urlopen(req, timeout=10)
    except Exception as e:
        logger.warning(f"[Telegram] Send failed: {e}")


def send(text: str):
    """Send a Telegram message (non-blocking). Rate-limited."""
    if not _enabled:
        return
    if _is_rate_limited():
        logger.warning("[Telegram] Rate limited — skipping message")
        return
    threading.Thread(target=_send_async, args=(text,), daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════
# TIER 3 — SUMMARY (3 per day: morning, half-day, day-end)
# ═══════════════════════════════════════════════════════════════════════

def morning_brief(capital: float, regime: str, vix: float, engines: list):
    """Morning brief — 1 message with everything you need to know."""
    engine_list = "\n".join(f"  • {e}" for e in engines)
    send(
        f"☀️ <b>Morning Brief</b>\n\n"
        f"Capital: ₹{capital:,.0f}\n"
        f"Regime: {regime} | VIX: {vix:.1f}\n\n"
        f"Engines:\n{engine_list}\n\n"
        f"Orders: 10:30 AM - 2:00 PM\n"
        f"Square-off: 3:15 PM\n"
        f"Auto-shutdown: 3:45 PM"
    )


def half_day_summary(total_pnl: float, open_count: int, closed_count: int, wins: int, losses: int):
    """1 PM half-day check-in."""
    emoji = "📈" if total_pnl >= 0 else "📉"
    send(
        f"{emoji} <b>Half-Day (1 PM)</b>\n\n"
        f"P&L: {'+'if total_pnl>=0 else ''}₹{total_pnl:.2f}\n"
        f"Open: {open_count} | Closed: {closed_count}\n"
        f"Win/Loss: {wins}W / {losses}L"
    )


def day_end(total_pnl: float, charges: float, net_pnl: float,
            trades: int, wins: int, losses: int, capital: float,
            btst_open: int = 0):
    """Day-end summary — final scorecard. Replaces squareoff_complete + day_summary + system_shutdown."""
    today = datetime.now(IST).strftime("%b %d")
    emoji = "🟢" if net_pnl >= 0 else "🔴"
    wr = round(wins * 100 / (wins + losses)) if (wins + losses) > 0 else 0

    btst_line = f"\nBTST overnight: {btst_open} position(s)" if btst_open > 0 else ""

    send(
        f"{emoji} <b>Day Complete — {today}</b>\n\n"
        f"Gross P&L: {'+'if total_pnl>=0 else ''}₹{total_pnl:.2f}\n"
        f"Charges: ₹{charges:.2f}\n"
        f"<b>Net P&L: {'+'if net_pnl>=0 else ''}₹{net_pnl:.2f}</b>\n\n"
        f"Trades: {trades} | Win rate: {wr}%\n"
        f"Capital: ₹{capital:,.0f}"
        f"{btst_line}\n\n"
        f"All intraday squared off. Server off. 🌙"
    )


# ═══════════════════════════════════════════════════════════════════════
# TIER 2 — TRADE (per event: money in / money out)
# ═══════════════════════════════════════════════════════════════════════

def trade_placed(symbol: str, side: str, qty: int, entry: float, sl: float, strategy: str, engine: str = "Equity"):
    """New trade entry."""
    emoji = "🟢" if side == "BUY" else "🔴"
    sl_pct = abs(entry - sl) / entry * 100 if entry > 0 else 0
    risk = abs(entry - sl) * qty
    send(
        f"{emoji} <b>{engine}: {side} {symbol}</b>\n\n"
        f"Entry: ₹{entry:.2f} | SL: ₹{sl:.2f} ({sl_pct:.1f}%)\n"
        f"Qty: {qty} | Risk: ₹{risk:.0f}\n"
        f"Strategy: {strategy}"
    )


def trade_closed(symbol: str, side: str, pnl: float, reason: str, engine: str = "Equity"):
    """Trade exit — P&L realized."""
    emoji = "✅" if pnl >= 0 else "❌"
    send(
        f"{emoji} <b>{engine} Exit: {symbol}</b>\n\n"
        f"P&L: {'+'if pnl>=0 else ''}₹{pnl:.2f}\n"
        f"Reason: {reason}"
    )


def btst_position(symbol: str, entry: float, qty: int, strategy: str):
    """BTST overnight hold — carries risk overnight."""
    send(
        f"🌙 <b>BTST: BUY {symbol}</b>\n\n"
        f"Entry: ₹{entry:.2f} | Qty: {qty}\n"
        f"Strategy: {strategy}\n"
        f"Exit: Tomorrow (+2%/-1.5%/2-day max)"
    )


def sl_breakeven(symbol: str, entry: float, new_sl: float):
    """SL moved to breakeven — trade is now risk-free. Only meaningful trail notification."""
    send(
        f"🔒 <b>Risk-Free: {symbol}</b>\n\n"
        f"SL moved to breakeven ₹{new_sl:.2f}\n"
        f"Entry was ₹{entry:.2f} — zero downside now"
    )


# ═══════════════════════════════════════════════════════════════════════
# TIER 1 — ALERT (money at risk, always send)
# ═══════════════════════════════════════════════════════════════════════

def flash_crash(symbol: str, loss_pct: float):
    """Emergency exit — position crashed >3%."""
    send(
        f"🚨 <b>FLASH CRASH: {symbol}</b>\n\n"
        f"Down {loss_pct:.1f}% — EMERGENCY EXIT\n"
        f"Position closed at market"
    )


def margin_warning(available: float):
    """Not enough margin — can't place orders or SL."""
    send(
        f"⚠️ <b>Margin Warning</b>\n\n"
        f"Available: ₹{available:,.0f}\n"
        f"Orders stopped until margin frees up"
    )


def broker_disconnected():
    """Broker connection lost — record time, send alert only if prolonged (>2 min)."""
    global _broker_disconnect_time
    _broker_disconnect_time = _time_mod.time()
    logger.warning("[Telegram] Broker disconnected — will alert if not reconnected in 2 min")


def broker_still_disconnected(minutes: int = 5):
    """Broker still down after multiple checks — now it's serious."""
    send(
        f"🔌 <b>Broker Down ({minutes}+ min)</b>\n\n"
        f"Connection lost. Retrying...\n"
        f"SL orders on exchange still active"
    )


def broker_reconnected():
    """Broker back — only notify if it was down >2 min."""
    global _broker_disconnect_time
    if _broker_disconnect_time > 0:
        down_seconds = _time_mod.time() - _broker_disconnect_time
        _broker_disconnect_time = 0
        if down_seconds >= 120:
            send(f"✅ <b>Broker Reconnected</b> (was down {int(down_seconds/60)} min)")




# ═══════════════════════════════════════════════════════════════════════
# DEPRECATED — kept for backward compatibility, maps to new functions
# ═══════════════════════════════════════════════════════════════════════

def system_started(engines: list, capital: float, regime: str, vix: float):
    """Deprecated — use morning_brief()."""
    morning_brief(capital, regime, vix, engines)


def squareoff_complete(total_pnl: float, trades: int, wins: int, losses: int):
    """Deprecated — merged into day_end(). Now a no-op."""
    pass  # Squareoff info is included in day_end summary


def day_summary(total_pnl: float, charges: float, net_pnl: float,
                trades: int, wins: int, losses: int, capital: float):
    """Deprecated — use day_end()."""
    day_end(total_pnl, charges, net_pnl, trades, wins, losses, capital)


def system_shutdown():
    """Deprecated — merged into day_end(). Now a no-op."""
    pass  # Shutdown info is included in day_end summary


def sl_trailed(symbol: str, old_sl: float, new_sl: float, profit_pct: float):
    """Deprecated — only breakeven trail matters. Silent for all other trails."""
    pass  # Caller should use sl_breakeven() for breakeven moves only
