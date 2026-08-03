"""FastAPI routes for dashboard + advisory endpoints."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.ai import TradingAnalyst
from app.core.config import get_settings
from app.core.security import redact_settings
from app.execution.live_gate import LiveTradingGate
from app.monitoring import HealthRegistry, MonitoringService
from app.strategies.registry import list_strategies

router = APIRouter()
_monitoring = MonitoringService(HealthRegistry())
_analyst = TradingAnalyst()
_paper_paused = False
_kill_switch_override: bool | None = None


class KillSwitchBody(BaseModel):
    enabled: bool


class StrategyControlBody(BaseModel):
    strategy_id: str
    action: str = Field(description="start|stop|select")
    params: dict[str, Any] = Field(default_factory=dict)


@router.get("/health/ready")
async def readiness() -> dict:
    return _monitoring.readiness().to_dict()


@router.get("/portfolio/summary")
async def portfolio_summary() -> dict:
    settings = get_settings()
    return {
        "cash_balance": "10000",
        "equity": "10000",
        "realized_pnl": "0",
        "unrealized_pnl": "0",
        "daily_pnl": "0",
        "drawdown": "0",
        "trading_mode": settings.trading_mode,
        "kill_switch_enabled": (
            settings.kill_switch_enabled
            if _kill_switch_override is None
            else _kill_switch_override
        ),
        "paused": _paper_paused,
    }


@router.get("/strategies")
async def strategies() -> list[dict]:
    return [
        {
            "strategy_id": s.strategy_id,
            "name": s.name,
            "version": s.version,
            "governance_status": "PAPER",
        }
        for s in list_strategies()
    ]


@router.post("/controls/kill-switch")
async def kill_switch(body: KillSwitchBody) -> dict:
    global _kill_switch_override
    _kill_switch_override = body.enabled
    if body.enabled:
        await _monitoring.alert(
            "KILL_SWITCH_ACTIVATED", "Kill switch activated via API"
        )
    return {"kill_switch_enabled": body.enabled}


@router.post("/controls/pause")
async def pause_trading(paused: bool = True) -> dict:
    global _paper_paused
    _paper_paused = paused
    return {"paused": _paper_paused}


@router.post("/controls/strategy")
async def strategy_control(body: StrategyControlBody) -> dict:
    # Paper-only control surface — does not touch live gates.
    return {
        "strategy_id": body.strategy_id,
        "action": body.action,
        "params": body.params,
        "status": "accepted_paper_only",
    }


@router.get("/settings/risk")
async def risk_settings() -> dict:
    settings = get_settings()
    safe = redact_settings(settings)
    return {
        "trading_mode": safe["trading_mode"],
        "live_trading_enabled": safe["live_trading_enabled"],
        "kill_switch_enabled": safe["kill_switch_enabled"],
        "exchange_env": safe["exchange_env"],
        "max_risk_per_trade": str(settings.max_risk_per_trade),
        "max_position_exposure": str(settings.max_position_exposure),
        "max_portfolio_exposure": str(settings.max_portfolio_exposure),
        "max_open_positions": settings.max_open_positions,
        "max_daily_loss": str(settings.max_daily_loss),
        "max_drawdown": str(settings.max_drawdown),
        "note": "Mutating live-trading-relevant settings from UI is out of scope.",
    }


@router.get("/live-gate/status")
async def live_gate_status() -> dict:
    result = LiveTradingGate().evaluate()
    return {
        "allowed": result.allowed,
        "failed_conditions": result.failed_conditions,
        "reason_code": result.reason_code.value if result.reason_code else None,
    }


@router.post("/ai/explain-trade")
async def ai_explain_trade(record: dict[str, Any]) -> dict:
    return _analyst.explain_trade(record).to_api_dict()


@router.post("/ai/summarize-session")
async def ai_summarize(events: list[dict[str, Any]]) -> dict:
    return _analyst.summarize_session(events).to_api_dict()


@router.get("/equity-curve")
async def equity_curve() -> list[dict]:
    # Placeholder series for dashboard wiring
    return [
        {"t": f"2024-01-0{i + 1}", "equity": str(Decimal("10000") + i * 10)}
        for i in range(5)
    ]
