"""
Paper-trading orchestrator.

The single explicit orchestration layer for paper trading. It is deliberately
decoupled from API route handlers and from any live-exchange code. It consumes
**normalized, closed** candle events and drives the full deterministic lifecycle:

    candle -> validation -> indicators/strategy -> journal(decision)
           -> risk engine (via OrderGateway) -> paper execution -> fills
           -> portfolio update -> journal(order/fill/risk) -> metrics

Safety properties:
- Every actionable order flows through ``app/risk/engine.py`` via ``OrderGateway``;
  nothing here calls the paper engine (or any exchange) directly, bypassing risk.
- No coupling to AI or news modules — they never authorize execution.
- Deterministic client-order-ids + candle/signal dedup make re-processing the
  same event idempotent (restart-safe): a replayed candle never creates a
  duplicate trade.
- All money is ``Decimal``; all timestamps are timezone-aware UTC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.time import ensure_utc, utc_now
from app.execution.gateway import OrderGateway, RiskBlockedError
from app.execution.paper.engine import PaperTradingEngine
from app.journal.store import JournalStore
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
from app.strategies.base import Strategy, StrategyConfig, StrategyContext

logger = get_logger("orchestrator")


@dataclass
class OrchestratorStats:
    candles_received: int = 0
    candles_rejected: int = 0
    signals_generated: int = 0
    hold_decisions: int = 0
    risk_approvals: int = 0
    risk_rejections: int = 0
    paper_orders: int = 0
    fills: int = 0
    fees: Decimal = Decimal(0)
    errors: int = 0


@dataclass
class CandleOutcome:
    accepted: bool
    reject_reason: str | None = None
    signal_direction: str | None = None
    order_id: str | None = None
    order_status: str | None = None
    risk_decision: str | None = None
    risk_reason_code: str | None = None


@dataclass
class TradingOrchestrator:
    """Drives one deterministic paper-trading session for a single strategy."""

    strategy: Strategy
    session_id: str
    settings: Settings = field(default_factory=get_settings)
    paper_engine: PaperTradingEngine | None = None
    risk_engine: RiskEngine | None = None
    journal: JournalStore | None = None
    strategy_params: dict | None = None
    entry_size_fraction: Decimal = Decimal("0.1")
    max_candle_age_seconds: int | None = None
    kill_switch_enabled: bool | None = None

    def __post_init__(self) -> None:
        self.paper = self.paper_engine or PaperTradingEngine()
        # Fresh risk state per session avoids idempotency-key contamination.
        self.risk = self.risk_engine or RiskEngine(
            settings=self.settings, state=RiskEngineState()
        )
        self.gateway = OrderGateway(self.paper, self.risk)
        self.stats = OrchestratorStats()

        self._seen_candles: set[tuple[str, datetime]] = set()
        self._last_open_time: dict[str, datetime] = {}
        self._seen_signal_fps: set[str] = set()
        self._journaled_fill_ids: set[str] = set()
        self._bars_held: dict[str, int] = {}
        self._window: dict[str, list[Candle]] = {}
        self._peak_equity = Decimal(str(self.paper.config.initial_cash))
        self._consecutive_losses = 0
        self._max_drawdown = Decimal(0)

    # -------------------------------------------------------------- validation

    def _reject_reason(self, candle: Candle) -> str | None:
        if not candle.is_closed:
            return "INCOMPLETE_CANDLE"
        key = (candle.symbol, ensure_utc(candle.open_time))
        if key in self._seen_candles:
            return "DUPLICATE_CANDLE"
        last = self._last_open_time.get(candle.symbol)
        if last is not None and ensure_utc(candle.open_time) <= last:
            return "OUT_OF_ORDER_CANDLE"
        if self.max_candle_age_seconds is not None:
            age = (utc_now() - ensure_utc(candle.open_time)).total_seconds()
            if age > self.max_candle_age_seconds:
                return "STALE_CANDLE"
        return None

    def prime_candles(self, candles: list[Candle]) -> int:
        """
        Load historical closed candles into the strategy window without evaluating
        or trading. Used to warm indicators before ``process_candle`` on the tip.
        Skips duplicates / out-of-order bars. Returns number of candles primed.
        """
        primed = 0
        for candle in candles:
            if not candle.is_closed:
                continue
            reason = self._reject_reason(candle)
            if reason is not None:
                continue
            symbol = candle.symbol
            self._seen_candles.add((symbol, ensure_utc(candle.open_time)))
            self._last_open_time[symbol] = ensure_utc(candle.open_time)
            self._window.setdefault(symbol, []).append(candle)
            self.paper.set_mark_price(symbol, candle.close)
            primed += 1
        return primed

    # ------------------------------------------------------------- main entry

    async def process_candle(self, candle: Candle) -> CandleOutcome:
        self.stats.candles_received += 1

        reason = self._reject_reason(candle)
        if reason is not None:
            self.stats.candles_rejected += 1
            await self._journal_event(
                "CANDLE_REJECTED",
                f"{reason} for {candle.symbol} @ {candle.open_time.isoformat()}",
                severity="warning",
                payload={"reason_code": reason, "symbol": candle.symbol},
            )
            return CandleOutcome(accepted=False, reject_reason=reason)

        symbol = candle.symbol
        self._seen_candles.add((symbol, ensure_utc(candle.open_time)))
        self._last_open_time[symbol] = ensure_utc(candle.open_time)
        window = self._window.setdefault(symbol, [])
        window.append(candle)
        self.paper.set_mark_price(symbol, candle.close)
        if symbol in self.paper.state.positions:
            self._bars_held[symbol] = self._bars_held.get(symbol, 0) + 1

        try:
            signal = self._evaluate(symbol, window)
        except Exception as exc:
            self.stats.errors += 1
            await self._journal_event(
                "STRATEGY_ERROR",
                f"Strategy raised: {type(exc).__name__}",
                severity="error",
                payload={"symbol": symbol},
            )
            return CandleOutcome(accepted=True, reject_reason="STRATEGY_ERROR")

        self.stats.signals_generated += 1
        if signal.direction == SignalDirection.HOLD:
            self.stats.hold_decisions += 1

        order: Order | None = None
        if signal.direction in (
            SignalDirection.BUY,
            SignalDirection.SELL,
            SignalDirection.EXIT,
        ):
            order = await self._act_on_signal(symbol, candle, signal)

        # Journal EVERY strategy decision, including HOLD.
        await self._journal_signal(signal, order_id=order.id if order else None)

        self._update_drawdown()

        return CandleOutcome(
            accepted=True,
            signal_direction=signal.direction.value,
            order_id=order.id if order else None,
            order_status=order.status.value if order else None,
            risk_decision=order.risk_decision.value
            if order and order.risk_decision
            else None,
            risk_reason_code=(
                order.risk_reason_code.value
                if order and order.risk_reason_code
                else None
            ),
        )

    # -------------------------------------------------------------- strategy

    def _evaluate(self, symbol: str, window: list[Candle]) -> TradeSignal:
        params = self.strategy_params or dict(self.strategy.default_config().params)
        position = self.paper.state.positions.get(symbol)
        ctx = StrategyContext(
            candles=window,
            portfolio=self._portfolio_state(),
            position=position,
            indicators={"bars_held": self._bars_held.get(symbol, 0)},
            config=StrategyConfig(
                strategy_id=self.strategy.strategy_id,
                version=self.strategy.version,
                params=params,
            ),
        )
        return self.strategy.evaluate(ctx)

    async def _act_on_signal(
        self, symbol: str, candle: Candle, signal: TradeSignal
    ) -> Order | None:
        # Signal-level dedup (same input fingerprint never acts twice).
        if signal.input_data_fingerprint in self._seen_signal_fps:
            return None

        position = self.paper.state.positions.get(symbol)
        mark = candle.close
        if signal.direction == SignalDirection.BUY:
            if position is not None:
                return None
            side = OrderSide.BUY
            quantity = self._entry_quantity(mark)
            stop_loss = signal.suggested_stop
            take_profit = signal.suggested_target
            reduce_only = False
        else:  # SELL / EXIT
            if position is None:
                return None
            side = OrderSide.SELL
            quantity = position.quantity
            # Tight protective stop lets risk size the full reduce-only exit.
            stop_loss = (mark * Decimal("0.999")).quantize(Decimal("0.01"))
            take_profit = None
            reduce_only = True

        if quantity <= 0:
            return None

        # Honour PaperSession trading_paused when this orchestrator shares the
        # dashboard/runtime paper ledger (not isolated CLI/unit orchestrators).
        try:
            from app.services.paper_session import get_paper_session

            session = get_paper_session()
            if self.paper is session.paper and session.trading_paused:
                return None
        except Exception:
            pass

        self._seen_signal_fps.add(signal.input_data_fingerprint)
        coid = self._client_order_id(candle, signal.direction)
        request = OrderRequest(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy_name=self.strategy.name,
            idempotency_key=coid,
            client_order_id=coid,
            reduce_only=reduce_only,
        )
        context = self._risk_context(symbol, mark)
        realized_before = self.paper.state.realized_pnl

        try:
            order = await self.gateway.submit(request, context)
        except RiskBlockedError as blocked:
            self.stats.risk_rejections += 1
            await self._journal_risk(coid, blocked.evaluation)
            rejected = self._rejected_order(request, blocked.evaluation)
            await self._journal_order(rejected)
            return rejected

        self.stats.risk_approvals += 1
        self.stats.paper_orders += 1
        # Reconstruct the evaluation for the journal (gateway consumed the object).
        evaluation = RiskEvaluation(
            decision=order.risk_decision or RiskDecision.APPROVED,
            reason_code=order.risk_reason_code or RiskReasonCode.OK,
            approved_quantity=order.quantity,
            message="approved",
        )
        await self._journal_risk(coid, evaluation)
        await self._journal_order(order)
        await self._journal_new_fills(order)

        if order.status in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED):
            if side == OrderSide.BUY:
                self._bars_held[symbol] = 0
            else:
                realized_delta = self.paper.state.realized_pnl - realized_before
                if realized_delta < 0:
                    self._consecutive_losses += 1
                elif realized_delta > 0:
                    self._consecutive_losses = 0
                self._bars_held.pop(symbol, None)
        return order

    # ------------------------------------------------------------- helpers

    def _entry_quantity(self, price: Decimal) -> Decimal:
        if price <= 0:
            return Decimal(0)
        notional = self.paper.state.cash * self.entry_size_fraction
        return (notional / price).quantize(Decimal("0.00000001"))

    def _client_order_id(self, candle: Candle, direction: SignalDirection) -> str:
        from app.core.time import to_unix_ms

        symbol = candle.symbol.replace("/", "")
        return f"{self.session_id[:8]}-{symbol}-{to_unix_ms(candle.open_time)}-{direction.value}"

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
        return PortfolioState(
            cash_balance=self.paper.state.cash,
            equity=equity,
            realized_pnl=self.paper.state.realized_pnl,
            unrealized_pnl=unrealized,
            daily_pnl=equity - Decimal(str(self.paper.config.initial_cash)),
            peak_equity=self._peak_equity,
            drawdown=drawdown,
            open_positions=self._positions(),
            consecutive_losses=self._consecutive_losses,
        )

    def _risk_context(self, symbol: str, mark: Decimal) -> RiskContext:
        kill = (
            self.kill_switch_enabled
            if self.kill_switch_enabled is not None
            else self.settings.kill_switch_enabled
        )
        return RiskContext(
            portfolio=self._portfolio_state(),
            symbol_info=None,
            mark_price=mark,
            # Receipt time — the feed just delivered this candle. Freshness is
            # about feed liveness, not the candle's historical open_time.
            market_data_ts=utc_now(),
            trading_mode=self.settings.trading_mode,
            live_trading_enabled=self.settings.live_trading_enabled,
            kill_switch_enabled=kill,
            has_exchange_credentials=self.settings.has_exchange_credentials,
            live_approval_valid=False,
            exchange_env=self.settings.exchange_env,
        )

    def _rejected_order(
        self, request: OrderRequest, evaluation: RiskEvaluation
    ) -> Order:
        now = utc_now()
        return Order(
            id=request.idempotency_key,
            client_order_id=request.client_order_id or request.idempotency_key,
            idempotency_key=request.idempotency_key,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            status=OrderStatus.REJECTED,
            strategy_name=request.strategy_name,
            risk_decision=evaluation.decision,
            risk_reason_code=evaluation.reason_code,
            created_at=now,
            updated_at=now,
        )

    def _update_drawdown(self) -> None:
        self._portfolio_state()  # refreshes peak
        equity = self._equity()
        if self._peak_equity > 0:
            dd = (self._peak_equity - equity) / self._peak_equity
            self._max_drawdown = max(self._max_drawdown, dd)

    def snapshot(self) -> dict:
        state = self._portfolio_state()
        return {
            "session_id": self.session_id,
            "candles_received": self.stats.candles_received,
            "candles_rejected": self.stats.candles_rejected,
            "signals_generated": self.stats.signals_generated,
            "hold_decisions": self.stats.hold_decisions,
            "risk_approvals": self.stats.risk_approvals,
            "risk_rejections": self.stats.risk_rejections,
            "paper_orders": self.stats.paper_orders,
            "fills": self.stats.fills,
            "fees": str(self.stats.fees.quantize(Decimal("0.01"))),
            "realized_pnl": str(state.realized_pnl.quantize(Decimal("0.01"))),
            "unrealized_pnl": str(state.unrealized_pnl.quantize(Decimal("0.01"))),
            "current_balance": str(state.cash_balance.quantize(Decimal("0.01"))),
            "equity": str(state.equity.quantize(Decimal("0.01"))),
            "max_drawdown": str(self._max_drawdown.quantize(Decimal("0.0001"))),
            "open_positions": len(state.open_positions),
            "errors": self.stats.errors,
        }

    # ------------------------------------------------------------- journaling

    async def _journal_signal(
        self, signal: TradeSignal, *, order_id: str | None
    ) -> None:
        if self.journal is not None:
            await self._guarded(self.journal.record_signal(signal, order_id=order_id))

    async def _guarded(self, awaitable) -> None:
        """Await a journal write; persistence must never break the trading loop."""
        try:
            await awaitable
        except Exception:
            self.stats.errors += 1

    async def _journal_risk(
        self, idempotency_key: str, evaluation: RiskEvaluation
    ) -> None:
        if self.journal is not None:
            await self._guarded(
                self.journal.record_risk_decision(
                    idempotency_key=idempotency_key, evaluation=evaluation
                )
            )

    async def _journal_order(self, order: Order) -> None:
        if self.journal is not None:
            await self._guarded(self.journal.record_order(order))

    async def _journal_new_fills(self, order: Order) -> None:
        for fill in self.paper.state.fills:
            if fill.order_id != order.id or fill.id in self._journaled_fill_ids:
                continue
            self._journaled_fill_ids.add(fill.id)
            self.stats.fills += 1
            self.stats.fees += fill.fee
            if self.journal is not None:
                await self._guarded(self.journal.record_fill(fill))

    async def _journal_event(
        self,
        event_type: str,
        message: str,
        *,
        severity: str,
        payload: dict | None = None,
    ) -> None:
        if self.journal is not None:
            await self._guarded(
                self.journal.record_system_event(
                    event_type, message, severity=severity, payload=payload
                )
            )
