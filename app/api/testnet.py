"""Binance Spot Testnet API surface (read + controlled cycle)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import AdminAuthDep
from app.core.config import get_settings
from app.core.errors import ConfigurationError, LiveTradingDisabledError
from app.monitoring.probes import probe_database, probe_from_registry, probe_redis
from app.services import testnet_runtime as tn
from app.services.paper_session import get_paper_session

router = APIRouter(tags=["testnet"])


class TestnetCycleBody(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1m"
    use_sample_candles: bool = Field(
        default=True,
        description="When true, run one offline-engineered candle cycle (no network).",
    )


class KillBody(BaseModel):
    enabled: bool = True
    reason: str = "manual"


@router.get("/testnet/status")
async def testnet_status() -> dict[str, Any]:
    settings = get_settings()
    runtime = tn.get_testnet_runtime()
    snap = runtime.dashboard_snapshot() if runtime else None
    return {
        "exchange_env": settings.exchange_env,
        "trading_mode": settings.trading_mode,
        "has_credentials": settings.has_exchange_credentials,
        "rest_url": settings.binance_testnet_rest_url,
        "ws_url": settings.binance_testnet_ws_url,
        "runtime_active": runtime is not None,
        "dashboard": snap,
        "live_disabled": True,
        "note": "Spot Testnet only — live trading is disabled.",
    }


@router.get("/testnet/diagnostics")
async def testnet_diagnostics() -> dict[str, Any]:
    settings = get_settings()
    runtime = tn.get_testnet_runtime()
    registry = runtime.health if runtime else None
    db = await probe_database()
    redis = await probe_redis()
    if registry is not None:
        registry.db_healthy = db.healthy
        registry.redis_healthy = redis.healthy
        diag = probe_from_registry(
            registry,
            execution_latency_ms=runtime.stats.last_latency_ms if runtime else None,
            exchange_connected=settings.exchange_env == "testnet"
            and settings.has_exchange_credentials,
            reconcile_healthy=(
                runtime.reconciler.reconciliation_healthy
                if runtime and runtime.reconciler
                else True
            ),
        )
    else:
        from app.monitoring.health import HealthRegistry

        reg = HealthRegistry(db_healthy=db.healthy, redis_healthy=redis.healthy)
        diag = probe_from_registry(reg)
    payload = diag.to_dict()
    payload["database"] = {"healthy": db.healthy, "detail": db.detail}
    payload["redis"] = {"healthy": redis.healthy, "detail": redis.detail}
    return payload


@router.post("/testnet/runtime/start")
async def start_runtime(_: AdminAuthDep) -> dict[str, Any]:
    settings = get_settings()
    if settings.exchange_env == "live" or settings.trading_mode == "live":
        raise LiveTradingDisabledError("Live trading disabled")
    if settings.exchange_env not in {"paper", "testnet"}:
        raise ConfigurationError("Unsupported exchange env")
    existing = tn.get_testnet_runtime()
    if existing is not None:
        return {"ok": True, "already_running": True}
    # Paper env uses injectable mock-free runtime for dashboard demos;
    # testnet requires credentials (or will raise).
    runtime = tn.init_testnet_runtime(settings=settings)
    if settings.exchange_env == "testnet":
        await runtime.start()
    else:
        runtime._ensure_backend()
        runtime._running = True
    return {"ok": True, "exchange_env": settings.exchange_env}


@router.post("/testnet/cycle/run")
async def run_testnet_cycle(body: TestnetCycleBody) -> dict[str, Any]:
    """
    Run one deterministic cycle.

    With ``use_sample_candles=true`` (default), uses offline EMA-crossover
    fixtures and the configured execution backend (paper or mocked testnet).
    """
    settings = get_settings()
    if settings.trading_mode == "live" or settings.exchange_env == "live":
        raise LiveTradingDisabledError("Live trading disabled")

    runtime = tn.get_testnet_runtime()
    if runtime is None:
        runtime = tn.init_testnet_runtime(
            settings=settings, symbol=body.symbol, strategy_id="ema_crossover"
        )
        runtime._ensure_backend()

    if body.use_sample_candles:
        from app.services.sample_market import build_ema_crossover_candles

        candles = build_ema_crossover_candles(
            symbol=body.symbol, interval=body.timeframe, force_buy_on_last=True
        )
        # Warm window without trading intermediate bars
        runtime._window = list(candles[:-1])
        result = await runtime.process_candle(candles[-1])
    else:
        raise HTTPException(
            status_code=501,
            detail="Live stream cycle requires an attached WebSocket transport",
        )

    snap = runtime.dashboard_snapshot()
    # Mirror into paper session for existing dashboard widgets when in paper env.
    if settings.exchange_env == "paper":
        session = get_paper_session()
        session.signal_log.extend(runtime._signals[-1:])
    return {"cycle": result, "dashboard": snap, "simulated_testnet": True}


@router.post("/testnet/kill-switch")
async def testnet_kill_switch(body: KillBody, _: AdminAuthDep) -> dict[str, Any]:
    runtime = tn.get_testnet_runtime()
    if runtime is None:
        # Fall back to paper session kill switch
        return get_paper_session().set_kill_switch(body.enabled)
    return runtime.set_kill_switch(body.enabled)


@router.get("/testnet/dashboard")
async def testnet_dashboard() -> dict[str, Any]:
    runtime = tn.get_testnet_runtime()
    if runtime is None:
        return {
            "runtime_active": False,
            "message": "Start testnet runtime or run a cycle first",
            "exchange_env": get_settings().exchange_env,
        }
    return runtime.dashboard_snapshot()
