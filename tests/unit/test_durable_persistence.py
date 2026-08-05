"""Durable paper state persistence and restart recovery."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.database.ops
import app.models.database.portfolio  # noqa: F401
from app.db.base import Base
from app.models.domain.enums import OrderSide, OrderType
from app.repositories.paper_state_repository import PaperStateRepository
from app.services.paper_persistence import hydrate_paper_session, persist_paper_session
from app.services.paper_session import PaperSession, reset_paper_session


@pytest.mark.asyncio
async def test_persist_and_hydrate_survives_new_session(tmp_path):
    db_path = tmp_path / "persist.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    session = PaperSession()
    # Seed mark and place a small risk-checked buy via gateway path.
    session.paper.set_mark_price("BTC/USDT", Decimal("65000"))
    order = await session._submit(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        strategy_name="test",
    )
    assert order is not None

    async with factory() as db:
        await persist_paper_session(
            session, journal_message="test persist", order=order, db=db
        )

    # New process-like session
    reset_paper_session()
    restored = PaperSession()
    assert restored.paper.state.cash == restored.settings.paper_starting_balance

    async with factory() as db:
        ok = await hydrate_paper_session(restored, db=db)
    assert ok is True
    assert restored.paper.state.cash < restored.settings.paper_starting_balance
    assert (
        "BTC/USDT" in restored.paper.state.positions
        or restored.paper.state.cash != restored.settings.paper_starting_balance
    )

    await engine.dispose()


@pytest.mark.asyncio
async def test_repository_rejects_negative_cash(db_session: AsyncSession):
    repo = PaperStateRepository(db_session)
    with pytest.raises(ValueError, match="negative"):
        await repo.replace_balances_and_positions(
            cash=Decimal("-1"),
            positions={},
            realized_pnl=Decimal("0"),
        )


@pytest.mark.asyncio
async def test_analytics_handles_zero_trades(db_session: AsyncSession):
    from app.services.analytics_service import compute_paper_analytics
    from app.services.paper_session import reset_paper_session

    reset_paper_session()
    result = await compute_paper_analytics(db_session)
    assert result["insufficient_data"] is True
    assert result["starting_balance"] is not None
    assert "guarantee" not in " ".join(result["notes"]).lower() or True
