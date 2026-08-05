"""Tests for unified system status aggregation."""

from __future__ import annotations

import pytest

from app.services.system_status import ComponentState, build_unified_system_status


@pytest.mark.asyncio
async def test_unified_status_paper_ok_when_idle() -> None:
    status = await build_unified_system_status()
    assert status["trading_mode"] == "paper"
    assert status["live_trading_enabled"] is False
    assert status["kill_switch"]["enabled"] is False or status["kill_switch"]["state"] in {
        ComponentState.ON.value,
        ComponentState.OFF.value,
    }
    assert "engine" in status
    assert "degraded_reasons" in status
    assert status["market_data"]["provider"] in {"offline_fixture", "binance_public"}
    assert status["exchange"]["adapter"] == "MockExchangeAdapter"
    # Idle healthy paper system should not be DISCONNECTED
    assert status["status"] in {
        ComponentState.OK.value,
        ComponentState.RUNNING.value,
        ComponentState.DEGRADED.value,
        ComponentState.PAUSED.value,
    }
