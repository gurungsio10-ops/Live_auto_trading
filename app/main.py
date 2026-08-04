"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.mvp import router as mvp_router
from app.api.routes import router as api_router
from app.api.v1 import router as v1_router
from app.core.config import get_settings
from app.core.errors import AtlasError, ConfigurationError, LiveTradingDisabledError
from app.core.logging import configure_logging
from app.core.security import redact_settings
from app.services.paper_session import bootstrap_paper_runtime, get_paper_session


async def _probe_database() -> bool:
    try:
        from sqlalchemy import text

        from app.db.base import session_scope

        async with session_scope() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _reconciliation_loop(stop: asyncio.Event) -> None:
    from app.services.reconciliation import run_paper_reconciliation

    settings = get_settings()
    while not stop.is_set():
        try:
            await run_paper_reconciliation()
        except Exception:
            pass
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=settings.reconciliation_interval_seconds
            )
        except TimeoutError:
            continue


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    from app.services.trading_scheduler import start_scheduler, stop_scheduler

    settings = get_settings()
    settings.assert_startup_safe()
    await bootstrap_paper_runtime()
    stop = asyncio.Event()
    recon_task: asyncio.Task[None] | None = None
    if settings.enable_reconciliation:
        recon_task = asyncio.create_task(
            _reconciliation_loop(stop), name="atlas-reconciliation"
        )
    start_scheduler()
    try:
        yield
    finally:
        stop.set()
        await stop_scheduler()
        if recon_task is not None:
            recon_task.cancel()
            try:
                await recon_task
            except asyncio.CancelledError:
                pass
        from app.db.base import dispose_shared_engine

        try:
            await dispose_shared_engine()
        except Exception:
            pass


settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="0.5.0",
    description=(
        "Project Atlas — personal cryptocurrency paper/testnet trading platform. "
        "AI is advisory only. Every order passes through the central risk engine. "
        "Live money trading is hard-blocked."
    ),
    lifespan=lifespan,
)

# Strict CORS for the ops dashboard origins only.
_origins = [
    o.strip() for o in (settings.cors_allowed_origins or "").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Token"],
)

app.include_router(api_router, prefix="/api")
app.include_router(mvp_router, prefix="/api")
app.include_router(v1_router, prefix="/api/v1")
app.include_router(auth_router)
app.include_router(dashboard_router)


@app.exception_handler(LiveTradingDisabledError)
async def live_disabled_handler(
    _request: Request, exc: LiveTradingDisabledError
) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": str(exc)})


@app.exception_handler(ConfigurationError)
async def config_error_handler(
    _request: Request, exc: ConfigurationError
) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(AtlasError)
async def atlas_error_handler(_request: Request, exc: AtlasError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
@app.get("/health/live")
async def health() -> dict[str, Any]:
    from app.market_data.hub import get_market_data_hub
    from app.services.reconciliation import reconciliation_status
    from app.services.trading_scheduler import scheduler_status

    s = get_settings()
    session = get_paper_session()
    return {
        "status": "ok",
        "trading_mode": s.trading_mode,
        "runtime_mode": s.runtime_mode.value,
        "live_trading_enabled": s.live_trading_enabled,
        "kill_switch_enabled": session.kill_switch_enabled or s.kill_switch_enabled,
        "exchange_env": s.exchange_env,
        "scheduler": scheduler_status(),
        "reconciliation": reconciliation_status(),
        "market_data": get_market_data_hub().status(),
        "banner": "PAPER TRADING — NO REAL FUNDS",
    }


@app.get("/ready")
@app.get("/health/ready")
async def ready() -> dict[str, Any]:
    from app.services.reconciliation import is_reconciliation_healthy

    s = get_settings()
    if s.runtime_mode.value == "LIVE" or s.trading_mode == "live":
        return {
            "status": "not_ready",
            "reason": "LIVE runtime is hard-blocked",
            "runtime_mode": s.runtime_mode.value,
            "database_ok": False,
        }
    db_ok = await _probe_database()
    if not db_ok:
        return {
            "status": "not_ready",
            "reason": "database probe failed",
            "runtime_mode": s.runtime_mode.value,
            "database_ok": False,
        }
    recon_ok = is_reconciliation_healthy()
    if s.enable_reconciliation and not recon_ok:
        return {
            "status": "not_ready",
            "reason": "reconciliation unhealthy",
            "runtime_mode": s.runtime_mode.value,
            "database_ok": True,
            "reconciliation_healthy": False,
        }
    return {
        "status": "ready",
        "trading_mode": s.trading_mode,
        "runtime_mode": s.runtime_mode.value,
        "database_ok": True,
        "reconciliation_healthy": recon_ok,
    }


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    """Lightweight JSON metrics (Prometheus optional later)."""
    from app.services.paper_cycle import last_cycle_result
    from app.services.reconciliation import reconciliation_status
    from app.services.trading_scheduler import scheduler_status

    session = get_paper_session()
    cycle = last_cycle_result()
    return {
        "orders": len(session.orders()),
        "positions": len(session.positions()),
        "signals": len(session.signals()),
        "risk_events": len(session.risk_events()),
        "kill_switch_enabled": session.kill_switch_enabled,
        "scheduler": scheduler_status(),
        "reconciliation": reconciliation_status(),
        "last_cycle_signal": cycle.signal_direction if cycle else None,
        "last_cycle": (
            {
                "correlation_id": cycle.correlation_id,
                "signal_direction": cycle.signal_direction,
                "order_id": cycle.order_id,
                "risk_decision": cycle.risk_decision,
                "idempotent_replay": cycle.idempotent_replay,
                "reject_reason": cycle.reject_reason,
            }
            if cycle
            else None
        ),
        "live_orders_allowed": False,
    }


@app.get("/config/safe")
async def safe_config() -> dict[str, Any]:
    payload = redact_settings(settings)
    payload["runtime_mode"] = get_settings().runtime_mode.value
    return payload


@app.get("/api/portfolio/manager")
async def portfolio_manager_view() -> dict[str, Any]:
    from app.portfolio.manager import get_portfolio_manager

    return get_portfolio_manager().snapshot()


@app.get("/api/market/status")
async def market_status() -> dict[str, Any]:
    from app.market_data.hub import get_market_data_hub

    return get_market_data_hub().status()


@app.get("/api/market/derivatives/advisory")
async def market_derivatives_advisory(symbol: str | None = None) -> dict[str, Any]:
    from app.market_data.hub import get_market_data_hub

    s = get_settings()
    hub = get_market_data_hub()
    snap = await hub.fetch_advisory_derivatives(symbol or s.default_symbol)
    return snap.to_dict()


@app.get("/ops/stream")
async def ops_stream() -> Any:
    """Server-sent events for near-real-time ops dashboard updates."""
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    from app.market_data.hub import get_market_data_hub
    from app.portfolio.manager import get_portfolio_manager
    from app.services.paper_cycle import last_cycle_result
    from app.services.reconciliation import reconciliation_status
    from app.services.trading_scheduler import scheduler_status

    if not get_settings().enable_ops_sse:
        return JSONResponse(
            status_code=503, content={"detail": "ops SSE disabled by configuration"}
        )

    from app.core.time import utc_now

    async def event_generator() -> Any:
        while True:
            cycle = last_cycle_result()
            payload = {
                "ts": utc_now().isoformat(),
                "portfolio": get_portfolio_manager().snapshot(),
                "scheduler": scheduler_status(),
                "reconciliation": reconciliation_status(),
                "market_data": get_market_data_hub().status(),
                "last_cycle": (
                    {
                        "signal_direction": cycle.signal_direction,
                        "order_id": cycle.order_id,
                        "idempotent_replay": cycle.idempotent_replay,
                    }
                    if cycle
                    else None
                ),
                "banner": "PAPER TRADING — NO REAL FUNDS",
            }
            yield f"data: {json.dumps(payload, default=str)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
