"""Phase 14 — live trading preparation: all 9 gates, API status, gateway."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.core.time import utc_now
from app.execution.gateway import OrderGateway, RiskBlockedError
from app.execution.live_gate import LIVE_CONDITIONS, LiveReadinessState, LiveTradingGate
from app.execution.paper import PaperConfig, PaperTradingEngine
from app.main import app
from app.models.domain.enums import OrderSide, OrderType, RiskReasonCode
from app.models.domain.market import SymbolInfo
from app.models.domain.trading import OrderRequest, PortfolioState
from app.risk.engine import (
    RiskContext,
    RiskEngine,
    RiskEngineState,
    get_risk_engine,
    reset_risk_engine,
)

CONDITION_REASON = {
    "trading_mode_live": RiskReasonCode.LIVE_GATING_INCOMPLETE,
    "live_trading_enabled": RiskReasonCode.LIVE_TRADING_DISABLED,
    "kill_switch_off": RiskReasonCode.KILL_SWITCH_ACTIVE,
    "valid_credentials": RiskReasonCode.INVALID_CREDENTIALS,
    "risk_engine_healthy": RiskReasonCode.RISK_ENGINE_UNHEALTHY,
    "market_data_healthy": RiskReasonCode.MARKET_DATA_UNHEALTHY,
    "database_healthy": RiskReasonCode.DATABASE_UNHEALTHY,
    "reconciliation_healthy": RiskReasonCode.RECONCILIATION_UNHEALTHY,
    "valid_live_approval_token": RiskReasonCode.INVALID_LIVE_APPROVAL,
}


def _live_settings(**overrides: object) -> Settings:
    data: dict[str, object] = dict(
        trading_mode="live",
        live_trading_enabled=True,
        kill_switch_enabled=False,
        exchange_api_key=SecretStr("key-123456789012345678901234"),
        exchange_api_secret=SecretStr("secret-123456789012345678901234"),
        live_approval_token=SecretStr("approve-live-token-1234567890"),
        _env_file=None,
    )
    data.update(overrides)
    return Settings(**data)


def _ready_state(**overrides: object) -> LiveReadinessState:
    data: dict[str, object] = dict(
        risk_engine_healthy=True,
        market_data_healthy=True,
        database_healthy=True,
        reconciliation_healthy=True,
        live_approval_valid=True,
    )
    data.update(overrides)
    return LiveReadinessState(**data)  # type: ignore[arg-type]


def test_roadmap_nine_conditions_match_gate() -> None:
    assert LIVE_CONDITIONS == (
        "trading_mode_live",
        "live_trading_enabled",
        "kill_switch_off",
        "valid_credentials",
        "risk_engine_healthy",
        "market_data_healthy",
        "database_healthy",
        "reconciliation_healthy",
        "valid_live_approval_token",
    )
    assert len(LIVE_CONDITIONS) == 9


@pytest.mark.parametrize(
    "override_settings,override_state,expected",
    [
        ({"trading_mode": "paper"}, {}, "trading_mode_live"),
        ({"live_trading_enabled": False}, {}, "live_trading_enabled"),
        ({"kill_switch_enabled": True}, {}, "kill_switch_off"),
        (
            {"exchange_api_key": None, "exchange_api_secret": None},
            {},
            "valid_credentials",
        ),
        ({}, {"risk_engine_healthy": False}, "risk_engine_healthy"),
        ({}, {"market_data_healthy": False}, "market_data_healthy"),
        ({}, {"database_healthy": False}, "database_healthy"),
        ({}, {"reconciliation_healthy": False}, "reconciliation_healthy"),
        ({}, {"live_approval_valid": False}, "valid_live_approval_token"),
        ({"live_approval_token": None}, {}, "valid_live_approval_token"),
        (
            {"live_approval_token": SecretStr("   ")},
            {},
            "valid_live_approval_token",
        ),
    ],
)
def test_each_condition_maps_reason_code(
    override_settings: dict,
    override_state: dict,
    expected: str,
) -> None:
    gate = LiveTradingGate(
        _live_settings(**override_settings),
        _ready_state(**override_state),
    )
    result = gate.evaluate()
    assert result.allowed is False
    assert expected in result.failed_conditions
    assert result.reason_code == CONDITION_REASON[result.failed_conditions[0]]
    assert result.details is not None
    assert result.details[expected] is False


def test_multi_fail_uses_first_condition_reason() -> None:
    gate = LiveTradingGate(
        _live_settings(trading_mode="paper", live_trading_enabled=False),
        _ready_state(live_approval_valid=False),
    )
    result = gate.evaluate()
    assert result.failed_conditions[0] == "trading_mode_live"
    assert result.reason_code == RiskReasonCode.LIVE_GATING_INCOMPLETE
    assert "live_trading_enabled" in result.failed_conditions
    assert "valid_live_approval_token" in result.failed_conditions


def test_unused_readiness_fields_do_not_gate() -> None:
    gate = LiveTradingGate(
        _live_settings(),
        _ready_state(
            clock_synced=False,
            account_readable=False,
            balances_verified=False,
        ),
    )
    result = gate.evaluate()
    assert result.allowed is True


def test_validate_approval_token_constant_time() -> None:
    gate = LiveTradingGate(_live_settings())
    assert gate.validate_approval_token("approve-live-token-1234567890") is True
    assert gate.validate_approval_token("wrong-token") is False
    assert gate.validate_approval_token("") is False
    bare = LiveTradingGate(_live_settings(live_approval_token=None))
    assert bare.validate_approval_token("approve-live-token-1234567890") is False
    blank = LiveTradingGate(_live_settings(live_approval_token=SecretStr("   ")))
    assert blank.validate_approval_token("approve-live-token-1234567890") is False


def test_whitespace_credentials_are_invalid() -> None:
    settings = _live_settings(
        exchange_api_key=SecretStr("   "),
        exchange_api_secret=SecretStr("   "),
    )
    assert settings.has_exchange_credentials is False
    result = LiveTradingGate(settings, _ready_state()).evaluate()
    assert result.allowed is False
    assert "valid_credentials" in result.failed_conditions


def test_default_settings_block_live_gate() -> None:
    settings = Settings(_env_file=None)
    assert settings.trading_mode == "paper"
    assert settings.live_trading_enabled is False
    result = LiveTradingGate(settings).evaluate()
    assert result.allowed is False
    assert "trading_mode_live" in result.failed_conditions
    assert "live_trading_enabled" in result.failed_conditions
    assert "valid_live_approval_token" in result.failed_conditions


def test_api_live_gate_status_blocked_by_default() -> None:
    client = TestClient(app)
    resp = client.get("/api/live-gate/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["allowed"] is False
    assert body["conditions"] == list(LIVE_CONDITIONS)
    assert "trading_mode_live" in body["failed_conditions"]
    assert body["reason_code"] is not None
    assert isinstance(body["details"], dict)
    assert set(body["details"]) == set(LIVE_CONDITIONS)


def _portfolio() -> PortfolioState:
    return PortfolioState(
        cash_balance=Decimal("10000"),
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
    )


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


def _live_ctx(**overrides: object) -> RiskContext:
    data: dict[str, object] = dict(
        portfolio=_portfolio(),
        symbol_info=_symbol(),
        mark_price=Decimal("100000"),
        market_data_ts=utc_now(),
        trading_mode="live",
        live_trading_enabled=True,
        kill_switch_enabled=False,
        has_exchange_credentials=True,
        live_approval_valid=True,
    )
    data.update(overrides)
    return RiskContext(**data)  # type: ignore[arg-type]


def _req() -> OrderRequest:
    return OrderRequest(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        stop_loss=Decimal("90000"),
        idempotency_key=uuid4().hex,
    )


@pytest.mark.asyncio
async def test_gateway_blocks_live_without_approval() -> None:
    paper = PaperTradingEngine(PaperConfig(initial_cash=Decimal("10000")))
    paper.set_mark_price("BTC/USDT", Decimal("100000"))
    risk = RiskEngine(_live_settings())
    gateway = OrderGateway(paper, risk_engine=risk)
    with pytest.raises(RiskBlockedError) as exc:
        await gateway.submit(_req(), _live_ctx(live_approval_valid=False))
    assert exc.value.evaluation.reason_code == RiskReasonCode.INVALID_LIVE_APPROVAL


@pytest.mark.asyncio
async def test_gateway_blocks_live_without_credentials() -> None:
    paper = PaperTradingEngine(PaperConfig(initial_cash=Decimal("10000")))
    paper.set_mark_price("BTC/USDT", Decimal("100000"))
    # No credentials in settings either
    risk = RiskEngine(_live_settings(exchange_api_key=None, exchange_api_secret=None))
    gateway = OrderGateway(paper, risk_engine=risk)
    with pytest.raises(RiskBlockedError) as exc:
        await gateway.submit(_req(), _live_ctx(has_exchange_credentials=False))
    assert exc.value.evaluation.reason_code == RiskReasonCode.INVALID_CREDENTIALS


@pytest.mark.asyncio
async def test_gateway_allows_live_when_all_nine_pass() -> None:
    paper = PaperTradingEngine(PaperConfig(initial_cash=Decimal("10000")))
    paper.set_mark_price("BTC/USDT", Decimal("100000"))
    risk = RiskEngine(_live_settings())
    gateway = OrderGateway(paper, risk_engine=risk)
    order = await gateway.submit(_req(), _live_ctx())
    assert order.risk_decision.value == "APPROVED"
    assert order.status.value == "FILLED"


@pytest.mark.asyncio
async def test_gateway_live_uses_settings_credentials_fallback() -> None:
    paper = PaperTradingEngine(PaperConfig(initial_cash=Decimal("10000")))
    paper.set_mark_price("BTC/USDT", Decimal("100000"))
    risk = RiskEngine(_live_settings())
    gateway = OrderGateway(paper, risk_engine=risk)
    # Context says no creds, but settings have them — must still pass credentials gate
    order = await gateway.submit(_req(), _live_ctx(has_exchange_credentials=False))
    assert order.status.value == "FILLED"


def test_risk_rejects_live_without_configured_approval_token() -> None:
    engine = RiskEngine(
        _live_settings(live_approval_token=None),
        state=RiskEngineState(),
    )
    result = engine.evaluate(_req(), _live_ctx(live_approval_valid=True))
    assert result.reason_code == RiskReasonCode.INVALID_LIVE_APPROVAL


def test_get_risk_engine_singleton_after_reset() -> None:
    import app.risk.engine as risk_mod

    risk_mod._ENGINE = None
    a = get_risk_engine()
    b = get_risk_engine()
    assert a is b
    reset_risk_engine()
    c = get_risk_engine()
    assert c is not a
