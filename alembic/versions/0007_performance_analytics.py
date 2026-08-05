"""Closed trades journal + performance reports for paper analytics.

Revision ID: 0007_perf_analytics
Revises: 0006_paper_durable
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_perf_analytics"
down_revision: str | None = "0006_paper_durable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "closed_trades",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("strategy_name", sa.String(length=128), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("exit_price", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("fees", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("slippage", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("gross_pnl", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("net_pnl", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("roi_pct", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("exit_reason", sa.String(length=64), nullable=False),
        sa.Column("risk_score", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("market_regime", sa.String(length=32), nullable=False),
        sa.Column("paper_session_id", sa.String(length=64), nullable=False),
        sa.Column("order_id", sa.String(length=64), nullable=True),
        sa.Column("fill_id", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_closed_trades_symbol", "closed_trades", ["symbol"])
    op.create_index("ix_closed_trades_strategy", "closed_trades", ["strategy_name"])
    op.create_index("ix_closed_trades_exit_time", "closed_trades", ["exit_time"])
    op.create_index(
        "ix_closed_trades_session", "closed_trades", ["paper_session_id"]
    )

    op.create_table(
        "performance_reports",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "period", "period_start", "period_end", name="uq_performance_reports_period"
        ),
    )
    op.create_index("ix_performance_reports_period", "performance_reports", ["period"])


def downgrade() -> None:
    op.drop_index("ix_performance_reports_period", table_name="performance_reports")
    op.drop_table("performance_reports")
    op.drop_index("ix_closed_trades_session", table_name="closed_trades")
    op.drop_index("ix_closed_trades_exit_time", table_name="closed_trades")
    op.drop_index("ix_closed_trades_strategy", table_name="closed_trades")
    op.drop_index("ix_closed_trades_symbol", table_name="closed_trades")
    op.drop_table("closed_trades")
