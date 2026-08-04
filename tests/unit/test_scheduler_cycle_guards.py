"""Scheduler cycle guards: kill-switch, pause, recon halt, overlap."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import get_settings
from app.services import trading_scheduler as sched
from app.services.paper_session import get_paper_session, reset_paper_session
from app.services.reconciliation import clear_reconciliation_halt


@pytest.fixture(autouse=True)
def _reset():
    get_settings.cache_clear()
    reset_paper_session()
    clear_reconciliation_halt()
    if sched._TASK is not None and not sched._TASK.done():
        sched._STOP.set()
    sched._TASK = None
    sched._STOP = asyncio.Event()
    sched._LAST_OK = None
    sched._LAST_ERROR = None
    sched._CYCLE_COUNT = 0
    sched._CONSECUTIVE_FAILURES = 0
    sched._PAUSED_BY_FAILURES = False
    yield
    if sched._TASK is not None and not sched._TASK.done():
        sched._STOP.set()
        try:
            asyncio.get_event_loop().run_until_complete(sched.stop_scheduler())
        except Exception:
            sched._TASK = None
    sched._TASK = None
    reset_paper_session()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_run_one_cycle_respects_kill_switch():
    session = get_paper_session()
    session.kill_switch_enabled = True
    await sched._run_one_cycle()
    assert sched._LAST_ERROR == "kill_switch_active"


@pytest.mark.asyncio
async def test_run_one_cycle_respects_trading_paused():
    session = get_paper_session()
    session.set_paused(True)
    await sched._run_one_cycle()
    assert sched._LAST_ERROR == "trading_paused"


@pytest.mark.asyncio
async def test_run_one_cycle_respects_trading_disabled(monkeypatch):
    monkeypatch.setenv("TRADING_ENABLED", "false")
    get_settings.cache_clear()
    session = get_paper_session()
    session.trading_enabled = False
    session.trading_paused = False
    session.kill_switch_enabled = False
    await sched._run_one_cycle()
    assert sched._LAST_ERROR == "trading_disabled"


@pytest.mark.asyncio
async def test_run_one_cycle_respects_failure_pause():
    sched._PAUSED_BY_FAILURES = True
    await sched._run_one_cycle()
    assert sched._LAST_ERROR == "paused_after_failure_threshold"


@pytest.mark.asyncio
async def test_run_one_cycle_respects_reconciliation_halt(monkeypatch):
    monkeypatch.setenv("ENABLE_RECONCILIATION", "true")
    get_settings.cache_clear()
    session = get_paper_session()
    session.trading_enabled = True
    import app.services.reconciliation as recon

    monkeypatch.setattr(recon, "is_reconciliation_healthy", lambda: False)
    await sched._run_one_cycle()
    assert sched._LAST_ERROR == "reconciliation_halt"


@pytest.mark.asyncio
async def test_overlap_guard_skips_second_entry():
    entered = {"n": 0}

    async def slow_cycle():
        entered["n"] += 1
        await asyncio.sleep(0.2)

    async def attempt():
        if sched._OVERLAP_GUARD.locked():
            return "skipped"
        async with sched._OVERLAP_GUARD:
            await slow_cycle()
            return "ran"

    t1 = asyncio.create_task(attempt())
    await asyncio.sleep(0.05)
    t2 = asyncio.create_task(attempt())
    results = await asyncio.gather(t1, t2)
    assert "ran" in results
    assert "skipped" in results
    assert entered["n"] == 1


@pytest.mark.asyncio
async def test_run_one_cycle_success_path(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'sched.db'}")
    monkeypatch.setenv("ENABLE_RECONCILIATION", "false")
    monkeypatch.setenv("TRADING_ENABLED", "true")
    get_settings.cache_clear()
    session = get_paper_session()
    session.trading_enabled = True
    session.trading_paused = False
    session.kill_switch_enabled = False

    fake_result = MagicMock(
        correlation_id="corr-1",
        signal_direction="HOLD",
        order_id=None,
    )

    async def fake_cycle(**kwargs):
        return fake_result

    async def fake_resolve(settings=None):
        return MagicMock()

    monkeypatch.setattr(
        "app.services.market_sources.resolve_candle_source", fake_resolve
    )
    monkeypatch.setattr("app.services.paper_cycle.run_paper_trading_cycle", fake_cycle)
    monkeypatch.setattr("app.services.paper_cycle.persist_cycle_keys", AsyncMock())
    monkeypatch.setattr("app.services.paper_session.persist_paper_session", AsyncMock())
    monkeypatch.setattr(sched, "_persist_run", AsyncMock())

    # Patch the imports used inside _run_one_cycle via their modules
    import app.services.market_sources as ms
    import app.services.paper_cycle as pc
    import app.services.paper_session as ps

    monkeypatch.setattr(ms, "resolve_candle_source", fake_resolve)
    monkeypatch.setattr(pc, "run_paper_trading_cycle", fake_cycle)
    monkeypatch.setattr(pc, "persist_cycle_keys", AsyncMock())
    monkeypatch.setattr(ps, "persist_paper_session", AsyncMock())

    await sched._run_one_cycle()
    assert sched._CYCLE_COUNT == 1
    assert sched._LAST_OK is not None
    assert sched._LAST_ERROR is None
