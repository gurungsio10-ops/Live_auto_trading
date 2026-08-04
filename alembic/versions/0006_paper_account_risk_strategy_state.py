"""Paper account, risk state, strategy state, equity snapshots.

Revision ID: 0006_paper_durable
Revises: 0005_cycle_ops
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_paper_durable"
down_revision: str | None = "0005_cycle_ops"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_accounts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("cash", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column(
            "realized_pnl",
            sa.Numeric(precision=36, scale=18),
            nullable=False,
            server_default="0",
        ),
        sa.Column("peak_equity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("daily_start_equity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("consecutive_losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "fees_paid",
            sa.Numeric(precision=36, scale=18),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "reserved_capital",
            sa.Numeric(precision=36, scale=18),
            nullable=False,
            server_default="0",
        ),
        sa.Column("idempotency_index", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "risk_state",
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column(
            "circuit_breaker_open",
            sa.String(length=8),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "circuit_breaker_reason",
            sa.String(length=256),
            nullable=False,
            server_default="",
        ),
        sa.Column("seen_idempotency_keys", sa.JSON(), nullable=False),
        sa.Column(
            "reconciliation_healthy",
            sa.String(length=8),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "risk_engine_healthy",
            sa.String(length=8),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "database_healthy", sa.String(length=8), nullable=False, server_default="true"
        ),
        sa.Column(
            "market_data_healthy",
            sa.String(length=8),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "peak_equity",
            sa.Numeric(precision=36, scale=18),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "daily_start_equity",
            sa.Numeric(precision=36, scale=18),
            nullable=False,
            server_default="0",
        ),
        sa.Column("consecutive_losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "kill_switch_enabled",
            sa.String(length=8),
            nullable=False,
            server_default="false",
        ),
        sa.Column("halt_reason", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("account_id"),
    )

    op.create_table(
        "strategy_state",
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("selected_strategy_id", sa.String(length=128), nullable=True),
        sa.Column("running_strategies", sa.JSON(), nullable=False),
        sa.Column("param_overrides", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("account_id"),
    )

    op.create_table(
        "processed_cycle_keys",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("strategy_version", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("candle_open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "strategy_version",
            "symbol",
            "timeframe",
            "candle_open_time",
            name="uq_processed_cycle_key",
        ),
    )
    op.create_index(
        "ix_processed_cycle_keys_account_id", "processed_cycle_keys", ["account_id"]
    )

    op.create_table(
        "equity_snapshots",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("equity", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("cash", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("drawdown", sa.Numeric(precision=36, scale=18), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_equity_snapshots_account_id", "equity_snapshots", ["account_id"])
    op.create_index("ix_equity_snapshots_created_at", "equity_snapshots", ["created_at"])

    op.create_table(
        "kill_switch_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.String(length=8), nullable=False),
        sa.Column("reason", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kill_switch_events_created_at", "kill_switch_events", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_kill_switch_events_created_at", table_name="kill_switch_events")
    op.drop_table("kill_switch_events")
    op.drop_index("ix_equity_snapshots_created_at", table_name="equity_snapshots")
    op.drop_index("ix_equity_snapshots_account_id", table_name="equity_snapshots")
    op.drop_table("equity_snapshots")
    op.drop_index("ix_processed_cycle_keys_account_id", table_name="processed_cycle_keys")
    op.drop_table("processed_cycle_keys")
    op.drop_table("strategy_state")
    op.drop_table("risk_state")
    op.drop_table("paper_accounts")
