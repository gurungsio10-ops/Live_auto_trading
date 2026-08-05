"""Persistent closed-trade journal for paper performance analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.models import ClosedTradeORM
from app.core.time import ensure_utc, utc_now
from app.models.domain.enums import OrderSide
from app.models.domain.trading import Fill, Order, Position


def _q(value: Decimal, places: str = "0.00000001") -> Decimal:
    return Decimal(value).quantize(Decimal(places))


def _d(value: Decimal) -> str:
    return str(_q(Decimal(value)))


@dataclass
class ClosedTrade:
    """Round-trip paper trade record."""

    id: str
    strategy_name: str
    symbol: str
    side: str
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    fees: Decimal
    slippage: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    roi_pct: Decimal
    duration_seconds: int
    exit_reason: str
    risk_score: Decimal
    market_regime: str
    paper_session_id: str
    order_id: str | None = None
    fill_id: str | None = None
    correlation_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trade_id": self.id,
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "trading_pair": self.symbol,
            "side": self.side,
            "buy_sell": self.side,
            "entry_time": ensure_utc(self.entry_time).isoformat(),
            "exit_time": ensure_utc(self.exit_time).isoformat(),
            "entry_price": _d(self.entry_price),
            "exit_price": _d(self.exit_price),
            "quantity": _d(self.quantity),
            "fees": _d(self.fees),
            "slippage": _d(self.slippage),
            "gross_pnl": _d(self.gross_pnl),
            "net_pnl": _d(self.net_pnl),
            "roi_pct": str(self.roi_pct.quantize(Decimal("0.0001"))),
            "duration_seconds": self.duration_seconds,
            "trade_duration": self.duration_seconds,
            "exit_reason": self.exit_reason,
            "risk_score": str(self.risk_score.quantize(Decimal("0.01"))),
            "market_regime": self.market_regime,
            "paper_session_id": self.paper_session_id,
            "order_id": self.order_id,
            "fill_id": self.fill_id,
            "correlation_id": self.correlation_id,
            "payload": dict(self.payload),
        }


def build_closed_trade_from_exit(
    *,
    position: Position,
    order: Order,
    fill: Fill,
    fee_rate: Decimal,
    slippage_rate: Decimal,
    paper_session_id: str,
    exit_reason: str = "signal_exit",
    risk_score: Decimal = Decimal("0"),
    market_regime: str = "unclassified",
    correlation_id: str | None = None,
) -> ClosedTrade:
    """Build a closed-trade record from a SELL fill against an open position."""
    qty = Decimal(fill.quantity)
    entry = Decimal(position.entry_price)
    exit_px = Decimal(fill.price)
    exit_fee = Decimal(fill.fee)
    # Approximate round-trip fees: estimated entry taker fee + exit fee.
    entry_fee = _q(entry * qty * fee_rate)
    fees = _q(entry_fee + exit_fee)
    slippage = _q(exit_px * qty * slippage_rate)
    gross = _q((exit_px - entry) * qty)
    net = _q(gross - fees)
    notional = entry * qty
    roi = (
        _q((net / notional) * Decimal("100"), "0.0001")
        if notional > 0
        else Decimal("0")
    )
    entry_time = ensure_utc(position.opened_at)
    exit_time = ensure_utc(fill.timestamp)
    duration = max(0, int((exit_time - entry_time).total_seconds()))
    trade_id = f"ct-{fill.id}"
    side = "sell" if order.side == OrderSide.SELL else str(order.side.value).lower()
    return ClosedTrade(
        id=trade_id,
        strategy_name=order.strategy_name or position.strategy_name or "unknown",
        symbol=order.symbol,
        side=side,
        entry_time=entry_time,
        exit_time=exit_time,
        entry_price=entry,
        exit_price=exit_px,
        quantity=qty,
        fees=fees,
        slippage=slippage,
        gross_pnl=gross,
        net_pnl=net,
        roi_pct=roi,
        duration_seconds=duration,
        exit_reason=exit_reason,
        risk_score=Decimal(risk_score),
        market_regime=market_regime,
        paper_session_id=paper_session_id,
        order_id=order.id,
        fill_id=fill.id,
        correlation_id=correlation_id,
        payload={
            "entry_fee_est": _d(entry_fee),
            "exit_fee": _d(exit_fee),
            "reduce_only": bool((order.metadata or {}).get("reduce_only")),
        },
    )


class TradeJournalService:
    """CRUD for durable closed trades (idempotent by trade id)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(self, trade: ClosedTrade, *, commit: bool = True) -> bool:
        """Persist trade. Returns False if already present (no duplicate)."""
        existing = await self.session.get(ClosedTradeORM, trade.id)
        if existing is not None:
            return False
        self.session.add(
            ClosedTradeORM(
                id=trade.id,
                strategy_name=trade.strategy_name,
                symbol=trade.symbol,
                side=trade.side,
                entry_time=ensure_utc(trade.entry_time),
                exit_time=ensure_utc(trade.exit_time),
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                quantity=trade.quantity,
                fees=trade.fees,
                slippage=trade.slippage,
                gross_pnl=trade.gross_pnl,
                net_pnl=trade.net_pnl,
                roi_pct=trade.roi_pct,
                duration_seconds=trade.duration_seconds,
                exit_reason=trade.exit_reason,
                risk_score=trade.risk_score,
                market_regime=trade.market_regime,
                paper_session_id=trade.paper_session_id,
                order_id=trade.order_id,
                fill_id=trade.fill_id,
                correlation_id=trade.correlation_id,
                payload=dict(trade.payload),
                created_at=utc_now(),
            )
        )
        if commit:
            await self.session.commit()
        return True

    async def get(self, trade_id: str) -> ClosedTrade | None:
        row = await self.session.get(ClosedTradeORM, trade_id)
        return _from_orm(row) if row else None

    async def list_trades(
        self,
        *,
        symbol: str | None = None,
        strategy_name: str | None = None,
        side: str | None = None,
        q: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ClosedTrade]:
        stmt = select(ClosedTradeORM).order_by(ClosedTradeORM.exit_time.desc())
        if symbol:
            stmt = stmt.where(ClosedTradeORM.symbol == symbol.upper())
        if strategy_name:
            stmt = stmt.where(ClosedTradeORM.strategy_name == strategy_name)
        if side:
            stmt = stmt.where(ClosedTradeORM.side == side.lower())
        if q:
            needle = f"%{q}%"
            stmt = stmt.where(
                or_(
                    ClosedTradeORM.symbol.ilike(needle),
                    ClosedTradeORM.strategy_name.ilike(needle),
                    ClosedTradeORM.id.ilike(needle),
                )
            )
        stmt = stmt.offset(max(0, offset)).limit(min(max(limit, 1), 500))
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_from_orm(r) for r in rows]

    async def all_trades(self) -> list[ClosedTrade]:
        rows = (
            (
                await self.session.execute(
                    select(ClosedTradeORM).order_by(ClosedTradeORM.exit_time.asc())
                )
            )
            .scalars()
            .all()
        )
        return [_from_orm(r) for r in rows]


def _from_orm(row: ClosedTradeORM) -> ClosedTrade:
    return ClosedTrade(
        id=row.id,
        strategy_name=row.strategy_name,
        symbol=row.symbol,
        side=row.side,
        entry_time=row.entry_time,
        exit_time=row.exit_time,
        entry_price=Decimal(str(row.entry_price)),
        exit_price=Decimal(str(row.exit_price)),
        quantity=Decimal(str(row.quantity)),
        fees=Decimal(str(row.fees)),
        slippage=Decimal(str(row.slippage)),
        gross_pnl=Decimal(str(row.gross_pnl)),
        net_pnl=Decimal(str(row.net_pnl)),
        roi_pct=Decimal(str(row.roi_pct)),
        duration_seconds=int(row.duration_seconds),
        exit_reason=row.exit_reason,
        risk_score=Decimal(str(row.risk_score)),
        market_regime=row.market_regime,
        paper_session_id=row.paper_session_id,
        order_id=row.order_id,
        fill_id=row.fill_id,
        correlation_id=row.correlation_id,
        payload=dict(row.payload or {}),
    )


def classify_market_regime(
    *, rsi: Decimal | None = None, atr_pct: Decimal | None = None
) -> str:
    """Lightweight regime label for journal enrichment (not ML)."""
    if rsi is None and atr_pct is None:
        return "unclassified"
    if rsi is not None:
        if rsi >= 70:
            return "overbought"
        if rsi <= 30:
            return "oversold"
    if atr_pct is not None:
        if atr_pct >= Decimal("0.03"):
            return "high_volatility"
        if atr_pct <= Decimal("0.005"):
            return "low_volatility"
    return "ranging"


def risk_score_from_context(
    *,
    drawdown: Decimal,
    consecutive_losses: int,
    kill_switch: bool,
) -> Decimal:
    """0-100 heuristic risk score for journal / dashboard."""
    if kill_switch:
        return Decimal("100")
    score = Decimal("10")
    score += min(Decimal("40"), drawdown * Decimal("100"))
    score += Decimal(min(consecutive_losses, 10)) * Decimal("5")
    return min(Decimal("100"), score.quantize(Decimal("0.01")))
