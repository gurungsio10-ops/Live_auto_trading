"""Short deterministic soak for CI (no exchange credentials)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.paper_soak import SoakConfig, run_paper_soak


@pytest.mark.asyncio
async def test_short_paper_soak(tmp_path: Path):
    summary = await run_paper_soak(
        SoakConfig(
            duration_hours=0.001,
            symbols=["BTC/USDT"],
            restart_interval_minutes=0.0001,
            seed=42,
            artifact_dir=tmp_path / "soak",
            max_cycles=6,
        )
    )
    assert summary["cycles"] >= 1
    assert summary["live_money"] is False
    assert (tmp_path / "soak" / "summary.json").exists()
    assert (tmp_path / "soak" / "events.jsonl").exists()
    assert (tmp_path / "soak" / "equity.csv").exists()
    assert (tmp_path / "soak" / "invariants.json").exists()
    assert (tmp_path / "soak" / "reconciliation.json").exists()
