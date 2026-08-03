"""Application settings. TRADING_MODE defaults to paper — never change that default."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TradingMode = Literal["paper", "live"]
ExchangeEnv = Literal["paper", "testnet", "live"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Project Atlas"
    app_env: str = "development"
    log_level: str = "INFO"

    # Safety-critical defaults — do not weaken.
    trading_mode: TradingMode = "paper"
    live_trading_enabled: bool = False
    kill_switch_enabled: bool = False
    exchange_env: ExchangeEnv = "paper"
    live_approval_token: SecretStr | None = None

    exchange_id: str = "binance"
    exchange_api_key: SecretStr | None = None
    exchange_api_secret: SecretStr | None = None

    database_url: str = "sqlite+aiosqlite:///./atlas.db"
    redis_url: str = "redis://localhost:6379/0"

    market_data_stale_seconds: int = Field(default=30, ge=1)
    webhook_alert_url: str | None = None

    # Risk defaults (paper-safe)
    max_risk_per_trade: Decimal = Decimal("0.01")
    max_position_exposure: Decimal = Decimal("0.25")
    max_portfolio_exposure: Decimal = Decimal("0.80")
    max_open_positions: int = 3
    max_daily_loss: Decimal = Decimal("0.03")
    max_drawdown: Decimal = Decimal("0.10")
    max_consecutive_losses: int = 5
    max_orders_per_minute: int = 10
    min_order_notional: Decimal = Decimal("10")
    default_leverage: Decimal = Decimal("1")

    supported_symbols: tuple[str, ...] = ("BTC/USDT",)
    supported_timeframes: tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h")

    @field_validator("trading_mode")
    @classmethod
    def _normalize_trading_mode(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in {"paper", "live"}:
            raise ValueError("TRADING_MODE must be 'paper' or 'live'")
        return normalized

    @property
    def has_exchange_credentials(self) -> bool:
        key = self.exchange_api_key.get_secret_value() if self.exchange_api_key else ""
        secret = (
            self.exchange_api_secret.get_secret_value()
            if self.exchange_api_secret
            else ""
        )
        return bool(key.strip() and secret.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
