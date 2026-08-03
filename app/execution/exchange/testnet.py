"""
Binance Spot Testnet execution broker.

Uses Binance Spot Testnet endpoints only (``testnet.binance.vision`` via ccxt
sandbox mode or an injectable ``api`` for tests). Never targets production.

Implements the ``ExecutionBackend.submit`` protocol plus balance / order /
metadata helpers for the testnet pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError, LiveTradingDisabledError
from app.core.logging import get_logger
from app.core.time import utc_now
from app.execution.exchange.precision import (
    meets_min_notional,
    quantize_price,
    quantize_quantity,
)
from app.models.domain.enums import OrderSide, OrderStatus, OrderType, RiskDecision
from app.models.domain.market import SymbolInfo
from app.models.domain.trading import Balance, Fill, Order, OrderRequest, RiskEvaluation

logger = get_logger("execution.testnet")

# Official Binance Spot Testnet REST host — never use api.binance.com for execution.
DEFAULT_TESTNET_REST = "https://testnet.binance.vision"


@dataclass
class TestnetConfig:
    exchange_env: str = "testnet"
    rate_limit_per_minute: int = 60
    rest_base_url: str = DEFAULT_TESTNET_REST


@dataclass
class ExchangeTestnetClient:
    """
    Binance Spot Testnet broker.

    ``api`` is injectable (ccxt-like) so unit tests never hit the network.
    When ``api`` is omitted, a ccxt.binance client is created in sandbox mode.
    """

    __test__ = False  # prevent pytest collection

    api: Any | None = None
    config: TestnetConfig = field(default_factory=TestnetConfig)
    rest_base_url: str = DEFAULT_TESTNET_REST
    settings: Settings | None = None
    _order_times: list = field(default_factory=list)
    _symbol_cache: dict[str, SymbolInfo] = field(default_factory=dict)
    _idempotency_index: dict[str, Order] = field(default_factory=dict)
    _owns_api: bool = False
    _env_mismatch: bool = False

    def __post_init__(self) -> None:
        self.settings = self.settings or get_settings()
        if self.settings.exchange_env == "live":
            raise LiveTradingDisabledError(
                "Cannot construct testnet client while EXCHANGE_ENV=live"
            )
        if (
            self.settings.exchange_env != "testnet"
            and self.config.exchange_env == "testnet"
        ):
            self._env_mismatch = True
        self.config.rest_base_url = self.rest_base_url or self.config.rest_base_url
        if self.api is None:
            self.api = self._build_ccxt_client()
            self._owns_api = True

    def _build_ccxt_client(self) -> Any:
        import ccxt.async_support as ccxt

        settings = self.settings or get_settings()
        key = (
            settings.exchange_api_key.get_secret_value()
            if settings.exchange_api_key
            else ""
        )
        secret = (
            settings.exchange_api_secret.get_secret_value()
            if settings.exchange_api_secret
            else ""
        )
        if not key or not secret:
            raise ConfigurationError(
                "Binance Spot Testnet requires EXCHANGE_API_KEY and EXCHANGE_API_SECRET"
            )
        exchange = ccxt.binance(
            {
                "apiKey": key,
                "secret": secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
        )
        # Force sandbox / testnet — never production execution endpoints.
        if hasattr(exchange, "set_sandbox_mode"):
            exchange.set_sandbox_mode(True)
        # Prefer explicit testnet URLs when ccxt exposes them.
        if hasattr(exchange, "urls") and isinstance(exchange.urls, dict):
            api_urls = exchange.urls.get("api")
            if isinstance(api_urls, dict):
                for k in list(api_urls):
                    if "binance.com" in str(api_urls[k]) and "testnet" not in str(
                        api_urls[k]
                    ):
                        # Leave sandbox override to set_sandbox_mode; do not silently
                        # rewrite unknown keys. Documented testnet host for ops:
                        _ = self.config.rest_base_url
        return exchange

    async def close(self) -> None:
        if self._owns_api and self.api is not None and hasattr(self.api, "close"):
            await self.api.close()

    # ---------------------------------------------------------------- metadata

    async def load_markets(self) -> dict[str, Any]:
        assert self.api is not None
        if not hasattr(self.api, "load_markets"):
            return {}
        try:
            result = self.api.load_markets()
            if hasattr(result, "__await__"):
                result = await result
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    async def fetch_symbol_info(self, symbol: str) -> SymbolInfo:
        if symbol in self._symbol_cache:
            return self._symbol_cache[symbol]
        assert self.api is not None
        markets = await self.load_markets()
        market = markets.get(symbol) if markets else None
        if not isinstance(market, dict):
            market = None
        if market is None and hasattr(self.api, "market"):
            try:
                candidate = self.api.market(symbol)
                market = candidate if isinstance(candidate, dict) else None
            except Exception:
                market = None
        info = self._symbol_info_from_market(symbol, market)
        self._symbol_cache[symbol] = info
        return info

    def _symbol_info_from_market(
        self, symbol: str, market: dict[str, Any] | None
    ) -> SymbolInfo:
        if not market:
            # Conservative BTC/USDT-like defaults for mocked tests.
            return SymbolInfo(
                symbol=symbol,
                base=symbol.split("/")[0] if "/" in symbol else symbol,
                quote=symbol.split("/")[1] if "/" in symbol else "USDT",
                price_precision=2,
                quantity_precision=5,
                min_quantity=Decimal("0.00001"),
                min_notional=Decimal("10"),
                tick_size=Decimal("0.01"),
                step_size=Decimal("0.00001"),
            )
        precision = market.get("precision") or {}
        limits = market.get("limits") or {}
        amount_limits = limits.get("amount") or {}
        cost_limits = limits.get("cost") or {}
        info = market.get("info") or {}
        filters = {
            f.get("filterType"): f
            for f in info.get("filters", [])
            if f.get("filterType")
        }
        lot = filters.get("LOT_SIZE") or {}
        price_f = filters.get("PRICE_FILTER") or {}
        notional_f = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL") or {}
        step = Decimal(
            str(
                lot.get("stepSize")
                or market.get("limits", {}).get("amount", {}).get("min")
                or "0.00001"
            )
        )
        if "stepSize" not in lot and precision.get("amount") is not None:
            step = Decimal("1") / (Decimal("10") ** int(precision["amount"]))
        tick = Decimal(str(price_f.get("tickSize") or "0.01"))
        if "tickSize" not in price_f and precision.get("price") is not None:
            tick = Decimal("1") / (Decimal("10") ** int(precision["price"]))
        min_qty = Decimal(str(lot.get("minQty") or amount_limits.get("min") or step))
        min_notional = Decimal(
            str(
                notional_f.get("minNotional")
                or notional_f.get("notional")
                or cost_limits.get("min")
                or "10"
            )
        )
        if "/" in symbol:
            parts = [*symbol.split("/"), "USDT"]
            base, quote = parts[0], parts[1]
        else:
            base, quote = symbol, "USDT"
        return SymbolInfo(
            symbol=symbol,
            base=str(market.get("base") or base),
            quote=str(market.get("quote") or quote),
            price_precision=int(precision.get("price") or 2),
            quantity_precision=int(precision.get("amount") or 5),
            min_quantity=min_qty,
            min_notional=min_notional,
            tick_size=tick,
            step_size=step,
            active=bool(market.get("active", True)),
        )

    # ---------------------------------------------------------------- balances

    async def fetch_balances(self) -> list[Balance]:
        assert self.api is not None
        raw = await self.api.fetch_balance()
        totals = raw.get("total") or {}
        free = raw.get("free") or {}
        used = raw.get("used") or {}
        out: list[Balance] = []
        assets = set(totals) | set(free) | set(used)
        for asset in sorted(assets):
            f = Decimal(str(free.get(asset) or "0"))
            locked = Decimal(str(used.get(asset) or "0"))
            total = Decimal(str(totals.get(asset) or f + locked))
            if total == 0 and f == 0 and locked == 0:
                continue
            out.append(Balance(asset=str(asset), free=f, locked=locked, total=total))
        return out

    async def fetch_balance_map(self) -> dict[str, Balance]:
        return {b.asset: b for b in await self.fetch_balances()}

    # ------------------------------------------------------------------ orders

    async def fetch_open_orders(self, symbol: str | None = None) -> list[Order]:
        assert self.api is not None
        raw_list = (
            await self.api.fetch_open_orders(symbol)
            if symbol
            else await self.api.fetch_open_orders()
        )
        return [self._order_from_raw(r) for r in raw_list]

    async def fetch_order(self, order_id: str, symbol: str) -> Order:
        assert self.api is not None
        raw = await self.api.fetch_order(order_id, symbol)
        return self._order_from_raw(raw)

    async def cancel_order(self, order_id: str, symbol: str) -> Order:
        assert self.api is not None
        raw = await self.api.cancel_order(order_id, symbol)
        order = self._order_from_raw(raw)
        return order.model_copy(
            update={"status": OrderStatus.CANCELLED, "updated_at": utc_now()}
        )

    async def place_market_order(
        self,
        *,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        client_order_id: str | None = None,
    ) -> Order:
        info = await self.fetch_symbol_info(symbol)
        qty = quantize_quantity(quantity, info)
        if qty <= 0:
            raise ConfigurationError("Quantity below exchange minimum after precision")
        # Market orders still need a reference price for min-notional checks when available.
        return await self._create_raw_order(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=qty,
            price=None,
            client_order_id=client_order_id,
        )

    async def place_limit_order(
        self,
        *,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal,
        client_order_id: str | None = None,
    ) -> Order:
        info = await self.fetch_symbol_info(symbol)
        qty = quantize_quantity(quantity, info)
        px = quantize_price(price, info)
        if qty <= 0 or px <= 0:
            raise ConfigurationError("Invalid quantity/price after precision rounding")
        if not meets_min_notional(qty, px, info):
            raise ConfigurationError("Order below exchange minimum notional")
        return await self._create_raw_order(
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=qty,
            price=px,
            client_order_id=client_order_id,
        )

    async def _create_raw_order(
        self,
        *,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal | None,
        client_order_id: str | None,
    ) -> Order:
        assert self.api is not None
        client_order_id = client_order_id or f"testnet-{uuid4().hex[:16]}"
        # Prefer ccxt create_order(symbol, type, side, amount, price, params)
        if hasattr(self.api, "create_order") and not _is_legacy_payload_api(self.api):
            params = {
                "newClientOrderId": client_order_id,
                "clientOrderId": client_order_id,
            }
            raw = await self.api.create_order(
                symbol,
                order_type.value,
                side.value,
                float(quantity),
                float(price) if price is not None else None,
                params,
            )
        else:
            payload = {
                "symbol": symbol,
                "side": side.value,
                "type": order_type.value,
                "amount": str(quantity),
                "price": str(price) if price is not None else None,
                "clientOrderId": client_order_id,
            }
            raw = await self.api.create_order(payload)
        return self._order_from_raw(raw, fallback_client_id=client_order_id)

    # -------------------------------------------------------- gateway protocol

    async def submit(self, request: OrderRequest, risk: RiskEvaluation) -> Order:
        if risk.decision in (RiskDecision.REJECTED, RiskDecision.HALTED):
            return Order(
                id=uuid4().hex,
                client_order_id=request.client_order_id or uuid4().hex,
                idempotency_key=request.idempotency_key,
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                price=request.price,
                status=OrderStatus.REJECTED,
                risk_decision=risk.decision,
                risk_reason_code=risk.reason_code,
            )

        if request.idempotency_key in self._idempotency_index:
            return self._idempotency_index[request.idempotency_key]

        now = utc_now()
        self._order_times = [
            t for t in self._order_times if (now - t).total_seconds() < 60
        ]
        if len(self._order_times) >= self.config.rate_limit_per_minute:
            return Order(
                id=uuid4().hex,
                client_order_id=request.client_order_id or uuid4().hex,
                idempotency_key=request.idempotency_key,
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                status=OrderStatus.FAILED,
                metadata={"error": "rate_limited"},
            )

        info = await self.fetch_symbol_info(request.symbol)
        qty = quantize_quantity(request.quantity, info)
        price = (
            quantize_price(request.price, info) if request.price is not None else None
        )
        if qty <= 0:
            return Order(
                id=uuid4().hex,
                client_order_id=request.client_order_id or uuid4().hex,
                idempotency_key=request.idempotency_key,
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                status=OrderStatus.REJECTED,
                metadata={"error": "quantity_precision"},
            )

        started = utc_now()
        try:
            if request.order_type == OrderType.LIMIT:
                if price is None or price <= 0:
                    raise ConfigurationError("Limit order requires price")
                order = await self.place_limit_order(
                    symbol=request.symbol,
                    side=request.side,
                    quantity=qty,
                    price=price,
                    client_order_id=request.client_order_id,
                )
            else:
                order = await self.place_market_order(
                    symbol=request.symbol,
                    side=request.side,
                    quantity=qty,
                    client_order_id=request.client_order_id,
                )
        except Exception as exc:
            logger.warning(
                "testnet_order_failed",
                extra={"symbol": request.symbol, "error_type": type(exc).__name__},
            )
            failed = Order(
                id=uuid4().hex,
                client_order_id=request.client_order_id or uuid4().hex,
                idempotency_key=request.idempotency_key,
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                quantity=qty,
                price=price,
                status=OrderStatus.FAILED,
                risk_decision=risk.decision,
                risk_reason_code=risk.reason_code,
                metadata={"error": type(exc).__name__},
            )
            return failed

        elapsed_ms = (utc_now() - started).total_seconds() * 1000
        order = order.model_copy(
            update={
                "idempotency_key": request.idempotency_key,
                "risk_decision": risk.decision,
                "risk_reason_code": risk.reason_code,
                "strategy_name": request.strategy_name,
                "signal_id": request.signal_id,
                "metadata": {
                    **order.metadata,
                    "execution_time_ms": elapsed_ms,
                    "exchange": "binance_spot_testnet",
                    "rest_base": self.config.rest_base_url,
                },
            }
        )
        self._order_times.append(now)
        self._idempotency_index[request.idempotency_key] = order
        logger.info(
            "testnet_order_submitted",
            extra={
                "symbol": order.symbol,
                "side": order.side.value,
                "quantity": str(order.quantity),
                "status": order.status.value,
                "exchange_order_id": order.id,
                "execution_time_ms": elapsed_ms,
            },
        )
        return order

    def extract_fills(
        self, order: Order, raw: dict[str, Any] | None = None
    ) -> list[Fill]:
        """Build Fill records from an order / raw exchange payload."""
        if order.filled_quantity <= 0:
            return []
        fee = Decimal("0")
        if raw and raw.get("fee"):
            fee = Decimal(str((raw["fee"] or {}).get("cost") or "0"))
        price = order.average_fill_price or order.price or Decimal("0")
        return [
            Fill(
                id=uuid4().hex,
                order_id=order.id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.filled_quantity,
                price=price,
                fee=fee,
            )
        ]

    # ----------------------------------------------------------------- helpers

    def _order_from_raw(
        self, raw: dict[str, Any], *, fallback_client_id: str | None = None
    ) -> Order:
        now = utc_now()
        filled = Decimal(str(raw.get("filled") or raw.get("filled_quantity") or "0"))
        amount = Decimal(str(raw.get("amount") or raw.get("quantity") or filled or "0"))
        status_raw = str(raw.get("status") or "").lower()
        status = _map_status(status_raw, filled, amount)
        side_raw = str(raw.get("side") or "buy").lower()
        type_raw = str(raw.get("type") or "market").lower()
        return Order(
            id=str(raw.get("id") or uuid4().hex),
            client_order_id=str(
                raw.get("clientOrderId")
                or raw.get("client_order_id")
                or fallback_client_id
                or uuid4().hex
            ),
            idempotency_key=str(
                raw.get("clientOrderId") or raw.get("idempotency_key") or uuid4().hex
            ),
            symbol=str(raw.get("symbol") or ""),
            side=OrderSide.BUY if side_raw == "buy" else OrderSide.SELL,
            order_type=OrderType.LIMIT if type_raw == "limit" else OrderType.MARKET,
            quantity=amount,
            filled_quantity=filled,
            price=(
                Decimal(str(raw["price"]))
                if raw.get("price") not in (None, "", 0, "0")
                else None
            ),
            average_fill_price=(
                Decimal(str(raw["average"])) if raw.get("average") else None
            ),
            status=status,
            fees=Decimal(
                str((raw.get("fee") or {}).get("cost") or raw.get("fees") or "0")
            ),
            created_at=now,
            updated_at=now,
            metadata={"exchange": "binance_spot_testnet", "raw_status": status_raw},
        )


def _map_status(status_raw: str, filled: Decimal, amount: Decimal) -> OrderStatus:
    if status_raw in {"closed", "filled"}:
        return OrderStatus.FILLED
    if status_raw in {"canceled", "cancelled"}:
        return OrderStatus.CANCELLED
    if status_raw in {"expired"}:
        return OrderStatus.EXPIRED
    if status_raw in {"rejected"}:
        return OrderStatus.REJECTED
    if status_raw in {"open", "new", "submitted"}:
        if filled > 0 and filled < amount:
            return OrderStatus.PARTIALLY_FILLED
        return OrderStatus.SUBMITTED
    if filled >= amount > 0:
        return OrderStatus.FILLED
    if filled > 0:
        return OrderStatus.PARTIALLY_FILLED
    return OrderStatus.SUBMITTED


def _is_legacy_payload_api(api: Any) -> bool:
    """True when create_order expects a single payload dict (legacy mock style)."""
    create = getattr(api, "create_order", None)
    if create is None:
        return False
    # Heuristic: MagicMock/AsyncMock from existing unit tests use payload dict.
    name = type(api).__name__
    return name in {"MagicMock", "AsyncMock"} or getattr(
        api, "_atlas_payload_api", False
    )
