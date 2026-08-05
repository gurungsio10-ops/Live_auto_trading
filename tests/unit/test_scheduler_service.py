"""Scheduler safety — paper only, disabled by default."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.database.ops  # noqa: F401
from app.db.base import Base
from app.services import scheduler_service


@pytest.mark.asyncio
async def test_scheduler_disabled_by_default(tmp_path, monkeypatch):
    url = f"sqlite+aiosqlite:///{tmp_path / 'sched.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    from app.core.config import get_settings

    get_settings.cache_clear()

    # Rebind SessionLocal used by scheduler
    import app.db.base as db_base

    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    db_base.engine = engine
    db_base.SessionLocal = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    job = await scheduler_service.ensure_default_job()
    assert job.enabled is False
    status = await scheduler_service.get_scheduler_status()
    assert status["enabled"] is False
    assert status["live_trading_enabled"] is False

    await engine.dispose()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_scheduler_enable_blocks_when_live_flag(tmp_path, monkeypatch):
    url = f"sqlite+aiosqlite:///{tmp_path / 'sched2.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    from app.core.config import get_settings

    get_settings.cache_clear()
    import app.db.base as db_base

    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    db_base.engine = engine
    db_base.SessionLocal = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    settings = get_settings()
    monkeypatch.setattr(settings, "live_trading_enabled", True)
    with pytest.raises(RuntimeError, match="paper"):
        await scheduler_service.set_enabled(True)

    await engine.dispose()
    get_settings.cache_clear()
