"""Phase 2: exponential backoff retry."""

from __future__ import annotations

import pytest

from app.market_data.providers.retry import ProviderRetryError, with_exponential_backoff


@pytest.mark.asyncio
async def test_retry_eventually_succeeds():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    result = await with_exponential_backoff(
        flaky, max_attempts=5, base_delay=0.001, jitter=0
    )
    assert result == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_retry_exhaustion():
    async def always_fail():
        raise RuntimeError("nope")

    with pytest.raises(ProviderRetryError):
        await with_exponential_backoff(
            always_fail, max_attempts=3, base_delay=0.001, jitter=0
        )
