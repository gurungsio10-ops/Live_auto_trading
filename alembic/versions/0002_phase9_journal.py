"""Phase 9: journal tables

Revision ID: 0002_phase9
Revises: 0001_phase2
Create Date: 2026-08-03 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase9"
down_revision: Union[str, None] = "0001_phase2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("strategy_name", sa.String(length=128), nullable=False),
        sa.Column("strategy_version", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Numeric(36, 18), nullable=False),
        sa.Column("entry_rationale", sa.Text(), nullable=False),
        sa.Column("invalidation_condition", sa.Text(), nullable=False),
        sa.Column("suggested_stop", sa.Numeric(36, 18)),
        sa.Column("suggested_target", sa.Numeric(36, 18)),
        sa.Column("input_data_fingerprint", sa.String(length=256), nullable=False),
        sa.Column("led_to_order", sa.String(length=64)),
        sa.Column("payload", sa.JSON()),
    )
    op.create_table(
        "risk_decisions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("order_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("approved_quantity", sa.Numeric(36, 18)),
        sa.Column("message", sa.Text()),
        sa.Column("checks", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("client_order_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("order_type", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Numeric(36, 18), nullable=False),
        sa.Column("filled_quantity", sa.Numeric(36, 18), nullable=False),
        sa.Column("price", sa.Numeric(36, 18)),
        sa.Column("average_fill_price", sa.Numeric(36, 18)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("strategy_name", sa.String(length=128)),
        sa.Column("signal_id", sa.String(length=64)),
        sa.Column("risk_decision", sa.String(length=32)),
        sa.Column("risk_reason_code", sa.String(length=64)),
        sa.Column("fees", sa.Numeric(36, 18), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON()),
    )
    op.create_table(
        "fills",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(36, 18), nullable=False),
        sa.Column("price", sa.Numeric(36, 18), nullable=False),
        sa.Column("fee", sa.Numeric(36, 18), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "system_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_events")
    op.drop_table("fills")
    op.drop_table("orders")
    op.drop_table("risk_decisions")
    op.drop_table("signals")
