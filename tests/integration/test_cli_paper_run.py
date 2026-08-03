"""Stage 7 — CLI paper-run smoke test (offline, deterministic, no network)."""

from __future__ import annotations

import argparse

import pytest

from app.cli import paper_run


def _args(**overrides):
    base = {
        "symbol": "BTC/USDT",
        "interval": "1m",
        "strategy": "ema_trend",
        "duration_minutes": 0,
        "exchange": "binance",
        "warmup": 120,
        "poll_seconds": 0,
        "max_candle_age": None,
        "offline": True,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


@pytest.mark.asyncio
async def test_offline_paper_run_starts_and_exits_cleanly(capsys):
    rc = await paper_run(_args())
    assert rc == 0
    out = capsys.readouterr().out
    assert "PAPER MODE" in out
    assert "PAPER-RUN SESSION SUMMARY" in out
    assert "candles_received" in out


@pytest.mark.asyncio
async def test_paper_run_refuses_non_paper_mode(monkeypatch):
    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.cli.get_settings",
        lambda: Settings(trading_mode="live", live_trading_enabled=True),
    )
    rc = await paper_run(_args())
    assert rc == 2  # hard refusal to run outside paper mode


@pytest.mark.asyncio
async def test_offline_paper_run_unknown_strategy():
    rc = await paper_run(_args(strategy="does_not_exist"))
    assert rc == 2
