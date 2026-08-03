"""
Execution backend factory.

Supports:
- paper   → PaperTradingEngine
- testnet → Binance Spot Testnet broker
- live    → raises LiveTradingDisabledError immediately
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError, LiveTradingDisabledError
from app.core.logging import get_logger
from app.execution.exchange.testnet import ExchangeTestnetClient
from app.execution.gateway import ExecutionBackend
from app.execution.paper.engine import PaperConfig, PaperTradingEngine

logger = get_logger("execution.factory")


class LiveBrokerDisabled:
    """Sentinel that always raises — live money path is not implemented."""

    async def submit(self, request: Any, risk: Any) -> Any:
        raise LiveTradingDisabledError(
            "Live broker is disabled. Use paper or Binance Spot Testnet only."
        )


def build_execution_backend(
    settings: Settings | None = None,
    *,
    api: Any | None = None,
    paper_engine: PaperTradingEngine | None = None,
) -> ExecutionBackend:
    """
    Construct the execution backend for the configured exchange environment.

    ``EXCHANGE_ENV``:
    - ``paper``   → local paper broker
    - ``testnet`` → Binance Spot Testnet (requires credentials unless ``api`` injected)
    - ``live``    → raises ``LiveTradingDisabledError``
    """
    settings = settings or get_settings()
    env = settings.exchange_env

    if env == "live":
        raise LiveTradingDisabledError(
            "Selecting live execution is forbidden. "
            "Set EXCHANGE_ENV=paper or EXCHANGE_ENV=testnet."
        )

    if env == "paper":
        if paper_engine is not None:
            return paper_engine
        return PaperTradingEngine(
            PaperConfig(
                initial_cash=settings.paper_starting_balance,
                fee_rate=settings.paper_fee_rate,
                slippage_rate=settings.paper_slippage_rate,
            )
        )

    if env == "testnet":
        if api is None and not settings.has_exchange_credentials:
            raise ConfigurationError(
                "EXCHANGE_ENV=testnet requires EXCHANGE_API_KEY and "
                "EXCHANGE_API_SECRET (Binance Spot Testnet keys)."
            )
        logger.info(
            "building_testnet_backend",
            extra={
                "rest_url": settings.binance_testnet_rest_url,
                "exchange_id": settings.exchange_id,
            },
        )
        return ExchangeTestnetClient(
            api=api,
            rest_base_url=settings.binance_testnet_rest_url,
            settings=settings,
        )

    raise ConfigurationError(f"Unsupported EXCHANGE_ENV: {env}")
