"""v0.2 multi-currency performance schema

Revision ID: 0002_v02_multi_currency_performance
Revises: 0001_initial_schema
Create Date: 2026-04-29 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_v02_multi_currency_performance"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE assettype ADD VALUE IF NOT EXISTS 'CASH'")
        op.execute("ALTER TYPE assettype ADD VALUE IF NOT EXISTS 'FUND'")
        op.execute("ALTER TYPE assettype ADD VALUE IF NOT EXISTS 'WEALTH_PRODUCT'")

    event_type_enum = sa.Enum(
        "FX_BUY",
        "FX_SELL",
        "FX_SWAP",
        "BOND_BUY",
        "BOND_SELL",
        "BOND_REDEMPTION",
        "INTEREST_INCOME",
        "FUND_BUY",
        "FUND_SELL",
        "FUND_DIVIDEND",
        "FUND_DIVIDEND_REINVEST",
        "WEALTH_BUY",
        "WEALTH_REDEEM",
        "WEALTH_INCOME",
        "MANUAL_ADJUSTMENT",
        name="eventtype",
    )
    event_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_type", sa.Enum("CASH", "FOREX", "BOND", "FUND", "WEALTH_PRODUCT", name="assettype"), nullable=False),
        sa.Column("asset_code", sa.String(length=64), nullable=False),
        sa.Column("asset_name", sa.String(length=255), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("issuer", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assets_asset_type", "assets", ["asset_type"], unique=False)
    op.create_index("ix_assets_asset_code", "assets", ["asset_code"], unique=False)
    op.create_index("ix_assets_currency", "assets", ["currency"], unique=False)

    op.create_table(
        "portfolio_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", event_type_enum, nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "CONFIRMED", "REJECTED", name="recordstatus"), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_portfolio_events_user_id", "portfolio_events", ["user_id"], unique=False)
    op.create_index("ix_portfolio_events_event_type", "portfolio_events", ["event_type"], unique=False)
    op.create_index("ix_portfolio_events_event_time", "portfolio_events", ["event_time"], unique=False)

    op.create_table(
        "cash_ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("portfolio_events.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("amount_delta", sa.Numeric(18, 6), nullable=False),
        sa.Column("rmb_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("fx_rate_to_cny", sa.Numeric(18, 6), nullable=True),
        sa.Column("is_external_flow", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cash_ledger_entries_event_id", "cash_ledger_entries", ["event_id"], unique=False)
    op.create_index("ix_cash_ledger_entries_user_id", "cash_ledger_entries", ["user_id"], unique=False)
    op.create_index("ix_cash_ledger_entries_currency", "cash_ledger_entries", ["currency"], unique=False)

    op.create_table(
        "asset_ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("portfolio_events.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(18, 6), nullable=False),
        sa.Column("cash_currency", sa.String(length=16), nullable=False),
        sa.Column("cash_amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("fx_rate_to_cny", sa.Numeric(18, 6), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_asset_ledger_entries_event_id", "asset_ledger_entries", ["event_id"], unique=False)
    op.create_index("ix_asset_ledger_entries_user_id", "asset_ledger_entries", ["user_id"], unique=False)
    op.create_index("ix_asset_ledger_entries_asset_id", "asset_ledger_entries", ["asset_id"], unique=False)

    op.create_table(
        "valuation_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("valuation_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("market_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("fx_rate_to_cny", sa.Numeric(18, 6), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("is_estimated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_valuation_snapshots_user_id", "valuation_snapshots", ["user_id"], unique=False)
    op.create_index("ix_valuation_snapshots_asset_id", "valuation_snapshots", ["asset_id"], unique=False)
    op.create_index("ix_valuation_snapshots_valuation_time", "valuation_snapshots", ["valuation_time"], unique=False)
    op.create_index("ix_valuation_snapshots_currency", "valuation_snapshots", ["currency"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_valuation_snapshots_currency", table_name="valuation_snapshots")
    op.drop_index("ix_valuation_snapshots_valuation_time", table_name="valuation_snapshots")
    op.drop_index("ix_valuation_snapshots_asset_id", table_name="valuation_snapshots")
    op.drop_index("ix_valuation_snapshots_user_id", table_name="valuation_snapshots")
    op.drop_table("valuation_snapshots")
    op.drop_index("ix_asset_ledger_entries_asset_id", table_name="asset_ledger_entries")
    op.drop_index("ix_asset_ledger_entries_user_id", table_name="asset_ledger_entries")
    op.drop_index("ix_asset_ledger_entries_event_id", table_name="asset_ledger_entries")
    op.drop_table("asset_ledger_entries")
    op.drop_index("ix_cash_ledger_entries_currency", table_name="cash_ledger_entries")
    op.drop_index("ix_cash_ledger_entries_user_id", table_name="cash_ledger_entries")
    op.drop_index("ix_cash_ledger_entries_event_id", table_name="cash_ledger_entries")
    op.drop_table("cash_ledger_entries")
    op.drop_index("ix_portfolio_events_event_time", table_name="portfolio_events")
    op.drop_index("ix_portfolio_events_event_type", table_name="portfolio_events")
    op.drop_index("ix_portfolio_events_user_id", table_name="portfolio_events")
    op.drop_table("portfolio_events")
    op.drop_index("ix_assets_currency", table_name="assets")
    op.drop_index("ix_assets_asset_code", table_name="assets")
    op.drop_index("ix_assets_asset_type", table_name="assets")
    op.drop_table("assets")
    sa.Enum(name="eventtype").drop(op.get_bind(), checkfirst=True)
