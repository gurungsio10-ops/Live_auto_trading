"""
Versioned paper-trading API (``/api/v1``).

Read endpoints are open for local dashboard use. Mutating system endpoints
require ``ADMIN_API_TOKEN`` via :func:`app.api.deps.require_admin_token`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import AdminAuthDep, Pagination, PaginationDep
from app.core.config import get_settings
from app.core.errors import LiveTradingDisabledError
from app.core.time import utc_now
from app.models.domain.trading import SystemHealth
from app.services import paper_cycle
from app.services.paper_session import get_paper_session, reset_paper_session

router = APIRouter(tags=["api-v1"])


class PaperCycleBody(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1m"
    correlation_id: str | None = None
    strategy_id: str = "ema_crossover"


class PaperResetBody(BaseModel):
    confirm: str = Field(
        ...,
        description="Must equal RESET_PAPER_ACCOUNT to proceed",
    )


class KillSwitchBody(BaseModel):
    reason: str = "manual"


def _page(items: list[Any], pagination: Pagination) -> dict[str, Any]:
    total = len(items)
    slice_ = items[pagination.offset : pagination.offset + pagination.limit]
    return {
        "items": slice_,
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }


@router.get(
    "/health",
    summary="Liveness probe",
    description="Process is up. Does not verify database connectivity.",
)
async def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "kill_switch_enabled": get_paper_session().kill_switch_enabled
        or settings.kill_switch_enabled,
        "timestamp": utc_now().isoformat(),
    }


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Ready for paper trading requests when mode is paper.",
)
async def ready() -> dict[str, Any]:
    settings = get_settings()
    if settings.trading_mode != "paper":
        raise HTTPException(
            status_code=503, detail="Not ready: trading_mode is not paper"
        )
    return {"status": "ready", "trading_mode": settings.trading_mode}


@router.get("/system/status", response_model=SystemHealth)
async def system_status() -> SystemHealth:
    settings = get_settings()
    session = get_paper_session()
    kill = session.kill_switch_enabled or settings.kill_switch_enabled
    db_ok = True
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from app.db.base import create_engine

        engine = create_engine()
        factory = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
        async with factory() as db:
            await db.execute(text("SELECT 1"))
        await engine.dispose()
    except Exception:
        db_ok = False
    return SystemHealth(
        status="halted" if kill else "ok",
        trading_mode=settings.trading_mode,
        runtime_mode=settings.runtime_mode.value,
        kill_switch_enabled=kill,
        live_trading_enabled=settings.live_trading_enabled,
        exchange_env=settings.exchange_env,
        database_ok=db_ok,
        market_data_ok=True,
        risk_engine_ok=True,
        detail="paper trading vertical slice",
    )


@router.get("/market/candles")
async def market_candles(
    symbol: str = Query(default="BTC/USDT"),
    timeframe: str = Query(default="1m"),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    source = paper_cycle.OfflineCandleSource()
    candles = await source.load_closed_candles(symbol, timeframe, limit=limit)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "items": [
            {
                "open_time": c.open_time.isoformat(),
                "open": str(c.open),
                "high": str(c.high),
                "low": str(c.low),
                "close": str(c.close),
                "volume": str(c.volume),
                "is_closed": c.is_closed,
            }
            for c in candles
        ],
        "simulated": True,
        "note": "Offline deterministic candles for paper mode (not a live exchange feed).",
    }


@router.get("/strategy/latest")
async def strategy_latest() -> dict[str, Any]:
    signal = paper_cycle.last_signal()
    runs = paper_cycle.strategy_runs(limit=1)
    if signal is None and not runs:
        return {"signal": None, "strategy_run": None}
    return {
        "signal": None
        if signal is None
        else {
            "strategy_name": signal.strategy_name,
            "strategy_version": signal.strategy_version,
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "confidence": str(signal.confidence),
            "confidence_kind": signal.metadata.get(
                "confidence_kind", "rule_derived_not_predictive"
            ),
            "reason": signal.entry_rationale,
            "indicators": signal.metadata.get("indicators", {}),
            "candle_timestamp": signal.metadata.get("candle_timestamp"),
            "calculation_timestamp": signal.metadata.get("calculation_timestamp"),
        },
        "strategy_run": None
        if not runs
        else {
            "id": runs[0].id,
            "strategy_name": runs[0].strategy_name,
            "strategy_version": runs[0].strategy_version,
            "symbol": runs[0].symbol,
            "timeframe": runs[0].timeframe,
            "direction": runs[0].direction.value,
            "candle_open_time": runs[0].candle_open_time.isoformat(),
            "correlation_id": runs[0].correlation_id,
        },
    }


@router.get("/signals")
async def signals(pagination: PaginationDep) -> dict[str, Any]:
    items = get_paper_session().signals()
    # Prefer cycle signal history if session empty after cycle-only path
    return _page(items, pagination)


@router.get("/risk/decisions")
async def risk_decisions(pagination: PaginationDep) -> dict[str, Any]:
    return _page(get_paper_session().risk_events(), pagination)


@router.get("/orders")
async def orders(pagination: PaginationDep) -> dict[str, Any]:
    return _page(get_paper_session().orders(), pagination)


@router.get("/fills")
async def fills(pagination: PaginationDep) -> dict[str, Any]:
    session = get_paper_session()
    items = [
        {
            "id": f.id,
            "order_id": f.order_id,
            "symbol": f.symbol,
            "side": f.side.value if hasattr(f.side, "value") else str(f.side),
            "quantity": str(f.quantity),
            "price": str(f.price),
            "fee": str(f.fee),
            "timestamp": f.timestamp.isoformat(),
            "simulated": True,
        }
        for f in session.paper.state.fills
    ]
    items = list(reversed(items))
    return _page(items, pagination)


@router.get("/portfolio")
async def portfolio() -> dict[str, Any]:
    summary = get_paper_session().portfolio_summary()
    summary["simulated"] = True
    summary["disclaimer"] = (
        "Paper / simulated results only. Not financial advice. "
        "Past or simulated performance does not guarantee future results."
    )
    return summary


@router.get("/portfolio/history")
async def portfolio_history(pagination: PaginationDep) -> dict[str, Any]:
    return _page(get_paper_session().equity_points(), pagination)


@router.get(
    "/recovery/status",
    summary="Durable recovery / reconciliation status",
    description=(
        "Backend source of truth for restart recovery: recon halt, kill switch, "
        "risk health flags, and last reconciliation result. Frontend must not "
        "recompute balances or P&L."
    ),
)
async def recovery_status() -> dict[str, Any]:
    from app.core.config import get_settings
    from app.services import paper_cycle
    from app.services.reconciliation import reconciliation_status
    from app.services.trading_scheduler import scheduler_status

    settings = get_settings()
    session = get_paper_session()
    rs = session.risk_engine.state
    recon = reconciliation_status()
    from decimal import Decimal

    last = paper_cycle.last_cycle_result()
    equity = session.paper.state.cash + sum(
        (p.quantity * p.current_price for p in session.paper.state.positions.values()),
        Decimal("0"),
    )
    try:
        sched = scheduler_status()
    except Exception:
        sched = {"running": False, "detail": "unavailable"}
    return {
        "recovery": {
            "runtime_mode": settings.runtime_mode.value
            if hasattr(settings.runtime_mode, "value")
            else str(settings.runtime_mode),
            "trading_mode": settings.trading_mode,
            "reconciliation": recon,
            "kill_switch_enabled": session.kill_switch_enabled,
            "trading_enabled": session.trading_enabled,
            "trading_paused": session.trading_paused,
            "last_hydrated_at": session.last_hydrated_at,
            "persistence_status": ("healthy" if rs.database_healthy else "degraded"),
            "database_status": "ok" if rs.database_healthy else "unhealthy",
            "scheduler": sched,
            "market_data_stale": not rs.market_data_healthy,
            "last_cycle": None
            if last is None
            else {
                "correlation_id": last.correlation_id,
                "accepted": last.accepted,
                "signal_direction": last.signal_direction,
                "order_status": last.order_status,
                "reject_reason": last.reject_reason,
                "idempotent_replay": last.idempotent_replay,
                "message": last.message,
            },
            "risk": {
                "reconciliation_healthy": rs.reconciliation_healthy,
                "risk_engine_healthy": rs.risk_engine_healthy,
                "database_healthy": rs.database_healthy,
                "market_data_healthy": rs.market_data_healthy,
                "circuit_breaker_open": rs.circuit_breaker_open,
                "circuit_breaker_reason": rs.circuit_breaker_reason,
                "seen_idempotency_keys": len(rs.seen_idempotency_keys),
            },
            "portfolio": {
                "cash": str(session.paper.state.cash),
                "equity": str(equity),
                "realized_pnl": str(session.paper.state.realized_pnl),
                "peak_equity": str(session._peak_equity),
                "daily_start_equity": str(session._daily_start_equity),
                "open_positions": len(session.paper.state.positions),
                "open_orders": sum(
                    1
                    for o in session.paper.state.orders.values()
                    if o.status.value
                    in {
                        "SUBMITTED",
                        "PARTIALLY_FILLED",
                        "APPROVED",
                        "RISK_PENDING",
                    }
                ),
                "fills": len(session.paper.state.fills),
                "positions": [
                    {
                        "symbol": p.symbol,
                        "quantity": str(p.quantity),
                        "entry_price": str(p.entry_price),
                        "current_price": str(p.current_price),
                        "unrealized_pnl": str(p.unrealized_pnl),
                    }
                    for p in session.paper.state.positions.values()
                ],
            },
            "strategy": {
                "selected_strategy_id": session.selected_strategy_id,
                "running_strategies": sorted(session.running_strategies),
            },
            "last_successful_reconciliation": (
                recon.get("last_run_at")
                if recon.get("healthy") and not recon.get("halted")
                else None
            ),
            "source_of_truth": "backend",
            "simulated": True,
        }
    }


@router.post(
    "/reconciliation/clear-halt",
    summary="Clear durable reconciliation halt after corrective action",
)
async def clear_recon_halt(_: AdminAuthDep) -> dict[str, Any]:
    from app.services.reconciliation import (
        clear_reconciliation_halt_persisted,
        reconciliation_status,
    )

    await clear_reconciliation_halt_persisted()
    return {"ok": True, "reconciliation": reconciliation_status()}


@router.get("/journal")
async def journal(pagination: PaginationDep) -> dict[str, Any]:
    export = get_paper_session().journal_export()
    # journal_export returns a file-shaped payload; also include structured rows.
    session = get_paper_session()
    rows: list[dict[str, Any]] = []
    for s in session.signal_log:
        rows.append({"event_type": "SIGNAL", **s})
    for r in session.risk_event_log:
        rows.append({"event_type": "RISK", **r})
    for o in session.order_history:
        rows.append(
            {
                "event_type": "ORDER",
                "id": o.id,
                "symbol": o.symbol,
                "status": o.status.value,
                "side": o.side.value,
            }
        )
    cycle = paper_cycle.last_cycle_result()
    if cycle is not None:
        rows.append(
            {
                "event_type": "CYCLE",
                "correlation_id": cycle.correlation_id,
                "direction": cycle.signal_direction,
                "order_id": cycle.order_id,
                "message": cycle.message,
            }
        )
    payload = _page(list(reversed(rows)), pagination)
    payload["export_filename"] = export.get("filename")
    return payload


@router.post(
    "/paper/cycle/run",
    summary="Run one deterministic paper trading cycle",
    description=(
        "Loads closed candles, evaluates EMA crossover, routes any order intent "
        "through the central risk engine, simulates a paper fill, and updates "
        "portfolio/journal views. Paper mode only."
    ),
)
async def run_cycle(body: PaperCycleBody, _: AdminAuthDep) -> dict[str, Any]:
    settings = get_settings()
    if settings.trading_mode != "paper":
        raise LiveTradingDisabledError("Paper cycle requires TRADING_MODE=paper")
    session = get_paper_session()
    if session.kill_switch_enabled or settings.kill_switch_enabled:
        raise HTTPException(
            status_code=423, detail="Kill switch active — trading blocked"
        )
    # Share the dashboard paper/risk engines so UI and cycle see one portfolio.
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.db.base import create_engine
    from app.execution.gateway import OrderGateway
    from app.journal.store import JournalStore

    engine = create_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with factory() as db:
            journal = JournalStore(db)
            key = paper_cycle._session_key(body.symbol, body.strategy_id)
            orch = paper_cycle._CYCLE_ORCHESTRATORS.get(key)
            if orch is None:
                orch = paper_cycle.get_or_create_orchestrator(
                    symbol=body.symbol,
                    strategy_id=body.strategy_id,
                    settings=settings,
                    paper_engine=session.paper,
                    journal=journal,
                )
            orch.paper = session.paper
            orch.risk = session.risk_engine
            orch.gateway = OrderGateway(session.paper, session.risk_engine)
            orch.journal = journal
            orch.kill_switch_enabled = session.kill_switch_enabled
            orch.settings = settings

            result = await paper_cycle.run_paper_trading_cycle(
                symbol=body.symbol,
                timeframe=body.timeframe,
                correlation_id=body.correlation_id,
                strategy_id=body.strategy_id,
                settings=settings,
                orchestrator=orch,
                journal=journal,
            )
    finally:
        await engine.dispose()

    # Mirror cycle artefacts into the dashboard session views.
    signal = paper_cycle.last_signal()
    if signal is not None:
        session.signal_log.append(
            {
                "id": result.strategy_run_id or result.correlation_id,
                "strategy_name": signal.strategy_name,
                "strategy_version": signal.strategy_version,
                "symbol": signal.symbol,
                "direction": signal.direction.value,
                "confidence": str(signal.confidence),
                "reason": signal.entry_rationale,
                "timestamp": signal.timestamp.isoformat(),
                "indicators": signal.metadata.get("indicators", {}),
            }
        )
    if result.order_id:
        order = session.paper.state.orders.get(result.order_id)
        if order is not None and order not in session.order_history:
            session.order_history.append(order)
        if result.risk_decision:
            session.risk_event_log.append(
                {
                    "id": result.order_id,
                    "decision": result.risk_decision,
                    "reason_code": result.risk_reason_code,
                    "symbol": body.symbol,
                    "timestamp": utc_now().isoformat(),
                    "message": result.signal_reason,
                }
            )
    session._record_equity_point()

    return {
        "correlation_id": result.correlation_id,
        "symbol": result.symbol,
        "timeframe": result.timeframe,
        "strategy_name": result.strategy_name,
        "strategy_version": result.strategy_version,
        "strategy_run_id": result.strategy_run_id,
        "candle_open_time": result.candle_open_time.isoformat()
        if result.candle_open_time
        else None,
        "signal_direction": result.signal_direction,
        "signal_reason": result.signal_reason,
        "accepted": result.accepted,
        "reject_reason": result.reject_reason,
        "order_id": result.order_id,
        "order_status": result.order_status,
        "risk_decision": result.risk_decision,
        "risk_reason_code": result.risk_reason_code,
        "portfolio": result.portfolio,
        "indicators": result.indicators,
        "idempotent_replay": result.idempotent_replay,
        "message": result.message,
        "simulated": True,
    }


@router.post(
    "/system/kill-switch/activate",
    summary="Activate emergency kill switch",
)
async def activate_kill_switch(body: KillSwitchBody, _: AdminAuthDep) -> dict[str, Any]:
    result = get_paper_session().set_kill_switch(True)
    return {**result, "reason": body.reason, "kill_switch_enabled": True}


@router.post(
    "/system/kill-switch/deactivate",
    summary="Deactivate emergency kill switch",
)
async def deactivate_kill_switch(
    body: KillSwitchBody, _: AdminAuthDep
) -> dict[str, Any]:
    result = get_paper_session().set_kill_switch(False)
    return {**result, "reason": body.reason, "kill_switch_enabled": False}


@router.post(
    "/paper/reset",
    summary="Reset paper account",
    description="Requires confirm=RESET_PAPER_ACCOUNT. Destroys in-memory paper state.",
)
async def paper_reset(body: PaperResetBody, _: AdminAuthDep) -> dict[str, Any]:
    if body.confirm != "RESET_PAPER_ACCOUNT":
        raise HTTPException(
            status_code=400,
            detail="Confirmation failed: confirm must equal RESET_PAPER_ACCOUNT",
        )
    paper_cycle.reset_cycle_state()
    session = reset_paper_session()
    return {
        "ok": True,
        "cash": str(session.paper.state.cash),
        "message": "Paper account reset to starting balance",
        "simulated": True,
    }


@router.get("/live/execute")
async def live_execute_blocked() -> None:
    """Explicit guard — live execution is not available."""
    raise LiveTradingDisabledError(
        "Live order execution is not implemented. Use paper cycle endpoints."
    )
