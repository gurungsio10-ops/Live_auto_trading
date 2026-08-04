"""Application settings. TRADING_MODE defaults to paper — never change that default."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.errors import ConfigurationError, LiveTradingDisabledError
from app.core.runtime_mode import RuntimeMode, derive_runtime_mode

TradingMode = Literal["paper", "live"]
ExchangeEnv = Literal["paper", "testnet", "live", "backtest"]


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
    # ENABLE_LIVE_TRADING preferred; LIVE_TRADING_ENABLED accepted for compat.
    live_trading_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("ENABLE_LIVE_TRADING", "LIVE_TRADING_ENABLED"),
    )
    # Paper automation gate (false = cycles require explicit one-shot confirm).
    trading_enabled: bool = Field(default=False, validation_alias="TRADING_ENABLED")
    kill_switch_enabled: bool = False
    exchange_env: ExchangeEnv = Field(
        default="paper",
        validation_alias=AliasChoices("EXCHANGE_ENV", "EXCHANGE_TESTNET"),
    )
    live_approval_token: SecretStr | None = None
    # Explicit acknowledgement required before any LIVE start attempt.
    live_startup_ack: str = Field(default="", validation_alias="LIVE_STARTUP_ACK")
    # Optional unified mode: BACKTEST | PAPER | TESTNET | LIVE
    atlas_runtime_mode: str | None = Field(
        default=None, validation_alias="ATLAS_RUNTIME_MODE"
    )

    # Local admin token for mutating system endpoints (kill switch, paper reset).
    admin_api_token: SecretStr | None = Field(
        default=None, validation_alias="ADMIN_API_TOKEN"
    )

    exchange_id: str = Field(
        default="bybit",
        validation_alias=AliasChoices("EXCHANGE_ID", "EXCHANGE_NAME"),
    )
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
    order_cooldown_seconds: int = Field(
        default=0, ge=0, validation_alias="ORDER_COOLDOWN_SECONDS"
    )
    webhook_alert_url: str | None = None

    # Production paper/testnet runtime controls (live money remains hard-blocked).
    use_live_market_data: bool = Field(
        default=False, validation_alias="USE_LIVE_MARKET_DATA"
    )
    enable_trading_scheduler: bool = Field(
        default=False, validation_alias="ENABLE_TRADING_SCHEDULER"
    )
    paper_cycle_interval_seconds: int = Field(
        default=60, ge=5, validation_alias="PAPER_CYCLE_INTERVAL_SECONDS"
    )
    enable_reconciliation: bool = Field(
        default=True, validation_alias="ENABLE_RECONCILIATION"
    )
    reconciliation_interval_seconds: int = Field(
        default=120, ge=30, validation_alias="RECONCILIATION_INTERVAL_SECONDS"
    )
    scheduler_failure_threshold: int = Field(
        default=5,
        ge=1,
        validation_alias="SCHEDULER_FAILURE_THRESHOLD",
    )
    cycle_lock_ttl_seconds: int = Field(
        default=120,
        ge=10,
        validation_alias="CYCLE_LOCK_TTL_SECONDS",
    )

    # Paper execution (env-driven; Decimal only)
    paper_starting_balance: Decimal = Field(
        default=Decimal("10000"),
        validation_alias=AliasChoices("PAPER_STARTING_BALANCE", "STARTING_BALANCE"),
    )
    paper_fee_bps: Decimal = Field(
        default=Decimal("10"), validation_alias="PAPER_FEE_BPS"
    )  # 10 bps = 0.10%
    paper_slippage_bps: Decimal = Field(
        default=Decimal("5"), validation_alias="PAPER_SLIPPAGE_BPS"
    )

    # Risk defaults (fractions: 0.01 = 1%). Percent env aliases accepted.
    max_risk_per_trade: Decimal = Field(
        default=Decimal("0.01"),
        validation_alias=AliasChoices(
            "RISK_PER_TRADE_PERCENT", "MAX_POSITION_RISK_PERCENT"
        ),
    )
    max_position_exposure: Decimal = Field(
        default=Decimal("0.20"),
        validation_alias=AliasChoices(
            "MAX_POSITION_PERCENT", "MAX_POSITION_SIZE_PERCENT"
        ),
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

    supported_symbols: tuple[str, ...] = Field(
        default=("BTC/USDT",),
        validation_alias="ALLOWED_SYMBOLS",
    )
    supported_timeframes: tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h")
    default_symbol: str = Field(default="BTC/USDT", validation_alias="DEFAULT_SYMBOL")
    default_timeframe: str = Field(default="5m", validation_alias="DEFAULT_TIMEFRAME")

    # Baseline EMA+RSI strategy env knobs
    fast_ema_period: int = Field(default=9, ge=1, validation_alias="FAST_EMA_PERIOD")
    slow_ema_period: int = Field(default=21, ge=2, validation_alias="SLOW_EMA_PERIOD")
    rsi_period: int = Field(default=14, ge=2, validation_alias="RSI_PERIOD")
    stop_loss_percent: Decimal = Field(
        default=Decimal("1"), validation_alias="STOP_LOSS_PERCENT"
    )
    take_profit_percent: Decimal = Field(
        default=Decimal("2"), validation_alias="TAKE_PROFIT_PERCENT"
    )

    @field_validator("trading_mode", mode="before")
    @classmethod
    def _normalize_trading_mode(cls, value: object) -> str:
        if value is None or str(value).strip() == "":
            return "paper"
        normalized = str(value).lower().strip()
        # Never fall through to live on typos — invalid → paper.
        if normalized not in {"paper", "live"}:
            return "paper"
        return normalized

    @field_validator("exchange_env", mode="before")
    @classmethod
    def _normalize_exchange_env(cls, value: object) -> str:
        if value is None or str(value).strip() == "":
            return "paper"
        raw = str(value).lower().strip()
        # EXCHANGE_TESTNET=true|false alias
        if raw in {"true", "1", "yes"}:
            return "testnet"
        if raw in {"false", "0", "no"}:
            return "paper"
        if raw not in {"paper", "testnet", "live", "backtest"}:
            return "paper"
        return raw

    @field_validator("atlas_runtime_mode", mode="before")
    @classmethod
    def _normalize_runtime_mode_field(cls, value: object) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        return str(value).strip().upper()

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
        "stop_loss_percent",
        "take_profit_percent",
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
            parts = [p.strip() for p in value.replace(";", ",").split(",") if p.strip()]
            return tuple(parts)
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
        """Accept fraction (0.01) or whole percent points (1 → 0.01, 20 → 0.20).

        Bare ``1`` is treated as 1% (not 100%) to match MVP env examples.
        """
        if value < 0:
            raise ValueError("risk percentages must be non-negative")
        if value > 100:
            raise ValueError("risk percentage out of range")
        if value >= 1:
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
        if self.fast_ema_period >= self.slow_ema_period:
            raise ConfigurationError("FAST_EMA_PERIOD must be < SLOW_EMA_PERIOD")
        if self.stop_loss_percent <= 0 or self.take_profit_percent <= 0:
            raise ConfigurationError(
                "STOP_LOSS_PERCENT and TAKE_PROFIT_PERCENT must be > 0"
            )
        # Keep allowlist in sync with default symbol.
        if self.default_symbol and self.default_symbol not in self.supported_symbols:
            self.supported_symbols = tuple(
                dict.fromkeys([*self.supported_symbols, self.default_symbol])
            )
        if self.default_timeframe not in self.supported_timeframes:
            raise ConfigurationError(
                f"DEFAULT_TIMEFRAME={self.default_timeframe!r} not in supported timeframes"
            )
        return self

    def assert_startup_safe(self) -> None:
        """
        Fail closed at application startup.

        LIVE remains hard-blocked in this development phase even when
        ENABLE_LIVE_TRADING, credentials, and LIVE_STARTUP_ACK are set.
        """
        from app.core.safety import SafetyGuard

        SafetyGuard(self).assert_paper_only()
        mode = self.runtime_mode
        if mode == RuntimeMode.LIVE or self.exchange_env == "live":
            raise LiveTradingDisabledError(
                "LIVE execution is hard-disabled in this development phase. "
                "Keep ATLAS_RUNTIME_MODE=PAPER (or TESTNET) and "
                "ENABLE_LIVE_TRADING=false."
            )
        if self.trading_mode == "live":
            raise LiveTradingDisabledError(
                "TRADING_MODE=live is disabled. Keep TRADING_MODE=paper."
            )

    @property
    def runtime_mode(self) -> RuntimeMode:
        """Effective mode: BACKTEST | PAPER | TESTNET | LIVE."""
        return derive_runtime_mode(
            explicit=self.atlas_runtime_mode,
            trading_mode=self.trading_mode,
            exchange_env=self.exchange_env,
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
