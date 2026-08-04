"""Trading domain models: signals, orders, positions, risk decisions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.time import utc_now
from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
    SignalDirection,
)


class TradeSignal(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    strategy_name: str
    strategy_version: str
    symbol: str
    timestamp: datetime = Field(default_factory=utc_now)
    direction: SignalDirection
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    entry_rationale: str
    invalidation_condition: str
    suggested_stop: Decimal | None = None
    suggested_target: Decimal | None = None
    suggested_entry: Decimal | None = None
    input_data_fingerprint: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrderRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    strategy_name: str | None = None
    signal_id: str | None = None
    idempotency_key: str
    client_order_id: str | None = None
    reduce_only: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskEvaluation(BaseModel):
    decision: RiskDecision
    reason_code: RiskReasonCode
    approved_quantity: Decimal | None = None
    message: str = ""
    checks: dict[str, Any] = Field(default_factory=dict)


class Order(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    client_order_id: str
    idempotency_key: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    filled_quantity: Decimal = Decimal("0")
    price: Decimal | None = None
    average_fill_price: Decimal | None = None
    status: OrderStatus
    strategy_name: str | None = None
    signal_id: str | None = None
    risk_decision: RiskDecision | None = None
    risk_reason_code: RiskReasonCode | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    fees: Decimal = Decimal("0")
    metadata: dict[str, Any] = Field(default_factory=dict)


class Fill(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    fee: Decimal
    fee_asset: str = "USDT"
    timestamp: datetime = Field(default_factory=utc_now)


class Position(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbol: str
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal = Decimal("0")
    opened_at: datetime
    strategy_name: str | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None


class PortfolioState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    cash_balance: Decimal
    equity: Decimal
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    daily_pnl: Decimal = Decimal("0")
    peak_equity: Decimal
    drawdown: Decimal = Decimal("0")
    open_positions: list[Position] = Field(default_factory=list)
    consecutive_losses: int = 0
    fees_paid: Decimal = Decimal("0")
    exposure: Decimal = Decimal("0")
    asset_balances: dict[str, Decimal] = Field(default_factory=dict)
    as_of: datetime = Field(default_factory=utc_now)


class Balance(BaseModel):
    """Single asset balance (quote or base)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    asset: str
    free: Decimal
    locked: Decimal = Decimal("0")
    total: Decimal | None = None

    @property
    def available(self) -> Decimal:
        return self.free


class MarketSnapshot(BaseModel):
    """Point-in-time market view used by risk / dashboard freshness checks."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbol: str
    timeframe: str
    last_price: Decimal
    candle_open_time: datetime
    received_at: datetime = Field(default_factory=utc_now)
    is_stale: bool = False
    source: str = "unknown"


class StrategyRun(BaseModel):
    """One strategy evaluation against a closed candle window."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    strategy_name: str
    strategy_version: str
    symbol: str
    timeframe: str
    candle_open_time: datetime
    correlation_id: str
    direction: SignalDirection
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TradeJournalEntry(BaseModel):
    """Append-only application-layer journal record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    event_type: str
    severity: str = "info"
    message: str
    correlation_id: str | None = None
    strategy_run_id: str | None = None
    order_id: str | None = None
    idempotency_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class SystemHealth(BaseModel):
    """API-facing system health snapshot (paper-safe; no secrets)."""

    status: str
    trading_mode: str
    runtime_mode: str = "PAPER"
    kill_switch_enabled: bool
    live_trading_enabled: bool
    exchange_env: str
    database_ok: bool = True
    market_data_ok: bool = True
    risk_engine_ok: bool = True
    detail: str = ""
    checked_at: datetime = Field(default_factory=utc_now)
