"""ORM models for the Day1 schema."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from investment_tracker.data.base import Base, TimestampMixin, utcnow
from investment_tracker.data.enums import (
    AdviceAction,
    AllocationPolicy,
    AssetType,
    AttributionStatus,
    EventType,
    FundingSourceType,
    GapType,
    LotStatus,
    RateSourceType,
    RecordStatus,
    TransactionDirection,
)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    risk_preference = Column(String(50), nullable=True)

    transactions = relationship("Transaction", back_populates="user")
    positions = relationship("Position", back_populates="user")
    portfolio_events = relationship("PortfolioEvent", back_populates="user")
    advice_items = relationship("InvestmentAdvice", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    funding_lots = relationship("FundingLot", back_populates="user")
    attribution_gaps = relationship("AttributionGap", back_populates="user")


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True)
    asset_type = Column(Enum(AssetType), nullable=False, index=True)
    asset_code = Column(String(64), nullable=False, index=True)
    asset_name = Column(String(255), nullable=True)
    currency = Column(String(16), nullable=False, index=True)
    issuer = Column(String(255), nullable=True)
    metadata_json = Column(JSON, nullable=True)

    asset_ledger_entries = relationship("AssetLedgerEntry", back_populates="asset")
    valuation_snapshots = relationship("ValuationSnapshot", back_populates="asset")
    attributions = relationship("Attribution", back_populates="target_asset")
    attribution_gaps = relationship("AttributionGap", back_populates="asset")


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    asset_type = Column(Enum(AssetType), nullable=False, index=True)
    asset_code = Column(String(32), nullable=False, index=True)
    asset_name = Column(String(255), nullable=True)
    direction = Column(Enum(TransactionDirection), nullable=False)
    quantity = Column(Numeric(18, 6), nullable=False)
    unit_price = Column(Numeric(18, 6), nullable=False)
    trade_currency = Column(String(16), nullable=False)
    trade_time = Column(DateTime(timezone=True), nullable=False)
    exchange_rate_to_cny = Column(Numeric(18, 6), nullable=True)
    total_cost_cny = Column(Numeric(18, 2), nullable=True)
    source = Column(String(32), nullable=False, default="manual")
    ocr_confidence = Column(Numeric(5, 4), nullable=True)
    status = Column(Enum(RecordStatus), nullable=False, default=RecordStatus.PENDING)
    raw_text = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    user = relationship("User", back_populates="transactions")


class PortfolioEvent(TimestampMixin, Base):
    __tablename__ = "portfolio_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(Enum(EventType), nullable=False, index=True)
    event_time = Column(DateTime(timezone=True), nullable=False, index=True)
    source = Column(String(32), nullable=False, default="manual")
    status = Column(Enum(RecordStatus), nullable=False, default=RecordStatus.CONFIRMED)
    raw_text = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    user = relationship("User", back_populates="portfolio_events")
    cash_ledger_entries = relationship("CashLedgerEntry", back_populates="event")
    asset_ledger_entries = relationship("AssetLedgerEntry", back_populates="event")
    source_funding_lots = relationship(
        "FundingLot",
        back_populates="source_event",
        foreign_keys="FundingLot.source_event_id",
    )
    target_attributions = relationship(
        "Attribution",
        back_populates="target_event",
        foreign_keys="Attribution.target_event_id",
    )
    attribution_gaps = relationship(
        "AttributionGap",
        back_populates="event",
        foreign_keys="AttributionGap.event_id",
    )
    lot_consumptions = relationship(
        "LotConsumption",
        back_populates="consuming_event",
        foreign_keys="LotConsumption.consuming_event_id",
    )


class CashLedgerEntry(Base):
    __tablename__ = "cash_ledger_entries"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("portfolio_events.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    currency = Column(String(16), nullable=False, index=True)
    amount_delta = Column(Numeric(18, 6), nullable=False)
    rmb_amount = Column(Numeric(18, 2), nullable=True)
    fx_rate_to_cny = Column(Numeric(18, 6), nullable=True)
    is_external_flow = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    event = relationship("PortfolioEvent", back_populates="cash_ledger_entries")


class AssetLedgerEntry(Base):
    __tablename__ = "asset_ledger_entries"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("portfolio_events.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False, index=True)
    quantity_delta = Column(Numeric(18, 6), nullable=False)
    cash_currency = Column(String(16), nullable=False)
    cash_amount = Column(Numeric(18, 6), nullable=True)
    unit_price = Column(Numeric(18, 6), nullable=True)
    fx_rate_to_cny = Column(Numeric(18, 6), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    event = relationship("PortfolioEvent", back_populates="asset_ledger_entries")
    asset = relationship("Asset", back_populates="asset_ledger_entries")


class Position(TimestampMixin, Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    asset_type = Column(Enum(AssetType), nullable=False, index=True)
    asset_code = Column(String(32), nullable=False, index=True)
    asset_name = Column(String(255), nullable=True)
    quantity = Column(Numeric(18, 6), nullable=False)
    average_cost_cny = Column(Numeric(18, 6), nullable=False)
    cost_basis_cny = Column(Numeric(18, 2), nullable=False)
    current_price = Column(Numeric(18, 6), nullable=True)
    current_value_cny = Column(Numeric(18, 2), nullable=True)
    unrealized_pnl_cny = Column(Numeric(18, 2), nullable=True)
    return_pct = Column(Numeric(10, 4), nullable=True)
    last_valued_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="positions")


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True)
    base_currency = Column(String(16), nullable=False, index=True)
    quote_currency = Column(String(16), nullable=False, index=True)
    rate = Column(Numeric(18, 6), nullable=False)
    rate_timestamp = Column(DateTime(timezone=True), nullable=False)
    is_estimated = Column(Boolean, nullable=False, default=False)
    source = Column(Enum(RateSourceType), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ValuationSnapshot(Base):
    __tablename__ = "valuation_snapshots"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False, index=True)
    valuation_time = Column(DateTime(timezone=True), nullable=False, index=True)
    quantity = Column(Numeric(18, 6), nullable=False)
    price = Column(Numeric(18, 6), nullable=True)
    market_value = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(16), nullable=False, index=True)
    fx_rate_to_cny = Column(Numeric(18, 6), nullable=True)
    source = Column(String(32), nullable=False, default="manual")
    is_estimated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    asset = relationship("Asset", back_populates="valuation_snapshots")


class InvestmentAdvice(Base):
    __tablename__ = "investment_advice"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    summary = Column(Text, nullable=False)
    action = Column(Enum(AdviceAction), nullable=False)
    reasoning = Column(Text, nullable=False)
    risk_level = Column(String(32), nullable=True)
    payload_json = Column(JSON, nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    user = relationship("User", back_populates="advice_items")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    details_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    user = relationship("User", back_populates="audit_logs")


class FundingLot(Base):
    __tablename__ = "funding_lots"
    __table_args__ = (
        CheckConstraint("original_amount >= 0", name="ck_funding_lots_original_amount_non_negative"),
        CheckConstraint("remaining_amount >= 0", name="ck_funding_lots_remaining_amount_non_negative"),
        CheckConstraint(
            "original_rmb_basis IS NULL OR original_rmb_basis >= 0",
            name="ck_funding_lots_original_rmb_basis_non_negative",
        ),
        CheckConstraint(
            "remaining_rmb_basis IS NULL OR remaining_rmb_basis >= 0",
            name="ck_funding_lots_remaining_rmb_basis_non_negative",
        ),
        CheckConstraint(
            "remaining_amount <= original_amount",
            name="ck_funding_lots_remaining_amount_lte_original",
        ),
        Index("idx_funding_lots_user_currency", "user_id", "currency"),
        Index("idx_funding_lots_source_event", "source_event_id"),
        Index("idx_funding_lots_status", "status"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    currency = Column(String(16), nullable=False)
    source_event_id = Column(Integer, ForeignKey("portfolio_events.id"), nullable=True)
    source_type = Column(Enum(FundingSourceType), nullable=False)
    original_amount = Column(Numeric(18, 6), nullable=False)
    remaining_amount = Column(Numeric(18, 6), nullable=False)
    original_rmb_basis = Column(Numeric(18, 2), nullable=True)
    remaining_rmb_basis = Column(Numeric(18, 2), nullable=True)
    status = Column(Enum(LotStatus), nullable=False, default=LotStatus.AVAILABLE)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    fully_consumed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="funding_lots")
    source_event = relationship(
        "PortfolioEvent",
        back_populates="source_funding_lots",
        foreign_keys=[source_event_id],
    )
    attributions = relationship("Attribution", back_populates="source_lot")
    consumptions = relationship("LotConsumption", back_populates="lot")


class Attribution(Base):
    __tablename__ = "attributions"
    __table_args__ = (
        CheckConstraint("native_amount >= 0", name="ck_attributions_native_amount_non_negative"),
        CheckConstraint("rmb_basis >= 0", name="ck_attributions_rmb_basis_non_negative"),
        Index("idx_attributions_target_event", "target_event_id"),
        Index("idx_attributions_target_asset", "target_asset_id"),
        Index("idx_attributions_source_lot", "source_lot_id"),
    )

    id = Column(Integer, primary_key=True)
    target_event_id = Column(Integer, ForeignKey("portfolio_events.id"), nullable=False)
    target_asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    source_lot_id = Column(Integer, ForeignKey("funding_lots.id"), nullable=False)
    native_amount = Column(Numeric(18, 6), nullable=False)
    rmb_basis = Column(Numeric(18, 2), nullable=False)
    allocation_policy = Column(Enum(AllocationPolicy), nullable=False, default=AllocationPolicy.FIFO)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    target_event = relationship(
        "PortfolioEvent",
        back_populates="target_attributions",
        foreign_keys=[target_event_id],
    )
    target_asset = relationship("Asset", back_populates="attributions")
    source_lot = relationship("FundingLot", back_populates="attributions")


class AttributionGap(Base):
    __tablename__ = "attribution_gaps"
    __table_args__ = (
        CheckConstraint(
            "shortfall_amount IS NULL OR shortfall_amount >= 0",
            name="ck_attribution_gaps_shortfall_non_negative",
        ),
        Index("idx_attribution_gaps_user", "user_id"),
        Index("idx_attribution_gaps_event", "event_id"),
        Index("idx_attribution_gaps_status", "status"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("portfolio_events.id"), nullable=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    gap_type = Column(Enum(GapType), nullable=False)
    currency = Column(String(16), nullable=False)
    shortfall_amount = Column(Numeric(18, 6), nullable=True)
    status = Column(Enum(AttributionStatus), nullable=False, default=AttributionStatus.INCOMPLETE)
    resolution_notes = Column(Text, nullable=True)
    detected_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="attribution_gaps")
    event = relationship(
        "PortfolioEvent",
        back_populates="attribution_gaps",
        foreign_keys=[event_id],
    )
    asset = relationship("Asset", back_populates="attribution_gaps")


class LotConsumption(Base):
    __tablename__ = "lot_consumptions"
    __table_args__ = (
        CheckConstraint("amount_consumed >= 0", name="ck_lot_consumptions_amount_non_negative"),
        CheckConstraint("rmb_basis_consumed >= 0", name="ck_lot_consumptions_rmb_basis_non_negative"),
        CheckConstraint("remaining_after >= 0", name="ck_lot_consumptions_remaining_after_non_negative"),
        Index("idx_lot_consumptions_lot", "lot_id"),
        Index("idx_lot_consumptions_event", "consuming_event_id"),
    )

    id = Column(Integer, primary_key=True)
    lot_id = Column(Integer, ForeignKey("funding_lots.id"), nullable=False)
    consuming_event_id = Column(Integer, ForeignKey("portfolio_events.id"), nullable=False)
    amount_consumed = Column(Numeric(18, 6), nullable=False)
    rmb_basis_consumed = Column(Numeric(18, 2), nullable=False)
    remaining_after = Column(Numeric(18, 6), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    lot = relationship("FundingLot", back_populates="consumptions")
    consuming_event = relationship(
        "PortfolioEvent",
        back_populates="lot_consumptions",
        foreign_keys=[consuming_event_id],
    )
