"""Performance analytics API — trade journal, metrics, equity, reports."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response

from app.analytics.performance import PerformanceEngine, build_equity_series
from app.analytics.reports import (
    build_period_report,
    export_report_json,
    export_trades_csv,
    export_trades_json,
)
from app.analytics.trade_journal import (
    ClosedTrade,
    TradeJournalService,
    risk_score_from_context,
)
from app.services.paper_session import get_paper_session

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _account_context() -> dict[str, Any]:
    session = get_paper_session()
    summary = session.portfolio_summary()
    positions = session.positions()
    unrealised = sum(
        (Decimal(str(p.get("unrealized_pnl", "0"))) for p in positions),
        Decimal("0"),
    )
    return {
        "session": session,
        "summary": summary,
        "current_balance": Decimal(str(summary.get("equity", "0"))),
        "unrealised_pnl": unrealised,
        "realised_pnl": Decimal(str(summary.get("realized_pnl", "0"))),
        "starting_balance": session._initial_cash,
        "open_position_count": int(summary.get("open_position_count") or 0),
        "equity_curve": session.equity_points(),
        "kill_switch_enabled": bool(summary.get("kill_switch_enabled")),
        "drawdown": Decimal(str(summary.get("drawdown", "0"))),
        "exposure": sum(
            (
                abs(
                    Decimal(str(p.get("quantity", "0")))
                    * Decimal(str(p.get("current_price", "0")))
                )
                for p in positions
            ),
            Decimal("0"),
        ),
    }


async def _with_db():
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.db.base import create_engine

    engine = create_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine, factory


async def _equity_points(
    db: Any, fallback: list[dict[str, Any]], limit: int = 500
) -> list[dict[str, Any]]:
    from app.services import paper_persistence as store

    snaps = await store.list_equity_snapshots(db, limit=limit)
    if not snaps:
        return fallback
    return [
        {
            "time": s["created_at"],
            "equity": s["equity"],
            "drawdown": s["drawdown"],
            "cash": s.get("cash"),
        }
        for s in reversed(snaps)
    ]


@router.get("/overview")
async def analytics_overview() -> dict[str, Any]:
    ctx = _account_context()
    engine, factory = await _with_db()
    try:
        async with factory() as db:
            trades = await TradeJournalService(db).all_trades()
            equity_curve = await _equity_points(db, ctx["equity_curve"])
            perf = PerformanceEngine(starting_balance=ctx["starting_balance"]).compute(
                trades=trades,
                current_balance=ctx["current_balance"],
                unrealised_pnl=ctx["unrealised_pnl"],
                realised_pnl=ctx["realised_pnl"],
                equity_curve=equity_curve,
                open_position_count=ctx["open_position_count"],
            )
            score = risk_score_from_context(
                drawdown=ctx["drawdown"],
                consecutive_losses=int(ctx["summary"].get("consecutive_losses") or 0),
                kill_switch=ctx["kill_switch_enabled"],
            )
            return {
                **perf.to_dict(),
                "kill_switch_enabled": ctx["kill_switch_enabled"],
                "exposure": str(ctx["exposure"].quantize(Decimal("0.01"))),
                "risk_score": str(score),
                "equity_curve": build_equity_series(
                    equity_curve, starting_balance=ctx["starting_balance"]
                ),
                "paper_session_id": ctx["session"].paper_session_id,
                "trading_mode": ctx["summary"].get("trading_mode", "paper"),
            }
    finally:
        await engine.dispose()


@router.get("/performance")
async def analytics_performance() -> dict[str, Any]:
    ctx = _account_context()
    engine, factory = await _with_db()
    try:
        async with factory() as db:
            trades = await TradeJournalService(db).all_trades()
            equity_curve = await _equity_points(db, ctx["equity_curve"])
            eng = PerformanceEngine(starting_balance=ctx["starting_balance"])
            snap = eng.compute(
                trades=trades,
                current_balance=ctx["current_balance"],
                unrealised_pnl=ctx["unrealised_pnl"],
                realised_pnl=ctx["realised_pnl"],
                equity_curve=equity_curve,
                open_position_count=ctx["open_position_count"],
            )
            return {
                "metrics": snap.to_dict(),
                "equity_curve": build_equity_series(
                    equity_curve, starting_balance=ctx["starting_balance"]
                ),
                "monthly_performance": eng.monthly_performance(trades),
                "strategies": eng.strategy_rankings(trades),
                "banner": "PAPER TRADING — NO REAL FUNDS",
            }
    finally:
        await engine.dispose()


@router.get("/equity-curve")
async def analytics_equity_curve(
    limit: int = Query(default=500, ge=1, le=5000),
) -> dict[str, Any]:
    ctx = _account_context()
    engine, factory = await _with_db()
    try:
        async with factory() as db:
            points = await _equity_points(db, ctx["equity_curve"], limit=limit)
            return build_equity_series(points, starting_balance=ctx["starting_balance"])
    finally:
        await engine.dispose()


@router.get("/trades")
async def analytics_trades(
    symbol: str | None = None,
    strategy_name: str | None = None,
    side: str | None = None,
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    engine, factory = await _with_db()
    try:
        async with factory() as db:
            trades = await TradeJournalService(db).list_trades(
                symbol=symbol,
                strategy_name=strategy_name,
                side=side,
                q=q,
                limit=limit,
                offset=offset,
            )
            return {
                "trades": [t.to_dict() for t in trades],
                "count": len(trades),
                "banner": "PAPER TRADING — SIMULATED FILLS",
            }
    finally:
        await engine.dispose()


@router.get("/trades/{trade_id}")
async def analytics_trade_detail(trade_id: str) -> dict[str, Any]:
    engine, factory = await _with_db()
    try:
        async with factory() as db:
            trade = await TradeJournalService(db).get(trade_id)
            if trade is None:
                raise HTTPException(status_code=404, detail="Trade not found")
            return trade.to_dict()
    finally:
        await engine.dispose()


@router.get("/strategies")
async def analytics_strategies() -> dict[str, Any]:
    ctx = _account_context()
    engine, factory = await _with_db()
    try:
        async with factory() as db:
            trades = await TradeJournalService(db).all_trades()
            rankings = PerformanceEngine(
                starting_balance=ctx["starting_balance"]
            ).strategy_rankings(trades)
            return {
                "strategies": rankings,
                "selected_strategy_id": ctx["session"].selected_strategy_id,
                "banner": "PAPER TRADING — NO REAL FUNDS",
            }
    finally:
        await engine.dispose()


@router.get("/risk")
async def analytics_risk() -> dict[str, Any]:
    ctx = _account_context()
    score = risk_score_from_context(
        drawdown=ctx["drawdown"],
        consecutive_losses=int(ctx["summary"].get("consecutive_losses") or 0),
        kill_switch=ctx["kill_switch_enabled"],
    )
    return {
        "exposure": str(ctx["exposure"].quantize(Decimal("0.01"))),
        "drawdown": str(ctx["drawdown"]),
        "risk_score": str(score),
        "kill_switch_enabled": ctx["kill_switch_enabled"],
        "open_position_count": ctx["open_position_count"],
        "consecutive_losses": int(ctx["summary"].get("consecutive_losses") or 0),
        "trading_paused": bool(ctx["summary"].get("trading_paused")),
        "banner": "PAPER TRADING — NO REAL FUNDS",
    }


@router.get("/reports/{period}")
async def analytics_report(
    period: Literal["daily", "weekly", "monthly"],
) -> dict[str, Any]:
    ctx = _account_context()
    engine, factory = await _with_db()
    try:
        async with factory() as db:
            return await build_period_report(
                db,
                period=period,
                current_balance=ctx["current_balance"],
                unrealised_pnl=ctx["unrealised_pnl"],
                realised_pnl=ctx["realised_pnl"],
                starting_balance=ctx["starting_balance"],
                equity_curve=ctx["equity_curve"],
                open_position_count=ctx["open_position_count"],
                persist=True,
            )
    finally:
        await engine.dispose()


@router.get("/export/trades")
async def export_trades(
    format: Literal["csv", "json"] = Query(default="csv"),
) -> Response:
    engine, factory = await _with_db()
    try:
        async with factory() as db:
            trades = await TradeJournalService(db).all_trades()
            if format == "json":
                return Response(
                    content=export_trades_json(trades),
                    media_type="application/json",
                    headers={
                        "Content-Disposition": "attachment; filename=paper_trades.json"
                    },
                )
            return PlainTextResponse(
                content=export_trades_csv(trades),
                media_type="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=paper_trades.csv"
                },
            )
    finally:
        await engine.dispose()


@router.get("/export/report/{period}")
async def export_report(
    period: Literal["daily", "weekly", "monthly"],
    format: Literal["json", "csv"] = Query(default="json"),
) -> Response:
    report = await analytics_report(period)
    if format == "csv":
        trades = [
            ClosedTrade(
                id=str(row["id"]),
                strategy_name=str(row["strategy_name"]),
                symbol=str(row["symbol"]),
                side=str(row["side"]),
                entry_time=datetime.fromisoformat(
                    str(row["entry_time"]).replace("Z", "+00:00")
                ),
                exit_time=datetime.fromisoformat(
                    str(row["exit_time"]).replace("Z", "+00:00")
                ),
                entry_price=Decimal(str(row["entry_price"])),
                exit_price=Decimal(str(row["exit_price"])),
                quantity=Decimal(str(row["quantity"])),
                fees=Decimal(str(row["fees"])),
                slippage=Decimal(str(row["slippage"])),
                gross_pnl=Decimal(str(row["gross_pnl"])),
                net_pnl=Decimal(str(row["net_pnl"])),
                roi_pct=Decimal(str(row["roi_pct"])),
                duration_seconds=int(row["duration_seconds"]),
                exit_reason=str(row["exit_reason"]),
                risk_score=Decimal(str(row["risk_score"])),
                market_regime=str(row["market_regime"]),
                paper_session_id=str(row["paper_session_id"]),
            )
            for row in (report.get("trades") or [])
        ]
        return PlainTextResponse(
            content=export_trades_csv(trades),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=paper_report_{period}.csv"
            },
        )
    return Response(
        content=export_report_json(report),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=paper_report_{period}.json"
        },
    )
