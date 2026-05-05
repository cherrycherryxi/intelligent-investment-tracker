"""fx funding attribution schema

Revision ID: 0003_fx_funding_attribution
Revises: 0002_v02_multi_currency_performance
Create Date: 2026-05-04 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_fx_funding_attribution"
down_revision = "0002_v02_multi_currency_performance"
branch_labels = None
depends_on = None


funding_source_type_enum = sa.Enum(
    "FX_BUY",
    "FX_SWAP",
    "REDEMPTION",
    "DIVIDEND",
    "INTEREST",
    "MANUAL_ADJUSTMENT",
    "CARRYFORWARD",
    name="fundingsourcetype",
)
lot_status_enum = sa.Enum("AVAILABLE", "FULLY_CONSUMED", "BASIS_MISSING", name="lotstatus")
attribution_status_enum = sa.Enum(
    "COMPLETE",
    "INCOMPLETE",
    "BASIS_MISSING",
    "NOT_APPLICABLE",
    name="attributionstatus",
)
gap_type_enum = sa.Enum(
    "UNATTRIBUTED_FUNDING",
    "BASIS_MISSING",
    "POLICY_CONFLICT",
    name="gaptype",
)
allocation_policy_enum = sa.Enum("FIFO", "LIFO", "WEIGHTED_AVERAGE", name="allocationpolicy")


def upgrade() -> None:
    bind = op.get_bind()
    funding_source_type_enum.create(bind, checkfirst=True)
    lot_status_enum.create(bind, checkfirst=True)
    attribution_status_enum.create(bind, checkfirst=True)
    gap_type_enum.create(bind, checkfirst=True)
    allocation_policy_enum.create(bind, checkfirst=True)

    op.create_table(
        "funding_lots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("source_event_id", sa.Integer(), sa.ForeignKey("portfolio_events.id"), nullable=True),
        sa.Column("source_type", funding_source_type_enum, nullable=False),
        sa.Column("original_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("remaining_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("original_rmb_basis", sa.Numeric(18, 2), nullable=True),
        sa.Column("remaining_rmb_basis", sa.Numeric(18, 2), nullable=True),
        sa.Column("status", lot_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fully_consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("original_amount >= 0", name="ck_funding_lots_original_amount_non_negative"),
        sa.CheckConstraint("remaining_amount >= 0", name="ck_funding_lots_remaining_amount_non_negative"),
        sa.CheckConstraint(
            "original_rmb_basis IS NULL OR original_rmb_basis >= 0",
            name="ck_funding_lots_original_rmb_basis_non_negative",
        ),
        sa.CheckConstraint(
            "remaining_rmb_basis IS NULL OR remaining_rmb_basis >= 0",
            name="ck_funding_lots_remaining_rmb_basis_non_negative",
        ),
        sa.CheckConstraint(
            "remaining_amount <= original_amount",
            name="ck_funding_lots_remaining_amount_lte_original",
        ),
    )
    op.create_index("idx_funding_lots_user_currency", "funding_lots", ["user_id", "currency"], unique=False)
    op.create_index("idx_funding_lots_source_event", "funding_lots", ["source_event_id"], unique=False)
    op.create_index("idx_funding_lots_status", "funding_lots", ["status"], unique=False)

    op.create_table(
        "attributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_event_id", sa.Integer(), sa.ForeignKey("portfolio_events.id"), nullable=False),
        sa.Column("target_asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("source_lot_id", sa.Integer(), sa.ForeignKey("funding_lots.id"), nullable=False),
        sa.Column("native_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("rmb_basis", sa.Numeric(18, 2), nullable=False),
        sa.Column("allocation_policy", allocation_policy_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("native_amount >= 0", name="ck_attributions_native_amount_non_negative"),
        sa.CheckConstraint("rmb_basis >= 0", name="ck_attributions_rmb_basis_non_negative"),
    )
    op.create_index("idx_attributions_target_event", "attributions", ["target_event_id"], unique=False)
    op.create_index("idx_attributions_target_asset", "attributions", ["target_asset_id"], unique=False)
    op.create_index("idx_attributions_source_lot", "attributions", ["source_lot_id"], unique=False)

    op.create_table(
        "attribution_gaps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("portfolio_events.id"), nullable=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("gap_type", gap_type_enum, nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("shortfall_amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("status", attribution_status_enum, nullable=False),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "shortfall_amount IS NULL OR shortfall_amount >= 0",
            name="ck_attribution_gaps_shortfall_non_negative",
        ),
    )
    op.create_index("idx_attribution_gaps_user", "attribution_gaps", ["user_id"], unique=False)
    op.create_index("idx_attribution_gaps_event", "attribution_gaps", ["event_id"], unique=False)
    op.create_index("idx_attribution_gaps_status", "attribution_gaps", ["status"], unique=False)

    op.create_table(
        "lot_consumptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lot_id", sa.Integer(), sa.ForeignKey("funding_lots.id"), nullable=False),
        sa.Column("consuming_event_id", sa.Integer(), sa.ForeignKey("portfolio_events.id"), nullable=False),
        sa.Column("amount_consumed", sa.Numeric(18, 6), nullable=False),
        sa.Column("rmb_basis_consumed", sa.Numeric(18, 2), nullable=False),
        sa.Column("remaining_after", sa.Numeric(18, 6), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_consumed >= 0", name="ck_lot_consumptions_amount_non_negative"),
        sa.CheckConstraint("rmb_basis_consumed >= 0", name="ck_lot_consumptions_rmb_basis_non_negative"),
        sa.CheckConstraint("remaining_after >= 0", name="ck_lot_consumptions_remaining_after_non_negative"),
    )
    op.create_index("idx_lot_consumptions_lot", "lot_consumptions", ["lot_id"], unique=False)
    op.create_index("idx_lot_consumptions_event", "lot_consumptions", ["consuming_event_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_lot_consumptions_event", table_name="lot_consumptions")
    op.drop_index("idx_lot_consumptions_lot", table_name="lot_consumptions")
    op.drop_table("lot_consumptions")

    op.drop_index("idx_attribution_gaps_status", table_name="attribution_gaps")
    op.drop_index("idx_attribution_gaps_event", table_name="attribution_gaps")
    op.drop_index("idx_attribution_gaps_user", table_name="attribution_gaps")
    op.drop_table("attribution_gaps")

    op.drop_index("idx_attributions_source_lot", table_name="attributions")
    op.drop_index("idx_attributions_target_asset", table_name="attributions")
    op.drop_index("idx_attributions_target_event", table_name="attributions")
    op.drop_table("attributions")

    op.drop_index("idx_funding_lots_status", table_name="funding_lots")
    op.drop_index("idx_funding_lots_source_event", table_name="funding_lots")
    op.drop_index("idx_funding_lots_user_currency", table_name="funding_lots")
    op.drop_table("funding_lots")

    bind = op.get_bind()
    allocation_policy_enum.drop(bind, checkfirst=True)
    gap_type_enum.drop(bind, checkfirst=True)
    attribution_status_enum.drop(bind, checkfirst=True)
    lot_status_enum.drop(bind, checkfirst=True)
    funding_source_type_enum.drop(bind, checkfirst=True)
