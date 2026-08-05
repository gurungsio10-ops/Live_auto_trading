"""Unified Atlas system status — backend-driven, never invented by the UI."""

from __future__ import annotations

from enum import Enum
from typing import Any

from app.core.config import get_settings
from app.core.time import utc_now
from app.monitoring.metrics import probe_database
from app.services import paper_cycle
from app.services.paper_session import get_paper_session
from app.services.scheduler_service import get_scheduler_status


class ComponentState(str, Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"
    PAUSED = "PAUSED"
    DISCONNECTED = "DISCONNECTED"
    IDLE = "IDLE"
    ON = "ON"
    OFF = "OFF"
    OK = "OK"


def _market_data_status() -> dict[str, Any]:
    """Honest market-data posture for paper mode."""
    settings = get_settings()
    # Public provider may be available via Binance REST without keys; cycles still
    # default to offline fixtures unless explicitly configured otherwise.
    use_public = bool(getattr(settings, "market_data_public_enabled", False))
    if use_public:
        return {
            "state": ComponentState.RUNNING.value,
            "provider": "binance_public",
            "mode": "public_live_market_data",
            "ok": True,
            "label": "Public exchange market data (trading remains paper)",
            "last_update": None,
            "latency_ms": None,
            "stale": False,
        }
    return {
        "state": ComponentState.OK.value,
        "provider": "offline_fixture",
        "mode": "simulated",
        "ok": True,
        "label": "Offline fixtures (simulated — not live exchange prices)",
        "last_update": None,
        "latency_ms": None,
        "stale": False,
    }


def _engine_state(session: Any, sched: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if session.kill_switch_enabled:
        return ComponentState.PAUSED.value, ["Kill switch is ON — new orders blocked"]
    if session.trading_paused:
        return ComponentState.PAUSED.value, ["Trading paused — new orders blocked"]
    worker = bool(sched.get("worker_running"))
    enabled = bool(sched.get("enabled")) and not bool(sched.get("paused"))
    # Prefer scheduler/cycle activity as engine RUNNING signal.
    if worker and enabled:
        return ComponentState.RUNNING.value, []
    # Active running strategies on the paper session (selected alone is not RUNNING)
    try:
        strategies = session.strategies() if hasattr(session, "strategies") else []
        if any(s.get("running") for s in strategies):
            return ComponentState.RUNNING.value, []
    except Exception:
        pass
    last = paper_cycle.last_cycle_result()
    if last is not None and not last.idempotent_replay:
        # Recently ran a cycle but no continuous engine — STOPPED is honest.
        reasons.append("Last paper cycle completed; continuous engine is not running")
    return ComponentState.STOPPED.value, reasons or [
        "Paper engine idle — enable scheduler or run a manual cycle"
    ]


def _overall_status(
    *,
    kill: bool,
    db_ok: bool,
    market_ok: bool,
    engine: str,
    sched_status: str,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if kill:
        return ComponentState.PAUSED.value, ["Kill switch active"]
    if not db_ok:
        reasons.append("Database unreachable")
    if not market_ok:
        reasons.append("Market data provider unhealthy")
    if sched_status == "unavailable":
        reasons.append("Scheduler tables unavailable — run alembic upgrade head")
    if engine == ComponentState.ERROR.value:
        reasons.append("Engine error")
    if reasons:
        return ComponentState.DEGRADED.value, reasons
    if engine == ComponentState.RUNNING.value:
        return ComponentState.RUNNING.value, []
    # Paper mode with healthy deps but idle engine is OK, not degraded.
    return ComponentState.OK.value, []


async def build_unified_system_status() -> dict[str, Any]:
    """Single source of truth for dashboard status chips and System Health."""
    settings = get_settings()
    session = get_paper_session()
    db = await probe_database()
    sched = await get_scheduler_status()
    market = _market_data_status()
    kill = bool(session.kill_switch_enabled or settings.kill_switch_enabled)
    engine, engine_reasons = _engine_state(session, sched)

    strategies = []
    try:
        strategies = session.strategies() if hasattr(session, "strategies") else []
    except Exception:
        strategies = []
    active_strategy_count = sum(1 for s in strategies if s.get("running") or s.get("selected"))

    last = paper_cycle.last_cycle_result()
    last_success = None
    last_failed = None
    if last is not None:
        payload = {
            "correlation_id": last.correlation_id,
            "symbol": last.symbol,
            "direction": last.signal_direction,
            "accepted": last.accepted,
            "order_id": last.order_id,
            "risk_decision": last.risk_decision,
            "message": last.message,
            "idempotent_replay": last.idempotent_replay,
        }
        if last.accepted or last.idempotent_replay:
            last_success = payload
        if last.reject_reason and not last.idempotent_replay:
            last_failed = payload

    overall, degraded_reasons = _overall_status(
        kill=kill,
        db_ok=bool(db.get("ok")),
        market_ok=bool(market.get("ok")),
        engine=engine,
        sched_status=str(sched.get("status") or ""),
    )
    # Only attach engine reasons that indicate a fault — idle is not degraded.
    fault_engine_reasons = [
        r
        for r in engine_reasons
        if "idle" not in r.lower() and "manual cycle" not in r.lower()
    ]
    degraded_reasons = list(dict.fromkeys([*degraded_reasons, *fault_engine_reasons]))

    # Exchange boundary — paper mock only unless live gates pass (they do not by default).
    exchange = {
        "state": ComponentState.OK.value,
        "adapter": "MockExchangeAdapter",
        "mode": "paper",
        "connected": True,
        "label": "Paper mock exchange (no live credentials required)",
    }

    sched_state = ComponentState.OFF.value
    if sched.get("status") == "unavailable":
        sched_state = ComponentState.DISCONNECTED.value
    elif sched.get("paused"):
        sched_state = ComponentState.PAUSED.value
    elif sched.get("worker_running") or str(sched.get("status")).lower() == "running":
        sched_state = ComponentState.RUNNING.value
    elif sched.get("enabled"):
        sched_state = ComponentState.IDLE.value

    portfolio = session.portfolio_summary()
    return {
        "status": overall,
        "trading_mode": settings.trading_mode,
        "engine": {
            "state": engine,
            "reasons": engine_reasons,
        },
        "system": {
            "state": overall,
            "degraded_reasons": degraded_reasons,
        },
        "database": {
            "state": ComponentState.OK.value if db.get("ok") else ComponentState.ERROR.value,
            "ok": bool(db.get("ok")),
            "latency_ms": db.get("latency_ms"),
            "error": db.get("error"),
        },
        "market_data": market,
        "exchange": exchange,
        "scheduler": {
            "state": sched_state,
            "enabled": sched.get("enabled"),
            "paused": sched.get("paused"),
            "status": sched.get("status"),
            "last_result": sched.get("last_result"),
            "last_error": sched.get("last_error"),
            "worker_running": sched.get("worker_running"),
            "last_run_at": sched.get("last_run_at"),
            "next_run_at": sched.get("next_run_at"),
            "interval_seconds": sched.get("interval_seconds"),
            "run_count": sched.get("run_count"),
            "fail_count": sched.get("fail_count"),
        },
        "kill_switch": {
            "state": ComponentState.ON.value if kill else ComponentState.OFF.value,
            "enabled": kill,
        },
        "trading_paused": bool(session.trading_paused),
        "last_successful_cycle": last_success,
        "last_failed_cycle": last_failed,
        "latency_ms": db.get("latency_ms"),
        "last_market_data_timestamp": market.get("last_update"),
        "active_strategy_count": active_strategy_count,
        "degraded_reasons": degraded_reasons,
        "paper_equity": portfolio.get("equity"),
        "open_position_count": portfolio.get("open_position_count"),
        "live_trading_enabled": settings.live_trading_enabled,
        "exchange_env": settings.exchange_env,
        "version": "0.2.0",
        "environment": settings.app_env,
        "timestamp": utc_now().isoformat(),
    }
