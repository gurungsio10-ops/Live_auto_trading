"""
MVP paper-trading API surface under ``/api/*`` (checklist contract).

Delegates to existing paper session / cycle services. Live trading remains disabled.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import AdminAuthDep
from app.core.config import get_settings
from app.core.safety import get_safety_guard
from app.core.security import redact_settings
from app.core.time import utc_now
from app.market_data.facade import public_market_status
from app.services import paper_cycle
from app.services.paper_session import get_paper_session, reset_paper_session

router = APIRouter(tags=["mvp-api"])

# Process-local trading_enabled override (start/stop). Seeded from settings.
_TRADING_ENABLED: bool | None = None
_SYSTEM_EVENTS: list[dict[str, Any]] = []


def _trading_enabled() -> bool:
    global _TRADING_ENABLED
    if _TRADING_ENABLED is None:
        _TRADING_ENABLED = bool(get_settings().trading_enabled)
    return _TRADING_ENABLED


def set_trading_enabled(enabled: bool) -> bool:
    global _TRADING_ENABLED
    _TRADING_ENABLED = enabled
    _emit("TRADING_ENABLED", {"enabled": enabled})
    return enabled


def _emit(kind: str, payload: dict[str, Any]) -> None:
    _SYSTEM_EVENTS.append(
        {
            "id": utc_now().isoformat(),
            "kind": kind,
            "timestamp": utc_now().isoformat(),
            "payload": payload,
        }
    )
    if len(_SYSTEM_EVENTS) > 500:
        del _SYSTEM_EVENTS[:-500]


class ConfirmBody(BaseModel):
    confirm: str


class CycleBody(BaseModel):
    symbol: str | None = None
    timeframe: str | None = None
    strategy_id: str = "ema_crossover"
    confirm: str | None = None
    correlation_id: str | None = None


class KillSwitchBody(BaseModel):
    enabled: bool = True
    reason: str = "manual"
    confirm: str | None = None


@router.get("/health")
async def health() -> dict[str, Any]:
    settings = get_settings()
    session = get_paper_session()
    return {
        "status": "ok",
        "trading_mode": settings.trading_mode,
        "trading_enabled": _trading_enabled(),
        "kill_switch_enabled": session.kill_switch_enabled
        or settings.kill_switch_enabled,
        "timestamp": utc_now().isoformat(),
        "paper_banner": "PAPER TRADING — NO REAL FUNDS",
    }


@router.get("/readiness")
async def readiness() -> dict[str, Any]:
    settings = get_settings()
    if settings.trading_mode != "paper":
        raise HTTPException(
            status_code=503, detail="Not ready: trading_mode is not paper"
        )
    # Reuse main DB probe pattern via paper session existence.
    return {
        "status": "ready",
        "trading_mode": settings.trading_mode,
        "runtime_mode": settings.runtime_mode.value,
        "trading_enabled": _trading_enabled(),
        "timestamp": utc_now().isoformat(),
    }


@router.get("/config/public")
async def config_public() -> dict[str, Any]:
    settings = get_settings()
    safe = redact_settings(settings)
    return {
        **{
            k: safe.get(k)
            for k in safe
            if "key" not in k.lower() and "secret" not in k.lower()
        },
        "default_symbol": settings.default_symbol,
        "default_timeframe": settings.default_timeframe,
        "starting_balance": str(settings.paper_starting_balance),
        "trading_enabled": _trading_enabled(),
        "safety": get_safety_guard(settings).public_status(),
        "market": public_market_status(settings),
        "banner": "PAPER TRADING — NO REAL FUNDS",
    }


@router.get("/market/candles")
async def market_candles(
    symbol: str | None = None,
    timeframe: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    settings = get_settings()
    symbol = symbol or settings.default_symbol
    timeframe = timeframe or settings.default_timeframe
    source = paper_cycle.OfflineCandleSource()
    candles = await source.load_closed_candles(symbol, timeframe, limit=limit)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "simulated": True,
        "source": "offline_fixture",
        "items": [
            {
                "open_time": c.open_time.isoformat(),
                "open": str(c.open),
                "high": str(c.high),
                "low": str(c.low),
                "close": str(c.close),
                "volume": str(c.volume),
            }
            for c in candles
        ],
    }


@router.get("/signals")
async def signals(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    session = get_paper_session()
    items = list(session.signals())[:limit]
    last = paper_cycle.last_signal()
    if last is not None:
        items = [
            {
                "strategy_name": last.strategy_name,
                "direction": last.direction.value,
                "confidence": str(last.confidence),
                "reason": last.entry_rationale,
                "symbol": last.symbol,
                "timestamp": last.timestamp.isoformat(),
                "indicators": last.metadata.get("indicators", {}),
            },
            *items,
        ]
    return {"items": items[:limit], "total": len(items)}


@router.get("/orders")
async def orders() -> dict[str, Any]:
    return {"items": get_paper_session().orders(), "simulated": True}


@router.get("/trades")
async def trades() -> dict[str, Any]:
    """Fills alias for MVP checklist ``/api/trades``."""
    session = get_paper_session()
    filled = [
        o for o in session.orders() if str(o.get("status", "")).upper() == "FILLED"
    ]
    return {"items": filled, "simulated": True}


@router.get("/positions")
async def positions() -> dict[str, Any]:
    return {"items": get_paper_session().positions(), "simulated": True}


@router.get("/portfolio")
async def portfolio() -> dict[str, Any]:
    summary = get_paper_session().portfolio_summary()
    summary["trading_enabled"] = _trading_enabled()
    summary["banner"] = "PAPER TRADING — NO REAL FUNDS"
    summary["simulated"] = True
    return summary


@router.get("/portfolio/equity-curve")
async def equity_curve() -> dict[str, Any]:
    return {"items": get_paper_session().equity_points(), "simulated": True}


@router.get("/system/events")
async def system_events(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    return {
        "items": list(reversed(_SYSTEM_EVENTS[-limit:])),
        "total": len(_SYSTEM_EVENTS),
    }


@router.post("/trading/cycle")
async def trading_cycle(body: CycleBody, _: AdminAuthDep) -> dict[str, Any]:
    settings = get_settings()
    get_safety_guard(settings).assert_paper_only()
    session = get_paper_session()
    if session.kill_switch_enabled or settings.kill_switch_enabled:
        raise HTTPException(
            status_code=423, detail="Kill switch active — trading blocked"
        )
    one_shot = (body.confirm or "").strip() == "RUN_ONE_CYCLE"
    if not _trading_enabled() and not one_shot:
        raise HTTPException(
            status_code=409,
            detail=(
                "TRADING_ENABLED is false. POST /api/trading/start with "
                "confirm=START_PAPER_TRADING, or pass confirm=RUN_ONE_CYCLE."
            ),
        )
    symbol = body.symbol or settings.default_symbol
    timeframe = body.timeframe or settings.default_timeframe

    # Share dashboard paper/risk engines so UI and cycle see one portfolio.
    from app.execution.gateway import OrderGateway

    key = paper_cycle._session_key(symbol, body.strategy_id)
    orch = paper_cycle._CYCLE_ORCHESTRATORS.get(key)
    if orch is None:
        orch = paper_cycle.get_or_create_orchestrator(
            symbol=symbol,
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
        symbol=symbol,
        timeframe=timeframe,
        strategy_id=body.strategy_id,
        correlation_id=body.correlation_id,
        settings=settings,
        orchestrator=orch,
    )
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
    session._record_equity_point()

    payload = {
        "correlation_id": result.correlation_id,
        "symbol": result.symbol,
        "timeframe": result.timeframe,
        "strategy_name": result.strategy_name,
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
        "banner": "PAPER TRADING — NO REAL FUNDS",
    }
    _emit(
        "PAPER_CYCLE",
        {"correlation_id": result.correlation_id, "signal": result.signal_direction},
    )
    return payload


@router.post("/trading/start")
async def trading_start(body: ConfirmBody, _: AdminAuthDep) -> dict[str, Any]:
    if body.confirm != "START_PAPER_TRADING":
        raise HTTPException(
            status_code=400, detail="confirm must equal START_PAPER_TRADING"
        )
    get_safety_guard().assert_paper_only()
    set_trading_enabled(True)
    from app.services.trading_scheduler import scheduler_status, start_scheduler

    # Enable continuous cycles when operator starts paper trading.
    get_settings().enable_trading_scheduler = True
    start_scheduler()
    return {
        "trading_enabled": True,
        "mode": "paper",
        "scheduler": scheduler_status(),
        "banner": "PAPER TRADING — NO REAL FUNDS",
    }


@router.post("/trading/stop")
async def trading_stop(body: ConfirmBody, _: AdminAuthDep) -> dict[str, Any]:
    if body.confirm != "STOP_PAPER_TRADING":
        raise HTTPException(
            status_code=400, detail="confirm must equal STOP_PAPER_TRADING"
        )
    set_trading_enabled(False)
    return {"trading_enabled": False, "mode": "paper"}


@router.post("/trading/kill-switch")
async def trading_kill_switch(body: KillSwitchBody, _: AdminAuthDep) -> dict[str, Any]:
    if body.enabled and body.confirm not in (None, "ACTIVATE_KILL_SWITCH"):
        # Allow without confirm for emergency, but prefer confirm when provided wrong.
        pass
    result = get_paper_session().set_kill_switch(body.enabled)
    if body.enabled:
        set_trading_enabled(False)
    _emit("KILL_SWITCH", {"enabled": body.enabled, "reason": body.reason})
    return {**result, "trading_enabled": _trading_enabled()}


@router.post("/paper/reset")
async def paper_reset(body: ConfirmBody, _: AdminAuthDep) -> dict[str, Any]:
    if body.confirm != "RESET_PAPER_ACCOUNT":
        raise HTTPException(
            status_code=400, detail="confirm must equal RESET_PAPER_ACCOUNT"
        )
    paper_cycle.reset_cycle_state()
    session = reset_paper_session()
    set_trading_enabled(False)
    _emit("PAPER_RESET", {})
    return {
        "reset": True,
        "cash_balance": str(session.paper.state.cash),
        "trading_enabled": False,
        "simulated": True,
    }
