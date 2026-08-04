"""Trading scheduler control-plane unit tests (paper only)."""

from __future__ import annotations

import asyncio

import pytest

from app.core.config import Settings, get_settings
from app.services import trading_scheduler as sched
from app.services.paper_session import reset_paper_session


@pytest.fixture(autouse=True)
def _reset_scheduler():
    get_settings.cache_clear()
    reset_paper_session()
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


def test_scheduler_status_defaults():
    status = sched.scheduler_status()
    assert status["running"] is False
    assert status["cycles_completed"] == 0
    assert "enabled_by_config" in status


def test_clear_failure_pause():
    sched._PAUSED_BY_FAILURES = True
    sched._CONSECUTIVE_FAILURES = 3
    sched.clear_failure_pause()
    assert sched._PAUSED_BY_FAILURES is False
    assert sched._CONSECUTIVE_FAILURES == 0


@pytest.mark.asyncio
async def test_start_noop_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_TRADING_SCHEDULER", "false")
    get_settings.cache_clear()
    Settings(enable_trading_scheduler=False, trading_mode="paper", _env_file=None)
    get_settings.cache_clear()
    monkeypatch.setenv("ENABLE_TRADING_SCHEDULER", "false")
    get_settings.cache_clear()
    sched.start_scheduler(force=False)
    assert sched.scheduler_status()["running"] is False
    await sched.stop_scheduler()


@pytest.mark.asyncio
async def test_force_start_and_stop(monkeypatch):
    monkeypatch.setenv("ENABLE_TRADING_SCHEDULER", "false")
    get_settings.cache_clear()
    sched.start_scheduler(force=True)
    assert sched.scheduler_status()["running"] is True
    await sched.pause_scheduler()
    await sched.resume_scheduler()
    await sched.stop_scheduler()
    assert sched.scheduler_status()["running"] is False
