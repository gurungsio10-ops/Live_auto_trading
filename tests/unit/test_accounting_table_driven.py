"""Table-driven portfolio accounting invariants (Decimal-only)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.accounting.invariants import check_cycle_invariants
from app.core.time import utc_now
from app.execution.paper.engine import PaperConfig, PaperTradingEngine
from app.models.domain.enums import (
    OrderSide,
    OrderType,
    RiskDecision,
    RiskReasonCode,
)
from app.models.domain.trading import OrderRequest, Position, RiskEvaluation


def _pos(qty: str, entry: str, mark: str) -> Position:
    q = Decimal(qty)
    e = Decimal(entry)
    m = Decimal(mark)
    return Position(
        symbol="BTC/USDT",
        quantity=q,
        entry_price=e,
        current_price=m,
        unrealized_pnl=(m - e) * q,
        opened_at=utc_now(),
    )


@pytest.mark.parametrize(
    "cash,qty,entry,mark,expect_ok",
    [
        ("10000", "0", "0", "0", True),
        ("9000", "0.1", "10000", "10000", True),
        ("9000", "0.1", "10000", "11000", True),
        ("-1", "0", "0", "0", False),
        ("1000", "-0.01", "100", "100", False),
    ],
)
def test_equity_identity_table(cash, qty, entry, mark, expect_ok):
    positions = {}
    if Decimal(qty) != 0 or Decimal(entry) != 0:
        positions["BTC/USDT"] = _pos(qty, entry, mark)
    report = check_cycle_invariants(
        cash=Decimal(cash),
        positions=positions,
        realized_pnl=Decimal("0"),
        fills=[],
    )
    assert report.ok is expect_ok
    if expect_ok and positions:
        marked = Decimal(qty) * Decimal(mark)
        assert report.equity == Decimal(cash) + marked


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "buys,sell_frac,expect_open",
    [
        (["0.01"], "0", True),
        (["0.01", "0.01"], "1", False),
        (["0.02"], "0.5", True),
    ],
)
async def test_engine_buy_sell_table(buys, sell_frac, expect_open):
    engine = PaperTradingEngine(
        PaperConfig(
            initial_cash=Decimal("10000"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0"),
            spread_rate=Decimal("0"),
        )
    )
    engine.set_mark_price("BTC/USDT", Decimal("100"))
    risk = RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=Decimal("10"),
        message="ok",
    )
    for i, qty in enumerate(buys):
        await engine.submit(
            OrderRequest(
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal(qty),
                idempotency_key=f"buy-{i}",
            ),
            risk.model_copy(update={"approved_quantity": Decimal(qty)}),
        )
    pos = engine.state.positions.get("BTC/USDT")
    if Decimal(sell_frac) > 0 and pos is not None:
        sell_qty = (pos.quantity * Decimal(sell_frac)).quantize(Decimal("0.00000001"))
        await engine.submit(
            OrderRequest(
                symbol="BTC/USDT",
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=sell_qty,
                idempotency_key="sell-1",
                reduce_only=True,
            ),
            risk.model_copy(update={"approved_quantity": sell_qty}),
        )
    open_pos = engine.state.positions.get("BTC/USDT")
    assert (open_pos is not None and open_pos.quantity > 0) is expect_open
    assert engine.state.cash >= Decimal("0")
    # Fees applied once per fill
    fill_ids = [f.id for f in engine.state.fills]
    assert len(fill_ids) == len(set(fill_ids))
    report = check_cycle_invariants(
        cash=engine.state.cash,
        positions=engine.state.positions,
        realized_pnl=engine.state.realized_pnl,
        fills=engine.state.fills,
        orders=engine.state.orders,
    )
    assert report.ok


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_no_second_fill():
    engine = PaperTradingEngine(
        PaperConfig(
            initial_cash=Decimal("10000"),
            fee_rate=Decimal("0"),
            slippage_rate=Decimal("0"),
            spread_rate=Decimal("0"),
        )
    )
    engine.set_mark_price("BTC/USDT", Decimal("100"))
    risk = RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=Decimal("1"),
        message="ok",
    )
    req = OrderRequest(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
        idempotency_key="same-key",
    )
    first = await engine.submit(req, risk)
    second = await engine.submit(req, risk)
    assert first.id == second.id
    assert len(engine.state.fills) == 1
