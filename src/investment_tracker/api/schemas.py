"""Pydantic schemas for API payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from investment_tracker.data.enums import AssetType, EventType, RecordStatus, TransactionDirection


class TransactionCreateRequest(BaseModel):
    user_id: int = Field(default=1, ge=1)
    asset_type: AssetType
    asset_code: str
    asset_name: Optional[str] = None
    direction: TransactionDirection
    quantity: float
    unit_price: float
    trade_currency: str
    trade_time: datetime
    exchange_rate_to_cny: Optional[float] = None
    total_cost_cny: Optional[float] = None
    source: str = "manual"
    raw_text: Optional[str] = None
    notes: Optional[str] = None


class TransactionHistoryUpdateRequest(BaseModel):
    trade_time: Optional[datetime] = None
    notes: Optional[str] = None


class AdviceRequest(BaseModel):
    user_id: int = Field(default=1, ge=1)
    risk_preference: str = "balanced"


class ExchangeRateRefreshRequest(BaseModel):
    currencies: List[str]


class ScreenshotUploadItem(BaseModel):
    filename: str
    content_base64: str
    language: str = "zh-CN"
    provider: Optional[str] = None


class ScreenshotUploadRequest(BaseModel):
    files: List[ScreenshotUploadItem]


class AssetCreateRequest(BaseModel):
    asset_type: AssetType
    asset_code: str
    asset_name: Optional[str] = None
    currency: str
    issuer: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class CashLedgerEntryRequest(BaseModel):
    currency: str
    amount_delta: float
    rmb_amount: Optional[float] = None
    rmb_basis: Optional[float] = None
    fx_rate_to_cny: Optional[float] = None
    is_external_flow: bool = False
    zero_basis: bool = False
    unknown_basis: bool = False
    basis_status: Optional[str] = None
    description: Optional[str] = None


class AttributionSummary(BaseModel):
    total_lots_used: int = 0
    oldest_lot_date: Optional[datetime] = None
    newest_lot_date: Optional[datetime] = None
    gap_count: int = 0


class FundingSourceDetail(BaseModel):
    lot_id: int
    source_event_id: Optional[int] = None
    source_type: str
    source_date: Optional[datetime] = None
    source_currency: str
    native_amount_allocated: float
    rmb_basis_allocated: float
    effective_rate: Optional[float] = None
    lineage_depth: int = 0


class PurchaseAttribution(BaseModel):
    purchase_event_id: int
    purchase_date: datetime
    purchase_amount: float
    funding_sources: List[FundingSourceDetail]


class AttributionDetailResponse(BaseModel):
    asset_id: int
    asset_code: str
    attribution_status: str
    total_attributed_cost_cny: Optional[float] = None
    attributions: List[PurchaseAttribution]
    gaps: List[Dict[str, Any]]


class PositionResponse(BaseModel):
    asset_id: Optional[int] = None
    asset_code: str
    asset_type: str
    currency: str
    cost_basis_cny: Optional[float] = None
    legacy_cost_basis_cny: Optional[float] = None
    attributed_cost_basis_cny: Optional[float] = None
    attribution_status: Optional[str] = None
    attribution_summary: Optional[AttributionSummary] = None
    investment_pnl_cny: Optional[float] = None
    fx_pnl_cny: Optional[float] = None


class GapDetail(BaseModel):
    asset_id: Optional[int] = None
    asset_code: Optional[str] = None
    event_id: Optional[int] = None
    gap_type: str
    currency: str
    shortfall_amount: Optional[float] = None
    event_date: Optional[str] = None
    suggestions: List[Dict[str, Any]] = Field(default_factory=list)


class BasisMissingLot(BaseModel):
    lot_id: int
    currency: str
    amount: float
    source_event_id: Optional[int] = None
    source_date: Optional[str] = None
    suggestion: str


class AttributionDiagnostics(BaseModel):
    total_products: int
    complete_attribution: int
    incomplete_attribution: int
    basis_missing: int
    not_applicable: int
    total_gaps: int
    gap_details: List[GapDetail]
    basis_missing_lots: List[BasisMissingLot]


class AuditResponse(BaseModel):
    audit_id: str
    audit_time: str
    user_id: int
    currencies_audited: List[str]
    summary: Dict[str, Any]
    attribution_diagnostics: Optional[AttributionDiagnostics] = None


class AssetLedgerEntryRequest(BaseModel):
    asset_id: Optional[int] = None
    asset: Optional[AssetCreateRequest] = None
    quantity_delta: float
    cash_currency: str
    cash_amount: Optional[float] = None
    unit_price: Optional[float] = None
    fx_rate_to_cny: Optional[float] = None
    description: Optional[str] = None


class PortfolioEventCreateRequest(BaseModel):
    user_id: int = Field(default=1, ge=1)
    event_type: EventType
    event_time: datetime
    source: str = "manual"
    status: RecordStatus = RecordStatus.CONFIRMED
    raw_text: Optional[str] = None
    notes: Optional[str] = None
    cash_entries: List[CashLedgerEntryRequest] = Field(default_factory=list)
    asset_entries: List[AssetLedgerEntryRequest] = Field(default_factory=list)


class ValuationCreateRequest(BaseModel):
    user_id: int = Field(default=1, ge=1)
    asset_id: Optional[int] = None
    asset: Optional[AssetCreateRequest] = None
    valuation_time: datetime
    quantity: float
    price: Optional[float] = None
    market_value: float
    currency: Optional[str] = None
    fx_rate_to_cny: Optional[float] = None
    source: str = "manual"
    is_estimated: bool = False


class WealthPositionHoldingRequest(BaseModel):
    asset_code: str
    asset_name: str
    currency: str
    market_value: float
    holding_income: Optional[float] = None
    income_as_of: Optional[str] = None
    redeemable_frequency: Optional[str] = None


class WealthPositionSnapshotRequest(BaseModel):
    user_id: int = Field(default=1, ge=1)
    valuation_time: datetime
    source: str = "manual"
    raw_text: Optional[str] = None
    holdings: List[WealthPositionHoldingRequest]
