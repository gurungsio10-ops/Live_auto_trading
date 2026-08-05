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
    from app.monitoring.metrics import build_system_health

    health = await build_system_health()
    settings = get_settings()
    return SystemHealth(
        status=health["status"],
        trading_mode=settings.trading_mode,
        kill_switch_enabled=health["kill_switch_enabled"],
        live_trading_enabled=settings.live_trading_enabled,
        exchange_env=settings.exchange_env,
        database_ok=bool(health["database"].get("ok")),
        market_data_ok=bool(health["market_data"].get("ok")),
        risk_engine_ok=True,
        detail="paper trading durable platform",
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
async def run_cycle(body: PaperCycleBody) -> dict[str, Any]:
    settings = get_settings()
    if settings.trading_mode != "paper":
        raise LiveTradingDisabledError("Paper cycle requires TRADING_MODE=paper")
    session = get_paper_session()
    # Share the dashboard paper/risk engines so UI and cycle see one portfolio.
    from app.execution.gateway import OrderGateway

    key = paper_cycle._session_key(body.symbol, body.strategy_id)
    orch = paper_cycle._CYCLE_ORCHESTRATORS.get(key)
    if orch is None:
        orch = paper_cycle.get_or_create_orchestrator(
            symbol=body.symbol,
            strategy_id=body.strategy_id,
            settings=settings,
            paper_engine=session.paper,
        )
    orch.paper = session.paper
    orch.risk = session.risk_engine
    orch.gateway = OrderGateway(session.paper, session.risk_engine)
    orch.kill_switch_enabled = session.kill_switch_enabled
    orch.settings = settings

    result = await paper_cycle.run_paper_trading_cycle(
        symbol=body.symbol,
        timeframe=body.timeframe,
        correlation_id=body.correlation_id,
        strategy_id=body.strategy_id,
        settings=settings,
        orchestrator=orch,
    )

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
    await session._persist_safe(
        message="Paper cycle completed",
        correlation_id=result.correlation_id,
    )
    from app.monitoring.metrics import inc
    from app.services.paper_persistence import record_cycle_run

    inc("paper_cycles_total")
    if result.accepted and result.order_id:
        inc("orders_accepted_total")
    if result.risk_decision in {"REJECTED", "HALTED"}:
        inc("orders_rejected_total")
    inc("risk_decisions_total")
    await record_cycle_run(
        correlation_id=result.correlation_id,
        symbol=result.symbol,
        timeframe=result.timeframe,
        strategy_id=body.strategy_id,
        status="completed"
        if result.accepted or result.idempotent_replay
        else "rejected",
        signal_direction=result.signal_direction,
        order_id=result.order_id,
        risk_decision=result.risk_decision,
        risk_reason_code=result.risk_reason_code,
        payload={"message": result.message, "simulated": True},
    )

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
        "market_data_mode": "offline_fixture",
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
    from app.services.paper_persistence import persist_paper_session

    await persist_paper_session(
        session, journal_message="Paper account reset to starting balance"
    )
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


class SchedulerEnableBody(BaseModel):
    confirm: str = Field(..., description="Must equal ENABLE_PAPER_SCHEDULER")


class SchedulerPauseBody(BaseModel):
    paused: bool = True


@router.get("/scheduler/status", summary="Paper scheduler status")
async def scheduler_status() -> dict[str, Any]:
    from app.services.scheduler_service import get_scheduler_status

    return await get_scheduler_status()


@router.post("/scheduler/enable", summary="Enable paper scheduler (admin)")
async def scheduler_enable(
    body: SchedulerEnableBody, _: AdminAuthDep
) -> dict[str, Any]:
    if body.confirm != "ENABLE_PAPER_SCHEDULER":
        raise HTTPException(
            status_code=400,
            detail="Confirmation failed: confirm must equal ENABLE_PAPER_SCHEDULER",
        )
    from app.services.scheduler_service import set_enabled

    return await set_enabled(True)


@router.post("/scheduler/disable", summary="Disable paper scheduler (admin)")
async def scheduler_disable(_: AdminAuthDep) -> dict[str, Any]:
    from app.services.scheduler_service import set_enabled

    return await set_enabled(False)


@router.post("/scheduler/pause", summary="Pause or resume paper scheduler (admin)")
async def scheduler_pause(body: SchedulerPauseBody, _: AdminAuthDep) -> dict[str, Any]:
    from app.services.scheduler_service import set_paused

    return await set_paused(body.paused)


@router.get("/analytics/paper", summary="Paper trading analytics")
async def paper_analytics() -> dict[str, Any]:
    from app.db.base import SessionLocal
    from app.services.analytics_service import compute_paper_analytics

    async with SessionLocal() as db:
        return await compute_paper_analytics(db)


@router.get("/audit/events", summary="Durable trade journal events")
async def audit_events(pagination: PaginationDep) -> dict[str, Any]:
    from app.db.base import SessionLocal
    from app.repositories.paper_state_repository import PaperStateRepository

    async with SessionLocal() as db:
        repo = PaperStateRepository(db)
        items = await repo.list_journal(
            limit=pagination.limit, offset=pagination.offset
        )
    return {
        "items": items,
        "total": len(items),
        "limit": pagination.limit,
        "offset": pagination.offset,
    }


@router.get("/provider/health", summary="Market data provider health")
async def provider_health() -> dict[str, Any]:
    from app.market_data.providers.offline import OfflineFixtureProvider
    from app.market_data.providers.public_exchange import PublicExchangeMarketDataProvider

    offline = OfflineFixtureProvider()
    providers = [await offline.get_provider_status()]
    # Probe public provider optionally — failure must not break paper mode.
    try:
        public = PublicExchangeMarketDataProvider()
        try:
            await public.get_ticker("BTC/USDT")
            providers.append(await public.get_provider_status())
        finally:
            await public.close()
    except Exception as exc:
        providers.append(
            {
                "provider": "public_exchange",
                "mode": "public_live_market_data",
                "ok": False,
                "label": "Public market data unavailable",
                "error": str(exc)[:160],
            }
        )
    return {
        "providers": providers,
        "active_for_cycles": "offline_fixture",
        "note": (
            "Paper cycles default to offline fixtures. Public Binance data is optional "
            "and never enables live trading."
        ),
    }


@router.get("/system/health", summary="Detailed system health")
async def v1_system_health() -> dict[str, Any]:
    from app.monitoring.metrics import build_system_health

    return await build_system_health()


@router.get("/system/status/unified", summary="Unified control-centre status")
async def v1_unified_status() -> dict[str, Any]:
    from app.services.system_status import build_unified_system_status

    return await build_unified_system_status()


@router.get("/decisions", summary="Strategy decision feed")
async def v1_decision_feed(
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    from app.services.decision_feed import build_decision_feed

    items = build_decision_feed(limit=limit)
    return {"items": items, "total": len(items), "limit": limit, "offset": 0}


@router.get("/brain", summary="Atlas Brain evidence-based summary")
async def v1_atlas_brain() -> dict[str, Any]:
    from app.services.atlas_brain import build_atlas_brain

    return await build_atlas_brain()


@router.get("/execution/connector/health", summary="External execution connector health")
async def v1_execution_connector_health() -> dict[str, Any]:
    from app.execution.connectors import get_execution_connector

    return await get_execution_connector().health()


@router.get("/exchange/status", summary="Exchange adapter status (paper mock by default)")
async def v1_exchange_status() -> dict[str, Any]:
    from app.execution.adapters import get_exchange_adapter

    return await get_exchange_adapter().get_exchange_status()


@router.get("/paper/cycles", summary="Paper cycle run history")
async def paper_cycles(pagination: PaginationDep) -> dict[str, Any]:
    from sqlalchemy import select

    from app.db.base import SessionLocal
    from app.models.database.ops import PaperCycleRunORM

    async with SessionLocal() as db:
        rows = (
            await db.scalars(
                select(PaperCycleRunORM)
                .order_by(PaperCycleRunORM.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.limit)
            )
        ).all()
    items = [
        {
            "id": r.id,
            "correlation_id": r.correlation_id,
            "symbol": r.symbol,
            "timeframe": r.timeframe,
            "strategy_id": r.strategy_id,
            "status": r.status,
            "signal_direction": r.signal_direction,
            "order_id": r.order_id,
            "risk_decision": r.risk_decision,
            "risk_reason_code": r.risk_reason_code,
            "duration_ms": r.duration_ms,
            "error_summary": r.error_summary,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return _page(items, pagination)
