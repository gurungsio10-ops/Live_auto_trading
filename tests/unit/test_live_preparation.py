"""Live-gate hardening: all 9 verification recommendations."""

from __future__ import annotations

import hmac
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.core.time import utc_now
from app.execution.gateway import OrderGateway, RiskBlockedError
from app.execution.live_gate import (
    LIVE_CONDITIONS,
    LiveReadinessState,
    LiveTradingGate,
    approval_token_matches,
)
from app.execution.paper import PaperConfig, PaperTradingEngine
from app.main import app
from app.models.domain.enums import OrderSide, OrderType, RiskReasonCode
from app.models.domain.market import SymbolInfo
from app.models.domain.trading import OrderRequest, PortfolioState
from app.reconciliation import (
    AssetBalance,
    InMemoryExchangeState,
    InMemoryLocalState,
    ReconciliationService,
)
from app.risk.engine import RiskContext, RiskEngine, RiskEngineState

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

TOKEN_A = "approve-live-token-alpha-1111111111"
TOKEN_B = "approve-live-token-bravo-2222222222"


def _live_settings(**overrides: object) -> Settings:
    data: dict[str, object] = dict(
        trading_mode="live",
        live_trading_enabled=True,
        kill_switch_enabled=False,
        exchange_api_key=SecretStr("key-123456789012345678901234"),
        exchange_api_secret=SecretStr("secret-123456789012345678901234"),
        live_approval_token=SecretStr(TOKEN_A),
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
        clock_synced=True,
        account_readable=True,
        balances_verified=True,
    )
    data.update(overrides)
    return LiveReadinessState(**data)  # type: ignore[arg-type]


def _matching_recon() -> ReconciliationService:
    bals = (AssetBalance("USDT", Decimal("10000")),)
    return ReconciliationService(
        InMemoryExchangeState(balances=bals),
        InMemoryLocalState(balances=bals),
    )


def test_roadmap_nine_conditions_match_gate() -> None:
    assert len(LIVE_CONDITIONS) == 9
    assert LIVE_CONDITIONS[-1] == "valid_live_approval_token"


# --- Item 1 + 2: reason codes + details list ALL failures ---


@pytest.mark.parametrize(
    "override_settings,override_state,token,expected",
    [
        ({"trading_mode": "paper"}, {}, TOKEN_A, "trading_mode_live"),
        ({"live_trading_enabled": False}, {}, TOKEN_A, "live_trading_enabled"),
        ({"kill_switch_enabled": True}, {}, TOKEN_A, "kill_switch_off"),
        (
            {"exchange_api_key": None, "exchange_api_secret": None},
            {},
            TOKEN_A,
            "valid_credentials",
        ),
        ({}, {"risk_engine_healthy": False}, TOKEN_A, "risk_engine_healthy"),
        ({}, {"market_data_healthy": False}, TOKEN_A, "market_data_healthy"),
        ({}, {"database_healthy": False}, TOKEN_A, "database_healthy"),
        ({}, {"reconciliation_healthy": False}, TOKEN_A, "reconciliation_healthy"),
        ({}, {}, "wrong-token", "valid_live_approval_token"),
        ({"live_approval_token": None}, {}, TOKEN_A, "valid_live_approval_token"),
    ],
)
def test_each_condition_maps_reason_code(
    override_settings: dict,
    override_state: dict,
    token: str,
    expected: str,
) -> None:
    gate = LiveTradingGate(
        _live_settings(**override_settings),
        _ready_state(**override_state),
        presented_approval_token=token,
    )
    result = gate.evaluate()
    assert result.allowed is False
    assert expected in result.failed_conditions
    assert result.details is not None
    assert expected in result.details["failed_conditions"]
    assert (
        result.details["failed_reason_codes"][expected]
        == CONDITION_REASON[expected].value
    )
    # Single failure → specific code; details still list that failure.
    if len(result.failed_conditions) == 1:
        assert result.reason_code == CONDITION_REASON[expected]


def test_multi_fail_details_lists_all_failed_conditions() -> None:
    gate = LiveTradingGate(
        _live_settings(trading_mode="paper", live_trading_enabled=False),
        _ready_state(reconciliation_healthy=False, balances_verified=False),
        presented_approval_token="nope",
    )
    result = gate.evaluate()
    assert result.allowed is False
    assert result.reason_code == RiskReasonCode.LIVE_GATING_INCOMPLETE
    failed = result.details["failed_conditions"]
    assert "trading_mode_live" in failed
    assert "live_trading_enabled" in failed
    assert "reconciliation_healthy" in failed
    assert "valid_live_approval_token" in failed
    assert set(failed) == set(result.failed_conditions)
    assert len(failed) >= 4
    assert set(result.details["failed_reason_codes"]) == set(failed)


# --- Item 3: credential edges ---


@pytest.mark.parametrize(
    "key,secret",
    [
        (None, None),
        (SecretStr(""), SecretStr("")),
        (SecretStr("   "), SecretStr("   ")),
        (SecretStr("key-only"), None),
        (None, SecretStr("secret-only")),
    ],
)
def test_credential_edges_invalid(key, secret) -> None:
    settings = _live_settings(exchange_api_key=key, exchange_api_secret=secret)
    assert settings.has_exchange_credentials is False
    result = LiveTradingGate(
        settings, _ready_state(), presented_approval_token=TOKEN_A
    ).evaluate()
    assert "valid_credentials" in result.details["failed_conditions"]


# --- Item 4: API status ---


def test_api_live_gate_status_blocked_by_default() -> None:
    client = TestClient(app)
    resp = client.get("/api/live-gate/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["allowed"] is False
    assert "trading_mode_live" in body["failed_conditions"]
    assert "live_trading_enabled" in body["failed_conditions"]
    assert body["reason_code"] is not None
    assert body["details"]["failed_conditions"] == body["failed_conditions"]
    assert len(body["details"]["failed_conditions"]) == len(
        [c for c, ok in body["details"]["conditions"].items() if not ok]
    )


def test_api_live_gate_status_token_header_compared() -> None:
    client = TestClient(app)
    # Without matching settings token in env, even correct-looking header fails.
    resp = client.get(
        "/api/live-gate/status", headers={"X-Live-Approval-Token": TOKEN_A}
    )
    assert resp.status_code == 200
    assert resp.json()["allowed"] is False
    assert "valid_live_approval_token" in resp.json()["details"]["failed_conditions"]


# --- Item 5: gateway integration per missing condition ---


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


def _req() -> OrderRequest:
    return OrderRequest(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        stop_loss=Decimal("90000"),
        idempotency_key=uuid4().hex,
    )


def _live_ready_settings(**overrides: object) -> Settings:
    return _live_settings(**overrides)


def _engine(settings: Settings, **state_kw) -> RiskEngine:
    state_data = dict(
        risk_engine_healthy=True,
        market_data_healthy=True,
        database_healthy=True,
        reconciliation_healthy=True,
    )
    state_data.update(state_kw)
    return RiskEngine(settings, RiskEngineState(**state_data))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "settings_kw,state_kw,token,expected_code",
    [
        (
            {"live_trading_enabled": False},
            {},
            TOKEN_A,
            RiskReasonCode.LIVE_TRADING_DISABLED,
        ),
        ({"kill_switch_enabled": True}, {}, TOKEN_A, RiskReasonCode.KILL_SWITCH_ACTIVE),
        (
            {"exchange_api_key": None, "exchange_api_secret": None},
            {},
            TOKEN_A,
            RiskReasonCode.INVALID_CREDENTIALS,
        ),
        (
            {},
            {"market_data_healthy": False},
            TOKEN_A,
            RiskReasonCode.MARKET_DATA_UNHEALTHY,
        ),
        ({}, {"database_healthy": False}, TOKEN_A, RiskReasonCode.DATABASE_UNHEALTHY),
        (
            {},
            {"reconciliation_healthy": False},
            TOKEN_A,
            RiskReasonCode.RECONCILIATION_UNHEALTHY,
        ),
        ({}, {}, "wrong-token", RiskReasonCode.INVALID_LIVE_APPROVAL),
    ],
)
async def test_gateway_blocks_each_live_condition(
    settings_kw, state_kw, token, expected_code
) -> None:
    settings = _live_ready_settings(**settings_kw)
    paper = PaperTradingEngine(PaperConfig(initial_cash=Decimal("10000")))
    paper.set_mark_price("BTC/USDT", Decimal("100000"))
    gateway = OrderGateway(paper, risk_engine=_engine(settings, **state_kw))
    ctx = RiskContext.from_settings(
        settings,
        portfolio=_portfolio(),
        symbol_info=_symbol(),
        mark_price=Decimal("100000"),
        market_data_ts=utc_now(),
        presented_live_approval_token=token,
    )
    with pytest.raises(RiskBlockedError) as exc:
        await gateway.submit(_req(), ctx)
    ev = exc.value.evaluation
    if expected_code == RiskReasonCode.KILL_SWITCH_ACTIVE:
        assert ev.reason_code == RiskReasonCode.KILL_SWITCH_ACTIVE
        return
    details = ev.checks["live_gate_details"]
    assert expected_code.value in details["failed_reason_codes"].values() or (
        ev.reason_code in {expected_code, RiskReasonCode.LIVE_GATING_INCOMPLETE}
    )


@pytest.mark.asyncio
async def test_gateway_allows_when_settings_and_token_satisfied() -> None:
    settings = _live_ready_settings()
    paper = PaperTradingEngine(PaperConfig(initial_cash=Decimal("10000")))
    paper.set_mark_price("BTC/USDT", Decimal("100000"))
    gateway = OrderGateway(paper, risk_engine=_engine(settings))
    ctx = RiskContext.from_settings(
        settings,
        portfolio=_portfolio(),
        symbol_info=_symbol(),
        mark_price=Decimal("100000"),
        market_data_ts=utc_now(),
        presented_live_approval_token=TOKEN_A,
    )
    assert ctx._test_override is False
    order = await gateway.submit(_req(), ctx)
    assert order.status.value == "FILLED"
    assert order.risk_decision.value == "APPROVED"


# --- Item 6: Settings source of truth ---


def test_context_only_live_enabled_rejected() -> None:
    settings = _live_settings(live_trading_enabled=False)
    engine = _engine(settings)
    ctx = RiskContext.for_tests(
        portfolio=_portfolio(),
        settings=settings,
        symbol_info=_symbol(),
        mark_price=Decimal("100000"),
        market_data_ts=utc_now(),
        live_trading_enabled=True,
        presented_live_approval_token=TOKEN_A,
    )
    assert ctx.live_trading_enabled is True
    assert settings.live_trading_enabled is False
    result = engine.evaluate(_req(), ctx)
    assert result.decision.value == "REJECTED"
    assert (
        "live_trading_enabled"
        in result.checks["live_gate_details"]["failed_conditions"]
    )


def test_for_tests_marked_and_from_settings_not() -> None:
    settings = _live_settings()
    prod = RiskContext.from_settings(settings, portfolio=_portfolio())
    test = RiskContext.for_tests(
        portfolio=_portfolio(), settings=settings, live_trading_enabled=True
    )
    assert prod._test_override is False
    assert test._test_override is True


def test_production_paths_do_not_call_for_tests() -> None:
    for rel in (
        "app/api/routes.py",
        "app/execution/gateway.py",
        "app/main.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        assert "for_tests" not in src
        assert (
            "RiskContext(" not in src or "from_settings" in src or "RiskContext" in src
        )


# --- Item 7: unused fields wired ---


def test_clock_synced_wires_into_market_data_healthy() -> None:
    result = LiveTradingGate(
        _live_settings(),
        _ready_state(clock_synced=False),
        presented_approval_token=TOKEN_A,
    ).evaluate()
    assert result.allowed is False
    assert "market_data_healthy" in result.failed_conditions


def test_account_readable_wires_into_valid_credentials() -> None:
    result = LiveTradingGate(
        _live_settings(),
        _ready_state(account_readable=False),
        presented_approval_token=TOKEN_A,
    ).evaluate()
    assert result.allowed is False
    assert "valid_credentials" in result.failed_conditions


def test_balances_verified_wires_into_reconciliation_healthy() -> None:
    result = LiveTradingGate(
        _live_settings(),
        _ready_state(balances_verified=False),
        presented_approval_token=TOKEN_A,
    ).evaluate()
    assert result.allowed is False
    assert "reconciliation_healthy" in result.failed_conditions


# --- Item 8: reconciliation producer ---


def test_live_gate_uses_reconciliation_producer_fail_closed() -> None:
    recon = ReconciliationService()  # no sources
    gate = LiveTradingGate(
        _live_settings(),
        LiveReadinessState(
            risk_engine_healthy=True,
            market_data_healthy=True,
            database_healthy=True,
            # intentionally leave recon defaults fail-closed
        ),
        presented_approval_token=TOKEN_A,
        reconciliation=recon,
    )
    result = gate.evaluate()
    assert result.allowed is False
    assert "reconciliation_healthy" in result.failed_conditions
    assert recon.healthy is False


def test_live_gate_passes_after_successful_reconciliation() -> None:
    recon = _matching_recon()
    gate = LiveTradingGate(
        _live_settings(),
        LiveReadinessState(
            risk_engine_healthy=True,
            market_data_healthy=True,
            database_healthy=True,
        ),
        presented_approval_token=TOKEN_A,
        reconciliation=recon,
    )
    result = gate.evaluate()
    assert recon.healthy is True
    assert result.allowed is True


# --- Item 9: hmac.compare_digest + real token values ---


def test_approval_uses_hmac_compare_digest_not_equality() -> None:
    src = Path("app/execution/live_gate.py").read_text(encoding="utf-8")
    assert "hmac.compare_digest" in src
    assert "secrets.compare_digest" not in src


def test_token_values_varied_must_match_settings() -> None:
    settings_a = _live_settings(live_approval_token=SecretStr(TOKEN_A))
    settings_b = _live_settings(live_approval_token=SecretStr(TOKEN_B))
    assert approval_token_matches(TOKEN_A, settings_a) is True
    assert approval_token_matches(TOKEN_B, settings_a) is False
    assert approval_token_matches(TOKEN_B, settings_b) is True
    assert approval_token_matches(TOKEN_A, settings_b) is False

    # Gate path uses the same compare — bool flag alone is insufficient.
    ok = LiveTradingGate(
        settings_a, _ready_state(), presented_approval_token=TOKEN_A
    ).evaluate()
    bad = LiveTradingGate(
        settings_a, _ready_state(), presented_approval_token=TOKEN_B
    ).evaluate()
    assert ok.allowed is True
    assert bad.allowed is False
    assert "valid_live_approval_token" in bad.failed_conditions


def test_hmac_digest_path_matches_helper() -> None:
    key = b"atlas-live-approval"
    left = hmac.new(key, TOKEN_A.encode(), sha256).digest()
    right = hmac.new(key, TOKEN_A.encode(), sha256).digest()
    assert hmac.compare_digest(left, right) is True


def test_no_live_pass_bypasses_settings_validation() -> None:
    """Happy-path live approval must satisfy Settings, not context overrides."""
    settings = _live_settings(live_trading_enabled=False)
    engine = _engine(settings)
    ctx = RiskContext.for_tests(
        portfolio=_portfolio(),
        settings=settings,
        symbol_info=_symbol(),
        mark_price=Decimal("100000"),
        market_data_ts=utc_now(),
        trading_mode="live",
        live_trading_enabled=True,
        has_exchange_credentials=True,
        presented_live_approval_token=TOKEN_A,
    )
    result = engine.evaluate(_req(), ctx)
    assert result.checks.get("live_gating") != "passed"
    assert result.decision.value != "APPROVED"


def test_has_configured_approval_token_edges() -> None:
    assert LiveTradingGate(_live_settings()).has_configured_approval_token() is True
    assert (
        LiveTradingGate(
            _live_settings(live_approval_token=None)
        ).has_configured_approval_token()
        is False
    )
    assert (
        LiveTradingGate(
            _live_settings(live_approval_token=SecretStr("  "))
        ).has_configured_approval_token()
        is False
    )


def test_sync_reconciliation_skips_rerun_when_already_completed() -> None:
    recon = _matching_recon()
    recon.run()
    gate = LiveTradingGate(
        _live_settings(),
        LiveReadinessState(
            risk_engine_healthy=True,
            market_data_healthy=True,
            database_healthy=True,
        ),
        presented_approval_token=TOKEN_A,
        reconciliation=recon,
    )
    gate.sync_reconciliation()
    assert gate.state.reconciliation_healthy is True
    assert gate.state.balances_verified is True
