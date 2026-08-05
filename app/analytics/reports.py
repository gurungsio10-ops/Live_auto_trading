"""Automatic daily / weekly / monthly paper performance reports + export."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.models import PerformanceReportORM
from app.analytics.performance import PerformanceEngine, PerformanceSnapshot
from app.analytics.trade_journal import ClosedTrade, TradeJournalService
from app.core.time import ensure_utc, utc_now

Period = Literal["daily", "weekly", "monthly"]


def period_window(
    period: Period, *, now: datetime | None = None
) -> tuple[datetime, datetime]:
    now = ensure_utc(now or utc_now())
    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, now


def filter_trades_in_window(
    trades: list[ClosedTrade], start: datetime, end: datetime
) -> list[ClosedTrade]:
    return [t for t in trades if start <= ensure_utc(t.exit_time) <= end]


def generate_report_payload(
    *,
    period: Period,
    trades: list[ClosedTrade],
    snapshot: PerformanceSnapshot,
    period_start: datetime,
    period_end: datetime,
) -> dict[str, Any]:
    return {
        "period": period,
        "period_start": ensure_utc(period_start).isoformat(),
        "period_end": ensure_utc(period_end).isoformat(),
        "trade_count": len(trades),
        "metrics": snapshot.to_dict(),
        "trades": [t.to_dict() for t in trades],
        "banner": "PAPER TRADING — NO REAL FUNDS",
        "generated_at": utc_now().isoformat(),
    }


async def persist_report(
    session: AsyncSession,
    *,
    period: Period,
    payload: dict[str, Any],
    period_start: datetime,
    period_end: datetime,
) -> str:
    existing = (
        await session.execute(
            select(PerformanceReportORM).where(
                PerformanceReportORM.period == period,
                PerformanceReportORM.period_start == ensure_utc(period_start),
                PerformanceReportORM.period_end == ensure_utc(period_end),
            )
        )
    ).scalar_one_or_none()
    report_id = existing.id if existing else uuid4().hex
    if existing is None:
        session.add(
            PerformanceReportORM(
                id=report_id,
                period=period,
                period_start=ensure_utc(period_start),
                period_end=ensure_utc(period_end),
                metrics=payload.get("metrics") or {},
                trade_count=int(payload.get("trade_count") or 0),
                created_at=utc_now(),
            )
        )
    else:
        existing.metrics = payload.get("metrics") or {}
        existing.trade_count = int(payload.get("trade_count") or 0)
        existing.created_at = utc_now()
    await session.commit()
    return report_id


async def build_period_report(
    session: AsyncSession,
    *,
    period: Period,
    current_balance: Decimal,
    unrealised_pnl: Decimal,
    realised_pnl: Decimal,
    starting_balance: Decimal,
    equity_curve: list[dict[str, Any]] | None = None,
    open_position_count: int = 0,
    persist: bool = True,
) -> dict[str, Any]:
    journal = TradeJournalService(session)
    all_trades = await journal.all_trades()
    start, end = period_window(period)
    window_trades = filter_trades_in_window(all_trades, start, end)
    engine = PerformanceEngine(starting_balance=starting_balance)
    # Metrics for the window use window trades; balances remain current account.
    snap = engine.compute(
        trades=window_trades,
        current_balance=current_balance,
        unrealised_pnl=unrealised_pnl,
        realised_pnl=realised_pnl,
        equity_curve=equity_curve,
        open_position_count=open_position_count,
    )
    payload = generate_report_payload(
        period=period,
        trades=window_trades,
        snapshot=snap,
        period_start=start,
        period_end=end,
    )
    if persist:
        payload["report_id"] = await persist_report(
            session,
            period=period,
            payload=payload,
            period_start=start,
            period_end=end,
        )
    return payload


def export_trades_csv(trades: list[ClosedTrade]) -> str:
    buf = io.StringIO()
    fields = [
        "trade_id",
        "strategy_name",
        "trading_pair",
        "side",
        "entry_time",
        "exit_time",
        "entry_price",
        "exit_price",
        "quantity",
        "fees",
        "slippage",
        "gross_pnl",
        "net_pnl",
        "roi_pct",
        "duration_seconds",
        "exit_reason",
        "risk_score",
        "market_regime",
        "paper_session_id",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for t in trades:
        row = t.to_dict()
        writer.writerow({k: row.get(k, "") for k in fields})
    return buf.getvalue()


def export_trades_json(trades: list[ClosedTrade]) -> str:
    return json.dumps(
        {
            "banner": "PAPER TRADING — NO REAL FUNDS",
            "trade_count": len(trades),
            "trades": [t.to_dict() for t in trades],
        },
        indent=2,
    )


def export_report_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)
