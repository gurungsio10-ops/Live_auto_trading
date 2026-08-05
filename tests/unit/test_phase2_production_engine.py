"""Phase 2 production engine unit tests (paper-only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.decision import AdvisoryDecisionEngine
from app.backtesting.metrics import compute_metrics
from app.core.config import Settings, get_settings
from app.core.time import utc_now
from app.execution.paper.engine import PaperConfig, PaperTradingEngine
from app.market_data.hub import MarketDataHub
from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
    SignalDirection,
)
from app.models.domain.trading import OrderRequest, RiskEvaluation, TradeSignal
from app.portfolio.manager import PortfolioManager
from app.services.paper_session import reset_paper_session


@pytest.fixture(autouse=True)
def _reset():
    get_settings.cache_clear()
    reset_paper_session()
    yield
    reset_paper_session()
    get_settings.cache_clear()


def test_cycle_lock_fail_closed_default():
    s = Settings(_env_file=None)
    assert s.cycle_lock_fail_closed is True


def test_portfolio_manager_spot_paper_leverage():
    reset_paper_session()
    snap = PortfolioManager().snapshot()
    assert snap["leverage"] == "1"
    assert snap["margin_mode"] == "spot_paper"
    assert "weekly_pnl" in snap
    assert "monthly_pnl" in snap
    assert snap["banner"].startswith("PAPER")


def test_market_data_hub_status_shape():
    hub = MarketDataHub(settings=Settings(_env_file=None))
    status = hub.status()
    assert "heartbeat_at" in status
    assert status["websocket_observation_only"] is True
    assert status["banner"].startswith("PAPER")


def test_advisory_decision_rejects_low_score():
    engine = AdvisoryDecisionEngine()
    signal = TradeSignal(
        strategy_name="test",
        strategy_version="1",
        symbol="BTC/USDT",
        direction=SignalDirection.BUY,
        confidence=Decimal("0.2"),
        entry_rationale="weak",
        invalidation_condition="stop",
        input_data_fingerprint="fp-weak",
        suggested_entry=Decimal("100"),
        suggested_stop=Decimal("99"),
        suggested_target=Decimal("103"),
        timestamp=utc_now(),
        metadata={"indicators": {"close": "100"}},
    )
    decision = engine.evaluate(signal)
    assert decision.advisory is True
    assert decision.reject_reason == "LOW_QUALITY_SETUP"
    assert decision.direction == "hold"
    assert "order_submission" in decision.to_dict()["forbidden"]


def test_advisory_decision_scores_strong_setup():
    engine = AdvisoryDecisionEngine()
    signal = TradeSignal(
        strategy_name="test",
        strategy_version="1",
        symbol="BTC/USDT",
        direction=SignalDirection.BUY,
        confidence=Decimal("0.8"),
        entry_rationale="strong trend",
        invalidation_condition="stop",
        input_data_fingerprint="fp-strong",
        suggested_entry=Decimal("100"),
        suggested_stop=Decimal("98"),
        suggested_target=Decimal("106"),
        timestamp=utc_now(),
        metadata={"indicators": {"close": "100"}},
    )
    decision = engine.evaluate(signal, trend_strength=Decimal("0.7"))
    assert decision.reject_reason is None
    assert decision.direction == "buy"
    assert decision.risk_reward > 0
    assert decision.recommended_size_fraction > 0


@pytest.mark.asyncio
async def test_paper_engine_cancel_before_fill():
    paper = PaperTradingEngine(PaperConfig(initial_cash=Decimal("10000")))
    paper.set_mark_price("BTC/USDT", Decimal("100"))
    # Limit buy below market rests unfilled.
    req = OrderRequest(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.01"),
        price=Decimal("90"),
        idempotency_key="cancel-test-1",
        strategy_name="test",
    )
    risk = RiskEvaluation(
        decision=RiskDecision.APPROVED,
        reason_code=RiskReasonCode.OK,
        approved_quantity=Decimal("0.01"),
        message="ok",
    )
    order = await paper.submit(req, risk)
    assert order.status == OrderStatus.SUBMITTED
    cancelled = await paper.cancel(order.id)
    assert cancelled.status == OrderStatus.CANCELLED


def test_backtest_metrics_include_cagr():
    start = datetime(2024, 1, 1, tzinfo=UTC)
    curve = [
        (start, Decimal("10000")),
        (start + timedelta(days=365), Decimal("12000")),
    ]

    class _T:
        def __init__(self) -> None:
            self.pnl = Decimal("100")
            self.fees = Decimal("1")
            self.slippage_cost = Decimal("0")
            self.entry_time = start
            self.exit_time = start + timedelta(days=10)

    metrics = compute_metrics(
        trades=[_T()],  # type: ignore[list-item]
        equity_curve=curve,
        initial_cash=Decimal("10000"),
        final_equity=Decimal("12000"),
    )
    assert metrics.cagr > 0
    assert metrics.average_trade == metrics.expectancy
    assert "cagr" in metrics.to_dict()


@pytest.mark.asyncio
async def test_ops_endpoints_and_cors_headers():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        h = await client.get("/health")
        assert h.status_code == 200
        body = h.json()
        assert "market_data" in body
        port = await client.get("/api/portfolio/manager")
        assert port.status_code == 200
        assert port.json()["leverage"] == "1"
        md = await client.get("/api/market/status")
        assert md.status_code == 200
        score = await client.post(
            "/api/ai/score-signal",
            json={
                "direction": "buy",
                "confidence": "0.9",
                "suggested_entry": "100",
                "suggested_stop": "98",
                "suggested_target": "106",
                "reason": "unit",
            },
        )
        assert score.status_code == 200
        assert score.json()["advisory"] is True
