"""Phase 2: create symbols and candles tables

Revision ID: 0001_phase2
Revises:
Create Date: 2026-08-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_phase2"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "symbols",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("base", sa.String(length=16), nullable=False),
        sa.Column("quote", sa.String(length=16), nullable=False),
        sa.Column("price_precision", sa.Integer(), nullable=False),
        sa.Column("quantity_precision", sa.Integer(), nullable=False),
        sa.Column("min_quantity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("min_notional", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("tick_size", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("step_size", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol"),
    )
    op.create_table(
        "candles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("open", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("high", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("low", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("close", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("volume", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("quote_volume", sa.Numeric(precision=36, scale=18), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("is_closed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "timeframe", "open_time", name="uq_candle_key"),
    )
    op.create_index(
        "ix_candles_symbol_tf_time",
        "candles",
        ["symbol", "timeframe", "open_time"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_candles_symbol_tf_time", table_name="candles")
    op.drop_table("candles")
    op.drop_table("symbols")
