"""Phase 13: news sentiment adjustments — never triggers orders."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.models.domain.enums import RiskReasonCode
from app.news.sentiment import InMemoryNewsProvider, NewsSentimentService


def _item(**overrides) -> dict:
    data = {
        "source": "wire",
        "title": "Bitcoin update",
        "body": "market note",
        "source_timestamp": datetime.now(UTC).isoformat(),
        "symbols": ["BTC/USDT"],
        "sentiment": "0",
        "relevance": "0.9",
        "confidence": "0.8",
        "category": "market",
    }
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_reduce_on_negative_news():
    provider = InMemoryNewsProvider(
        [
            _item(
                title="Bitcoin plunges amid ETF outflows",
                body="BTC sells off",
                sentiment="-0.8",
            )
        ]
    )
    svc = NewsSentimentService(provider)
    adj = await svc.evaluate_for_symbol("BTC/USDT")
    assert adj.action == "reduce"
    assert adj.size_multiplier == Decimal("0.5")
    assert adj.reason_code == RiskReasonCode.SIZE_REDUCED_BY_NEWS


@pytest.mark.asyncio
async def test_block_on_extreme_uncertainty():
    provider = InMemoryNewsProvider(
        [
            _item(
                title="Unconfirmed BTC rumor",
                body="unclear",
                sentiment="0",
                confidence="0.1",
                category="rumor",
            )
        ]
    )
    svc = NewsSentimentService(provider)
    adj = await svc.evaluate_for_symbol("BTC/USDT")
    assert adj.action == "block"
    assert adj.size_multiplier == Decimal("0")
    assert adj.reason_code == RiskReasonCode.NEWS_EXTREME_UNCERTAINTY


@pytest.mark.asyncio
async def test_allow_when_no_relevant_news():
    provider = InMemoryNewsProvider([_item(relevance="0.1", sentiment="-0.9")])
    svc = NewsSentimentService(provider)
    adj = await svc.evaluate_for_symbol("BTC/USDT")
    assert adj.action == "allow"
    assert adj.size_multiplier == Decimal("1")
    assert adj.message == "no relevant news"


@pytest.mark.asyncio
async def test_require_confirmation_on_mild_negative():
    provider = InMemoryNewsProvider([_item(sentiment="-0.3", confidence="0.9")])
    svc = NewsSentimentService(provider)
    adj = await svc.evaluate_for_symbol("BTC/USDT")
    assert adj.action == "require_confirmation"
    assert adj.size_multiplier == Decimal("1")


@pytest.mark.asyncio
async def test_allow_on_supportive_news():
    provider = InMemoryNewsProvider([_item(sentiment="0.4", confidence="0.9")])
    svc = NewsSentimentService(provider)
    adj = await svc.evaluate_for_symbol("BTC/USDT")
    assert adj.action == "allow"
    assert "supportive" in adj.message or "neutral" in adj.message


@pytest.mark.asyncio
async def test_provider_fetch_all_when_symbol_none():
    provider = InMemoryNewsProvider(
        [_item(), _item(title="other", symbols=["ETH/USDT"])]
    )
    rows = await provider.fetch_recent()
    assert len(rows) == 2


def test_symbol_extraction_and_dedup():
    svc = NewsSentimentService(InMemoryNewsProvider())
    assert "BTC/USDT" in svc.extract_symbols("Bitcoin (BTC) rises")
    assert "ETH/USDT" in svc.extract_symbols("Ethereum ETH moves")
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


def test_normalize_rejects_missing_timestamp_and_stale():
    svc = NewsSentimentService(InMemoryNewsProvider())
    assert svc.normalize({"source": "a", "title": "t"}) is None
    stale = _item(
        source_timestamp=(datetime.now(UTC) - timedelta(hours=12)).isoformat()
    )
    assert svc.normalize(stale) is None


def test_news_module_never_submits_orders():
    src = Path("app/news/sentiment.py").read_text(encoding="utf-8")
    assert "from app.execution" not in src
    assert "OrderGateway" not in src
    assert "create_order" not in src
    assert "Never triggers an order" in src or "never" in src.lower()
    # Adjustments only modulate sizing / blocking
    assert "size_multiplier" in src
    assert "RiskReasonCode.NEWS_EXTREME_UNCERTAINTY" in src
    assert "RiskReasonCode.SIZE_REDUCED_BY_NEWS" in src
