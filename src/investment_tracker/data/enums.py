"""Shared enum types for the persistence layer."""

from __future__ import annotations

from enum import Enum


class AssetType(str, Enum):
    CASH = "CASH"
    FOREX = "FOREX"
    BOND = "BOND"
    FUND = "FUND"
    WEALTH_PRODUCT = "WEALTH_PRODUCT"


class TransactionDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class EventType(str, Enum):
    FX_BUY = "FX_BUY"
    FX_SELL = "FX_SELL"
    FX_SWAP = "FX_SWAP"
    BOND_BUY = "BOND_BUY"
    BOND_SELL = "BOND_SELL"
    BOND_REDEMPTION = "BOND_REDEMPTION"
    INTEREST_INCOME = "INTEREST_INCOME"
    FUND_BUY = "FUND_BUY"
    FUND_SELL = "FUND_SELL"
    FUND_DIVIDEND = "FUND_DIVIDEND"
    FUND_DIVIDEND_REINVEST = "FUND_DIVIDEND_REINVEST"
    WEALTH_BUY = "WEALTH_BUY"
    WEALTH_REDEEM = "WEALTH_REDEEM"
    WEALTH_INCOME = "WEALTH_INCOME"
    MANUAL_ADJUSTMENT = "MANUAL_ADJUSTMENT"


class CashFlowDirection(str, Enum):
    INFLOW = "INFLOW"
    OUTFLOW = "OUTFLOW"


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


class FundingSourceType(str, Enum):
    FX_BUY = "FX_BUY"
    FX_SWAP = "FX_SWAP"
    REDEMPTION = "REDEMPTION"
    DIVIDEND = "DIVIDEND"
    INTEREST = "INTEREST"
    MANUAL_ADJUSTMENT = "MANUAL_ADJUSTMENT"
    CARRYFORWARD = "CARRYFORWARD"


class LotStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    FULLY_CONSUMED = "FULLY_CONSUMED"
    BASIS_MISSING = "BASIS_MISSING"


class AttributionStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    BASIS_MISSING = "BASIS_MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GapType(str, Enum):
    UNATTRIBUTED_FUNDING = "UNATTRIBUTED_FUNDING"
    BASIS_MISSING = "BASIS_MISSING"
    POLICY_CONFLICT = "POLICY_CONFLICT"


class AllocationPolicy(str, Enum):
    FIFO = "FIFO"
    LIFO = "LIFO"
    WEIGHTED_AVERAGE = "WEIGHTED_AVERAGE"
