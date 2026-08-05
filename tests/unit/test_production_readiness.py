"""Production-readiness unit tests (paper/testnet only — no live money)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.config import Settings
from app.services.paper_session import reset_paper_session
from app.services.reconciliation import run_paper_reconciliation
from app.services.trading_scheduler import scheduler_status


@pytest.mark.asyncio
async def test_reconciliation_healthy_on_fresh_session():
    reset_paper_session()
    result = await run_paper_reconciliation()
    assert result.healthy is True
    assert result.cash_ok is True


@pytest.mark.asyncio
async def test_reconciliation_flags_negative_cash():
    session = reset_paper_session()
    session.paper.state.cash = Decimal("-1")
    result = await run_paper_reconciliation()
    assert result.healthy is False
    assert session.risk_engine.state.reconciliation_healthy is False


def test_scheduler_disabled_by_default():
    s = Settings(_env_file=None)
    assert s.enable_trading_scheduler is False
    assert s.use_live_market_data is False
    status = scheduler_status()
    assert "running" in status


def test_production_config_flags_present():
    s = Settings(
        ENABLE_TRADING_SCHEDULER="true",
        USE_LIVE_MARKET_DATA="false",
        PAPER_CYCLE_INTERVAL_SECONDS="90",
        _env_file=None,
    )
    assert s.enable_trading_scheduler is True
    assert s.paper_cycle_interval_seconds == 90
    assert s.trading_mode == "paper"
    assert s.live_trading_enabled is False
