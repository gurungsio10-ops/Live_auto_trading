"""Phase 13: news sentiment adjustments — never triggers orders."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.news.sentiment import InMemoryNewsProvider, NewsSentimentService


@pytest.mark.asyncio
async def test_reduce_on_negative_news():
    provider = InMemoryNewsProvider(
        [
            {
                "source": "wire",
                "title": "Bitcoin plunges amid ETF outflows",
                "body": "BTC sells off",
                "source_timestamp": datetime.now(UTC).isoformat(),
                "symbols": ["BTC/USDT"],
                "sentiment": "-0.8",
                "relevance": "0.9",
                "confidence": "0.8",
                "category": "market",
            }
        ]
    )
    svc = NewsSentimentService(provider)
    adj = await svc.evaluate_for_symbol("BTC/USDT")
    assert adj.action == "reduce"
    assert adj.size_multiplier == Decimal("0.5")


@pytest.mark.asyncio
async def test_block_on_extreme_uncertainty():
    provider = InMemoryNewsProvider(
        [
            {
                "source": "wire",
                "title": "Unconfirmed BTC rumor",
                "body": "unclear",
                "source_timestamp": datetime.now(UTC).isoformat(),
                "symbols": ["BTC/USDT"],
                "sentiment": "0",
                "relevance": "0.9",
                "confidence": "0.1",
                "category": "rumor",
            }
        ]
    )
    svc = NewsSentimentService(provider)
    adj = await svc.evaluate_for_symbol("BTC/USDT")
    assert adj.action == "block"
    assert adj.size_multiplier == Decimal("0")


def test_symbol_extraction_and_dedup():
    svc = NewsSentimentService(InMemoryNewsProvider())
    assert "BTC/USDT" in svc.extract_symbols("Bitcoin (BTC) rises")
    raw = {
        "source": "a",
        "title": "t",
        "source_timestamp": datetime.now(UTC),
        "sentiment": "0",
        "relevance": "1",
        "confidence": "1",
    }
    assert svc.normalize(raw) is not None
    assert svc.normalize(raw) is None  # dedup
