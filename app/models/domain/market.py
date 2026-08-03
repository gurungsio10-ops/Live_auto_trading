"""Market data domain models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.time import ensure_utc


class Candle(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbol: str
    timeframe: str
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: datetime | None = None
    quote_volume: Decimal | None = None
    trade_count: int | None = None
    is_closed: bool = True

    @field_validator("open_time", "close_time")
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return ensure_utc(value)

    @model_validator(mode="after")
    def _ohlc_sanity(self) -> Candle:
        if self.low > self.open or self.low > self.close:
            raise ValueError("low must be <= open and close")
        if self.high < self.open or self.high < self.close:
            raise ValueError("high must be >= open and close")
        if self.high < self.low:
            raise ValueError("high must be >= low")
        if self.volume < 0:
            raise ValueError("volume must be >= 0")
        return self


class SymbolInfo(BaseModel):
    symbol: str
    base: str
    quote: str
    price_precision: int = Field(ge=0)
    quantity_precision: int = Field(ge=0)
    min_quantity: Decimal
    min_notional: Decimal
    tick_size: Decimal
    step_size: Decimal
    active: bool = True
