"""Phase 13.5 + 14: testnet client and live gating (all 9 conditions)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.execution.exchange import ExchangeTestnetClient
from app.execution.exchange.testnet import TestnetConfig
from app.execution.live_gate import LIVE_CONDITIONS, LiveReadinessState, LiveTradingGate
from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
)
from app.models.domain.trading import OrderRequest, RiskEvaluation


def _approved(qty: Decimal = Decimal("0.01")) -> RiskEvaluation:
    return RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=qty,
    )


def _request(**overrides: object) -> OrderRequest:
    base: dict[str, object] = {
        "symbol": "BTC/USDT",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "quantity": Decimal("0.01"),
        "idempotency_key": "tn-key",
    }
    base.update(overrides)
    return OrderRequest(**base)  # type: ignore[arg-type]


def _mock_api(**raw: object) -> MagicMock:
    api = MagicMock()
    payload = {"id": "tn-1", "filled": "0.01", "average": "100000"}
    payload.update(raw)
    api.create_order = AsyncMock(return_value=payload)
    return api


@pytest.mark.asyncio
async def test_testnet_submit_mocked() -> None:
    api = _mock_api()
    client = ExchangeTestnetClient(api=api)
    order = await client.submit(_request(), _approved())
    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == Decimal("0.01")
    assert order.average_fill_price == Decimal("100000")
    api.create_order.assert_awaited_once()


@pytest.mark.asyncio
async def test_testnet_rejects_when_risk_not_approved() -> None:
    api = _mock_api()
    client = ExchangeTestnetClient(api=api)
    order = await client.submit(
        _request(),
        RiskEvaluation(
            decision=RiskDecision.REJECTED,
            reason_code=RiskReasonCode.MAX_POSITION_EXPOSURE,
            message="too large",
        ),
    )
    assert order.status == OrderStatus.REJECTED
    assert order.risk_decision == RiskDecision.REJECTED
    assert order.risk_reason_code == RiskReasonCode.MAX_POSITION_EXPOSURE
    api.create_order.assert_not_called()


@pytest.mark.asyncio
async def test_testnet_rejects_when_risk_halted() -> None:
    api = _mock_api()
    client = ExchangeTestnetClient(api=api)
    order = await client.submit(
        _request(),
        RiskEvaluation(
            decision=RiskDecision.HALTED,
            reason_code=RiskReasonCode.KILL_SWITCH_ACTIVE,
        ),
    )
    assert order.status == OrderStatus.REJECTED
    assert order.risk_decision == RiskDecision.HALTED
    api.create_order.assert_not_called()


@pytest.mark.asyncio
async def test_testnet_partial_fill() -> None:
    api = _mock_api(filled="0.004", average="99000")
    client = ExchangeTestnetClient(api=api)
    order = await client.submit(_request(quantity=Decimal("0.01")), _approved())
    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert order.filled_quantity == Decimal("0.004")
    assert order.average_fill_price == Decimal("99000")


@pytest.mark.asyncio
async def test_testnet_rate_limit_blocks_burst() -> None:
    api = _mock_api()
    client = ExchangeTestnetClient(
        api=api,
        config=TestnetConfig(exchange_env="testnet", rate_limit_per_minute=2),
    )
    assert (await client.submit(_request(idempotency_key="a"), _approved())).status == (
        OrderStatus.FILLED
    )
    assert (await client.submit(_request(idempotency_key="b"), _approved())).status == (
        OrderStatus.FILLED
    )
    limited = await client.submit(_request(idempotency_key="c"), _approved())
    assert limited.status == OrderStatus.FAILED
    assert limited.metadata == {"error": "rate_limited"}
    assert api.create_order.await_count == 2


def test_testnet_marks_env_mismatch_when_settings_not_testnet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXCHANGE_ENV", "paper")
    get_settings.cache_clear()
    client = ExchangeTestnetClient(api=MagicMock())
    assert client._env_mismatch is True


def test_testnet_env_matches_when_settings_testnet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXCHANGE_ENV", "testnet")
    get_settings.cache_clear()
    client = ExchangeTestnetClient(api=MagicMock())
    assert client._env_mismatch is False
    assert get_settings().exchange_env == "testnet"


def test_live_conditions_are_exactly_nine() -> None:
    assert len(LIVE_CONDITIONS) == 9
    assert "valid_live_approval_token" in LIVE_CONDITIONS


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


def test_live_gate_all_nine_pass() -> None:
    gate = LiveTradingGate(
        _live_settings(),
        LiveReadinessState(
            risk_engine_healthy=True,
            market_data_healthy=True,
            database_healthy=True,
            reconciliation_healthy=True,
            balances_verified=True,
            clock_synced=True,
            account_readable=True,
        ),
        presented_approval_token="approve-live-token-1234567890",
    )
    result = gate.evaluate()
    assert result.allowed is True
    assert result.failed_conditions == []
    assert set(result.details["conditions"]) == set(LIVE_CONDITIONS)


@pytest.mark.parametrize(
    "override_settings,override_state,token,expected_condition",
    [
        (
            {"trading_mode": "paper"},
            {},
            "approve-live-token-1234567890",
            "trading_mode_live",
        ),
        (
            {"live_trading_enabled": False},
            {},
            "approve-live-token-1234567890",
            "live_trading_enabled",
        ),
        (
            {"kill_switch_enabled": True},
            {},
            "approve-live-token-1234567890",
            "kill_switch_off",
        ),
        (
            {"exchange_api_key": None, "exchange_api_secret": None},
            {},
            "approve-live-token-1234567890",
            "valid_credentials",
        ),
        (
            {},
            {"risk_engine_healthy": False},
            "approve-live-token-1234567890",
            "risk_engine_healthy",
        ),
        (
            {},
            {"market_data_healthy": False},
            "approve-live-token-1234567890",
            "market_data_healthy",
        ),
        (
            {},
            {"database_healthy": False},
            "approve-live-token-1234567890",
            "database_healthy",
        ),
        (
            {},
            {"reconciliation_healthy": False},
            "approve-live-token-1234567890",
            "reconciliation_healthy",
        ),
        ({}, {}, "wrong-token", "valid_live_approval_token"),
    ],
)
def test_each_live_condition_blocks_individually(
    override_settings: dict,
    override_state: dict,
    token: str,
    expected_condition: str,
) -> None:
    state_kwargs = dict(
        risk_engine_healthy=True,
        market_data_healthy=True,
        database_healthy=True,
        reconciliation_healthy=True,
        balances_verified=True,
        clock_synced=True,
        account_readable=True,
    )
    state_kwargs.update(override_state)
    gate = LiveTradingGate(
        _live_settings(**override_settings),
        LiveReadinessState(**state_kwargs),
        presented_approval_token=token,
    )
    result = gate.evaluate()
    assert result.allowed is False
    assert expected_condition in result.failed_conditions
    assert expected_condition in result.details["failed_conditions"]
