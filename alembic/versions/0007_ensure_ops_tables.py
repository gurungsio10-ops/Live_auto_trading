"""Re-ensure durable ops tables when earlier stamps skipped creates.

Revision ID: 0007_ensure_ops_tables
Revises: 0006_paper_durable
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0007_ensure_ops_tables"
down_revision: Union[str, None] = "0006_paper_durable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    if not _has_table("scheduler_jobs"):
        op.create_table(
            "scheduler_jobs",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column(
                "interval_seconds", sa.Integer(), nullable=False, server_default="60"
            ),
            sa.Column(
                "symbol", sa.String(length=32), nullable=False, server_default="BTC/USDT"
            ),
            sa.Column(
                "timeframe", sa.String(length=16), nullable=False, server_default="1m"
            ),
            sa.Column(
                "strategy_id",
                sa.String(length=128),
                nullable=False,
                server_default="ema_crossover",
            ),
            sa.Column(
                "status", sa.String(length=32), nullable=False, server_default="idle"
            ),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_duration_ms", sa.Integer(), nullable=True),
            sa.Column("last_result", sa.String(length=64), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("last_correlation_id", sa.String(length=64), nullable=True),
            sa.Column("run_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("lock_owner", sa.String(length=128), nullable=True),
            sa.Column("lock_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("name", name="uq_scheduler_jobs_name"),
        )

    if not _has_table("closed_positions"):
        op.create_table(
            "closed_positions",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("quantity", sa.Numeric(36, 18), nullable=False),
            sa.Column("entry_price", sa.Numeric(36, 18), nullable=False),
            sa.Column("exit_price", sa.Numeric(36, 18), nullable=False),
            sa.Column("realized_pnl", sa.Numeric(36, 18), nullable=False),
            sa.Column("fees", sa.Numeric(36, 18), nullable=False, server_default="0"),
            sa.Column("strategy_name", sa.String(length=128), nullable=True),
            sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("correlation_id", sa.String(length=64), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False),
        )
        op.create_index("ix_closed_positions_symbol", "closed_positions", ["symbol"])
        op.create_index(
            "ix_closed_positions_closed_at", "closed_positions", ["closed_at"]
        )

    if not _has_table("idempotency_keys"):
        op.create_table(
            "idempotency_keys",
            sa.Column("key", sa.String(length=128), primary_key=True),
            sa.Column("scope", sa.String(length=64), nullable=False),
            sa.Column("response_ref", sa.String(length=128), nullable=True),
            sa.Column("payload_hash", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_idempotency_keys_scope", "idempotency_keys", ["scope"])

    if not _has_table("paper_cycle_runs"):
        op.create_table(
            "paper_cycle_runs",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("correlation_id", sa.String(length=64), nullable=False),
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("timeframe", sa.String(length=16), nullable=False),
            sa.Column("strategy_id", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("signal_direction", sa.String(length=16), nullable=True),
            sa.Column("order_id", sa.String(length=64), nullable=True),
            sa.Column("risk_decision", sa.String(length=32), nullable=True),
            sa.Column("risk_reason_code", sa.String(length=64), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("error_summary", sa.Text(), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "ix_paper_cycle_runs_created_at", "paper_cycle_runs", ["created_at"]
        )
        op.create_index(
            "ix_paper_cycle_runs_correlation_id",
            "paper_cycle_runs",
            ["correlation_id"],
        )


def downgrade() -> None:
    # Non-destructive: leave tables in place.
    return
