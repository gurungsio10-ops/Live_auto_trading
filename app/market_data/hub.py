"""
Unified MarketDataHub — production paper/testnet observation layer.

Wraps the existing facade MarketDataService. Adds heartbeat, exchange-time
skew tracking, and advisory derivatives snapshots (funding / OI).

Does NOT place orders. Futures/leverage trading remain blocked by SafetyGuard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.time import utc_now
from app.market_data.facade import MarketDataService, create_provider
from app.models.domain.market import Candle

logger = get_logger("market_data.hub")


class MarketDataHubProtocol(Protocol):
    async def load_closed_validated(
        self, symbol: str, timeframe: str, *, limit: int = 200
    ) -> list[Candle]: ...

    async def get_latest_price(self, symbol: str) -> Decimal: ...

    def status(self) -> dict[str, Any]: ...


@dataclass
class AdvisoryDerivativesSnapshot:
    """Read-only derivatives context — never used to enable futures trading."""

    symbol: str
    funding_rate: Decimal | None = None
    open_interest: Decimal | None = None
    mark_price: Decimal | None = None
    as_of: datetime | None = None
    source: str = "unavailable"
    advisory: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "funding_rate": (
                str(self.funding_rate) if self.funding_rate is not None else None
            ),
            "open_interest": str(self.open_interest)
            if self.open_interest is not None
            else None,
            "mark_price": str(self.mark_price) if self.mark_price is not None else None,
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "source": self.source,
            "advisory": True,
            "note": "Advisory only — does not enable futures/leverage trading",
        }


@dataclass
class MarketDataHub:
    """Unified market-data interface for paper production runtime."""

    settings: Settings = field(default_factory=get_settings)
    service: MarketDataService | None = None
    _last_success_at: datetime | None = field(default=None, init=False)
    _last_error: str | None = field(default=None, init=False)
    _heartbeat_at: datetime | None = field(default=None, init=False)
    _fetch_ok: int = field(default=0, init=False)
    _fetch_fail: int = field(default=0, init=False)
    _exchange_skew_ms: int | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.service is None:
            self.service = MarketDataService(
                provider=create_provider(self.settings), settings=self.settings
            )

    async def load_closed_validated(
        self, symbol: str, timeframe: str, *, limit: int = 200
    ) -> list[Candle]:
        assert self.service is not None
        self._heartbeat_at = utc_now()
        try:
            candles = await self.service.load_closed_validated(
                symbol, timeframe, limit=limit
            )
            self._last_success_at = utc_now()
            self._last_error = None
            self._fetch_ok += 1
            if candles:
                # Approximate exchange time sync via last candle close/open.
                skew = int((utc_now() - candles[-1].open_time).total_seconds() * 1000)
                self._exchange_skew_ms = skew
            return candles
        except Exception as exc:
            self._fetch_fail += 1
            self._last_error = str(exc)[:300]
            logger.warning(
                "market_data_fetch_failed",
                extra={"symbol": symbol, "error": self._last_error},
            )
            raise

    async def get_latest_price(self, symbol: str) -> Decimal:
        assert self.service is not None
        self._heartbeat_at = utc_now()
        price = await self.service.get_latest_price(symbol)
        self._last_success_at = utc_now()
        return price

    async def fetch_advisory_derivatives(
        self, symbol: str
    ) -> AdvisoryDerivativesSnapshot:
        """
        Best-effort public derivatives snapshot via CCXT when available.

        Always advisory. Never enables futures order placement.
        """
        assert self.service is not None
        provider = self.service.provider
        exchange = getattr(provider, "_exchange", None) or getattr(
            provider, "exchange", None
        )
        snap = AdvisoryDerivativesSnapshot(symbol=symbol, as_of=utc_now())
        if exchange is None:
            return snap
        try:
            # CCXT optional helpers — fail soft.
            if hasattr(exchange, "fetch_funding_rate"):
                fr = await exchange.fetch_funding_rate(symbol)
                if isinstance(fr, dict):
                    rate = fr.get("fundingRate")
                    if rate is not None:
                        snap.funding_rate = Decimal(str(rate))
                    snap.source = "ccxt_funding_rate"
            if hasattr(exchange, "fetch_open_interest"):
                oi = await exchange.fetch_open_interest(symbol)
                if isinstance(oi, dict) and oi.get("openInterestAmount") is not None:
                    snap.open_interest = Decimal(str(oi["openInterestAmount"]))
                    snap.source = (
                        "ccxt_funding_and_oi"
                        if snap.funding_rate is not None
                        else "ccxt_open_interest"
                    )
            try:
                snap.mark_price = await self.get_latest_price(symbol)
            except Exception:
                pass
        except Exception as exc:
            snap.source = f"unavailable:{type(exc).__name__}"
        return snap

    def status(self) -> dict[str, Any]:
        stale = True
        if self._last_success_at is not None:
            age = (utc_now() - self._last_success_at).total_seconds()
            stale = age > float(self.settings.market_data_stale_seconds)
        return {
            "healthy": self._last_error is None and not stale,
            "stale": stale,
            "heartbeat_at": self._heartbeat_at.isoformat()
            if self._heartbeat_at
            else None,
            "last_success_at": self._last_success_at.isoformat()
            if self._last_success_at
            else None,
            "last_error": self._last_error,
            "fetch_ok": self._fetch_ok,
            "fetch_fail": self._fetch_fail,
            "exchange_skew_ms": self._exchange_skew_ms,
            "exchange_id": self.settings.exchange_id,
            "use_live_market_data": self.settings.use_live_market_data,
            "websocket_observation_only": True,
            "banner": "PAPER TRADING — NO REAL FUNDS",
        }

    async def close(self) -> None:
        if self.service is not None:
            await self.service.close()


_HUB: MarketDataHub | None = None


def get_market_data_hub() -> MarketDataHub:
    global _HUB
    if _HUB is None:
        _HUB = MarketDataHub()
    return _HUB
