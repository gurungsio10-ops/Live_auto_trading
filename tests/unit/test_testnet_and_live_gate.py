"""Phase 13.5 + 14: testnet client and live gating (all 9 conditions)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.execution.exchange import ExchangeTestnetClient
from app.execution.live_gate import LIVE_CONDITIONS, LiveReadinessState, LiveTradingGate
from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
)
from app.models.domain.trading import OrderRequest, RiskEvaluation


@pytest.mark.asyncio
async def test_testnet_submit_mocked():
    api = MagicMock()
    api.create_order = AsyncMock(
        return_value={"id": "tn-1", "filled": "0.01", "average": "100000"}
    )
    client = ExchangeTestnetClient(api=api)
    order = await client.submit(
        OrderRequest(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.01"),
            idempotency_key="tn-key",
        ),
        RiskEvaluation(
            decision=RiskDecision.APPROVED,
            reason_code=RiskReasonCode.OK,
            approved_quantity=Decimal("0.01"),
        ),
    )
    assert order.status == OrderStatus.FILLED
    api.create_order.assert_awaited_once()


def _live_settings(**overrides) -> Settings:
    data = dict(
        trading_mode="live",
        live_trading_enabled=True,
        kill_switch_enabled=False,
        exchange_api_key=SecretStr("key-123456789012345678901234"),
        exchange_api_secret=SecretStr("secret-123456789012345678901234"),
        _env_file=None,
    )
    data.update(overrides)
    return Settings(**data)


def test_live_gate_all_nine_pass():
    gate = LiveTradingGate(
        _live_settings(),
        LiveReadinessState(live_approval_valid=True),
    )
    result = gate.evaluate()
    assert result.allowed is True
    assert result.failed_conditions == []
    assert set(result.details) == set(LIVE_CONDITIONS)


@pytest.mark.parametrize(
    "override_settings,override_state,expected_condition",
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
    ],
)
def test_each_live_condition_blocks_individually(
    override_settings, override_state, expected_condition
):
    state_kwargs = dict(
        risk_engine_healthy=True,
        market_data_healthy=True,
        database_healthy=True,
        reconciliation_healthy=True,
        live_approval_valid=True,
    )
    state_kwargs.update(override_state)
    gate = LiveTradingGate(
        _live_settings(**override_settings), LiveReadinessState(**state_kwargs)
    )
    result = gate.evaluate()
    assert result.allowed is False
    assert expected_condition in result.failed_conditions
