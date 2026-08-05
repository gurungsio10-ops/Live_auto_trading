"""Decision feed and Atlas Brain evidence rules."""

from __future__ import annotations

import pytest

from app.services.atlas_brain import build_atlas_brain
from app.services.decision_feed import build_decision_feed
from app.services import paper_cycle


@pytest.mark.asyncio
async def test_decision_feed_never_invents_confidence() -> None:
    items = build_decision_feed(limit=20)
    assert isinstance(items, list)
    for item in items:
        conf = item.get("confidence")
        assert conf is None or (isinstance(conf, str) and conf not in {"", "0", "0.0"})


@pytest.mark.asyncio
async def test_atlas_brain_marks_missing_confidence() -> None:
    brain = await build_atlas_brain()
    assert brain["title"] == "Atlas Brain"
    assert brain["confidence_source"] in {"unavailable", "strategy_output"}
    if brain["confidence"] is None:
        assert brain["confidence_source"] == "unavailable"
    assert "explanation" in brain
    assert brain["data_freshness"] in {"simulated_fixtures", "public_live", "stale"}


@pytest.mark.asyncio
async def test_cycle_in_flight_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate locked cycle
    monkeypatch.setattr(paper_cycle, "_CYCLE_IN_FLIGHT", True)
    result = await paper_cycle.run_paper_trading_cycle(symbol="BTC/USDT", timeframe="1m")
    assert result.reject_reason == "CYCLE_IN_FLIGHT"
    assert result.accepted is False
