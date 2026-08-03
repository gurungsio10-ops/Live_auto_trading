"""Phase 7: paper trading lifecycle + replay determinism."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.execution.gateway import OrderGateway, RiskBlockedError
from app.execution.paper import PaperConfig, PaperTradingEngine
from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
)
from app.models.domain.trading import OrderRequest, PortfolioState, RiskEvaluation
from app.risk.engine import RiskContext, RiskEngine, RiskEngineState


def _risk_ok(qty: Decimal = Decimal("0.01")) -> RiskEvaluation:
    return RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=qty,
        message="OK",
    )


def _req(**overrides) -> OrderRequest:
    data = dict(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        idempotency_key=uuid4().hex,
    )
    data.update(overrides)
    return OrderRequest(**data)


@pytest.mark.asyncio
async def test_market_order_full_lifecycle():
    engine = PaperTradingEngine(PaperConfig(initial_cash=Decimal("10000")))
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    order = await engine.submit(_req(), _risk_ok())
    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == Decimal("0.01")
    assert "BTC/USDT" in engine.state.positions
    assert engine.state.cash < Decimal("10000")
    events = [j["event"] for j in engine.state.journal]
    assert "ORDER_CREATED" in events and "FILL" in events


@pytest.mark.asyncio
async def test_partial_fill():
    engine = PaperTradingEngine(
        PaperConfig(partial_fill_fraction=Decimal("0.5"), initial_cash=Decimal("10000"))
    )
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    order = await engine.submit(
        _req(quantity=Decimal("0.02")), _risk_ok(Decimal("0.02"))
    )
    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert order.filled_quantity == Decimal("0.01")


@pytest.mark.asyncio
async def test_idempotency_prevents_duplicate():
    engine = PaperTradingEngine()
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    key = "same-key"
    o1 = await engine.submit(_req(idempotency_key=key), _risk_ok())
    o2 = await engine.submit(_req(idempotency_key=key), _risk_ok())
    assert o1.id == o2.id
    assert len([o for o in engine.state.orders.values()]) == 1


@pytest.mark.asyncio
async def test_sell_realizes_pnl():
    engine = PaperTradingEngine()
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    await engine.submit(_req(idempotency_key="b1"), _risk_ok())
    engine.set_mark_price("BTC/USDT", Decimal("110000"))
    sell = await engine.submit(
        _req(side=OrderSide.SELL, idempotency_key="s1"),
        _risk_ok(),
    )
    assert sell.status == OrderStatus.FILLED
    assert engine.state.realized_pnl > 0
    assert "BTC/USDT" not in engine.state.positions


@pytest.mark.asyncio
async def test_gateway_blocks_rejected():
    paper = PaperTradingEngine()
    paper.set_mark_price("BTC/USDT", Decimal("100000"))
    settings = Settings(kill_switch_enabled=True, _env_file=None)
    risk = RiskEngine(settings)
    gateway = OrderGateway(paper, risk_engine=risk)
    with pytest.raises(RiskBlockedError):
        await gateway.submit(
            _req(),
            RiskContext(
                portfolio=PortfolioState(
                    cash_balance=Decimal("10000"),
                    equity=Decimal("10000"),
                    peak_equity=Decimal("10000"),
                ),
                mark_price=Decimal("100000"),
                kill_switch_enabled=True,
            ),
        )


@pytest.mark.asyncio
async def test_limit_order_rests_when_not_crossed():
    engine = PaperTradingEngine()
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    order = await engine.submit(
        _req(
            order_type=OrderType.LIMIT,
            price=Decimal("90000"),
            idempotency_key="limit-rest",
        ),
        _risk_ok(),
    )
    assert order.status == OrderStatus.SUBMITTED
    assert order.filled_quantity == Decimal("0")


@pytest.mark.asyncio
async def test_limit_buy_fills_when_crossed():
    engine = PaperTradingEngine()
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    order = await engine.submit(
        _req(
            order_type=OrderType.LIMIT,
            price=Decimal("100000"),
            idempotency_key="limit-fill",
        ),
        _risk_ok(),
    )
    assert order.status == OrderStatus.FILLED


@pytest.mark.asyncio
async def test_rejected_risk_marks_order():
    engine = PaperTradingEngine()
    engine.set_mark_price("BTC/USDT", Decimal("100000"))
    risk = RiskEvaluation(
        decision=RiskDecision.REJECTED,
        reason_code=RiskReasonCode.KILL_SWITCH_ACTIVE,
        message="halted",
    )
    order = await engine.submit(_req(idempotency_key="rej"), risk)
    assert order.status == OrderStatus.REJECTED


@pytest.mark.asyncio
async def test_gateway_reduced_quantity():
    paper = PaperTradingEngine()
    paper.set_mark_price("BTC/USDT", Decimal("100000"))
    settings = Settings(
        max_risk_per_trade=Decimal("0.01"),
        max_position_exposure=Decimal("0.5"),
        max_portfolio_exposure=Decimal("0.8"),
        _env_file=None,
    )
    risk = RiskEngine(settings, RiskEngineState())
    gateway = OrderGateway(paper, risk_engine=risk)
    order = await gateway.submit(
        _req(
            quantity=Decimal("1"),
            stop_loss=Decimal("99000"),
            idempotency_key="gw-reduce",
        ),
        RiskContext(
            portfolio=PortfolioState(
                cash_balance=Decimal("10000"),
                equity=Decimal("10000"),
                peak_equity=Decimal("10000"),
            ),
            mark_price=Decimal("100000"),
            market_data_ts=__import__("app.core.time", fromlist=["utc_now"]).utc_now(),
            symbol_info=None,
        ),
    )
    assert order.quantity < Decimal("1")
    assert order.risk_decision in (RiskDecision.REDUCED, RiskDecision.APPROVED)


@pytest.mark.asyncio
async def test_failed_without_mark_price():
    engine = PaperTradingEngine()
    order = await engine.submit(_req(idempotency_key="nomark"), _risk_ok())
    assert order.status == OrderStatus.FAILED


@pytest.mark.asyncio
async def test_replay_byte_identical_output():
    """Feeding the same input sequence twice must produce byte-identical snapshots
    after normalizing volatile UUIDs/timestamps.
    """

    async def run_sequence() -> dict:
        engine = PaperTradingEngine(
            PaperConfig(
                initial_cash=Decimal("10000"),
                fee_rate=Decimal("0.001"),
                slippage_rate=Decimal("0.0005"),
                spread_rate=Decimal("0.0002"),
            )
        )
        engine.set_mark_price("BTC/USDT", Decimal("100000"))
        await engine.submit(
            _req(idempotency_key="r1", quantity=Decimal("0.01")), _risk_ok()
        )
        engine.set_mark_price("BTC/USDT", Decimal("101000"))
        await engine.submit(
            _req(side=OrderSide.SELL, idempotency_key="r2", quantity=Decimal("0.01")),
            _risk_ok(),
        )
        snap = engine.snapshot()
        # Normalize volatile fields; sort by side for stable ordering across UUID ids
        orders = sorted(
            snap["orders"].values(), key=lambda o: (o["side"], o["quantity"])
        )
        snap["orders"] = {
            str(i): {
                "symbol": o["symbol"],
                "side": o["side"],
                "quantity": o["quantity"],
                "filled_quantity": o["filled_quantity"],
                "status": o["status"],
                "average_fill_price": o["average_fill_price"],
                "fees": o["fees"],
            }
            for i, o in enumerate(orders)
        }
        fills = sorted(snap["fills"], key=lambda f: (f["side"], f["price"]))
        snap["fills"] = [
            {
                "symbol": f["symbol"],
                "side": f["side"],
                "quantity": f["quantity"],
                "price": f["price"],
                "fee": f["fee"],
            }
            for f in fills
        ]
        snap["positions"] = {
            k: {
                "quantity": v["quantity"],
                "entry_price": v["entry_price"],
                "realized_pnl": v.get("realized_pnl", "0"),
            }
            for k, v in sorted(snap["positions"].items())
        }
        return snap

    a = await run_sequence()
    b = await run_sequence()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
