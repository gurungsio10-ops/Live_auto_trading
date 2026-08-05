"""Prometheus-compatible metrics and dependency health probes."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.config import get_settings
from app.core.time import utc_now
from app.db import base as db_base
from app.services.paper_session import get_paper_session

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
    """Backward-compatible health blob enriched with unified status fields."""
    from app.services.system_status import build_unified_system_status

    unified = await build_unified_system_status()
    # Preserve legacy keys used by existing frontend/tests.
    legacy_status = "halted" if unified["kill_switch"]["enabled"] else (
        "degraded" if unified["status"] == "DEGRADED" else (
            "ok" if unified["status"] in {"OK", "RUNNING"} else "degraded"
        )
    )
    return {
        "status": legacy_status,
        "unified_status": unified["status"],
        "version": unified["version"],
        "environment": unified["environment"],
        "trading_mode": unified["trading_mode"],
        "live_trading_enabled": unified["live_trading_enabled"],
        "kill_switch_enabled": unified["kill_switch"]["enabled"],
        "exchange_env": unified["exchange_env"],
        "database": {
            "ok": unified["database"]["ok"],
            "latency_ms": unified["database"].get("latency_ms"),
            "error": unified["database"].get("error"),
            "state": unified["database"]["state"],
        },
        "market_data": {
            "provider": unified["market_data"]["provider"],
            "default_mode": unified["market_data"]["mode"],
            "ok": unified["market_data"]["ok"],
            "label": unified["market_data"]["label"],
            "state": unified["market_data"]["state"],
        },
        "scheduler": {
            "enabled": unified["scheduler"]["enabled"],
            "paused": unified["scheduler"]["paused"],
            "status": unified["scheduler"]["status"],
            "last_result": unified["scheduler"]["last_result"],
            "worker_running": unified["scheduler"]["worker_running"],
            "state": unified["scheduler"]["state"],
            "next_run_at": unified["scheduler"].get("next_run_at"),
            "last_run_at": unified["scheduler"].get("last_run_at"),
        },
        "engine": unified["engine"],
        "exchange": unified["exchange"],
        "degraded_reasons": unified["degraded_reasons"],
        "last_successful_cycle": unified["last_successful_cycle"],
        "last_failed_cycle": unified["last_failed_cycle"],
        "active_strategy_count": unified["active_strategy_count"],
        "risk_engine_ok": True,
        "paper_equity": unified["paper_equity"],
        "timestamp": unified["timestamp"],
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
