"""Continuous paper trading scheduler (never submits live money)."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.safety import get_safety_guard
from app.core.time import utc_now

logger = get_logger("trading.scheduler")

_TASK: asyncio.Task[None] | None = None
_STOP = asyncio.Event()
_LAST_OK: str | None = None
_LAST_ERROR: str | None = None
_LAST_FAILURE_AT: str | None = None
_CYCLE_COUNT = 0
_CONSECUTIVE_FAILURES = 0
_PAUSED_BY_FAILURES = False
_HEARTBEAT_AT: str | None = None
_OVERLAP_GUARD = asyncio.Lock()


def scheduler_status() -> dict[str, Any]:
    return {
        "running": _TASK is not None and not _TASK.done(),
        "last_success_at": _LAST_OK,
        "last_failure_at": _LAST_FAILURE_AT,
        "last_error": _LAST_ERROR,
        "cycles_completed": _CYCLE_COUNT,
        "consecutive_failures": _CONSECUTIVE_FAILURES,
        "paused_by_failures": _PAUSED_BY_FAILURES,
        "heartbeat_at": _HEARTBEAT_AT,
        "enabled_by_config": get_settings().enable_trading_scheduler,
    }


def clear_failure_pause() -> None:
    global _PAUSED_BY_FAILURES, _CONSECUTIVE_FAILURES
    _PAUSED_BY_FAILURES = False
    _CONSECUTIVE_FAILURES = 0


async def _persist_run(
    *,
    run_id: str,
    symbol: str,
    timeframe: str,
    strategy_id: str,
    status: str,
    correlation_id: str | None = None,
    error: str | None = None,
) -> None:
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from app.db.base import create_engine
        from app.services.cycle_lock import record_scheduler_run

        engine = create_engine()
        factory = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
        async with factory() as db:
            await record_scheduler_run(
                db,
                run_id=run_id,
                symbol=symbol,
                timeframe=timeframe,
                strategy_id=strategy_id,
                status=status,
                correlation_id=correlation_id,
                error=error,
            )
        await engine.dispose()
    except Exception:
        logger.warning("scheduler_run_persist_failed")


async def _run_one_cycle() -> None:
    global _LAST_OK, _LAST_ERROR, _LAST_FAILURE_AT, _CYCLE_COUNT
    global _CONSECUTIVE_FAILURES, _PAUSED_BY_FAILURES, _HEARTBEAT_AT

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.db.base import create_engine
    from app.execution.gateway import OrderGateway
    from app.journal.store import JournalStore
    from app.services import paper_cycle
    from app.services.market_sources import resolve_candle_source
    from app.services.paper_session import get_paper_session, persist_paper_session
    from app.services.reconciliation import is_reconciliation_healthy

    settings = get_settings()
    get_safety_guard(settings).assert_paper_only()
    _HEARTBEAT_AT = utc_now().isoformat()
    session = get_paper_session()

    if _PAUSED_BY_FAILURES:
        _LAST_ERROR = "paused_after_failure_threshold"
        return
    if session.kill_switch_enabled or settings.kill_switch_enabled:
        _LAST_ERROR = "kill_switch_active"
        return
    if session.trading_paused:
        _LAST_ERROR = "trading_paused"
        return
    if not session.trading_enabled and not settings.trading_enabled:
        _LAST_ERROR = "trading_disabled"
        return
    if settings.enable_reconciliation and not is_reconciliation_healthy():
        _LAST_ERROR = "reconciliation_halt"
        return

    symbol = settings.default_symbol
    timeframe = settings.default_timeframe
    strategy_id = session.selected_strategy_id or "ema_crossover"
    run_id = uuid4().hex
    source = await resolve_candle_source(settings)

    engine = create_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as db:
            await _persist_run(
                run_id=run_id,
                symbol=symbol,
                timeframe=timeframe,
                strategy_id=strategy_id,
                status="running",
            )
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
            _CONSECUTIVE_FAILURES = 0
            await _persist_run(
                run_id=run_id,
                symbol=symbol,
                timeframe=timeframe,
                strategy_id=strategy_id,
                status="success",
                correlation_id=result.correlation_id,
            )
            logger.info(
                "scheduler_cycle_complete",
                extra={
                    "correlation_id": result.correlation_id,
                    "signal": result.signal_direction,
                    "order_id": result.order_id,
                },
            )
    except Exception as exc:
        _LAST_ERROR = str(exc)[:500]
        _LAST_FAILURE_AT = utc_now().isoformat()
        _CONSECUTIVE_FAILURES += 1
        await _persist_run(
            run_id=run_id,
            symbol=symbol,
            timeframe=timeframe,
            strategy_id=strategy_id,
            status="failed",
            error=_LAST_ERROR,
        )
        if _CONSECUTIVE_FAILURES >= settings.scheduler_failure_threshold:
            _PAUSED_BY_FAILURES = True
            session.set_paused(True)
            logger.error(
                "scheduler_paused_after_failures",
                extra={"consecutive_failures": _CONSECUTIVE_FAILURES},
            )
        raise
    finally:
        await engine.dispose()


async def _loop() -> None:
    settings = get_settings()
    interval = settings.paper_cycle_interval_seconds
    logger.info("scheduler_started", extra={"interval_seconds": interval})
    backoff = interval
    while not _STOP.is_set():
        try:
            if _OVERLAP_GUARD.locked():
                logger.warning("scheduler_overlap_skipped")
            else:
                async with _OVERLAP_GUARD:
                    await _run_one_cycle()
            backoff = interval
        except Exception:
            global _LAST_ERROR
            logger.exception("scheduler_cycle_failed")
            # Bounded exponential backoff to avoid retry storms.
            backoff = min(backoff * 2, max(interval * 8, 300))
        try:
            await asyncio.wait_for(_STOP.wait(), timeout=backoff)
        except TimeoutError:
            continue
    logger.info("scheduler_stopped")


def start_scheduler(*, force: bool = False) -> None:
    global _TASK
    settings = get_settings()
    if not force and not settings.enable_trading_scheduler:
        return
    if _TASK is not None and not _TASK.done():
        return
    _STOP.clear()
    clear_failure_pause()
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


async def pause_scheduler() -> dict[str, Any]:
    from app.services.paper_session import get_paper_session

    get_paper_session().set_paused(True)
    return scheduler_status()


async def resume_scheduler() -> dict[str, Any]:
    from app.services.paper_session import get_paper_session

    clear_failure_pause()
    get_paper_session().set_paused(False)
    return scheduler_status()
