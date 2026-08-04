"""
In-memory paper-trading session that wires the real engines together.

This is the live data source behind the dashboard endpoints. Every order still
flows through ``app/risk/engine.py`` (via ``OrderGateway``) before touching the
paper execution engine — nothing here bypasses risk checks. State is process-local
and resets on restart, which is appropriate for a paper/demo session.
"""

from __future__ import annotations

import json
import math
from decimal import Decimal
from threading import RLock
from typing import Any
from uuid import uuid4

from app.backtesting.engine import BacktestConfig, BacktestEngine
from app.core.config import Settings, get_settings
from app.core.time import utc_now
from app.execution.gateway import OrderGateway, RiskBlockedError
from app.execution.paper.engine import PaperConfig, PaperTradingEngine
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
from app.risk.engine import RiskContext, RiskEngine, RiskEngineState
from app.strategies.base import StrategyConfig, StrategyContext
from app.strategies.registry import get_strategy, list_strategies

# Reference prices used to synthesise a deterministic paper market per symbol.
_BASE_PRICES: dict[str, Decimal] = {
    "BTC/USDT": Decimal(65000),
    "ETH/USDT": Decimal(3200),
    "SOL/USDT": Decimal(150),
}

# Presentation metadata for registered strategies (governance is not on the base class).
_STRATEGY_META: dict[str, dict[str, str]] = {
    "ema_crossover": {
        "governance_status": "PAPER",
        "description": (
            "Minimal EMA(9)/EMA(21) crossover, long-only spot. "
            "Deterministic rule-derived signals — not predictive."
        ),
        "timeframe": "1m",
    },
    "ema_rsi": {
        "governance_status": "PAPER",
        "description": (
            "EMA crossover with RSI>50 confirmation and percent stop/target. "
            "Paper MVP baseline — not marketed as profitable."
        ),
        "timeframe": "5m",
    },
    "ema_trend": {
        "governance_status": "PAPER",
        "description": "Dual EMA crossover with ATR-based stops. Deterministic, no LLM in path.",
        "timeframe": "1h",
    },
    "rsi_mean_reversion": {
        "governance_status": "PAPER",
        "description": (
            "RSI oversold/overbought mean-reversion, long-only. "
            "Deterministic — not marketed as profitable."
        ),
        "timeframe": "1h",
    },
    "breakout": {
        "governance_status": "PAPER",
        "description": (
            "Donchian breakout using prior N-bar high/low (excludes current bar). "
            "Long-only, deterministic."
        ),
        "timeframe": "1h",
    },
}


def _q(value: Decimal, places: str = "0.01") -> str:
    return str(Decimal(value).quantize(Decimal(places)))


def _qty(value: Decimal) -> str:
    return str(Decimal(value).quantize(Decimal("0.00000001")).normalize())


class PaperSession:
    """Holds live paper-trading state and exposes dashboard-shaped views."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._lock = RLock()
        starting = self.settings.paper_starting_balance
        self.paper = PaperTradingEngine(
            PaperConfig(
                initial_cash=starting,
                fee_rate=self.settings.paper_fee_rate,
                slippage_rate=self.settings.paper_slippage_rate,
            )
        )
        self.risk_engine = RiskEngine(settings=self.settings, state=RiskEngineState())
        self.gateway = OrderGateway(self.paper, self.risk_engine)

        self.kill_switch_enabled: bool = self.settings.kill_switch_enabled
        self.trading_enabled: bool = bool(self.settings.trading_enabled)
        self.trading_paused: bool = False
        self.selected_strategy_id: str | None = "ema_crossover"
        self.running_strategies: set[str] = set()
        self.param_overrides: dict[str, dict[str, Any]] = {}

        self._initial_cash = starting
        self._daily_start_equity = starting
        self._peak_equity = starting
        self._consecutive_losses = 0
        self._ticks: dict[str, int] = {}

        self.order_history: list[Order] = []
        self.signal_log: list[dict[str, Any]] = []
        self.risk_event_log: list[dict[str, Any]] = []
        self.equity_curve: list[dict[str, str]] = []
        self.backtest_reports: list[dict[str, Any]] = []

        self._persist_task: Any = None
        self.last_hydrated_at: str | None = None
        self._record_equity_point()

    # ------------------------------------------------------------------ market

    def _base_price(self, symbol: str) -> Decimal:
        return _BASE_PRICES.get(symbol, Decimal(100))

    def _candles_from_closes(self, symbol: str, closes: list[Decimal]) -> list[Candle]:
        timeframe = _STRATEGY_META.get("ema_trend", {}).get("timeframe", "1h")
        candles: list[Candle] = []
        start = utc_now()
        n = len(closes)
        for i, close in enumerate(closes):
            close = close.quantize(Decimal("0.01"))
            open_ = (
                closes[i - 1].quantize(Decimal("0.01"))
                if i > 0
                else (close * Decimal("0.999")).quantize(Decimal("0.01"))
            )
            hi = (max(open_, close) * Decimal("1.0015")).quantize(Decimal("0.01"))
            lo = (min(open_, close) * Decimal("0.9985")).quantize(Decimal("0.01"))
            vol = Decimal(1000) + Decimal(300) * Decimal(str(abs(math.sin(i / 3.0))))
            if i == n - 1:
                vol = Decimal(5000)  # final spike so volume > volume MA on entry bar
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=start,
                    open=open_,
                    high=hi,
                    low=lo,
                    close=close,
                    volume=vol,
                    is_closed=True,
                )
            )
        return candles

    def _live_series(self, symbol: str, bars: int = 60) -> list[Candle]:
        """Series whose final bar satisfies the EMA-trend entry filters.

        A gentle uptrend keeps ``fast EMA > slow EMA``; the last ~12 bars form a
        dip-then-rally so RSI lands in the mid band (not overbought) while the
        final bar closes up on a volume spike — a real, risk-checked entry moment.
        ``tick`` lifts the overall level each call so marks/P&L move over time.
        """
        base = self._base_price(symbol) * (
            Decimal(1) + Decimal("0.002") * Decimal(self._ticks.get(symbol, 0))
        )
        closes = [
            base * (Decimal(1) + Decimal("0.0015") * Decimal(i)) for i in range(bars)
        ]
        # Tail zig-zag: balanced up/down bar returns keep RSI in the mid band while
        # the final bar closes up — a genuine (non-overbought) entry trigger.
        tail = [
            "0.004",
            "-0.006",
            "0.003",
            "-0.007",
            "0.004",
            "-0.006",
            "0.005",
            "-0.007",
            "0.004",
            "-0.006",
            "0.005",
            "-0.007",
            "0.004",
            "0.006",
        ]
        k0 = bars - len(tail)
        c = closes[k0 - 1]
        for k, r in enumerate(tail):
            c = c * (Decimal(1) + Decimal(r))
            closes[k0 + k] = c
        return self._candles_from_closes(symbol, closes)

    def _backtest_series(self, symbol: str, bars: int = 180) -> list[Candle]:
        """Oscillating uptrend that produces multiple entries/exits for a backtest."""
        base = self._base_price(symbol)
        closes = [
            base
            * (
                Decimal(1)
                + Decimal("0.0008") * Decimal(i)
                + Decimal("0.02") * Decimal(str(math.sin(i / 7.0)))
            )
            for i in range(bars)
        ]
        return self._candles_from_closes(symbol, closes)

    def _mark(self, symbol: str) -> Decimal:
        mark = self.paper.config.mark_prices.get(symbol)
        if mark is None:
            mark = self._live_series(symbol)[-1].close
            self.paper.set_mark_price(symbol, mark)
        return mark

    # ------------------------------------------------------------ portfolio math

    def _positions(self) -> list[Position]:
        return list(self.paper.state.positions.values())

    def _equity(self) -> Decimal:
        total = self.paper.state.cash
        for pos in self._positions():
            total += pos.quantity * pos.current_price
        return total

    def _portfolio_state(self) -> PortfolioState:
        equity = self._equity()
        self._peak_equity = max(self._peak_equity, equity)
        drawdown = (
            (self._peak_equity - equity) / self._peak_equity
            if self._peak_equity > 0
            else Decimal(0)
        )
        unrealized = sum((p.unrealized_pnl for p in self._positions()), Decimal(0))
        daily_pnl = equity - self._daily_start_equity
        return PortfolioState(
            cash_balance=self.paper.state.cash,
            equity=equity,
            realized_pnl=self.paper.state.realized_pnl,
            unrealized_pnl=unrealized,
            daily_pnl=daily_pnl,
            peak_equity=self._peak_equity,
            drawdown=drawdown,
            open_positions=self._positions(),
            consecutive_losses=self._consecutive_losses,
        )

    def _risk_context(self, symbol: str) -> RiskContext:
        from app.services.market_sources import last_market_data_ts
        from app.services.reconciliation import is_reconciliation_healthy

        md_ts = last_market_data_ts() or utc_now()
        self.risk_engine.state.last_market_data_ts = md_ts
        self.risk_engine.state.reconciliation_healthy = is_reconciliation_healthy()
        return RiskContext(
            portfolio=self._portfolio_state(),
            symbol_info=None,
            mark_price=self._mark(symbol),
            market_data_ts=md_ts,
            trading_mode=self.settings.trading_mode,
            live_trading_enabled=self.settings.live_trading_enabled,
            kill_switch_enabled=self.kill_switch_enabled,
            has_exchange_credentials=self.settings.has_exchange_credentials,
            live_approval_valid=False,
            exchange_env=self.settings.exchange_env,
        )

    def _record_equity_point(self) -> None:
        equity = self._equity()
        self._peak_equity = max(self._peak_equity, equity)
        drawdown = (
            (self._peak_equity - equity) / self._peak_equity
            if self._peak_equity > 0
            else Decimal(0)
        )
        self.equity_curve.append(
            {
                "time": utc_now().isoformat(),
                "equity": _q(equity),
                "drawdown": str(drawdown.quantize(Decimal("0.0001"))),
            }
        )
        if len(self.equity_curve) > 240:
            self.equity_curve = self.equity_curve[-240:]

    # ------------------------------------------------------------- order routing

    async def _submit(
        self,
        *,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal | None = None,
        stop_loss: Decimal | None = None,
        take_profit: Decimal | None = None,
        strategy_name: str | None = None,
        signal_id: str | None = None,
        reduce_only: bool = False,
    ) -> Order:
        """Route an order through the risk engine + paper engine, logging outcomes."""
        request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy_name=strategy_name,
            signal_id=signal_id,
            idempotency_key=uuid4().hex,
            reduce_only=reduce_only,
        )
        context = self._risk_context(symbol)
        realized_before = self.paper.state.realized_pnl

        try:
            order = await self.gateway.submit(request, context)
        except RiskBlockedError as blocked:
            order = self._synth_rejected_order(request, blocked.evaluation)
            self.order_history.insert(0, order)
            self._log_risk_event(order, requested=quantity)
            self._record_equity_point()
            return order

        self.order_history.insert(0, order)
        self._log_risk_event(order, requested=quantity)

        if side == OrderSide.SELL and order.status in (
            OrderStatus.FILLED,
            OrderStatus.PARTIALLY_FILLED,
        ):
            realized_delta = self.paper.state.realized_pnl - realized_before
            if realized_delta < 0:
                self._consecutive_losses += 1
            elif realized_delta > 0:
                self._consecutive_losses = 0

        self._record_equity_point()
        return order

    def _synth_rejected_order(
        self, request: OrderRequest, evaluation: RiskEvaluation
    ) -> Order:
        now = utc_now()
        return Order(
            id=uuid4().hex,
            client_order_id=f"paper-{uuid4().hex[:12]}",
            idempotency_key=request.idempotency_key,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            filled_quantity=Decimal(0),
            price=request.price,
            status=OrderStatus.REJECTED,
            strategy_name=request.strategy_name,
            risk_decision=evaluation.decision,
            risk_reason_code=evaluation.reason_code,
            created_at=now,
            updated_at=now,
        )

    def _log_risk_event(self, order: Order, *, requested: Decimal) -> None:
        approved = (
            order.quantity
            if order.risk_decision in (RiskDecision.APPROVED, RiskDecision.REDUCED)
            else None
        )
        decision = order.risk_decision or RiskDecision.APPROVED
        reason = order.risk_reason_code or RiskReasonCode.OK
        self.risk_event_log.insert(
            0,
            {
                "id": f"risk_{uuid4().hex[:12]}",
                "timestamp": utc_now().isoformat(),
                "decision": decision.value,
                "reason_code": reason.value,
                "message": self._risk_message(decision, reason),
                "symbol": order.symbol,
                "strategy_name": order.strategy_name,
                "requested_quantity": _qty(requested),
                "approved_quantity": _qty(approved) if approved is not None else None,
                "order_id": order.id,
            },
        )
        if len(self.risk_event_log) > 200:
            self.risk_event_log = self.risk_event_log[:200]

    @staticmethod
    def _risk_message(decision: RiskDecision, reason: RiskReasonCode) -> str:
        if decision == RiskDecision.APPROVED:
            return "All risk checks passed."
        if decision == RiskDecision.REDUCED:
            return "Order size reduced to satisfy risk limits."
        if decision == RiskDecision.HALTED:
            return "Order halted by safety control."
        return f"Order rejected: {reason.value}."

    # ---------------------------------------------------------------- serializers

    @staticmethod
    def _position_dict(pos: Position) -> dict[str, Any]:
        return {
            "symbol": pos.symbol,
            "quantity": _qty(pos.quantity),
            "entry_price": _q(pos.entry_price),
            "current_price": _q(pos.current_price),
            "unrealized_pnl": _q(pos.unrealized_pnl),
            "realized_pnl": _q(pos.realized_pnl),
            "opened_at": pos.opened_at.isoformat(),
            "strategy_name": pos.strategy_name,
            "stop_loss": _q(pos.stop_loss) if pos.stop_loss is not None else None,
            "take_profit": _q(pos.take_profit) if pos.take_profit is not None else None,
        }

    @staticmethod
    def _order_dict(order: Order) -> dict[str, Any]:
        return {
            "id": order.id,
            "client_order_id": order.client_order_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": _qty(order.quantity),
            "filled_quantity": _qty(order.filled_quantity),
            "price": _q(order.price) if order.price is not None else None,
            "average_fill_price": (
                _q(order.average_fill_price)
                if order.average_fill_price is not None
                else None
            ),
            "status": order.status.value,
            "strategy_name": order.strategy_name,
            "risk_decision": order.risk_decision.value if order.risk_decision else None,
            "risk_reason_code": (
                order.risk_reason_code.value if order.risk_reason_code else None
            ),
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
            "fees": _q(order.fees),
        }

    def _signal_dict(self, signal: TradeSignal, signal_id: str) -> dict[str, Any]:
        return {
            "id": signal_id,
            "strategy_name": signal.strategy_name,
            "strategy_version": signal.strategy_version,
            "symbol": signal.symbol,
            "timestamp": signal.timestamp.isoformat(),
            "direction": signal.direction.value,
            "confidence": str(signal.confidence.quantize(Decimal("0.01"))),
            "entry_rationale": signal.entry_rationale,
            "invalidation_condition": signal.invalidation_condition,
            "suggested_stop": _q(signal.suggested_stop)
            if signal.suggested_stop
            else None,
            "suggested_target": (
                _q(signal.suggested_target) if signal.suggested_target else None
            ),
            "suggested_entry": _q(signal.suggested_entry)
            if signal.suggested_entry
            else None,
        }

    # --------------------------------------------------------------- public views

    def portfolio_summary(self) -> dict[str, Any]:
        with self._lock:
            state = self._portfolio_state()
            return {
                "cash_balance": _q(state.cash_balance),
                "equity": _q(state.equity),
                "realized_pnl": _q(state.realized_pnl),
                "unrealized_pnl": _q(state.unrealized_pnl),
                "daily_pnl": _q(state.daily_pnl),
                "peak_equity": _q(state.peak_equity),
                "drawdown": str(state.drawdown.quantize(Decimal("0.0001"))),
                "open_position_count": len(state.open_positions),
                "consecutive_losses": state.consecutive_losses,
                "trading_mode": self.settings.trading_mode,
                "runtime_mode": self.settings.runtime_mode.value,
                "kill_switch_enabled": self.kill_switch_enabled,
                "trading_enabled": self.trading_enabled,
                "trading_paused": self.trading_paused,
                "exchange_env": self.settings.exchange_env,
            }

    def positions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._position_dict(p) for p in self._positions()]

    def orders(
        self,
        *,
        status: str | None = None,
        symbol: str | None = None,
        date: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            result = [self._order_dict(o) for o in self.order_history]
        if status:
            result = [o for o in result if o["status"] == status]
        if symbol:
            needle = symbol.upper()
            result = [o for o in result if needle in o["symbol"].upper()]
        if date:
            result = [o for o in result if o["created_at"][:10] == date]
        return result

    def signals(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.signal_log)

    def risk_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.risk_event_log)

    def equity_points(self) -> list[dict[str, str]]:
        with self._lock:
            return list(self.equity_curve)

    def strategies(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._strategy_dict(s.strategy_id) for s in list_strategies()]

    def _strategy_dict(self, strategy_id: str) -> dict[str, Any]:
        strategy = get_strategy(strategy_id)
        meta = _STRATEGY_META.get(
            strategy_id,
            {
                "governance_status": "DRAFT",
                "description": strategy.name,
                "timeframe": "1h",
            },
        )
        params = self.param_overrides.get(strategy_id)
        if params is None:
            params = dict(strategy.default_config().params)
        return {
            "strategy_id": strategy.strategy_id,
            "name": strategy.name,
            "version": strategy.version,
            "governance_status": meta["governance_status"],
            "description": meta["description"],
            "running": strategy_id in self.running_strategies,
            "selected": strategy_id == self.selected_strategy_id,
            "paper_params": params,
            "symbols": list(self.settings.supported_symbols),
            "timeframe": meta["timeframe"],
        }

    def settings_view(self) -> dict[str, Any]:
        s = self.settings
        return {
            "trading_mode": s.trading_mode,
            "live_trading_enabled": s.live_trading_enabled,
            "kill_switch_enabled": self.kill_switch_enabled,
            "exchange_env": s.exchange_env,
            "exchange_id": s.exchange_id,
            "supported_symbols": list(s.supported_symbols),
            "supported_timeframes": list(s.supported_timeframes),
            "market_data_stale_seconds": s.market_data_stale_seconds,
            "risk_limits": {
                "max_risk_per_trade": str(s.max_risk_per_trade),
                "max_position_exposure": str(s.max_position_exposure),
                "max_portfolio_exposure": str(s.max_portfolio_exposure),
                "max_open_positions": s.max_open_positions,
                "max_daily_loss": str(s.max_daily_loss),
                "max_drawdown": str(s.max_drawdown),
                "max_consecutive_losses": s.max_consecutive_losses,
                "max_orders_per_minute": s.max_orders_per_minute,
                "min_order_notional": str(s.min_order_notional),
                "default_leverage": str(s.default_leverage),
            },
        }

    def journal_export(self) -> dict[str, Any]:
        with self._lock:
            payload = {
                "exported_at": utc_now().isoformat(),
                "mode": self.settings.trading_mode,
                "portfolio": self.portfolio_summary(),
                "positions": self.positions(),
                "orders": [self._order_dict(o) for o in self.order_history],
                "risk_events": list(self.risk_event_log),
                "signals": list(self.signal_log),
            }
        content = json.dumps(payload, indent=2)
        return {
            "filename": f"atlas-journal-{int(utc_now().timestamp())}.json",
            "content": content,
            "content_type": "application/json",
        }

    # ------------------------------------------------------------ safety controls

    def set_kill_switch(self, enabled: bool) -> dict[str, Any]:
        with self._lock:
            self.kill_switch_enabled = enabled
            if enabled:
                self.risk_event_log.insert(
                    0,
                    {
                        "id": f"risk_{uuid4().hex[:12]}",
                        "timestamp": utc_now().isoformat(),
                        "decision": RiskDecision.HALTED.value,
                        "reason_code": RiskReasonCode.KILL_SWITCH_ACTIVE.value,
                        "message": "Kill switch engaged — all new orders halted.",
                        "symbol": None,
                        "strategy_name": None,
                        "requested_quantity": None,
                        "approved_quantity": None,
                        "order_id": None,
                    },
                )
            # Best-effort durable persist (sync wrapper for async store).
            try:
                import asyncio

                from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

                from app.db.base import create_engine
                from app.services import paper_persistence as store

                async def _persist() -> None:
                    engine = create_engine()
                    factory = async_sessionmaker(
                        engine, expire_on_commit=False, class_=AsyncSession
                    )
                    try:
                        async with factory() as session:
                            await store.save_kill_switch(session, enabled=enabled)
                            await store.record_kill_switch_event(
                                session,
                                enabled=enabled,
                                reason=("activated" if enabled else "deactivated"),
                                payload={"source": "set_kill_switch"},
                            )
                            await store.append_audit_event(
                                session,
                                event_type="KILL_SWITCH",
                                message=(
                                    "Kill switch activated"
                                    if enabled
                                    else "Kill switch deactivated"
                                ),
                                severity="critical" if enabled else "info",
                                payload={"enabled": enabled},
                            )
                    finally:
                        await engine.dispose()

                try:
                    loop = asyncio.get_running_loop()
                    self._persist_task = loop.create_task(_persist())
                except RuntimeError:
                    asyncio.run(_persist())
            except Exception:
                pass
            return {"kill_switch_enabled": enabled}

    def set_trading_enabled(self, enabled: bool) -> dict[str, Any]:
        """Authoritative paper trading enable/disable (persisted to DB)."""
        with self._lock:
            self.trading_enabled = enabled
            try:
                import asyncio

                from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

                from app.db.base import create_engine
                from app.services import paper_persistence as store

                async def _persist() -> None:
                    engine = create_engine()
                    factory = async_sessionmaker(
                        engine, expire_on_commit=False, class_=AsyncSession
                    )
                    try:
                        async with factory() as session:
                            await store.save_trading_enabled(session, enabled=enabled)
                            await store.append_audit_event(
                                session,
                                event_type="TRADING_ENABLED",
                                message=(
                                    "Paper trading enabled"
                                    if enabled
                                    else "Paper trading disabled"
                                ),
                                payload={"enabled": enabled},
                            )
                    finally:
                        await engine.dispose()

                try:
                    loop = asyncio.get_running_loop()
                    self._persist_task = loop.create_task(_persist())
                except RuntimeError:
                    asyncio.run(_persist())
            except Exception:
                pass
            return {
                "trading_enabled": enabled,
                "kill_switch_enabled": self.kill_switch_enabled,
            }

    def set_paused(self, paused: bool) -> dict[str, Any]:
        with self._lock:
            self.trading_paused = paused
            try:
                import asyncio

                from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

                from app.db.base import create_engine
                from app.services import paper_persistence as store

                async def _persist() -> None:
                    engine = create_engine()
                    factory = async_sessionmaker(
                        engine, expire_on_commit=False, class_=AsyncSession
                    )
                    try:
                        async with factory() as session:
                            await store.save_trading_paused(session, paused=paused)
                    finally:
                        await engine.dispose()

                try:
                    loop = asyncio.get_running_loop()
                    self._persist_task = loop.create_task(_persist())
                except RuntimeError:
                    asyncio.run(_persist())
            except Exception:
                pass
            return self.portfolio_summary()

    # ------------------------------------------------------------------ strategy

    def select_strategy(self, strategy_id: str) -> dict[str, Any]:
        with self._lock:
            get_strategy(strategy_id)  # raises KeyError if unknown
            self.selected_strategy_id = strategy_id
            return self._strategy_dict(strategy_id)

    def stop_strategy(self, strategy_id: str) -> dict[str, Any]:
        with self._lock:
            get_strategy(strategy_id)
            self.running_strategies.discard(strategy_id)
            return self._strategy_dict(strategy_id)

    def update_params(self, strategy_id: str, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            get_strategy(strategy_id)
            meta = _STRATEGY_META.get(strategy_id, {"governance_status": "DRAFT"})
            if meta["governance_status"] not in ("PAPER", "TESTNET"):
                raise PermissionError(
                    "Paper params only editable for PAPER/TESTNET strategies"
                )
            self.param_overrides[strategy_id] = dict(params)
            return self._strategy_dict(strategy_id)

    async def start_strategy(self, strategy_id: str) -> dict[str, Any]:
        """Mark a strategy running and run one paper 'tick' (signal -> risk -> fill)."""
        with self._lock:
            get_strategy(strategy_id)
            self.running_strategies.add(strategy_id)
            self.selected_strategy_id = strategy_id
        await self.run_strategy_tick(strategy_id)
        with self._lock:
            return self._strategy_dict(strategy_id)

    async def run_strategy_tick(self, strategy_id: str) -> dict[str, Any]:
        """Evaluate the strategy on the synthetic market and act on the signal."""
        strategy = get_strategy(strategy_id)
        symbol = (self.settings.supported_symbols or ("BTC/USDT",))[0]

        with self._lock:
            self._ticks[symbol] = self._ticks.get(symbol, 0) + 3
            candles = self._live_series(symbol)
            mark = candles[-1].close
            self.paper.set_mark_price(symbol, mark)

            params = self.param_overrides.get(strategy_id) or dict(
                strategy.default_config().params
            )
            position = self.paper.state.positions.get(symbol)
            ctx = StrategyContext(
                candles=candles,
                portfolio=self._portfolio_state(),
                position=position,
                indicators={"bars_held": 0},
                config=StrategyConfig(
                    strategy_id=strategy.strategy_id,
                    version=strategy.version,
                    params=params,
                ),
            )
            signal = strategy.evaluate(ctx)
            signal_id = f"sig_{uuid4().hex[:12]}"
            self.signal_log.insert(0, self._signal_dict(signal, signal_id))
            if len(self.signal_log) > 200:
                self.signal_log = self.signal_log[:200]

        acted: Order | None = None
        if not self.trading_paused and not self.kill_switch_enabled:
            if signal.direction == SignalDirection.BUY and position is None:
                acted = await self._submit(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=self._suggested_qty(symbol, mark),
                    stop_loss=signal.suggested_stop,
                    take_profit=signal.suggested_target,
                    strategy_name=strategy.name,
                    signal_id=signal_id,
                )
            elif signal.direction == SignalDirection.EXIT and position is not None:
                acted = await self._close_symbol(symbol, strategy_name=strategy.name)
        else:
            # Record the halt as a risk event so the UI reflects why nothing traded.
            if signal.direction in (SignalDirection.BUY, SignalDirection.EXIT):
                self.set_kill_switch(self.kill_switch_enabled)

        with self._lock:
            self._record_equity_point()
        return {"signal_id": signal_id, "acted": acted.id if acted else None}

    def _suggested_qty(self, symbol: str, price: Decimal) -> Decimal:
        # Request ~10% of cash; the risk engine will size it down to limits.
        notional = self.paper.state.cash * Decimal("0.1")
        if price <= 0:
            return Decimal(0)
        return (notional / price).quantize(Decimal("0.00000001"))

    # ------------------------------------------------------------------ manual

    async def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        symbol = payload["symbol"]
        with self._lock:
            self._mark(symbol)
        order = await self._submit(
            symbol=symbol,
            side=OrderSide(payload["side"]),
            order_type=OrderType(payload["order_type"]),
            quantity=Decimal(str(payload["quantity"])),
            price=Decimal(str(payload["price"])) if payload.get("price") else None,
            stop_loss=Decimal(str(payload["stop_loss"]))
            if payload.get("stop_loss")
            else None,
            take_profit=(
                Decimal(str(payload["take_profit"]))
                if payload.get("take_profit")
                else None
            ),
            strategy_name=payload.get("strategy_name") or "manual",
        )
        return self._order_dict(order)

    async def close_position(self, symbol: str) -> list[dict[str, Any]]:
        await self._close_symbol(symbol, strategy_name="manual")
        return self.positions()

    async def _close_symbol(
        self, symbol: str, *, strategy_name: str | None
    ) -> Order | None:
        """Close a position via risk-checked reduce-only sells (may take a few passes)."""
        last: Order | None = None
        for _ in range(4):
            with self._lock:
                position = self.paper.state.positions.get(symbol)
                qty = position.quantity if position else Decimal(0)
                mark = self._mark(symbol)
            if qty <= 0:
                break
            # A tight protective stop lets the risk engine size the full reduce-only
            # exit (fixed-fractional sizing would otherwise slice it to ~1% of equity).
            # All safety gates (kill switch, live gating, exposure) still apply.
            last = await self._submit(
                symbol=symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=qty,
                stop_loss=(mark * Decimal("0.999")).quantize(Decimal("0.01")),
                strategy_name=strategy_name,
                reduce_only=True,
            )
            with self._lock:
                remaining = self.paper.state.positions.get(symbol)
            if remaining is not None and remaining.quantity >= qty:
                break  # no progress; avoid infinite loop
        return last

    # ---------------------------------------------------------------- backtests

    def backtests(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.backtest_reports)

    def run_backtest(self, request: dict[str, Any]) -> dict[str, Any]:
        strategy_id = request.get("strategy_id", "ema_trend")
        symbol = request.get("symbol", "BTC/USDT")
        timeframe = request.get("timeframe", "1h")
        strategy = get_strategy(strategy_id)
        initial_cash = Decimal(str(request.get("initial_cash") or "10000"))

        candles = self._backtest_series(symbol, bars=180)
        engine = BacktestEngine(strategy, BacktestConfig(initial_cash=initial_cash))
        result = engine.run(candles, write_reports=False)
        metrics = self._round_metrics(result.metrics.to_dict())
        run_id = f"bt_{uuid4().hex[:12]}"

        report = {
            "run_id": run_id,
            "strategy_id": strategy_id,
            "status": "completed",
            "created_at": utc_now().isoformat(),
            "config": {
                "symbol": symbol,
                "timeframe": timeframe,
                "start": request.get("start", ""),
                "end": request.get("end", ""),
                "initial_cash": str(initial_cash),
            },
            "metrics": {
                "trade_count": metrics["trade_count"],
                "total_return": metrics["total_return"],
                "net_return": metrics["net_return"],
                "win_rate": metrics["win_rate"],
                "profit_factor": metrics["profit_factor"],
                "max_drawdown": metrics["max_drawdown"],
                "sharpe": metrics["sharpe"],
                "sortino": metrics["sortino"],
                "fees_paid": metrics["fees_paid"],
                "slippage_cost": metrics["slippage_cost"],
            },
            "json_report": {
                "run_id": run_id,
                "strategy_id": strategy_id,
                "config": request,
                "metrics": metrics,
                "trade_count": metrics["trade_count"],
            },
            "markdown_report": self._backtest_markdown(strategy.name, run_id, metrics),
            "error": None,
        }
        with self._lock:
            self.backtest_reports.insert(0, report)
        return report

    @staticmethod
    def _round_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
        places = {
            "total_return": "0.0001",
            "net_return": "0.01",
            "win_rate": "0.0001",
            "profit_factor": "0.01",
            "max_drawdown": "0.0001",
            "sharpe": "0.01",
            "sortino": "0.01",
            "fees_paid": "0.01",
            "slippage_cost": "0.01",
        }
        rounded = dict(metrics)
        for key, place in places.items():
            if key in rounded and rounded[key] is not None:
                try:
                    rounded[key] = str(
                        Decimal(str(rounded[key])).quantize(Decimal(place))
                    )
                except (ValueError, ArithmeticError):
                    pass
        return rounded

    @staticmethod
    def _backtest_markdown(name: str, run_id: str, metrics: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"# Backtest Report — {name}",
                "",
                f"- Run ID: `{run_id}`",
                f"- Trades: **{metrics['trade_count']}**",
                f"- Total return: **{metrics['total_return']}**",
                f"- Net P&L: **{metrics['net_return']}**",
                f"- Win rate: **{metrics['win_rate']}**",
                f"- Profit factor: **{metrics['profit_factor']}**",
                f"- Max drawdown: **{metrics['max_drawdown']}**",
                f"- Sharpe: **{metrics['sharpe']}**",
                f"- Sortino: **{metrics['sortino']}**",
                f"- Fees paid: **{metrics['fees_paid']}**",
                f"- Slippage cost: **{metrics['slippage_cost']}**",
                "",
            ]
        )


_SESSION: PaperSession | None = None


def get_paper_session() -> PaperSession:
    global _SESSION
    if _SESSION is None:
        _SESSION = PaperSession()
    return _SESSION


def reset_paper_session() -> PaperSession:
    global _SESSION
    _SESSION = PaperSession()
    return _SESSION


async def hydrate_paper_session_from_db(session: Any) -> PaperSession:
    """Load durable kill-switch + portfolio + risk/strategy + order/fill ledger."""
    from app.journal.store import JournalStore
    from app.services import paper_persistence as store
    from app.services import reconciliation as recon

    paper = get_paper_session()
    kill = await store.load_kill_switch(session)
    if kill is not None:
        paper.kill_switch_enabled = kill
    trading_enabled = await store.load_trading_enabled(session)
    if trading_enabled is not None:
        paper.trading_enabled = trading_enabled
    trading_paused = await store.load_trading_paused(session)
    if trading_paused is not None:
        paper.trading_paused = trading_paused
    halt = await store.load_reconciliation_halt(session)
    if halt is not None:
        halted = bool(halt.get("halted"))
        paper.risk_engine.state.reconciliation_healthy = not halted
        recon.apply_halt_from_storage(halted=halted)

    checkpoint = await store.load_paper_checkpoint(session)
    account = await store.load_paper_account(session)
    if checkpoint:
        cash = Decimal(str(checkpoint.get("cash", paper.paper.state.cash)))
        paper.paper.state.cash = cash
        paper._peak_equity = Decimal(
            str(checkpoint.get("peak_equity", paper._peak_equity))
        )
        if checkpoint.get("daily_start_equity") is not None:
            paper._daily_start_equity = Decimal(str(checkpoint["daily_start_equity"]))
        paper._consecutive_losses = int(checkpoint.get("consecutive_losses") or 0)
        paper.paper.state.realized_pnl = Decimal(
            str(checkpoint.get("realized_pnl") or "0")
        )
        paper.paper.state.positions = store.checkpoint_to_positions(checkpoint)
        idx = checkpoint.get("idempotency_index") or {}
        if isinstance(idx, dict):
            paper.paper.state.idempotency_index = {
                str(k): str(v) for k, v in idx.items()
            }
        for symbol, pos in paper.paper.state.positions.items():
            paper.paper.set_mark_price(symbol, pos.current_price)
        paper._record_equity_point()
    elif account is not None:
        # First-class account row when checkpoint JSON is absent.
        paper.paper.state.cash = Decimal(str(account["cash"]))
        paper.paper.state.realized_pnl = Decimal(str(account["realized_pnl"]))
        paper._peak_equity = Decimal(str(account["peak_equity"]))
        paper._daily_start_equity = Decimal(str(account["daily_start_equity"]))
        paper._consecutive_losses = int(account["consecutive_losses"] or 0)
        idx = account.get("idempotency_index") or {}
        if isinstance(idx, dict):
            paper.paper.state.idempotency_index = {
                str(k): str(v) for k, v in idx.items()
            }
        paper._record_equity_point()

    risk_state = await store.load_risk_state(session)
    if risk_state is not None:
        rs = paper.risk_engine.state
        rs.circuit_breaker_open = bool(risk_state["circuit_breaker_open"])
        rs.circuit_breaker_reason = str(risk_state.get("circuit_breaker_reason") or "")
        rs.seen_idempotency_keys = {
            str(k) for k in (risk_state.get("seen_idempotency_keys") or [])
        }
        rs.reconciliation_healthy = bool(risk_state["reconciliation_healthy"])
        rs.risk_engine_healthy = bool(risk_state["risk_engine_healthy"])
        rs.database_healthy = bool(risk_state["database_healthy"])
        rs.market_data_healthy = bool(risk_state["market_data_healthy"])
        paper._peak_equity = Decimal(
            str(risk_state["peak_equity"] or paper._peak_equity)
        )
        paper._daily_start_equity = Decimal(
            str(risk_state["daily_start_equity"] or paper._daily_start_equity)
        )
        paper._consecutive_losses = int(
            risk_state.get("consecutive_losses") or paper._consecutive_losses
        )
        if risk_state.get("kill_switch_enabled"):
            paper.kill_switch_enabled = True

    # Seed risk seen-keys from order idempotency index when risk_state empty.
    if not paper.risk_engine.state.seen_idempotency_keys:
        paper.risk_engine.state.seen_idempotency_keys = set(
            paper.paper.state.idempotency_index.keys()
        )

    strategy_state = await store.load_strategy_state(session)
    if strategy_state is not None:
        paper.selected_strategy_id = strategy_state.get("selected_strategy_id")
        paper.running_strategies = {
            str(s) for s in (strategy_state.get("running_strategies") or [])
        }
        overrides = strategy_state.get("param_overrides") or {}
        if isinstance(overrides, dict):
            paper.param_overrides = {
                str(k): dict(v) if isinstance(v, dict) else {}
                for k, v in overrides.items()
            }

    # Hydrate order/fill ledger from journal tables when present.
    try:
        journal = JournalStore(session)
        orders = await journal.list_orders(limit=500)
        fills = await journal.list_fills(limit=500)
        for order in orders:
            paper.paper.state.orders[order.id] = order
            paper.paper.state.idempotency_index[order.idempotency_key] = order.id
            paper.risk_engine.state.seen_idempotency_keys.add(order.idempotency_key)
            if order not in paper.order_history:
                paper.order_history.append(order)
        if fills:
            paper.paper.state.fills = list(fills)
    except Exception:
        # Older DBs without journal tables still boot from checkpoint.
        pass

    # Fallback: restore fills/orders from checkpoint so restart recon and
    # idempotency stay coherent when journal rows were never written.
    if checkpoint:
        if not paper.paper.state.fills:
            restored_fills = store.checkpoint_to_fills(checkpoint)
            if restored_fills:
                paper.paper.state.fills = list(restored_fills)
        if not paper.paper.state.orders:
            restored_orders = store.checkpoint_to_orders(checkpoint)
            for order_id, order in restored_orders.items():
                paper.paper.state.orders[order_id] = order
                paper.paper.state.idempotency_index[order.idempotency_key] = order_id
                paper.risk_engine.state.seen_idempotency_keys.add(order.idempotency_key)
                if order not in paper.order_history:
                    paper.order_history.append(order)
    from app.core.time import utc_now as _utc_now

    paper.last_hydrated_at = _utc_now().isoformat()
    return paper


async def persist_paper_session(
    session: Any, *, correlation_id: str | None = None
) -> None:
    """Write kill switch + portfolio + risk/strategy durable state atomically.

    Stages all dual-writes in one transaction and commits once. Callers must
    treat exceptions as fail-closed (do not continue trading with divergent
    memory vs DB state).
    """
    from app.services import paper_persistence as store

    paper = get_paper_session()
    await store.save_kill_switch(
        session, enabled=paper.kill_switch_enabled, commit=False
    )
    await store.save_trading_enabled(
        session, enabled=paper.trading_enabled, commit=False
    )
    await store.save_trading_paused(session, paused=paper.trading_paused, commit=False)
    fees = sum((f.fee for f in paper.paper.state.fills), Decimal("0"))
    equity = paper.paper.state.cash + sum(
        (p.quantity * p.current_price for p in paper.paper.state.positions.values()),
        Decimal("0"),
    )
    drawdown = (
        (paper._peak_equity - equity) / paper._peak_equity
        if paper._peak_equity > 0
        else Decimal("0")
    )
    await store.save_paper_checkpoint(
        session,
        cash=paper.paper.state.cash,
        positions=dict(paper.paper.state.positions),
        realized_pnl=paper.paper.state.realized_pnl,
        peak_equity=paper._peak_equity,
        consecutive_losses=paper._consecutive_losses,
        idempotency_index=dict(paper.paper.state.idempotency_index),
        fees_paid=fees,
        daily_start_equity=paper._daily_start_equity,
        correlation_id=correlation_id,
        fills=list(paper.paper.state.fills),
        orders=dict(paper.paper.state.orders),
        commit=False,
    )
    await store.save_paper_account(
        session,
        cash=paper.paper.state.cash,
        realized_pnl=paper.paper.state.realized_pnl,
        peak_equity=paper._peak_equity,
        daily_start_equity=paper._daily_start_equity,
        consecutive_losses=paper._consecutive_losses,
        fees_paid=fees,
        idempotency_index=dict(paper.paper.state.idempotency_index),
        commit=False,
    )
    rs = paper.risk_engine.state
    await store.save_risk_state(
        session,
        circuit_breaker_open=rs.circuit_breaker_open,
        circuit_breaker_reason=rs.circuit_breaker_reason,
        seen_idempotency_keys=list(rs.seen_idempotency_keys),
        reconciliation_healthy=rs.reconciliation_healthy,
        risk_engine_healthy=rs.risk_engine_healthy,
        database_healthy=rs.database_healthy,
        market_data_healthy=rs.market_data_healthy,
        peak_equity=paper._peak_equity,
        daily_start_equity=paper._daily_start_equity,
        consecutive_losses=paper._consecutive_losses,
        kill_switch_enabled=paper.kill_switch_enabled,
        commit=False,
    )
    await store.save_strategy_state(
        session,
        selected_strategy_id=paper.selected_strategy_id,
        running_strategies=list(paper.running_strategies),
        param_overrides=dict(paper.param_overrides),
        commit=False,
    )
    await store.save_equity_snapshot(
        session,
        equity=equity,
        cash=paper.paper.state.cash,
        drawdown=drawdown,
        commit=False,
    )
    await session.commit()


async def bootstrap_paper_runtime() -> None:
    """Startup: hydrate durable state and reconcile; fail closed on recon errors."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.core.logging import get_logger
    from app.db.base import Base, create_engine
    from app.services import cycle_lock as _cycle_lock_models  # noqa: F401
    from app.services import paper_cycle

    log = get_logger("paper.bootstrap")
    engine = create_engine()
    try:
        async with engine.begin() as conn:
            # Dev/sqlite safety: create missing tables if migrations not run yet.
            # Production should use ``alembic upgrade head``.
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
        async with factory() as session:
            await hydrate_paper_session_from_db(session)
            keys = await paper_cycle.load_persisted_cycle_keys(session)
            paper_cycle.set_processed_cycle_keys(keys)
        # Startup reconciliation — fail-closed via risk engine flag.
        try:
            from app.services.reconciliation import run_paper_reconciliation

            await run_paper_reconciliation(persist=True)
        except Exception as exc:
            paper = get_paper_session()
            paper.risk_engine.state.reconciliation_healthy = False
            paper.trading_paused = True
            from app.services import reconciliation as recon

            recon.apply_halt_from_storage(halted=True)
            recon._STATE["last_result"] = {
                "healthy": False,
                "detail": f"startup reconciliation failed: {type(exc).__name__}",
            }
            log.error(
                "paper_bootstrap_reconciliation_failed",
                extra={"error": type(exc).__name__},
            )
            try:
                async with factory() as session:
                    from app.services import paper_persistence as store

                    await store.save_reconciliation_halt(
                        session,
                        halted=True,
                        detail=f"startup reconciliation failed: {type(exc).__name__}",
                    )
                    await store.save_trading_paused(session, paused=True)
            except Exception:
                log.warning("paper_bootstrap_halt_persist_failed")
    except Exception:
        # DB unavailable: keep in-memory session but mark database unhealthy.
        paper = get_paper_session()
        paper.risk_engine.state.database_healthy = False
        log.warning(
            "paper_bootstrap_failed",
            extra={"detail": "continuing with in-memory paper session"},
        )
    finally:
        await engine.dispose()
