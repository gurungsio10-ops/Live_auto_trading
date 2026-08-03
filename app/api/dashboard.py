"""
Live dashboard endpoints (root-level, matching the Next.js proxy contract).

These are backed by the in-memory :class:`PaperSession`, which routes every order
through the risk engine and paper execution engine. Mounted without the ``/api``
prefix so the frontend's ``backendFetch`` paths resolve here.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.paper_session import get_paper_session

router = APIRouter(tags=["dashboard"])


class KillSwitchBody(BaseModel):
    enabled: bool


class PauseBody(BaseModel):
    paused: bool = True


class SelectStrategyBody(BaseModel):
    strategy_id: str


class ParamsBody(BaseModel):
    paper_params: dict[str, Any] = Field(default_factory=dict)


class ClosePositionBody(BaseModel):
    symbol: str


class OrderTicketBody(BaseModel):
    symbol: str
    side: str
    order_type: str
    quantity: str
    price: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    strategy_name: str | None = None


class BacktestBody(BaseModel):
    strategy_id: str
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    start: str = ""
    end: str = ""
    initial_cash: str | None = None


@router.get("/portfolio")
async def portfolio() -> dict:
    return get_paper_session().portfolio_summary()


@router.get("/portfolio/equity-curve")
async def equity_curve() -> list[dict]:
    return get_paper_session().equity_points()


@router.get("/positions")
async def positions() -> list[dict]:
    return get_paper_session().positions()


@router.post("/positions/close")
async def close_position(body: ClosePositionBody) -> list[dict]:
    return await get_paper_session().close_position(body.symbol)


@router.get("/orders")
async def orders(
    status: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    date: str | None = Query(default=None),
) -> list[dict]:
    return get_paper_session().orders(status=status, symbol=symbol, date=date)


@router.post("/orders")
async def place_order(body: OrderTicketBody) -> dict:
    return await get_paper_session().place_order(body.model_dump())


@router.get("/signals")
async def signals() -> list[dict]:
    return get_paper_session().signals()


@router.get("/risk-events")
async def risk_events() -> list[dict]:
    return get_paper_session().risk_events()


@router.get("/strategies")
async def strategies() -> list[dict]:
    return get_paper_session().strategies()


@router.post("/strategies/select")
async def select_strategy(body: SelectStrategyBody) -> dict:
    try:
        return get_paper_session().select_strategy(body.strategy_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Strategy not found") from None


@router.post("/strategies/{strategy_id}/start")
async def start_strategy(strategy_id: str) -> dict:
    try:
        return await get_paper_session().start_strategy(strategy_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Strategy not found") from None


@router.post("/strategies/{strategy_id}/stop")
async def stop_strategy(strategy_id: str) -> dict:
    try:
        return get_paper_session().stop_strategy(strategy_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Strategy not found") from None


@router.patch("/strategies/{strategy_id}/params")
async def update_params(strategy_id: str, body: ParamsBody) -> dict:
    session = get_paper_session()
    try:
        return session.update_params(strategy_id, body.paper_params)
    except KeyError:
        raise HTTPException(status_code=404, detail="Strategy not found") from None
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/kill-switch")
async def kill_switch(body: KillSwitchBody) -> dict:
    return get_paper_session().set_kill_switch(body.enabled)


@router.post("/trading/pause")
async def pause_trading(body: PauseBody) -> dict:
    return get_paper_session().set_paused(body.paused)


@router.get("/settings")
async def settings_view() -> dict:
    return get_paper_session().settings_view()


@router.get("/journal/export")
async def journal_export() -> dict:
    return get_paper_session().journal_export()


@router.get("/backtests")
async def backtests() -> list[dict]:
    return get_paper_session().backtests()


@router.post("/backtests")
async def run_backtest(body: BacktestBody) -> dict:
    return get_paper_session().run_backtest(body.model_dump())
