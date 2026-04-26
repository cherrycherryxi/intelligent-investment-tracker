"""Shared enum types for the persistence layer."""

from __future__ import annotations

from enum import Enum


class AssetType(str, Enum):
    FOREX = "FOREX"
    BOND = "BOND"


class TransactionDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class RateSourceType(str, Enum):
    PRIMARY = "PRIMARY"
    FALLBACK = "FALLBACK"
    MANUAL = "MANUAL"


class AdviceAction(str, Enum):
    HOLD = "HOLD"
    BUY = "BUY"
    SELL = "SELL"


class RecordStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"

