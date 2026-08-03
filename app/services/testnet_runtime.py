"""
Binance Spot Testnet runtime: market stream → strategy → risk → testnet order
→ portfolio → journal → dashboard broadcast state.

Live trading is never enabled here.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.errors import LiveTradingDisabledError
from app.core.logging import get_logger
from app.core.time import utc_now
from app.execution.factory import build_execution_backend
from app.execution.gateway import ExecutionBackend, OrderGateway, RiskBlockedError
from app.execution.paper.engine import PaperTradingEngine
from app.journal.store import JournalStore
from app.market_data.websocket.binance_spot import BinanceSpotTestnetWebSocket
from app.models.domain.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecision,
    RiskReasonCode,
    SignalDirection,
)
from app.models.domain.market import Candle
from app.models.domain.trading import (
    Order,
    OrderRequest,
    PortfolioState,
    Position,
    RiskEvaluation,
    TradeSignal,
)
from app.monitoring.health import (
    AlertChannel,
    ConsoleAlertChannel,
    HealthRegistry,
    MonitoringService,
    WebhookAlertChannel,
)
from app.risk.engine import RiskContext, RiskEngine, RiskEngineState
from app.services.portfolio_reconciler import (
    InMemoryLocalPortfolio,
    PortfolioReconciler,
)
from app.strategies.base import StrategyConfig, StrategyContext
from app.strategies.registry import get_strategy

logger = get_logger("testnet.runtime")


@dataclass
class TestnetRuntimeStats:
    candles: int = 0
    signals: int = 0
    orders: int = 0
    fills: int = 0
    rejections: int = 0
    last_latency_ms: float = 0.0
    last_error: str | None = None


@dataclass
class TestnetRuntime:
    """
    Process-local Spot Testnet trading runtime.

    ``EXCHANGE_ENV`` must be ``testnet``. ``TRADING_MODE`` remains ``paper``
    (testnet funds are not live money).
    """

    __test__ = False  # prevent pytest collection

    settings: Settings = field(default_factory=get_settings)
    strategy_id: str = "ema_crossover"
    symbol: str = "BTC/USDT"
    timeframe: str = "1m"
    journal: JournalStore | None = None
    transport: Any | None = None  # injectable WS transport for tests
    exchange_api: Any | None = None  # injectable REST api for tests
    enable_websocket: bool = True  # set False in offline unit tests

    def __post_init__(self) -> None:
        if self.settings.exchange_env == "live" or self.settings.trading_mode == "live":
            raise LiveTradingDisabledError(
                "TestnetRuntime refuses live mode. Use EXCHANGE_ENV=testnet."
            )
        self.kill_switch_enabled = self.settings.kill_switch_enabled
        self.stats = TestnetRuntimeStats()
        self.health = HealthRegistry()
        channels: list[AlertChannel] = [ConsoleAlertChannel()]
        if self.settings.webhook_alert_url:
            channels.append(WebhookAlertChannel(self.settings.webhook_alert_url))
        self.monitoring = MonitoringService(registry=self.health, channels=channels)
        self.risk_state = RiskEngineState()
        self.risk = RiskEngine(settings=self.settings, state=self.risk_state)
        self.local_portfolio = InMemoryLocalPortfolio(
            balances={"USDT": self.settings.paper_starting_balance}
        )
        self._window: list[Candle] = []
        self._orders: list[Order] = []
        self._signals: list[dict[str, Any]] = []
        self._risk_events: list[dict[str, Any]] = []
        self._fills: list[dict[str, Any]] = []
        self._last_signal: TradeSignal | None = None
        self._last_candle: Candle | None = None
        self._seen_candle_keys: set[tuple[str, str]] = set()
        self._last_order_at: datetime | None = None
        self._peak_equity = self.settings.paper_starting_balance
        self._consecutive_losses = 0
        self._backend: ExecutionBackend | None = None
        self.gateway: OrderGateway | None = None
        self.ws: BinanceSpotTestnetWebSocket | None = None
        self.reconciler: PortfolioReconciler | None = None
        self._lock = asyncio.Lock()
        self._running = False
        self._alert_task: asyncio.Task[None] | None = None

    def _ensure_backend(self) -> None:
        if self.gateway is not None:
            return
        if self.settings.exchange_env == "testnet":
            self._backend = build_execution_backend(
                self.settings, api=self.exchange_api
            )
        else:
            # Allow paper backend when running offline unit tests of the cycle.
            self._backend = PaperTradingEngine()
        assert self._backend is not None
        self.gateway = OrderGateway(self._backend, self.risk)

    async def start(self) -> None:
        if self.settings.exchange_env == "live":
            raise LiveTradingDisabledError("live disabled")
        self._ensure_backend()
        self._running = True
        self.health.order_engine_ok = True
        self.health.risk_engine_ok = True
        self.health.strategy_heartbeat_ok = True

        # Restart-safe hydrate: exchange balances/orders are source of truth on testnet.
        await self._hydrate_from_exchange()

        if hasattr(self._backend, "fetch_balances"):
            self.reconciler = PortfolioReconciler(
                exchange=self._backend,  # type: ignore[arg-type]
                local=self.local_portfolio,
                settings=self.settings,
                channels=list(self.monitoring.channels),
            )
            await self.reconciler.start()

        if self.enable_websocket:
            self.ws = BinanceSpotTestnetWebSocket(
                symbols=[self.symbol],
                on_candle=self._ws_candle_handler,
                on_trade=self.on_trade_tick,
                transport=self.transport,
                rest_fallback=self._rest_fallback,
                stale_seconds=self.settings.market_data_stale_seconds,
            )
            # RealWebSocketTransport is attached by default when transport is None.
            await self.ws.start()
            self.health.websocket_connected = True
        else:
            logger.info(
                "testnet_ws_disabled",
                extra={"detail": "enable_websocket=False (offline/test mode)"},
            )
        logger.info(
            "testnet_runtime_started",
            extra={
                "symbol": self.symbol,
                "strategy_id": self.strategy_id,
                "exchange_env": self.settings.exchange_env,
            },
        )

    async def _hydrate_from_exchange(self) -> None:
        """Seed local portfolio + open orders from the exchange after restart."""
        backend = self._backend
        if backend is None or not hasattr(backend, "fetch_balances"):
            return
        try:
            balances = await backend.fetch_balances()
            self.local_portfolio.apply_exchange_balances(balances)
            # Spot positions derived from non-quote base balances.
            positions: dict[str, Decimal] = {}
            for bal in balances:
                if bal.asset in {"USDT", "USD", "BUSD", "USDC"}:
                    continue
                total = bal.total if bal.total is not None else bal.free + bal.locked
                if total <= 0:
                    continue
                symbol = f"{bal.asset}/USDT"
                if symbol == self.symbol or symbol in self.settings.supported_symbols:
                    positions[symbol] = total
            self.local_portfolio.apply_exchange_positions(positions)
            if hasattr(backend, "fetch_open_orders"):
                open_orders = await backend.fetch_open_orders(self.symbol)
                # Replace process-local open cache with exchange open set.
                kept = [
                    o
                    for o in self._orders
                    if o.status
                    not in {
                        OrderStatus.SUBMITTED,
                        OrderStatus.PARTIALLY_FILLED,
                        OrderStatus.APPROVED,
                    }
                ]
                self._orders = kept + list(open_orders)
            logger.info(
                "testnet_hydrated_from_exchange",
                extra={
                    "balances": len(balances),
                    "positions": len(positions),
                    "open_orders": len(
                        [
                            o
                            for o in self._orders
                            if o.status
                            in {
                                OrderStatus.SUBMITTED,
                                OrderStatus.PARTIALLY_FILLED,
                                OrderStatus.APPROVED,
                            }
                        ]
                    ),
                },
            )
        except Exception as exc:
            logger.warning(
                "testnet_hydrate_failed",
                extra={"error_type": type(exc).__name__},
            )
            await self.monitoring.alert(
                "EXCHANGE_UNAVAILABLE",
                f"Hydrate from exchange failed: {type(exc).__name__}",
                {"symbol": self.symbol},
            )

    async def stop(self) -> None:
        self._running = False
        if self.ws is not None:
            await self.ws.stop()
        if self.reconciler is not None:
            await self.reconciler.stop()
        if self._backend is not None and hasattr(self._backend, "close"):
            await self._backend.close()

    async def _rest_fallback(self, symbol: str) -> dict[str, Any]:
        await self.monitoring.alert(
            "WEBSOCKET_DISCONNECTED",
            "WebSocket disconnected — REST fallback invoked",
            {"symbol": symbol},
        )
        self.health.websocket_connected = False
        # Gap recovery: pull recent closed candles via REST and process unseen ones.
        try:
            candles = await self.fetch_rest_candles(
                symbol=symbol, timeframe=self.timeframe, limit=5
            )
            processed = 0
            for candle in candles:
                key = (candle.symbol, candle.open_time.isoformat())
                if key in self._seen_candle_keys:
                    continue
                await self.on_closed_candle(candle)
                processed += 1
            return {
                "symbol": symbol,
                "fallback": True,
                "candles_fetched": len(candles),
                "candles_processed": processed,
                "ts": utc_now().isoformat(),
            }
        except Exception as exc:
            logger.warning(
                "testnet_rest_fallback_failed",
                extra={"symbol": symbol, "error_type": type(exc).__name__},
            )
            return {
                "symbol": symbol,
                "fallback": True,
                "error": type(exc).__name__,
                "ts": utc_now().isoformat(),
            }

    async def fetch_rest_candles(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
        limit: int = 60,
    ) -> list[Candle]:
        """Fetch closed OHLCV candles from Binance Spot Testnet REST (ccxt sandbox)."""
        from app.market_data.providers.binance import BinanceProvider

        symbol = symbol or self.symbol
        timeframe = timeframe or self.timeframe
        provider = BinanceProvider(
            sandbox=self.settings.exchange_env == "testnet",
            api_key=(
                self.settings.exchange_api_key.get_secret_value()
                if self.settings.exchange_api_key
                else None
            ),
            api_secret=(
                self.settings.exchange_api_secret.get_secret_value()
                if self.settings.exchange_api_secret
                else None
            ),
        )
        try:
            candles = list(await provider.fetch_ohlcv(symbol, timeframe, limit=limit))
            return candles
        finally:
            await provider.close()

    async def run_rest_cycle(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
        lookback: int = 60,
    ) -> dict[str, Any]:
        """
        One-shot live cycle using REST klines (no sample candles).

        Warms the indicator window from historical bars, then processes the
        newest closed candle through strategy → risk → execution.
        """
        symbol = symbol or self.symbol
        timeframe = timeframe or self.timeframe
        self.symbol = symbol
        self.timeframe = timeframe
        candles = await self.fetch_rest_candles(
            symbol=symbol, timeframe=timeframe, limit=lookback
        )
        if len(candles) < 25:
            return {
                "accepted": False,
                "reason": "INSUFFICIENT_REST_CANDLES",
                "candles": len(candles),
            }
        # Warm window without trading intermediate bars; act on the latest close.
        self._window = list(candles[:-1])
        # Allow re-processing the tip after restart (clear only that key).
        tip = candles[-1]
        self._seen_candle_keys.discard((tip.symbol, tip.open_time.isoformat()))
        return await self.process_candle(tip)

    async def on_trade_tick(self, msg: dict[str, Any]) -> None:
        self.health.last_market_data_at = utc_now()
        self.health.market_data_fresh = True
        self.health.websocket_connected = True

    async def _ws_candle_handler(self, candle: Candle) -> None:
        await self.on_closed_candle(candle)

    async def on_closed_candle(self, candle: Candle) -> dict[str, Any]:
        async with self._lock:
            return await self._process_candle(candle)

    async def process_candle(self, candle: Candle) -> dict[str, Any]:
        """Public entry for tests / REST-polled cycles."""
        async with self._lock:
            return await self._process_candle(candle)

    async def _process_candle(self, candle: Candle) -> dict[str, Any]:
        started = utc_now()
        self._ensure_backend()
        assert self.gateway is not None
        self.stats.candles += 1
        self._last_candle = candle
        self.health.last_market_data_at = utc_now()
        self.health.market_data_fresh = True
        self.health.strategy_heartbeat_ok = True

        key = (candle.symbol, candle.open_time.isoformat())
        if key in self._seen_candle_keys:
            return {"accepted": False, "reason": "DUPLICATE_CANDLE"}
        if not candle.is_closed:
            return {"accepted": False, "reason": "INCOMPLETE_CANDLE"}
        self._seen_candle_keys.add(key)
        self._window.append(candle)

        strategy = get_strategy(self.strategy_id)
        position = self._position_for(candle.symbol)
        ctx = StrategyContext(
            candles=list(self._window),
            portfolio=self._portfolio_state(mark=candle.close),
            position=position,
            indicators={},
            config=StrategyConfig(
                strategy_id=strategy.strategy_id,
                version=strategy.version,
                params=dict(strategy.default_config().params),
            ),
        )
        signal = strategy.evaluate(ctx)
        self._last_signal = signal
        self.stats.signals += 1
        self._signals.append(
            {
                "id": uuid4().hex,
                "strategy_name": signal.strategy_name,
                "symbol": signal.symbol,
                "direction": signal.direction.value,
                "reason": signal.entry_rationale,
                "confidence": str(signal.confidence),
                "timestamp": signal.timestamp.isoformat(),
            }
        )
        if self.journal is not None:
            await self.journal.record_signal(signal)

        result: dict[str, Any] = {
            "accepted": True,
            "signal_direction": signal.direction.value,
            "signal_reason": signal.entry_rationale,
            "order_id": None,
            "order_status": None,
            "risk_decision": None,
            "risk_reason_code": None,
        }

        if signal.direction == SignalDirection.HOLD:
            self.stats.last_latency_ms = (utc_now() - started).total_seconds() * 1000
            return result

        if self.kill_switch_enabled or self.settings.kill_switch_enabled:
            await self.monitoring.alert(
                "KILL_SWITCH_ACTIVATED",
                "Kill switch blocked testnet order",
                {"symbol": candle.symbol},
            )
            self.stats.rejections += 1
            result["risk_decision"] = RiskDecision.HALTED.value
            result["risk_reason_code"] = "KILL_SWITCH_ACTIVE"
            return result

        # Cooldown
        if self._last_order_at is not None:
            elapsed = (utc_now() - self._last_order_at).total_seconds()
            if elapsed < self.settings.order_cooldown_seconds:
                self.stats.rejections += 1
                result["risk_decision"] = RiskDecision.REJECTED.value
                result["risk_reason_code"] = "ORDER_COOLDOWN"
                result["signal_reason"] = f"cooldown {elapsed:.1f}s"
                return result

        order = await self._act(signal, candle)
        if order is not None:
            result["order_id"] = order.id
            result["order_status"] = order.status.value
            result["risk_decision"] = (
                order.risk_decision.value if order.risk_decision else None
            )
            result["risk_reason_code"] = (
                order.risk_reason_code.value if order.risk_reason_code else None
            )
        self.stats.last_latency_ms = (utc_now() - started).total_seconds() * 1000
        return result

    async def _act(self, signal: TradeSignal, candle: Candle) -> Order | None:
        assert self.gateway is not None
        position = self._position_for(candle.symbol)
        mark = candle.close
        if signal.direction == SignalDirection.BUY:
            if position is not None:
                return None
            side = OrderSide.BUY
            quantity = self._entry_qty(mark)
            reduce_only = False
            stop = signal.suggested_stop
        else:
            if position is None:
                return None
            side = OrderSide.SELL
            quantity = position.quantity
            reduce_only = True
            stop = (mark * Decimal("0.999")).quantize(Decimal("0.01"))

        if quantity <= 0:
            return None

        # Sync risk reconciliation flag
        if self.reconciler is not None:
            self.risk_state.reconciliation_healthy = (
                self.reconciler.reconciliation_healthy
            )

        symbol_info = None
        backend = self._backend
        if backend is not None and hasattr(backend, "fetch_symbol_info"):
            symbol_info = await backend.fetch_symbol_info(candle.symbol)
            from app.execution.exchange.precision import quantize_quantity

            quantity = quantize_quantity(quantity, symbol_info)
            if quantity <= 0:
                return None

        coid = f"tn-{candle.symbol.replace('/', '')}-{int(candle.open_time.timestamp())}-{side.value}"
        request = OrderRequest(
            symbol=candle.symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            stop_loss=stop,
            strategy_name=signal.strategy_name,
            idempotency_key=coid,
            client_order_id=coid,
            reduce_only=reduce_only,
        )

        context = RiskContext(
            portfolio=self._portfolio_state(mark=mark),
            symbol_info=symbol_info,
            mark_price=mark,
            market_data_ts=utc_now(),
            trading_mode="paper",  # testnet funds ≠ live mode
            live_trading_enabled=False,
            kill_switch_enabled=self.kill_switch_enabled,
            has_exchange_credentials=self.settings.has_exchange_credentials,
            live_approval_valid=False,
            exchange_env=self.settings.exchange_env,
        )
        try:
            order = await self.gateway.submit(request, context)
        except RiskBlockedError as blocked:
            self.stats.rejections += 1
            self._risk_events.append(
                {
                    "decision": blocked.evaluation.decision.value,
                    "reason_code": blocked.evaluation.reason_code.value,
                    "message": blocked.evaluation.message,
                    "timestamp": utc_now().isoformat(),
                }
            )
            await self.monitoring.alert(
                "RISK_VIOLATION",
                blocked.evaluation.message or blocked.evaluation.reason_code.value,
                {"reason_code": blocked.evaluation.reason_code.value},
            )
            if self.journal is not None:
                await self.journal.record_risk_decision(
                    idempotency_key=coid, evaluation=blocked.evaluation
                )
            return Order(
                id=coid,
                client_order_id=coid,
                idempotency_key=coid,
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                status=OrderStatus.REJECTED,
                risk_decision=blocked.evaluation.decision,
                risk_reason_code=blocked.evaluation.reason_code,
            )

        self.stats.orders += 1
        self._last_order_at = utc_now()
        self._orders.append(order)
        if self.journal is not None:
            await self.journal.record_risk_decision(
                idempotency_key=coid,
                evaluation=RiskEvaluation(
                    decision=order.risk_decision or RiskDecision.APPROVED,
                    reason_code=order.risk_reason_code or RiskReasonCode.OK,
                    approved_quantity=order.quantity,
                ),
            )
            await self.journal.record_order(order)

        if order.status in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED):
            self.stats.fills += 1
            self._apply_fill_locally(order, mark)
            self._fills.append(
                {
                    "order_id": order.id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "quantity": str(order.filled_quantity or order.quantity),
                    "price": str(order.average_fill_price or mark),
                    "fees": str(order.fees),
                    "timestamp": utc_now().isoformat(),
                    "exchange_order_id": order.id,
                    "status": order.status.value,
                }
            )
        elif order.status in (OrderStatus.REJECTED, OrderStatus.FAILED):
            self.stats.rejections += 1
            await self.monitoring.alert(
                "ORDER_REJECTED",
                f"Testnet order {order.status.value}",
                {"order_id": order.id, "symbol": order.symbol},
            )
        return order

    def _apply_fill_locally(self, order: Order, mark: Decimal) -> None:
        qty = order.filled_quantity or order.quantity
        px = order.average_fill_price or mark
        fee = order.fees
        usdt = self.local_portfolio.balances.get("USDT", Decimal("0"))
        base = order.symbol.split("/")[0]
        base_bal = self.local_portfolio.balances.get(base, Decimal("0"))
        if order.side == OrderSide.BUY:
            cost = qty * px + fee
            self.local_portfolio.balances["USDT"] = usdt - cost
            self.local_portfolio.balances[base] = base_bal + qty
            self.local_portfolio.positions[order.symbol] = (
                self.local_portfolio.positions.get(order.symbol, Decimal("0")) + qty
            )
        else:
            proceeds = qty * px - fee
            self.local_portfolio.balances["USDT"] = usdt + proceeds
            self.local_portfolio.balances[base] = max(Decimal("0"), base_bal - qty)
            remaining = (
                self.local_portfolio.positions.get(order.symbol, Decimal("0")) - qty
            )
            if remaining <= 0:
                self.local_portfolio.positions.pop(order.symbol, None)
            else:
                self.local_portfolio.positions[order.symbol] = remaining

    def _entry_qty(self, price: Decimal) -> Decimal:
        if price <= 0:
            return Decimal("0")
        usdt = self.local_portfolio.balances.get("USDT", Decimal("0"))
        notional = usdt * Decimal("0.1")
        return (notional / price).quantize(Decimal("0.00000001"))

    def _position_for(self, symbol: str) -> Position | None:
        qty = self.local_portfolio.positions.get(symbol, Decimal("0"))
        if qty <= 0:
            return None
        mark = self._last_candle.close if self._last_candle else Decimal("0")
        return Position(
            symbol=symbol,
            quantity=qty,
            entry_price=mark,
            current_price=mark,
            unrealized_pnl=Decimal("0"),
            opened_at=utc_now(),
        )

    def _portfolio_state(self, *, mark: Decimal) -> PortfolioState:
        usdt = self.local_portfolio.balances.get("USDT", Decimal("0"))
        equity = usdt
        positions: list[Position] = []
        for symbol, qty in self.local_portfolio.positions.items():
            equity += qty * mark
            positions.append(
                Position(
                    symbol=symbol,
                    quantity=qty,
                    entry_price=mark,
                    current_price=mark,
                    unrealized_pnl=Decimal("0"),
                    opened_at=utc_now(),
                )
            )
        self._peak_equity = max(self._peak_equity, equity)
        dd = (
            (self._peak_equity - equity) / self._peak_equity
            if self._peak_equity > 0
            else Decimal("0")
        )
        return PortfolioState(
            cash_balance=usdt,
            equity=equity,
            realized_pnl=Decimal("0"),
            unrealized_pnl=equity - usdt,
            daily_pnl=equity - self.settings.paper_starting_balance,
            peak_equity=self._peak_equity,
            drawdown=dd,
            open_positions=positions,
            consecutive_losses=self._consecutive_losses,
        )

    def dashboard_snapshot(self) -> dict[str, Any]:
        mark = self._last_candle.close if self._last_candle else Decimal("0")
        state = self._portfolio_state(mark=mark if mark > 0 else Decimal("1"))
        wins = sum(
            1
            for f in self._fills
            if f.get("side") == "sell"  # simplified
        )
        trades = len(self._fills)
        return {
            "exchange_env": self.settings.exchange_env,
            "trading_mode": self.settings.trading_mode,
            "symbol": self.symbol,
            "portfolio_value": str(state.equity.quantize(Decimal("0.01"))),
            "available_usdt": str(state.cash_balance.quantize(Decimal("0.01"))),
            "open_positions": [
                {
                    "symbol": p.symbol,
                    "quantity": str(p.quantity),
                    "current_price": str(p.current_price),
                }
                for p in state.open_positions
            ],
            "open_orders": [
                {
                    "id": o.id,
                    "symbol": o.symbol,
                    "side": o.side.value,
                    "status": o.status.value,
                    "quantity": str(o.quantity),
                }
                for o in self._orders
                if o.status
                in {
                    OrderStatus.SUBMITTED,
                    OrderStatus.PARTIALLY_FILLED,
                    OrderStatus.APPROVED,
                }
            ],
            "pnl": str(state.daily_pnl.quantize(Decimal("0.01"))),
            "win_rate": str(
                (Decimal(wins) / Decimal(trades)).quantize(Decimal("0.0001"))
                if trades
                else "0"
            ),
            "trade_history": list(reversed(self._fills[-50:])),
            "connection_status": {
                "websocket_connected": bool(self.ws.connected) if self.ws else False,
                "websocket_stale": bool(self.ws.is_stale) if self.ws else True,
                "last_market_update": (
                    self.health.last_market_data_at.isoformat()
                    if self.health.last_market_data_at
                    else None
                ),
                "exchange_env": self.settings.exchange_env,
            },
            "risk_status": {
                "kill_switch_enabled": self.kill_switch_enabled,
                "reconciliation_healthy": (
                    self.reconciler.reconciliation_healthy if self.reconciler else True
                ),
                "drawdown": str(state.drawdown),
            },
            "kill_switch": self.kill_switch_enabled,
            "websocket_health": {
                "connected": bool(self.ws.connected) if self.ws else False,
                "stale": bool(self.ws.is_stale) if self.ws else True,
                "metrics": {
                    "connects": self.ws.metrics.connects if self.ws else 0,
                    "disconnects": self.ws.metrics.disconnects if self.ws else 0,
                    "messages": self.ws.metrics.messages if self.ws else 0,
                    "duplicates": self.ws.metrics.duplicates if self.ws else 0,
                },
            },
            "last_signal": None
            if self._last_signal is None
            else {
                "direction": self._last_signal.direction.value,
                "reason": self._last_signal.entry_rationale,
                "strategy": self._last_signal.strategy_name,
            },
            "execution_latency_ms": self.stats.last_latency_ms,
            "stats": {
                "candles": self.stats.candles,
                "signals": self.stats.signals,
                "orders": self.stats.orders,
                "fills": self.stats.fills,
                "rejections": self.stats.rejections,
            },
            "simulated_testnet": True,
            "disclaimer": (
                "Binance Spot Testnet only — not live money. "
                "Results do not guarantee future performance."
            ),
        }

    def set_kill_switch(self, enabled: bool) -> dict[str, Any]:
        self.kill_switch_enabled = enabled
        if enabled:
            try:
                loop = asyncio.get_running_loop()
                self._alert_task = loop.create_task(
                    self.monitoring.alert(
                        "KILL_SWITCH_ACTIVATED", "Kill switch activated", {}
                    )
                )
            except RuntimeError:
                pass
        return {"kill_switch_enabled": enabled}


_RUNTIME: TestnetRuntime | None = None


def get_testnet_runtime() -> TestnetRuntime | None:
    return _RUNTIME


def init_testnet_runtime(**kwargs: Any) -> TestnetRuntime:
    global _RUNTIME
    _RUNTIME = TestnetRuntime(**kwargs)
    return _RUNTIME


def reset_testnet_runtime() -> None:
    global _RUNTIME
    _RUNTIME = None
