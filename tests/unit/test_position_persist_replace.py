"""Regression: replacing positions must not hit UNIQUE(symbol) on SQLite."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.domain.trading import Position
from app.services import paper_persistence as store


@pytest.mark.asyncio
async def test_save_paper_checkpoint_replaces_same_symbol() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    pos_v1 = Position(
        symbol="BTC/USDT",
        quantity=Decimal("0.01"),
        entry_price=Decimal("65000"),
        current_price=Decimal("65000"),
        unrealized_pnl=Decimal("0"),
        opened_at=datetime(2026, 8, 5, 12, 0, tzinfo=UTC),
    )
    pos_v2 = Position(
        symbol="BTC/USDT",
        quantity=Decimal("0.02"),
        entry_price=Decimal("64000"),
        current_price=Decimal("66000"),
        unrealized_pnl=Decimal("40"),
        opened_at=datetime(2026, 8, 5, 12, 5, tzinfo=UTC),
    )

    async with factory() as session:
        await store.save_paper_checkpoint(
            session,
            cash=Decimal("9000"),
            positions={"BTC/USDT": pos_v1},
            realized_pnl=Decimal("0"),
            peak_equity=Decimal("10000"),
            consecutive_losses=0,
            idempotency_index={},
        )
        await store.save_paper_checkpoint(
            session,
            cash=Decimal("8000"),
            positions={"BTC/USDT": pos_v2},
            realized_pnl=Decimal("10"),
            peak_equity=Decimal("10000"),
            consecutive_losses=0,
            idempotency_index={},
        )
        loaded = await store.load_paper_checkpoint(session)
        assert loaded is not None
        assert Decimal(loaded["positions"]["BTC/USDT"]["quantity"]) == Decimal("0.02")

    await engine.dispose()
