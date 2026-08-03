"""Paper vertical slice: strategy_runs, balances, positions, snapshots, journal, system_state

Revision ID: 0004_paper_slice
Revises: 0003_users
Create Date: 2026-08-03 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_paper_slice"
down_revision: Union[str, None] = "0003_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("strategy_name", sa.String(length=128), nullable=False),
        sa.Column("strategy_version", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("candle_open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "strategy_name",
            "strategy_version",
            "symbol",
            "timeframe",
            "candle_open_time",
            name="uq_strategy_run_candle",
        ),
    )
    op.create_index("ix_strategy_runs_symbol", "strategy_runs", ["symbol"])

    op.create_table(
        "balances",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("asset", sa.String(length=32), nullable=False),
        sa.Column("free", sa.Numeric(36, 18), nullable=False),
        sa.Column("locked", sa.Numeric(36, 18), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("asset", name="uq_balances_asset"),
    )

    op.create_table(
        "positions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Numeric(36, 18), nullable=False),
        sa.Column("entry_price", sa.Numeric(36, 18), nullable=False),
        sa.Column("current_price", sa.Numeric(36, 18), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(36, 18), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(36, 18), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("strategy_name", sa.String(length=128), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("symbol", name="uq_positions_symbol"),
    )

    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("cash_balance", sa.Numeric(36, 18), nullable=False),
        sa.Column("equity", sa.Numeric(36, 18), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(36, 18), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(36, 18), nullable=False),
        sa.Column("daily_pnl", sa.Numeric(36, 18), nullable=False),
        sa.Column("peak_equity", sa.Numeric(36, 18), nullable=False),
        sa.Column("drawdown", sa.Numeric(36, 18), nullable=False),
        sa.Column("fees_paid", sa.Numeric(36, 18), nullable=False),
        sa.Column("exposure", sa.Numeric(36, 18), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_portfolio_snapshots_created_at", "portfolio_snapshots", ["created_at"]
    )

    op.create_table(
        "trade_journal",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("strategy_run_id", sa.String(length=64), nullable=True),
        sa.Column("order_id", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trade_journal_created_at", "trade_journal", ["created_at"])
    op.create_index(
        "ix_trade_journal_correlation_id", "trade_journal", ["correlation_id"]
    )

    op.create_table(
        "system_state",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_state")
    op.drop_index("ix_trade_journal_correlation_id", table_name="trade_journal")
    op.drop_index("ix_trade_journal_created_at", table_name="trade_journal")
    op.drop_table("trade_journal")
    op.drop_index("ix_portfolio_snapshots_created_at", table_name="portfolio_snapshots")
    op.drop_table("portfolio_snapshots")
    op.drop_table("positions")
    op.drop_table("balances")
    op.drop_index("ix_strategy_runs_symbol", table_name="strategy_runs")
    op.drop_table("strategy_runs")
