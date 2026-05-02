"""ORM models for the Day1 schema."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from investment_tracker.data.base import Base, TimestampMixin, utcnow
from investment_tracker.data.enums import (
    AdviceAction,
    AssetType,
    EventType,
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
