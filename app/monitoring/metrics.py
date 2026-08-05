"""Prometheus-compatible metrics and dependency health probes."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.config import get_settings
from app.core.time import utc_now
from app.db import base as db_base
from app.services.paper_session import get_paper_session
from app.services.scheduler_service import get_scheduler_status

# Process counters (reset on restart — durable analytics live in DB).
_COUNTERS: dict[str, int] = {
    "risk_decisions_total": 0,
    "orders_accepted_total": 0,
    "orders_rejected_total": 0,
    "scheduler_success_total": 0,
    "scheduler_failure_total": 0,
    "paper_cycles_total": 0,
}


def inc(name: str, amount: int = 1) -> None:
    _COUNTERS[name] = _COUNTERS.get(name, 0) + amount


async def probe_database() -> dict[str, Any]:
    started = utc_now()
    try:
        async with db_base.SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        ms = int((utc_now() - started).total_seconds() * 1000)
        return {"ok": True, "latency_ms": ms}
    except Exception as exc:
        return {"ok": False, "error": "database_unreachable", "detail": str(exc)[:120]}


async def build_system_health() -> dict[str, Any]:
    settings = get_settings()
    session = get_paper_session()
    db = await probe_database()
    sched = await get_scheduler_status()
    kill = session.kill_switch_enabled or settings.kill_switch_enabled
    return {
        "status": "halted" if kill else ("degraded" if not db["ok"] else "ok"),
        "version": "0.2.0",
        "environment": settings.app_env,
        "trading_mode": settings.trading_mode,
        "live_trading_enabled": settings.live_trading_enabled,
        "kill_switch_enabled": kill,
        "exchange_env": settings.exchange_env,
        "database": db,
        "market_data": {
            "provider": "offline_fixture|binance_public",
            "default_mode": "simulated_or_public",
            "ok": True,
            "label": "Paper cycles use offline fixtures unless public provider configured",
        },
        "scheduler": {
            "enabled": sched["enabled"],
            "paused": sched["paused"],
            "status": sched["status"],
            "last_result": sched["last_result"],
            "worker_running": sched["worker_running"],
        },
        "risk_engine_ok": True,
        "paper_equity": session.portfolio_summary()["equity"],
        "timestamp": utc_now().isoformat(),
    }


def render_prometheus() -> str:
    settings = get_settings()
    session = get_paper_session()
    lines = [
        "# HELP atlas_info Static Atlas build labels",
        "# TYPE atlas_info gauge",
        f'atlas_info{{version="0.2.0",trading_mode="{settings.trading_mode}",app_env="{settings.app_env}"}} 1',
        "# HELP atlas_kill_switch Kill switch engaged (1/0)",
        "# TYPE atlas_kill_switch gauge",
        f"atlas_kill_switch {1 if session.kill_switch_enabled else 0}",
        "# HELP atlas_paper_equity Current paper equity",
        "# TYPE atlas_paper_equity gauge",
        f"atlas_paper_equity {session.portfolio_summary()['equity']}",
    ]
    for key, value in _COUNTERS.items():
        lines.append(f"# HELP atlas_{key} Counter")
        lines.append(f"# TYPE atlas_{key} counter")
        lines.append(f"atlas_{key} {value}")
    return "\n".join(lines) + "\n"
