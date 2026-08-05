"""Deterministic offline market-data provider (explicitly labelled simulated)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from app.market_data.providers.base import MarketDataProvider
from app.models.domain.market import Candle, SymbolInfo
from app.services.sample_market import build_ema_crossover_candles


class OfflineFixtureProvider(MarketDataProvider):
    """Offline fixtures — never presented as live exchange prices."""

    name = "offline_fixture"
    mode = "simulated"

    def __init__(self, *, base_price: Decimal = Decimal("65000")) -> None:
        self.base_price = base_price

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 500,
    ) -> Sequence[Candle]:
        candles = build_ema_crossover_candles(
            symbol=symbol,
            interval=timeframe,
            base_price=self.base_price,
            force_buy_on_last=True,
        )
        closed = [c for c in candles if c.is_closed]
        if since is not None:
            closed = [c for c in closed if c.open_time >= since]
        if until is not None:
            closed = [c for c in closed if c.open_time <= until]
        return closed[-limit:] if limit else closed

    async def fetch_symbols(self) -> Sequence[SymbolInfo]:
        return [
            SymbolInfo(
                symbol="BTC/USDT",
                base="BTC",
                quote="USDT",
                price_precision=2,
                quantity_precision=8,
                min_quantity=Decimal("0.00001"),
                min_notional=Decimal("10"),
                tick_size=Decimal("0.01"),
                step_size=Decimal("0.00001"),
                active=True,
            )
        ]

    async def close(self) -> None:
        return None

    async def health(self) -> dict[str, str]:
        return {
            "provider": self.name,
            "mode": self.mode,
            "status": "ok",
            "label": "Simulated offline fixtures (not live exchange data)",
        }
