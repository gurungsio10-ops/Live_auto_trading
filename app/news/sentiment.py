"""News sentiment — may only reduce size, block under extreme uncertainty, or require confirmation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol
from uuid import uuid4

from app.core.time import ensure_utc, utc_now
from app.models.domain.enums import RiskReasonCode


@dataclass
class NewsItem:
    id: str
    source: str
    title: str
    body: str
    source_timestamp: datetime
    symbols: list[str]
    sentiment: Decimal  # -1 .. 1
    relevance: Decimal  # 0 .. 1
    confidence: Decimal  # 0 .. 1
    category: str
    ingested_at: datetime = field(default_factory=utc_now)


@dataclass
class NewsRiskAdjustment:
    """Never triggers an order — only modulates risk sizing / blocking."""

    action: str  # allow | reduce | block | require_confirmation
    size_multiplier: Decimal = Decimal("1")
    reason_code: RiskReasonCode | None = None
    message: str = ""


class NewsProvider(Protocol):
    async def fetch_recent(self, *, symbol: str | None = None) -> list[dict[str, Any]]: ...


class InMemoryNewsProvider:
    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self.items = items or []

    async def fetch_recent(self, *, symbol: str | None = None) -> list[dict[str, Any]]:
        if symbol is None:
            return list(self.items)
        return [i for i in self.items if symbol in i.get("symbols", [])]


SYMBOL_ALIASES = {
    "BTC": "BTC/USDT",
    "BITCOIN": "BTC/USDT",
    "ETH": "ETH/USDT",
    "ETHEREUM": "ETH/USDT",
}


class NewsSentimentService:
    def __init__(
        self,
        provider: NewsProvider,
        *,
        max_age: timedelta = timedelta(hours=6),
        extreme_uncertainty_confidence: Decimal = Decimal("0.2"),
        reduce_threshold: Decimal = Decimal("-0.6"),
    ) -> None:
        self.provider = provider
        self.max_age = max_age
        self.extreme_uncertainty_confidence = extreme_uncertainty_confidence
        self.reduce_threshold = reduce_threshold
        self._seen_hashes: set[str] = set()

    def extract_symbols(self, text: str) -> list[str]:
        found: list[str] = []
        upper = text.upper()
        for token, symbol in SYMBOL_ALIASES.items():
            if token in upper and symbol not in found:
                found.append(symbol)
        return found

    def dedup_key(self, item: dict[str, Any]) -> str:
        return f"{item.get('source')}|{item.get('title')}|{item.get('source_timestamp')}"

    def normalize(self, raw: dict[str, Any]) -> NewsItem | None:
        key = self.dedup_key(raw)
        if key in self._seen_hashes:
            return None
        ts = raw.get("source_timestamp")
        if ts is None:
            return None
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        ts = ensure_utc(ts)
        if utc_now() - ts > self.max_age:
            return None  # stale
        self._seen_hashes.add(key)
        text = f"{raw.get('title', '')} {raw.get('body', '')}"
        symbols = list(raw.get("symbols") or self.extract_symbols(text))
        return NewsItem(
            id=str(raw.get("id") or uuid4().hex),
            source=str(raw.get("source") or "unknown"),
            title=str(raw.get("title") or ""),
            body=str(raw.get("body") or ""),
            source_timestamp=ts,
            symbols=symbols,
            sentiment=Decimal(str(raw.get("sentiment", "0"))),
            relevance=Decimal(str(raw.get("relevance", "0"))),
            confidence=Decimal(str(raw.get("confidence", "0"))),
            category=str(raw.get("category") or "general"),
        )

    async def evaluate_for_symbol(self, symbol: str) -> NewsRiskAdjustment:
        raw_items = await self.provider.fetch_recent(symbol=symbol)
        items = [n for r in raw_items if (n := self.normalize(r)) is not None]
        relevant = [i for i in items if symbol in i.symbols and i.relevance >= Decimal("0.5")]
        if not relevant:
            return NewsRiskAdjustment(action="allow", message="no relevant news")

        # Extreme uncertainty → block (does not place an order)
        if any(i.confidence <= self.extreme_uncertainty_confidence for i in relevant):
            return NewsRiskAdjustment(
                action="block",
                size_multiplier=Decimal("0"),
                reason_code=RiskReasonCode.NEWS_EXTREME_UNCERTAINTY,
                message="Blocked under extreme news uncertainty",
            )

        avg_sent = sum((i.sentiment for i in relevant), Decimal("0")) / Decimal(len(relevant))
        if avg_sent <= self.reduce_threshold:
            return NewsRiskAdjustment(
                action="reduce",
                size_multiplier=Decimal("0.5"),
                reason_code=RiskReasonCode.SIZE_REDUCED_BY_NEWS,
                message="Size reduced due to negative news sentiment",
            )
        if avg_sent < Decimal("0"):
            return NewsRiskAdjustment(
                action="require_confirmation",
                size_multiplier=Decimal("1"),
                message="Confirmation required due to mixed/negative news",
            )
        return NewsRiskAdjustment(action="allow", message="news supportive or neutral")
