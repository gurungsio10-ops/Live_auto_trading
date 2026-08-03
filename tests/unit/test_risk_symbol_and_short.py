"""Additional risk rules: allowlist, short-selling, leverage."""

from __future__ import annotations

from decimal import Decimal

from app.core.config import Settings
from app.core.time import utc_now
from app.models.domain.enums import OrderSide, OrderType, RiskDecision, RiskReasonCode
from app.models.domain.trading import OrderRequest, PortfolioState, Position
from app.risk.engine import RiskContext, RiskEngine, RiskEngineState


def _portfolio(positions: list[Position] | None = None) -> PortfolioState:
    return PortfolioState(
        cash_balance=Decimal("10000"),
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
        open_positions=positions or [],
    )


def _req(**kwargs) -> OrderRequest:
    base = dict(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        idempotency_key="k1",
    )
    base.update(kwargs)
    return OrderRequest(**base)


def test_symbol_not_allowed() -> None:
    settings = Settings(supported_symbols=("BTC/USDT",), _env_file=None)
    engine = RiskEngine(settings=settings, state=RiskEngineState())
    ev = engine.evaluate(
        _req(symbol="ETH/USDT", idempotency_key="sym1"),
        RiskContext(
            portfolio=_portfolio(),
            mark_price=Decimal("3000"),
            market_data_ts=utc_now(),
        ),
    )
    assert ev.decision == RiskDecision.REJECTED
    assert ev.reason_code == RiskReasonCode.SYMBOL_NOT_ALLOWED


def test_short_selling_rejected() -> None:
    settings = Settings(_env_file=None)
    engine = RiskEngine(settings=settings, state=RiskEngineState())
    ev = engine.evaluate(
        _req(
            side=OrderSide.SELL,
            reduce_only=False,
            idempotency_key="short1",
            quantity=Decimal("0.01"),
        ),
        RiskContext(
            portfolio=_portfolio(),
            mark_price=Decimal("65000"),
            market_data_ts=utc_now(),
        ),
    )
    assert ev.decision == RiskDecision.REJECTED
    assert ev.reason_code == RiskReasonCode.SHORT_SELLING_DISABLED


def test_reduce_only_sell_with_position_allowed() -> None:
    settings = Settings(_env_file=None)
    engine = RiskEngine(settings=settings, state=RiskEngineState())
    pos = Position(
        symbol="BTC/USDT",
        quantity=Decimal("0.01"),
        entry_price=Decimal("65000"),
        current_price=Decimal("65000"),
        unrealized_pnl=Decimal("0"),
        opened_at=utc_now(),
    )
    ev = engine.evaluate(
        _req(
            side=OrderSide.SELL,
            reduce_only=True,
            stop_loss=Decimal("64900"),
            idempotency_key="exit1",
            quantity=Decimal("0.01"),
        ),
        RiskContext(
            portfolio=_portfolio([pos]),
            mark_price=Decimal("65000"),
            market_data_ts=utc_now(),
        ),
    )
    assert ev.decision in {RiskDecision.APPROVED, RiskDecision.REDUCED}
