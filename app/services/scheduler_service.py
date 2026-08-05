"""
Paper-cycle scheduler — disabled by default, never starts live trading.

Uses DB-backed job state and an in-process lock (compatible with future Redis).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.core.time import utc_now
from app.db import base as db_base
from app.models.database.ops import SchedulerJobORM
from app.services import paper_cycle
from app.services.paper_persistence import persist_paper_session, record_cycle_run
from app.services.paper_session import get_paper_session

logger = logging.getLogger(__name__)

DEFAULT_JOB_NAME = "paper_cycle"
_OWNER = f"atlas-{uuid4().hex[:8]}"
_task: asyncio.Task[None] | None = None
_stop = asyncio.Event()


def _sessions():
    return db_base.SessionLocal


async def ensure_default_job() -> SchedulerJobORM:
    try:
        async with _sessions()() as db:
            row = await db.scalar(
                select(SchedulerJobORM).where(SchedulerJobORM.name == DEFAULT_JOB_NAME)
            )
            if row is None:
                settings = get_settings()
                row = SchedulerJobORM(
                    id=uuid4().hex,
                    name=DEFAULT_JOB_NAME,
                    enabled=False,
                    paused=False,
                    interval_seconds=int(
                        getattr(settings, "scheduler_interval_seconds", 60)
                    ),
                    symbol="BTC/USDT",
                    timeframe="1m",
                    strategy_id="ema_crossover",
                    status="idle",
                    updated_at=utc_now(),
                )
                db.add(row)
                await db.commit()
                await db.refresh(row)
            return row
    except Exception as exc:
        logger.warning("scheduler_ensure_failed", extra={"error": str(exc)[:200]})
        # Synthetic in-memory stand-in for environments without migrations.
        return SchedulerJobORM(
            id="ephemeral",
            name=DEFAULT_JOB_NAME,
            enabled=False,
            paused=False,
            interval_seconds=60,
            symbol="BTC/USDT",
            timeframe="1m",
            strategy_id="ema_crossover",
            status="unavailable",
            updated_at=utc_now(),
        )


async def get_scheduler_status() -> dict[str, Any]:
    try:
        job = await ensure_default_job()
    except Exception:
        job = None
    settings = get_settings()
    if job is None or job.id == "ephemeral" or job.status == "unavailable":
        return {
            "name": DEFAULT_JOB_NAME,
            "enabled": False,
            "paused": True,
            "status": "unavailable",
            "interval_seconds": 60,
            "symbol": "BTC/USDT",
            "timeframe": "1m",
            "strategy_id": "ema_crossover",
            "last_run_at": None,
            "next_run_at": None,
            "last_duration_ms": None,
            "last_result": None,
            "last_error": "scheduler tables unavailable — run alembic upgrade head",
            "last_correlation_id": None,
            "run_count": 0,
            "fail_count": 0,
            "worker_running": _task is not None and not _task.done(),
            "scheduler_enabled_by_config": bool(
                getattr(settings, "scheduler_enabled", False)
            ),
            "trading_mode": settings.trading_mode,
            "live_trading_enabled": settings.live_trading_enabled,
        }
    return {
        "name": job.name,
        "enabled": job.enabled,
        "paused": job.paused,
        "status": job.status,
        "interval_seconds": job.interval_seconds,
        "symbol": job.symbol,
        "timeframe": job.timeframe,
        "strategy_id": job.strategy_id,
        "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
        "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
        "last_duration_ms": job.last_duration_ms,
        "last_result": job.last_result,
        "last_error": job.last_error,
        "last_correlation_id": job.last_correlation_id,
        "run_count": job.run_count,
        "fail_count": job.fail_count,
        "worker_running": _task is not None and not _task.done(),
        "scheduler_enabled_by_config": bool(
            getattr(settings, "scheduler_enabled", False)
        ),
        "trading_mode": settings.trading_mode,
        "live_trading_enabled": settings.live_trading_enabled,
    }


async def _update_job(**fields: Any) -> SchedulerJobORM:
    async with _sessions()() as db:
        job = await db.scalar(
            select(SchedulerJobORM).where(SchedulerJobORM.name == DEFAULT_JOB_NAME)
        )
        if job is None:
            await ensure_default_job()
            job = await db.scalar(
                select(SchedulerJobORM).where(SchedulerJobORM.name == DEFAULT_JOB_NAME)
            )
        assert job is not None
        for key, value in fields.items():
            setattr(job, key, value)
        job.updated_at = utc_now()
        await db.commit()
        await db.refresh(job)
        return job


async def set_enabled(enabled: bool) -> dict[str, Any]:
    settings = get_settings()
    if settings.trading_mode != "paper" or settings.live_trading_enabled:
        raise RuntimeError("Scheduler only allowed in paper mode")
    await _update_job(
        enabled=enabled,
        paused=not enabled,
        status="running" if enabled else "stopped",
        next_run_at=utc_now() + timedelta(seconds=5) if enabled else None,
    )
    if enabled:
        await start_worker()
    else:
        await stop_worker()
    return await get_scheduler_status()


async def set_paused(paused: bool) -> dict[str, Any]:
    await _update_job(
        paused=paused,
        status="paused" if paused else "running",
    )
    return await get_scheduler_status()


async def _try_acquire_lock(job: SchedulerJobORM, db_session) -> bool:
    now = utc_now()
    if job.lock_until and job.lock_until > now and job.lock_owner != _OWNER:
        return False
    job.lock_owner = _OWNER
    job.lock_until = now + timedelta(seconds=max(30, job.interval_seconds))
    job.updated_at = now
    await db_session.commit()
    return True


async def _run_once() -> None:
    session = get_paper_session()
    settings = get_settings()
    if session.kill_switch_enabled or settings.kill_switch_enabled:
        await _update_job(
            last_result="skipped_kill_switch", last_error="kill switch active"
        )
        return
    if session.trading_paused:
        await _update_job(last_result="skipped_paused", last_error="trading paused")
        return

    async with _sessions()() as db:
        job = await db.scalar(
            select(SchedulerJobORM).where(SchedulerJobORM.name == DEFAULT_JOB_NAME)
        )
        if job is None or not job.enabled or job.paused:
            return
        if not await _try_acquire_lock(job, db):
            return
        symbol = job.symbol
        timeframe = job.timeframe
        strategy_id = job.strategy_id
        interval = job.interval_seconds

    correlation_id = uuid4().hex
    started = utc_now()
    await _update_job(status="running", last_correlation_id=correlation_id)
    try:
        # Share dashboard paper/risk engines so scheduler and UI share one account.
        from app.execution.gateway import OrderGateway

        session = get_paper_session()
        key = paper_cycle._session_key(symbol, strategy_id)
        orch = paper_cycle._CYCLE_ORCHESTRATORS.get(key)
        if orch is None:
            orch = paper_cycle.get_or_create_orchestrator(
                symbol=symbol,
                strategy_id=strategy_id,
                settings=settings,
                paper_engine=session.paper,
            )
        orch.paper = session.paper
        orch.risk = session.risk_engine
        orch.gateway = OrderGateway(session.paper, session.risk_engine)
        orch.kill_switch_enabled = session.kill_switch_enabled
        orch.settings = settings
        result = await paper_cycle.run_paper_trading_cycle(
            symbol=symbol,
            timeframe=timeframe,
            correlation_id=correlation_id,
            strategy_id=strategy_id,
            settings=settings,
            orchestrator=orch,
        )
        await persist_paper_session(
            session,
            correlation_id=correlation_id,
            journal_message="Scheduled paper cycle completed",
        )
        duration = int((utc_now() - started).total_seconds() * 1000)
        await record_cycle_run(
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            strategy_id=strategy_id,
            status="completed",
            duration_ms=duration,
            signal_direction=getattr(result, "signal_direction", None),
            order_id=getattr(result, "order_id", None),
            payload={"simulated": True},
        )
        job = await ensure_default_job()
        await _update_job(
            status="idle",
            last_run_at=started,
            next_run_at=utc_now() + timedelta(seconds=interval),
            last_duration_ms=duration,
            last_result="ok",
            last_error=None,
            last_correlation_id=correlation_id,
            run_count=job.run_count + 1,
            lock_owner=None,
            lock_until=None,
        )
        from app.monitoring.metrics import inc

        inc("scheduler_success_total")
        inc("paper_cycles_total")
    except Exception as exc:
        duration = int((utc_now() - started).total_seconds() * 1000)
        logger.exception("scheduler_cycle_failed")
        await record_cycle_run(
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            strategy_id=strategy_id,
            status="failed",
            duration_ms=duration,
            error_summary=str(exc)[:500],
        )
        job = await ensure_default_job()
        await _update_job(
            status="error",
            last_run_at=started,
            next_run_at=utc_now() + timedelta(seconds=interval),
            last_duration_ms=duration,
            last_result="error",
            last_error=str(exc)[:500],
            last_correlation_id=correlation_id,
            fail_count=job.fail_count + 1,
            lock_owner=None,
            lock_until=None,
        )
        from app.monitoring.metrics import inc

        inc("scheduler_failure_total")


async def _loop() -> None:
    logger.info("scheduler_worker_started", extra={"owner": _OWNER})
    while not _stop.is_set():
        settings = get_settings()
        if settings.trading_mode != "paper" or settings.live_trading_enabled:
            await asyncio.sleep(5)
            continue
        try:
            job = await ensure_default_job()
            if job.enabled and not job.paused:
                due = job.next_run_at is None or job.next_run_at <= utc_now()
                if due:
                    await _run_once()
        except Exception:
            logger.exception("scheduler_loop_error")
        try:
            await asyncio.wait_for(_stop.wait(), timeout=2.0)
        except TimeoutError:
            continue
    logger.info("scheduler_worker_stopped")


async def start_worker() -> None:
    global _task
    _stop.clear()
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop(), name="atlas-paper-scheduler")


async def stop_worker() -> None:
    global _task
    _stop.set()
    task = _task
    _task = None
    if task is not None and not task.done():
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=1.0)
        except (TimeoutError, asyncio.CancelledError):
            pass
