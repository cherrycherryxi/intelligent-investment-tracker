"""0001 initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-26 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


asset_type_enum = sa.Enum("FOREX", "BOND", name="assettype")
transaction_direction_enum = sa.Enum("BUY", "SELL", name="transactiondirection")
rate_source_type_enum = sa.Enum("PRIMARY", "FALLBACK", "MANUAL", name="ratesourcetype")
advice_action_enum = sa.Enum("HOLD", "BUY", "SELL", name="adviceaction")
record_status_enum = sa.Enum("PENDING", "CONFIRMED", "REJECTED", name="recordstatus")


def upgrade() -> None:
    bind = op.get_bind()
    asset_type_enum.create(bind, checkfirst=True)
    transaction_direction_enum.create(bind, checkfirst=True)
    rate_source_type_enum.create(bind, checkfirst=True)
    advice_action_enum.create(bind, checkfirst=True)
    record_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("risk_preference", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("base_currency", sa.String(length=16), nullable=False),
        sa.Column("quote_currency", sa.String(length=16), nullable=False),
        sa.Column("rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("rate_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_estimated", sa.Boolean(), nullable=False),
        sa.Column("source", rate_source_type_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_exchange_rates_base_currency", "exchange_rates", ["base_currency"], unique=False)
    op.create_index("ix_exchange_rates_quote_currency", "exchange_rates", ["quote_currency"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"], unique=False)

    op.create_table(
        "investment_advice",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("action", advice_action_enum, nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_investment_advice_user_id", "investment_advice", ["user_id"], unique=False)

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("asset_type", asset_type_enum, nullable=False),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("asset_name", sa.String(length=255), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("average_cost_cny", sa.Numeric(18, 6), nullable=False),
        sa.Column("cost_basis_cny", sa.Numeric(18, 2), nullable=False),
        sa.Column("current_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("current_value_cny", sa.Numeric(18, 2), nullable=True),
        sa.Column("unrealized_pnl_cny", sa.Numeric(18, 2), nullable=True),
        sa.Column("return_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("last_valued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_positions_user_id", "positions", ["user_id"], unique=False)
    op.create_index("ix_positions_asset_type", "positions", ["asset_type"], unique=False)
    op.create_index("ix_positions_asset_code", "positions", ["asset_code"], unique=False)

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("asset_type", asset_type_enum, nullable=False),
        sa.Column("asset_code", sa.String(length=32), nullable=False),
        sa.Column("asset_name", sa.String(length=255), nullable=True),
        sa.Column("direction", transaction_direction_enum, nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("trade_currency", sa.String(length=16), nullable=False),
        sa.Column("trade_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exchange_rate_to_cny", sa.Numeric(18, 6), nullable=True),
        sa.Column("total_cost_cny", sa.Numeric(18, 2), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("ocr_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", record_status_enum, nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"], unique=False)
    op.create_index("ix_transactions_asset_type", "transactions", ["asset_type"], unique=False)
    op.create_index("ix_transactions_asset_code", "transactions", ["asset_code"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_transactions_asset_code", table_name="transactions")
    op.drop_index("ix_transactions_asset_type", table_name="transactions")
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_table("transactions")

    op.drop_index("ix_positions_asset_code", table_name="positions")
    op.drop_index("ix_positions_asset_type", table_name="positions")
    op.drop_index("ix_positions_user_id", table_name="positions")
    op.drop_table("positions")

    op.drop_index("ix_investment_advice_user_id", table_name="investment_advice")
    op.drop_table("investment_advice")

    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_exchange_rates_quote_currency", table_name="exchange_rates")
    op.drop_index("ix_exchange_rates_base_currency", table_name="exchange_rates")
    op.drop_table("exchange_rates")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    record_status_enum.drop(bind, checkfirst=True)
    advice_action_enum.drop(bind, checkfirst=True)
    rate_source_type_enum.drop(bind, checkfirst=True)
    transaction_direction_enum.drop(bind, checkfirst=True)
    asset_type_enum.drop(bind, checkfirst=True)

