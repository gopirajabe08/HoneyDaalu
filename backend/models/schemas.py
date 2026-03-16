"""Pydantic schemas for API request/response models."""

from pydantic import BaseModel
from typing import Optional


class ScanRequest(BaseModel):
    strategy: str
    timeframe: str
    capital: float = 100000


class Signal(BaseModel):
    symbol: str
    name: str
    signal_type: str          # "BUY" or "SELL"
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: Optional[float] = None
    risk: float               # entry - SL
    reward: float             # T1 - entry
    risk_reward_ratio: str
    quantity: int             # based on capital & risk
    capital_required: float
    current_price: float
    strategy: str
    timeframe: str


class StrategyInfo(BaseModel):
    id: str
    name: str
    description: str
    category: str
    timeframes: list[str]
    indicators: list[str]
    long_setup: str
    short_setup: Optional[str] = None
    exit_rules: str
    stop_loss_rules: str


class ScanResult(BaseModel):
    strategy: str
    timeframe: str
    capital: float
    signals: list[Signal]
    stocks_scanned: int
    stocks_eligible: int
    scan_time_seconds: float
