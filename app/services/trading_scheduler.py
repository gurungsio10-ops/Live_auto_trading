"""Continuous paper/testnet trading scheduler (never submits live money)."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.safety import get_safety_guard
from app.core.time import utc_now

logger = get_logger("trading.scheduler")

_TASK: asyncio.Task[None] | None = None
_STOP = asyncio.Event()
_LAST_OK: str | None = None
_LAST_ERROR: str | None = None
_CYCLE_COUNT = 0


def scheduler_status() -> dict[str, Any]:
    return {
        "running": _TASK is not None and not _TASK.done(),
        "last_success_at": _LAST_OK,
        "last_error": _LAST_ERROR,
        "cycles_completed": _CYCLE_COUNT,
        "enabled_by_config": get_settings().enable_trading_scheduler,
    }


async def _run_one_cycle() -> None:
    global _LAST_OK, _LAST_ERROR, _CYCLE_COUNT
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.api import mvp as mvp_api
    from app.db.base import create_engine
    from app.execution.gateway import OrderGateway
    from app.journal.store import JournalStore
    from app.services import paper_cycle
    from app.services.market_sources import resolve_candle_source
    from app.services.paper_session import get_paper_session, persist_paper_session

    settings = get_settings()
    get_safety_guard(settings).assert_paper_only()
    session = get_paper_session()
    if session.kill_switch_enabled or settings.kill_switch_enabled:
        _LAST_ERROR = "kill_switch_active"
        return
    if session.trading_paused:
        _LAST_ERROR = "trading_paused"
        return
    if not mvp_api._trading_enabled() and not settings.trading_enabled:
        _LAST_ERROR = "trading_disabled"
        return

    symbol = settings.default_symbol
    timeframe = settings.default_timeframe
    strategy_id = "ema_crossover"
    source = await resolve_candle_source(settings)

    engine = create_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as db:
            journal = JournalStore(db)
            key = paper_cycle._session_key(symbol, strategy_id)
            orch = paper_cycle._CYCLE_ORCHESTRATORS.get(key)
            if orch is None:
                orch = paper_cycle.get_or_create_orchestrator(
                    symbol=symbol,
                    strategy_id=strategy_id,
                    settings=settings,
                    paper_engine=session.paper,
                    journal=journal,
                )
            orch.paper = session.paper
            orch.risk = session.risk_engine
            orch.gateway = OrderGateway(session.paper, session.risk_engine)
            orch.journal = journal
            orch.kill_switch_enabled = session.kill_switch_enabled
            result = await paper_cycle.run_paper_trading_cycle(
                symbol=symbol,
                timeframe=timeframe,
                strategy_id=strategy_id,
                settings=settings,
                orchestrator=orch,
                candle_source=source,
                journal=journal,
            )
            await persist_paper_session(db, correlation_id=result.correlation_id)
            await paper_cycle.persist_cycle_keys(db)
            _CYCLE_COUNT += 1
            _LAST_OK = utc_now().isoformat()
            _LAST_ERROR = None
            logger.info(
                "scheduler_cycle_complete",
                extra={
                    "correlation_id": result.correlation_id,
                    "signal": result.signal_direction,
                    "order_id": result.order_id,
                },
            )
    finally:
        await engine.dispose()


async def _loop() -> None:
    settings = get_settings()
    interval = settings.paper_cycle_interval_seconds
    logger.info("scheduler_started", extra={"interval_seconds": interval})
    while not _STOP.is_set():
        try:
            await _run_one_cycle()
        except Exception as exc:
            global _LAST_ERROR
            _LAST_ERROR = str(exc)
            logger.exception("scheduler_cycle_failed")
        try:
            await asyncio.wait_for(_STOP.wait(), timeout=interval)
        except TimeoutError:
            continue
    logger.info("scheduler_stopped")


def start_scheduler() -> None:
    global _TASK
    settings = get_settings()
    if not settings.enable_trading_scheduler:
        return
    if _TASK is not None and not _TASK.done():
        return
    _STOP.clear()
    _TASK = asyncio.create_task(_loop(), name="atlas-trading-scheduler")


async def stop_scheduler() -> None:
    global _TASK
    _STOP.set()
    if _TASK is not None:
        try:
            await asyncio.wait_for(_TASK, timeout=5)
        except (TimeoutError, asyncio.CancelledError):
            _TASK.cancel()
        _TASK = None
