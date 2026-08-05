"""Application settings. TRADING_MODE defaults to paper — never change that default."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.errors import ConfigurationError, LiveTradingDisabledError

TradingMode = Literal["paper", "live"]
ExchangeEnv = Literal["paper", "testnet", "live"]


def _bps_to_rate(bps: Decimal) -> Decimal:
    return bps / Decimal("10000")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Project Atlas"
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, ge=1, le=65535, validation_alias="API_PORT")

    # Safety-critical defaults — do not weaken.
    trading_mode: TradingMode = Field(default="paper", validation_alias="TRADING_MODE")
    live_trading_enabled: bool = False
    kill_switch_enabled: bool = False
    exchange_env: ExchangeEnv = "paper"
    live_approval_token: SecretStr | None = None

    # Local admin token for mutating system endpoints (kill switch, paper reset).
    admin_api_token: SecretStr | None = Field(
        default=None, validation_alias="ADMIN_API_TOKEN"
    )

    exchange_id: str = "binance"
    exchange_api_key: SecretStr | None = None
    exchange_api_secret: SecretStr | None = None

    database_url: str = Field(
        default="sqlite+aiosqlite:///./atlas.db", validation_alias="DATABASE_URL"
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0", validation_alias="REDIS_URL"
    )

    market_data_stale_seconds: int = Field(
        default=30, ge=1, validation_alias="MARKET_DATA_STALE_SECONDS"
    )
    market_data_public_enabled: bool = Field(
        default=False, validation_alias="MARKET_DATA_PUBLIC_ENABLED"
    )

    # Paper scheduler — disabled by default; never starts live trading.
    scheduler_enabled: bool = Field(default=False, validation_alias="SCHEDULER_ENABLED")
    scheduler_interval_seconds: int = Field(
        default=60, ge=5, le=3600, validation_alias="SCHEDULER_INTERVAL_SECONDS"
    )
    webhook_alert_url: str | None = None

    # Paper execution (env-driven; Decimal only)
    paper_starting_balance: Decimal = Field(
        default=Decimal("10000"), validation_alias="PAPER_STARTING_BALANCE"
    )
    paper_fee_bps: Decimal = Field(
        default=Decimal("10"), validation_alias="PAPER_FEE_BPS"
    )  # 10 bps = 0.10%
    paper_slippage_bps: Decimal = Field(
        default=Decimal("5"), validation_alias="PAPER_SLIPPAGE_BPS"
    )

    # Risk defaults (fractions: 0.01 = 1%). Percent env aliases accepted.
    max_risk_per_trade: Decimal = Field(
        default=Decimal("0.01"), validation_alias="RISK_PER_TRADE_PERCENT"
    )
    max_position_exposure: Decimal = Field(
        default=Decimal("0.25"), validation_alias="MAX_POSITION_PERCENT"
    )
    max_portfolio_exposure: Decimal = Decimal("0.80")
    max_open_positions: int = Field(default=3, validation_alias="MAX_OPEN_POSITIONS")
    max_daily_loss: Decimal = Field(
        default=Decimal("0.03"), validation_alias="MAX_DAILY_LOSS_PERCENT"
    )
    max_drawdown: Decimal = Field(
        default=Decimal("0.10"), validation_alias="MAX_DRAWDOWN_PERCENT"
    )
    max_consecutive_losses: int = 5
    max_orders_per_minute: int = 10
    min_order_notional: Decimal = Decimal("10")
    default_leverage: Decimal = Decimal("1")

    # NoDecode: keep plain "BTC/USDT" env values (avoid JSON-decoding tuples).
    supported_symbols: Annotated[tuple[str, ...], NoDecode] = Field(
        default=("BTC/USDT",), validation_alias="ALLOWED_SYMBOLS"
    )
    supported_timeframes: tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h")

    @field_validator("trading_mode")
    @classmethod
    def _normalize_trading_mode(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in {"paper", "live"}:
            raise ValueError("TRADING_MODE must be 'paper' or 'live'")
        return normalized

    @field_validator(
        "paper_starting_balance",
        "paper_fee_bps",
        "paper_slippage_bps",
        "max_risk_per_trade",
        "max_position_exposure",
        "max_daily_loss",
        "max_drawdown",
        "min_order_notional",
        "default_leverage",
        mode="before",
    )
    @classmethod
    def _decimal_finite(cls, value: object) -> object:
        if value is None:
            raise ValueError("numeric setting must not be None")
        try:
            d = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"invalid decimal setting: {value!r}") from exc
        if not d.is_finite():
            raise ValueError("NaN/Infinity are not allowed for financial settings")
        return d

    @field_validator("supported_symbols", mode="before")
    @classmethod
    def _parse_symbols(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("[") and text.endswith("]"):
                # Allow accidental JSON-array forms in .env
                import json

                try:
                    loaded = json.loads(text)
                    if isinstance(loaded, list):
                        return tuple(str(p).strip() for p in loaded if str(p).strip())
                except json.JSONDecodeError:
                    pass
            parts = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
            return tuple(parts)
        if isinstance(value, (list, tuple)):
            return tuple(str(p).strip() for p in value if str(p).strip())
        return value

    @field_validator(
        "max_risk_per_trade",
        "max_position_exposure",
        "max_daily_loss",
        "max_drawdown",
        mode="after",
    )
    @classmethod
    def _normalize_percent_or_fraction(cls, value: Decimal) -> Decimal:
        """Accept either fraction (0.01) or whole percent (1 → 0.01, 25 → 0.25)."""
        if value < 0:
            raise ValueError("risk percentages must be non-negative")
        if value > 1:
            if value > 100:
                raise ValueError("risk percentage out of range")
            return value / Decimal("100")
        return value

    @model_validator(mode="after")
    def _validate_paper_invariants(self) -> Settings:
        if self.paper_starting_balance <= 0:
            raise ConfigurationError("PAPER_STARTING_BALANCE must be > 0")
        if self.paper_fee_bps < 0 or self.paper_slippage_bps < 0:
            raise ConfigurationError("PAPER fee/slippage bps must be >= 0")
        if self.default_leverage != Decimal("1"):
            raise ConfigurationError(
                "default_leverage must be 1 — leverage is not supported"
            )
        return self

    def assert_startup_safe(self) -> None:
        """
        Fail closed at application startup.

        Live mode without every explicit gate → ConfigurationError.
        Live mode with gates → LiveTradingDisabledError (not implemented yet).
        """
        if self.trading_mode != "live":
            return
        token = (
            self.live_approval_token.get_secret_value()
            if self.live_approval_token
            else ""
        )
        gates_ok = (
            self.live_trading_enabled
            and self.exchange_env in {"testnet", "live"}
            and self.has_exchange_credentials
            and bool(token.strip())
            and not self.kill_switch_enabled
        )
        if not gates_ok:
            raise ConfigurationError(
                "TRADING_MODE=live rejected: incomplete live-trading gates "
                "(require LIVE_TRADING_ENABLED, credentials, LIVE_APPROVAL_TOKEN, "
                "exchange_env testnet|live, and kill switch off)."
            )
        raise LiveTradingDisabledError(
            "Live trading mode is not implemented. Keep TRADING_MODE=paper."
        )

    @property
    def has_exchange_credentials(self) -> bool:
        key = self.exchange_api_key.get_secret_value() if self.exchange_api_key else ""
        secret = (
            self.exchange_api_secret.get_secret_value()
            if self.exchange_api_secret
            else ""
        )
        return bool(key.strip() and secret.strip())

    @property
    def paper_fee_rate(self) -> Decimal:
        return _bps_to_rate(self.paper_fee_bps)

    @property
    def paper_slippage_rate(self) -> Decimal:
        return _bps_to_rate(self.paper_slippage_bps)

    @property
    def allowed_symbols(self) -> tuple[str, ...]:
        return self.supported_symbols


@lru_cache
def get_settings() -> Settings:
    return Settings()
