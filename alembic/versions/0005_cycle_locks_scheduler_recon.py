"""Cycle locks, scheduler runs, and reconciliation reports.

Revision ID: 0005_cycle_ops
Revises: 0004_paper_slice
Create Date: 2026-08-04 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_cycle_ops"
down_revision: Union[str, None] = "0004_paper_slice"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cycle_locks",
        sa.Column("lock_key", sa.String(length=255), primary_key=True),
        sa.Column("owner", sa.String(length=64), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_cycle_locks_expires_at", "cycle_locks", ["expires_at"])

    op.create_table(
        "scheduler_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("error", sa.String(length=512), nullable=True),
    )
    op.create_index("ix_scheduler_runs_started_at", "scheduler_runs", ["started_at"])

    op.create_table(
        "reconciliation_reports",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("healthy", sa.String(length=8), nullable=False),
        sa.Column("detail", sa.String(length=512), nullable=False),
        sa.Column("cash", sa.String(length=64), nullable=False),
        sa.Column("position_count", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.String(length=4096), nullable=False, server_default="{}"),
    )
    op.create_index(
        "ix_reconciliation_reports_created_at", "reconciliation_reports", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_reconciliation_reports_created_at", table_name="reconciliation_reports")
    op.drop_table("reconciliation_reports")
    op.drop_index("ix_scheduler_runs_started_at", table_name="scheduler_runs")
    op.drop_table("scheduler_runs")
    op.drop_index("ix_cycle_locks_expires_at", table_name="cycle_locks")
    op.drop_table("cycle_locks")
