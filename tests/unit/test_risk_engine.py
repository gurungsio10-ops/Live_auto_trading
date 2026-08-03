"""Phase 6: risk engine — every reason code has a dedicated test."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.config import Settings
from app.core.time import utc_now
from app.models.domain.enums import OrderSide, OrderType, RiskDecision, RiskReasonCode
from app.models.domain.market import SymbolInfo
from app.models.domain.trading import OrderRequest, PortfolioState, Position
from app.risk.engine import RiskContext, RiskEngine, RiskEngineState


def _settings(**overrides) -> Settings:
    base = dict(
        trading_mode="paper",
        live_trading_enabled=False,
        kill_switch_enabled=False,
        max_risk_per_trade=Decimal("0.01"),
        max_position_exposure=Decimal("0.25"),
        max_portfolio_exposure=Decimal("0.80"),
        max_open_positions=3,
        max_daily_loss=Decimal("0.03"),
        max_drawdown=Decimal("0.10"),
        max_consecutive_losses=5,
        max_orders_per_minute=10,
        min_order_notional=Decimal("10"),
        market_data_stale_seconds=30,
        _env_file=None,
    )
    base.update(overrides)
    return Settings(**base)


def _portfolio(**overrides) -> PortfolioState:
    data = dict(
        cash_balance=Decimal("10000"),
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
        daily_pnl=Decimal("0"),
        drawdown=Decimal("0"),
        open_positions=[],
        consecutive_losses=0,
    )
    data.update(overrides)
    return PortfolioState(**data)


def _symbol() -> SymbolInfo:
    return SymbolInfo(
        symbol="BTC/USDT",
        base="BTC",
        quote="USDT",
        price_precision=2,
        quantity_precision=6,
        min_quantity=Decimal("0.0001"),
        min_notional=Decimal("10"),
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.0001"),
    )


def _request(**overrides) -> OrderRequest:
    data = dict(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        price=None,
        stop_loss=Decimal("90000"),
        idempotency_key="key-1",
    )
    data.update(overrides)
    return OrderRequest(**data)


def _ctx(**overrides) -> RiskContext:
    data = dict(
        portfolio=_portfolio(),
        symbol_info=_symbol(),
        mark_price=Decimal("100000"),
        market_data_ts=utc_now(),
        trading_mode="paper",
    )
    data.update(overrides)
    return RiskContext(**data)


def test_approved_happy_path():
    engine = RiskEngine(_settings())
    result = engine.evaluate(_request(), _ctx())
    assert result.decision == RiskDecision.APPROVED
    assert result.reason_code == RiskReasonCode.OK


def test_kill_switch_active():
    engine = RiskEngine(_settings(kill_switch_enabled=True))
    result = engine.evaluate(_request(), _ctx(kill_switch_enabled=True))
    assert result.decision == RiskDecision.HALTED
    assert result.reason_code == RiskReasonCode.KILL_SWITCH_ACTIVE


def test_data_stale():
    engine = RiskEngine(_settings(market_data_stale_seconds=30))
    result = engine.evaluate(
        _request(),
        _ctx(market_data_ts=utc_now() - timedelta(seconds=120)),
    )
    assert result.decision == RiskDecision.REJECTED
    assert result.reason_code == RiskReasonCode.DATA_STALE


def test_duplicate_order():
    engine = RiskEngine(_settings())
    engine.evaluate(_request(idempotency_key="dup"), _ctx())
    result = engine.evaluate(_request(idempotency_key="dup"), _ctx())
    assert result.reason_code == RiskReasonCode.DUPLICATE_ORDER


def test_invalid_price():
    engine = RiskEngine(_settings())
    result = engine.evaluate(
        _request(order_type=OrderType.LIMIT, price=None),
        _ctx(),
    )
    assert result.reason_code == RiskReasonCode.INVALID_PRICE


def test_invalid_quantity():
    engine = RiskEngine(_settings())
    result = engine.evaluate(_request(quantity=Decimal("0")), _ctx())
    assert result.reason_code == RiskReasonCode.INVALID_QUANTITY


def test_min_order_size():
    engine = RiskEngine(_settings(min_order_notional=Decimal("10")))
    # Quantity respects step_size but notional is only $1
    result = engine.evaluate(
        _request(quantity=Decimal("0.01")),
        _ctx(mark_price=Decimal("100")),
    )
    assert result.reason_code == RiskReasonCode.MIN_ORDER_SIZE


def test_precision_invalid():
    engine = RiskEngine(_settings())
    result = engine.evaluate(_request(quantity=Decimal("0.00015")), _ctx())
    # step_size 0.0001 — 0.00015 invalid
    assert result.reason_code == RiskReasonCode.PRECISION_INVALID


def test_max_risk_per_trade_rejects():
    engine = RiskEngine(_settings(max_risk_per_trade=Decimal("0.0000001")))
    result = engine.evaluate(
        _request(quantity=Decimal("1"), stop_loss=Decimal("1")),
        _ctx(mark_price=Decimal("100000")),
    )
    assert result.reason_code in {
        RiskReasonCode.MAX_RISK_PER_TRADE,
        RiskReasonCode.SIZE_REDUCED_BY_RISK,
        RiskReasonCode.MAX_POSITION_EXPOSURE,
    }


def test_max_position_exposure():
    engine = RiskEngine(
        _settings(
            max_position_exposure=Decimal("0.0001"), max_risk_per_trade=Decimal("0.5")
        )
    )
    result = engine.evaluate(
        _request(quantity=Decimal("1"), stop_loss=None, idempotency_key="pos"),
        _ctx(mark_price=Decimal("100000")),
    )
    assert result.reason_code in {
        RiskReasonCode.MAX_POSITION_EXPOSURE,
        RiskReasonCode.SIZE_REDUCED_BY_RISK,
    }


def test_max_portfolio_exposure():
    positions = [
        Position(
            symbol="BTC/USDT",
            quantity=Decimal("0.08"),
            entry_price=Decimal("100000"),
            current_price=Decimal("100000"),
            unrealized_pnl=Decimal("0"),
            opened_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    ]
    engine = RiskEngine(
        _settings(
            max_portfolio_exposure=Decimal("0.80"),
            max_position_exposure=Decimal("0.90"),
            max_risk_per_trade=Decimal("0.50"),
            max_open_positions=10,
        )
    )
    result = engine.evaluate(
        _request(quantity=Decimal("0.05"), stop_loss=None, idempotency_key="port"),
        _ctx(
            portfolio=_portfolio(open_positions=positions), mark_price=Decimal("100000")
        ),
    )
    assert result.reason_code in {
        RiskReasonCode.MAX_PORTFOLIO_EXPOSURE,
        RiskReasonCode.SIZE_REDUCED_BY_RISK,
    }


def test_max_open_positions():
    positions = [
        Position(
            symbol=f"S{i}/USDT",
            quantity=Decimal("1"),
            entry_price=Decimal("10"),
            current_price=Decimal("10"),
            unrealized_pnl=Decimal("0"),
            opened_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        for i in range(3)
    ]
    engine = RiskEngine(_settings(max_open_positions=3))
    result = engine.evaluate(
        _request(idempotency_key="maxpos"),
        _ctx(portfolio=_portfolio(open_positions=positions)),
    )
    assert result.reason_code == RiskReasonCode.MAX_OPEN_POSITIONS


def test_daily_loss_limit_reached():
    engine = RiskEngine(_settings(max_daily_loss=Decimal("0.03")))
    result = engine.evaluate(
        _request(idempotency_key="daily"),
        _ctx(
            portfolio=_portfolio(
                daily_pnl=Decimal("-400"), peak_equity=Decimal("10000")
            )
        ),
    )
    assert result.reason_code == RiskReasonCode.DAILY_LOSS_LIMIT_REACHED


def test_max_drawdown_reached():
    engine = RiskEngine(_settings(max_drawdown=Decimal("0.10")))
    result = engine.evaluate(
        _request(idempotency_key="dd"),
        _ctx(portfolio=_portfolio(drawdown=Decimal("0.15"))),
    )
    assert result.reason_code == RiskReasonCode.MAX_DRAWDOWN_REACHED


def test_max_consecutive_losses():
    engine = RiskEngine(_settings(max_consecutive_losses=5))
    result = engine.evaluate(
        _request(idempotency_key="cl"),
        _ctx(portfolio=_portfolio(consecutive_losses=5)),
    )
    assert result.reason_code == RiskReasonCode.MAX_CONSECUTIVE_LOSSES


def test_max_order_frequency():
    state = RiskEngineState(recent_order_times=[utc_now() for _ in range(10)])
    engine = RiskEngine(_settings(max_orders_per_minute=10), state=state)
    result = engine.evaluate(_request(idempotency_key="freq"), _ctx())
    assert result.reason_code == RiskReasonCode.MAX_ORDER_FREQUENCY


def test_circuit_breaker_open():
    engine = RiskEngine(_settings())
    engine.open_circuit_breaker("too many errors")
    result = engine.evaluate(_request(idempotency_key="cb"), _ctx())
    assert result.decision == RiskDecision.HALTED
    assert result.reason_code == RiskReasonCode.CIRCUIT_BREAKER_OPEN


def test_risk_engine_unhealthy():
    state = RiskEngineState(risk_engine_healthy=False)
    engine = RiskEngine(_settings(), state=state)
    result = engine.evaluate(_request(idempotency_key="reh"), _ctx())
    assert result.reason_code == RiskReasonCode.RISK_ENGINE_UNHEALTHY


def test_market_data_unhealthy():
    state = RiskEngineState(market_data_healthy=False)
    engine = RiskEngine(_settings(), state=state)
    result = engine.evaluate(_request(idempotency_key="mdh"), _ctx())
    assert result.reason_code == RiskReasonCode.MARKET_DATA_UNHEALTHY


def test_database_unhealthy():
    state = RiskEngineState(database_healthy=False)
    engine = RiskEngine(_settings(), state=state)
    result = engine.evaluate(_request(idempotency_key="dbh"), _ctx())
    assert result.reason_code == RiskReasonCode.DATABASE_UNHEALTHY


def test_reconciliation_unhealthy():
    state = RiskEngineState(reconciliation_healthy=False)
    engine = RiskEngine(_settings(), state=state)
    result = engine.evaluate(_request(idempotency_key="rec"), _ctx())
    assert result.reason_code == RiskReasonCode.RECONCILIATION_UNHEALTHY


def test_live_trading_disabled():
    engine = RiskEngine(_settings(trading_mode="live", live_trading_enabled=False))
    result = engine.evaluate(
        _request(idempotency_key="liveoff"),
        _ctx(trading_mode="live", live_trading_enabled=False),
    )
    assert result.reason_code == RiskReasonCode.LIVE_TRADING_DISABLED


def test_invalid_credentials():
    engine = RiskEngine(_settings(trading_mode="live", live_trading_enabled=True))
    result = engine.evaluate(
        _request(idempotency_key="creds"),
        _ctx(
            trading_mode="live",
            live_trading_enabled=True,
            has_exchange_credentials=False,
            live_approval_valid=True,
        ),
    )
    assert result.reason_code == RiskReasonCode.INVALID_CREDENTIALS


def test_invalid_live_approval():
    engine = RiskEngine(_settings(trading_mode="live", live_trading_enabled=True))
    result = engine.evaluate(
        _request(idempotency_key="approval"),
        _ctx(
            trading_mode="live",
            live_trading_enabled=True,
            has_exchange_credentials=True,
            live_approval_valid=False,
        ),
    )
    assert result.reason_code == RiskReasonCode.INVALID_LIVE_APPROVAL


def test_size_reduced_by_risk():
    engine = RiskEngine(
        _settings(
            max_risk_per_trade=Decimal("0.01"),
            max_position_exposure=Decimal("0.50"),
            max_portfolio_exposure=Decimal("0.80"),
        )
    )
    # Large qty with tight stop relative to equity → reduced
    result = engine.evaluate(
        _request(
            quantity=Decimal("1"),
            stop_loss=Decimal("99000"),
            idempotency_key="reduce",
        ),
        _ctx(mark_price=Decimal("100000")),
    )
    assert result.decision == RiskDecision.REDUCED
    assert result.reason_code == RiskReasonCode.SIZE_REDUCED_BY_RISK
    assert result.approved_quantity is not None
    assert result.approved_quantity < Decimal("1")


def test_invalid_mark_price():
    engine = RiskEngine(_settings())
    result = engine.evaluate(
        _request(idempotency_key="mark"),
        _ctx(mark_price=Decimal("0")),
    )
    assert result.reason_code == RiskReasonCode.INVALID_PRICE


def test_no_valid_price_without_mark():
    engine = RiskEngine(_settings())
    result = engine.evaluate(
        _request(idempotency_key="noprice"),
        _ctx(mark_price=None),
    )
    assert result.reason_code == RiskReasonCode.INVALID_PRICE


def test_limit_price_zero():
    engine = RiskEngine(_settings())
    result = engine.evaluate(
        _request(order_type=OrderType.LIMIT, price=Decimal("0"), idempotency_key="lp0"),
        _ctx(),
    )
    assert result.reason_code == RiskReasonCode.INVALID_PRICE


def test_below_min_quantity():
    engine = RiskEngine(_settings())
    # Valid step but below exchange min_quantity
    result = engine.evaluate(
        _request(quantity=Decimal("0.0001"), idempotency_key="minq2"),
        _ctx(
            symbol_info=SymbolInfo(
                symbol="BTC/USDT",
                base="BTC",
                quote="USDT",
                price_precision=2,
                quantity_precision=6,
                min_quantity=Decimal("0.01"),
                min_notional=Decimal("10"),
                tick_size=Decimal("0.01"),
                step_size=Decimal("0.0001"),
            ),
            mark_price=Decimal("100000"),
        ),
    )
    assert result.reason_code == RiskReasonCode.MIN_ORDER_SIZE


def test_price_tick_invalid():
    engine = RiskEngine(_settings())
    result = engine.evaluate(
        _request(
            order_type=OrderType.LIMIT,
            price=Decimal("100000.005"),
            quantity=Decimal("0.01"),
            idempotency_key="tick",
        ),
        _ctx(mark_price=Decimal("100000")),
    )
    assert result.reason_code == RiskReasonCode.PRECISION_INVALID


def test_no_symbol_info_min_notional():
    engine = RiskEngine(_settings(min_order_notional=Decimal("10")))
    result = engine.evaluate(
        _request(quantity=Decimal("0.01"), idempotency_key="nosym"),
        _ctx(symbol_info=None, mark_price=Decimal("100")),
    )
    assert result.reason_code == RiskReasonCode.MIN_ORDER_SIZE


def test_close_circuit_breaker():
    engine = RiskEngine(_settings())
    engine.open_circuit_breaker("err")
    engine.close_circuit_breaker()
    result = engine.evaluate(_request(idempotency_key="cbc"), _ctx())
    assert result.decision == RiskDecision.APPROVED


def test_live_gating_all_pass():
    engine = RiskEngine(_settings(trading_mode="live", live_trading_enabled=True))
    result = engine.evaluate(
        _request(idempotency_key="liveok"),
        _ctx(
            trading_mode="live",
            live_trading_enabled=True,
            has_exchange_credentials=True,
            live_approval_valid=True,
            kill_switch_enabled=False,
        ),
    )
    assert result.decision == RiskDecision.APPROVED
    assert result.checks.get("live_gating") == "passed"


def test_live_kill_switch_in_gating():
    engine = RiskEngine(_settings(trading_mode="live", live_trading_enabled=True))
    result = engine.evaluate(
        _request(idempotency_key="livekill"),
        _ctx(
            trading_mode="live",
            live_trading_enabled=True,
            kill_switch_enabled=True,
            has_exchange_credentials=True,
            live_approval_valid=True,
        ),
    )
    assert result.reason_code == RiskReasonCode.KILL_SWITCH_ACTIVE


@pytest.mark.parametrize(
    "flag,code",
    [
        ("risk_engine_healthy", RiskReasonCode.RISK_ENGINE_UNHEALTHY),
        ("market_data_healthy", RiskReasonCode.MARKET_DATA_UNHEALTHY),
        ("database_healthy", RiskReasonCode.DATABASE_UNHEALTHY),
        ("reconciliation_healthy", RiskReasonCode.RECONCILIATION_UNHEALTHY),
    ],
)
def test_live_gating_health_flags(flag, code):
    state = RiskEngineState(**{flag: False})
    # risk_engine_healthy False is caught before live gating — still assert code
    engine = RiskEngine(
        _settings(trading_mode="live", live_trading_enabled=True),
        state=state,
    )
    result = engine.evaluate(
        _request(idempotency_key=f"live-{flag}"),
        _ctx(
            trading_mode="live",
            live_trading_enabled=True,
            has_exchange_credentials=True,
            live_approval_valid=True,
        ),
    )
    assert result.reason_code == code


def test_portfolio_exposure_no_room():
    positions = [
        Position(
            symbol="BTC/USDT",
            quantity=Decimal("0.08"),
            entry_price=Decimal("100000"),
            current_price=Decimal("100000"),
            unrealized_pnl=Decimal("0"),
            opened_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    ]
    engine = RiskEngine(
        _settings(
            max_portfolio_exposure=Decimal("0.80"),
            max_position_exposure=Decimal("0.90"),
            max_risk_per_trade=Decimal("0.50"),
            max_open_positions=10,
        )
    )
    result = engine.evaluate(
        _request(quantity=Decimal("0.01"), stop_loss=None, idempotency_key="noroom"),
        _ctx(
            portfolio=_portfolio(open_positions=positions), mark_price=Decimal("100000")
        ),
    )
    assert result.reason_code in {
        RiskReasonCode.MAX_PORTFOLIO_EXPOSURE,
        RiskReasonCode.SIZE_REDUCED_BY_RISK,
    }


def test_singleton_helpers():
    from app.risk.engine import get_risk_engine, reset_risk_engine

    reset_risk_engine()
    a = get_risk_engine()
    b = get_risk_engine()
    assert a is b
    c = reset_risk_engine()
    assert c is not a


def test_missing_market_data_ts_skips_stale_check():
    engine = RiskEngine(_settings())
    result = engine.evaluate(
        _request(idempotency_key="no-md-ts"),
        _ctx(market_data_ts=None),
    )
    assert result.decision == RiskDecision.APPROVED
    assert "market_data_age_seconds" not in result.checks


def _loose_symbol() -> SymbolInfo:
    return SymbolInfo(
        symbol="BTC/USDT",
        base="BTC",
        quote="USDT",
        price_precision=2,
        quantity_precision=8,
        min_quantity=Decimal("0.00000001"),
        min_notional=Decimal("0.01"),
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.00000001"),
    )


def test_max_risk_per_trade_hard_reject_when_budget_too_small():
    """Wide stop + tiny risk budget → max_qty_by_risk rounds to zero."""
    engine = RiskEngine(
        _settings(
            max_risk_per_trade=Decimal("0.01"),
            max_position_exposure=Decimal("1"),
            max_portfolio_exposure=Decimal("1"),
            min_order_notional=Decimal("0.01"),
        )
    )
    result = engine.evaluate(
        _request(
            quantity=Decimal("1"),
            stop_loss=Decimal("1"),
            idempotency_key="risk-hard",
        ),
        _ctx(
            portfolio=_portfolio(
                equity=Decimal("0.001"),
                cash_balance=Decimal("0.001"),
                peak_equity=Decimal("0.001"),
            ),
            mark_price=Decimal("100000"),
            symbol_info=_loose_symbol(),
        ),
    )
    assert result.decision == RiskDecision.REJECTED
    assert result.reason_code == RiskReasonCode.MAX_RISK_PER_TRADE
    assert result.approved_quantity is None


def test_max_position_exposure_hard_reject_tiny_equity():
    engine = RiskEngine(
        _settings(
            max_risk_per_trade=Decimal("1"),
            max_position_exposure=Decimal("0.01"),
            max_portfolio_exposure=Decimal("1"),
            min_order_notional=Decimal("0.01"),
        )
    )
    result = engine.evaluate(
        _request(
            quantity=Decimal("1"),
            stop_loss=None,
            idempotency_key="pos-hard",
        ),
        _ctx(
            portfolio=_portfolio(
                equity=Decimal("0.001"),
                cash_balance=Decimal("0.001"),
                peak_equity=Decimal("0.001"),
            ),
            mark_price=Decimal("100000"),
            symbol_info=_loose_symbol(),
        ),
    )
    assert result.decision == RiskDecision.REJECTED
    assert result.reason_code == RiskReasonCode.MAX_POSITION_EXPOSURE


def test_portfolio_exposure_reduces_when_partial_room():
    positions = [
        Position(
            symbol="ETH/USDT",
            quantity=Decimal("0.07"),
            entry_price=Decimal("100000"),
            current_price=Decimal("100000"),
            unrealized_pnl=Decimal("0"),
            opened_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    ]
    # Existing notional 7000 / equity 10000 = 0.70; max portfolio 0.80 → room 1000
    engine = RiskEngine(
        _settings(
            max_portfolio_exposure=Decimal("0.80"),
            max_position_exposure=Decimal("0.90"),
            max_risk_per_trade=Decimal("0.50"),
            max_open_positions=10,
        )
    )
    result = engine.evaluate(
        _request(
            quantity=Decimal("0.05"),
            stop_loss=None,
            idempotency_key="port-reduce",
        ),
        _ctx(
            portfolio=_portfolio(open_positions=positions),
            mark_price=Decimal("100000"),
        ),
    )
    assert result.decision == RiskDecision.REDUCED
    assert result.reason_code == RiskReasonCode.SIZE_REDUCED_BY_RISK
    assert result.approved_quantity is not None
    assert result.approved_quantity < Decimal("0.05")
    assert result.approved_quantity * Decimal("100000") <= Decimal("1000.01")


def test_rejected_evaluations_never_omit_reason_code():
    cases = [
        (
            RiskEngine(_settings(kill_switch_enabled=True)),
            _request(idempotency_key="r1"),
            _ctx(kill_switch_enabled=True),
        ),
        (
            RiskEngine(_settings()),
            _request(quantity=Decimal("0"), idempotency_key="r2"),
            _ctx(),
        ),
        (
            RiskEngine(_settings(), RiskEngineState(market_data_healthy=False)),
            _request(idempotency_key="r3"),
            _ctx(),
        ),
    ]
    for engine, req, ctx in cases:
        result = engine.evaluate(req, ctx)
        assert result.decision in {RiskDecision.REJECTED, RiskDecision.HALTED}
        assert result.reason_code is not None
        assert result.approved_quantity is None
