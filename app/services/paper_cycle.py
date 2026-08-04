"""
Single application service coordinating one paper-trading cycle.

    Market data → candle validation → strategy → signal → risk → paper fill
    → portfolio update → journal → structured cycle result

Every actionable order still flows through ``OrderGateway`` → ``RiskEngine``.
AI modules are never imported here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.time import ensure_utc
from app.execution.paper.engine import PaperConfig, PaperTradingEngine
from app.journal.store import JournalStore
from app.models.domain.enums import SignalDirection
from app.models.domain.market import Candle
from app.models.domain.trading import StrategyRun, TradeSignal
from app.services.sample_market import build_ema_crossover_candles
from app.services.trading_orchestrator import CandleOutcome, TradingOrchestrator
from app.strategies.ema_crossover import EMACrossoverStrategy
from app.strategies.registry import get_strategy

logger = get_logger("paper_cycle")


class CandleSource(Protocol):
    async def load_closed_candles(
        self, symbol: str, timeframe: str, *, limit: int
    ) -> list[Candle]: ...


@dataclass
class OfflineCandleSource:
    """Deterministic offline candles for paper cycles without network."""

    base_price: Decimal = Decimal("65000")
    force_buy_on_last: bool = True

    async def load_closed_candles(
        self, symbol: str, timeframe: str, *, limit: int
    ) -> list[Candle]:
        candles = build_ema_crossover_candles(
            symbol=symbol,
            interval=timeframe,
            base_price=self.base_price,
            force_buy_on_last=self.force_buy_on_last,
        )
        closed = [c for c in candles if c.is_closed]
        return closed[-limit:] if limit else closed


@dataclass
class ProvidedCandleSource:
    candles: list[Candle]

    async def load_closed_candles(
        self, symbol: str, timeframe: str, *, limit: int
    ) -> list[Candle]:
        filtered = [
            c
            for c in self.candles
            if c.symbol == symbol and c.timeframe == timeframe and c.is_closed
        ]
        filtered.sort(key=lambda c: ensure_utc(c.open_time))
        return filtered[-limit:] if limit else filtered


@dataclass
class CycleResult:
    correlation_id: str
    symbol: str
    timeframe: str
    strategy_name: str
    strategy_version: str
    strategy_run_id: str
    candle_open_time: datetime | None
    signal_direction: str
    signal_reason: str
    accepted: bool
    reject_reason: str | None = None
    order_id: str | None = None
    order_status: str | None = None
    risk_decision: str | None = None
    risk_reason_code: str | None = None
    portfolio: dict[str, Any] = field(default_factory=dict)
    indicators: dict[str, Any] = field(default_factory=dict)
    idempotent_replay: bool = False
    message: str = ""
    lock_status: str | None = None


# Process-local cycle registry for dashboard/API (one shared orchestrator).
_CYCLE_ORCHESTRATORS: dict[str, TradingOrchestrator] = {}
_LAST_CYCLE: CycleResult | None = None
_LAST_SIGNAL: TradeSignal | None = None
_STRATEGY_RUNS: list[StrategyRun] = []
_PROCESSED_CYCLE_KEYS: set[tuple[str, str, str, datetime]] = set()


def set_processed_cycle_keys(keys: set[tuple[str, str, str, str]]) -> None:
    """Hydrate idempotency keys from durable storage (ISO open_time strings)."""
    global _PROCESSED_CYCLE_KEYS
    out: set[tuple[str, str, str, datetime]] = set()
    for symbol, version, timeframe, open_iso in keys:
        out.add(
            (symbol, version, timeframe, ensure_utc(datetime.fromisoformat(open_iso)))
        )
    _PROCESSED_CYCLE_KEYS = out


def export_processed_cycle_keys() -> set[tuple[str, str, str, str]]:
    return {
        (s, v, tf, ensure_utc(ts).isoformat()) for s, v, tf, ts in _PROCESSED_CYCLE_KEYS
    }


async def load_persisted_cycle_keys(session: Any) -> set[tuple[str, str, str, str]]:
    from app.services import paper_persistence as store

    return await store.load_cycle_keys(session)


async def persist_cycle_keys(session: Any) -> None:
    from app.services import paper_persistence as store

    await store.save_cycle_keys(session, export_processed_cycle_keys())


def _session_key(symbol: str, strategy_id: str) -> str:
    return f"{strategy_id}:{symbol}"


def get_or_create_orchestrator(
    *,
    symbol: str = "BTC/USDT",
    strategy_id: str = "ema_crossover",
    settings: Settings | None = None,
    journal: JournalStore | None = None,
    paper_engine: PaperTradingEngine | None = None,
) -> TradingOrchestrator:
    settings = settings or get_settings()
    key = _session_key(symbol, strategy_id)
    existing = _CYCLE_ORCHESTRATORS.get(key)
    if existing is not None:
        if journal is not None:
            existing.journal = journal
        return existing
    strategy = get_strategy(strategy_id)
    if paper_engine is None:
        # Prefer the singleton dashboard/runtime paper engine so restarts hydrate
        # into the same ledger the API and scheduler use.
        try:
            from app.services.paper_session import get_paper_session

            paper = get_paper_session().paper
        except Exception:
            paper = PaperTradingEngine(
                PaperConfig(
                    initial_cash=settings.paper_starting_balance,
                    fee_rate=settings.paper_fee_rate,
                    slippage_rate=settings.paper_slippage_rate,
                )
            )
    else:
        paper = paper_engine
    orch = TradingOrchestrator(
        strategy=strategy,
        session_id=f"cycle-{uuid4().hex[:12]}",
        settings=settings,
        paper_engine=paper,
        journal=journal,
        strategy_params=dict(strategy.default_config().params),
        kill_switch_enabled=settings.kill_switch_enabled,
    )
    # Align risk/gateway with PaperSession when sharing its engine.
    try:
        from app.execution.gateway import OrderGateway
        from app.services.paper_session import get_paper_session

        session = get_paper_session()
        if paper is session.paper:
            orch.risk = session.risk_engine
            orch.gateway = OrderGateway(session.paper, session.risk_engine)
            orch.kill_switch_enabled = session.kill_switch_enabled
    except Exception:
        pass
    _CYCLE_ORCHESTRATORS[key] = orch
    return orch


def reset_cycle_state() -> None:
    """Reset process-local cycle orchestrators (paper account reset)."""
    global _LAST_CYCLE, _LAST_SIGNAL
    _CYCLE_ORCHESTRATORS.clear()
    _PROCESSED_CYCLE_KEYS.clear()
    _STRATEGY_RUNS.clear()
    _LAST_CYCLE = None
    _LAST_SIGNAL = None


def last_cycle_result() -> CycleResult | None:
    return _LAST_CYCLE


def last_signal() -> TradeSignal | None:
    return _LAST_SIGNAL


def strategy_runs(limit: int = 50) -> list[StrategyRun]:
    return list(reversed(_STRATEGY_RUNS[-limit:]))


def _empty_result(
    *,
    correlation_id: str,
    symbol: str,
    timeframe: str,
    orch: TradingOrchestrator,
    reason: str,
    message: str,
    reject_reason: str,
    candle_open_time: datetime | None = None,
    accepted: bool = False,
    idempotent_replay: bool = False,
    lock_status: str | None = None,
) -> CycleResult:
    snap = orch.snapshot() if accepted or idempotent_replay else {}
    return CycleResult(
        correlation_id=correlation_id,
        symbol=symbol,
        timeframe=timeframe,
        strategy_name=orch.strategy.name,
        strategy_version=orch.strategy.version,
        strategy_run_id="",
        candle_open_time=candle_open_time,
        signal_direction=SignalDirection.HOLD.value,
        signal_reason=reason,
        accepted=accepted,
        reject_reason=reject_reason,
        portfolio=snap,
        message=message,
        idempotent_replay=idempotent_replay,
        lock_status=lock_status,
    )


async def run_paper_trading_cycle(
    symbol: str = "BTC/USDT",
    timeframe: str = "1m",
    correlation_id: str | None = None,
    *,
    strategy_id: str = "ema_crossover",
    candle_source: CandleSource | None = None,
    settings: Settings | None = None,
    journal: JournalStore | None = None,
    orchestrator: TradingOrchestrator | None = None,
    candle_limit: int = 120,
    account_id: str = "paper-default",
) -> CycleResult:
    """
    Run one end-to-end paper cycle for the latest closed candle.

    Idempotent for the same (symbol, strategy version, candle close/open time):
    reprocessing the same closed bar does not create a second trade.
    Uses DB cycle locks when a database is available.
    """
    global _LAST_CYCLE, _LAST_SIGNAL

    settings = settings or get_settings()
    correlation_id = correlation_id or uuid4().hex
    source: CandleSource = candle_source or OfflineCandleSource()
    orch = orchestrator or get_or_create_orchestrator(
        symbol=symbol,
        strategy_id=strategy_id,
        settings=settings,
        journal=journal,
    )
    if journal is not None:
        orch.journal = journal

    logger.info(
        "paper_cycle_start",
        extra={
            "correlation_id": correlation_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy_id": strategy_id,
        },
    )

    # Fail closed when reconciliation halt is active.
    try:
        from app.services.reconciliation import is_reconciliation_healthy

        if settings.enable_reconciliation and not is_reconciliation_healthy():
            result = _empty_result(
                correlation_id=correlation_id,
                symbol=symbol,
                timeframe=timeframe,
                orch=orch,
                reason="reconciliation halt — new orders blocked",
                message="Cycle rejected: reconciliation unhealthy",
                reject_reason="RECONCILIATION_HALT",
            )
            _LAST_CYCLE = result
            return result
    except Exception:
        pass

    candles = await source.load_closed_candles(symbol, timeframe, limit=candle_limit)
    if not candles:
        result = _empty_result(
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            orch=orch,
            reason="no closed candles available",
            message="No closed candles to evaluate",
            reject_reason="NO_CANDLES",
        )
        _LAST_CYCLE = result
        return result

    # Warm indicators from history without generating trades on intermediate bars.
    orch.prime_candles(candles[:-1])

    target = candles[-1]
    cycle_key = (
        symbol,
        orch.strategy.version,
        timeframe,
        ensure_utc(target.open_time),
    )
    if cycle_key in _PROCESSED_CYCLE_KEYS:
        result = _empty_result(
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            orch=orch,
            reason="idempotent: candle already processed for this strategy version",
            message="Cycle skipped — same symbol/strategy/candle already processed",
            reject_reason=None,
            candle_open_time=ensure_utc(target.open_time),
            accepted=True,
            idempotent_replay=True,
            lock_status="skipped_idempotent",
        )
        _LAST_CYCLE = result
        return result

    # Acquire DB cycle lock (final uniqueness protection).
    lock_owner: str | None = None
    lock_key: str | None = None
    lock_session_factory = None
    lock_engine = None
    lock_status = "memory_only"
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from app.db.base import create_engine
        from app.services.cycle_lock import (
            LockStatus,
            acquire_cycle_lock,
            make_cycle_lock_key,
            release_cycle_lock,
        )

        lock_key = make_cycle_lock_key(
            account_id=account_id,
            strategy_id=strategy_id,
            strategy_version=orch.strategy.version,
            symbol=symbol,
            timeframe=timeframe,
            candle_open_time=target.open_time,
        )
        lock_engine = create_engine()
        lock_session_factory = async_sessionmaker(
            lock_engine, expire_on_commit=False, class_=AsyncSession
        )
        async with lock_session_factory() as lock_db:
            acquired = await acquire_cycle_lock(
                lock_db,
                lock_key=lock_key,
                ttl_seconds=settings.cycle_lock_ttl_seconds,
                correlation_id=correlation_id,
            )
            if acquired.status == LockStatus.HELD:
                result = _empty_result(
                    correlation_id=correlation_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    orch=orch,
                    reason="cycle lock held by another worker",
                    message="Cycle rejected: lock held (safe fail-closed)",
                    reject_reason="CYCLE_LOCK_HELD",
                    candle_open_time=ensure_utc(target.open_time),
                    lock_status="held",
                )
                _LAST_CYCLE = result
                await lock_engine.dispose()
                return result
            if acquired.status == LockStatus.ACQUIRED and acquired.lock is not None:
                lock_owner = acquired.lock.owner
                lock_status = "acquired"
            else:
                lock_status = "unavailable"
    except Exception:
        lock_status = "unavailable"
        if lock_engine is not None:
            try:
                await lock_engine.dispose()
            except Exception:
                pass
            lock_engine = None
            lock_session_factory = None

    try:
        # Evaluate on the tip before execution so cycle metadata reflects the
        # decision that drove the order (not the post-fill flat/long state).
        primed_window = list(orch._window.get(symbol, []))
        signal = orch._evaluate(symbol, [*primed_window, target])
        _LAST_SIGNAL = signal

        outcome: CandleOutcome = await orch.process_candle(target)
        _PROCESSED_CYCLE_KEYS.add(cycle_key)
        run = StrategyRun(
            id=uuid4().hex,
            strategy_name=orch.strategy.name,
            strategy_version=orch.strategy.version,
            symbol=symbol,
            timeframe=timeframe,
            candle_open_time=ensure_utc(target.open_time),
            correlation_id=correlation_id,
            direction=signal.direction,
            metadata={
                "outcome": {
                    "accepted": outcome.accepted,
                    "reject_reason": outcome.reject_reason,
                    "order_id": outcome.order_id,
                    "order_status": outcome.order_status,
                    "risk_decision": outcome.risk_decision,
                    "risk_reason_code": outcome.risk_reason_code,
                },
                "indicators": signal.metadata.get("indicators", {}),
            },
        )
        _STRATEGY_RUNS.append(run)
        if journal is not None:
            try:
                await journal.record_system_event(
                    "STRATEGY_RUN",
                    f"{run.strategy_name} {run.direction.value} on {symbol}",
                    severity="info",
                    payload={
                        "strategy_run_id": run.id,
                        "correlation_id": correlation_id,
                        "candle_open_time": run.candle_open_time.isoformat(),
                    },
                )
            except Exception:
                logger.warning(
                    "journal_strategy_run_failed",
                    extra={"correlation_id": correlation_id},
                )

        snap = orch.snapshot()
        result = CycleResult(
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            strategy_name=orch.strategy.name,
            strategy_version=orch.strategy.version,
            strategy_run_id=run.id,
            candle_open_time=ensure_utc(target.open_time),
            signal_direction=outcome.signal_direction or signal.direction.value,
            signal_reason=signal.entry_rationale,
            accepted=outcome.accepted,
            reject_reason=outcome.reject_reason,
            order_id=outcome.order_id,
            order_status=outcome.order_status,
            risk_decision=outcome.risk_decision,
            risk_reason_code=outcome.risk_reason_code,
            portfolio=snap,
            indicators=dict(signal.metadata.get("indicators", {})),
            message="paper cycle complete",
            lock_status=lock_status,
        )
        _LAST_CYCLE = result
        logger.info(
            "paper_cycle_complete",
            extra={
                "correlation_id": correlation_id,
                "direction": result.signal_direction,
                "order_id": result.order_id,
                "risk_decision": result.risk_decision,
                "lock_status": lock_status,
            },
        )
        # Best-effort durable persistence (cycle keys + portfolio checkpoint).
        try:
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

            from app.db.base import create_engine
            from app.services import paper_persistence as store
            from app.services.paper_session import get_paper_session, persist_paper_session

            engine = create_engine()
            factory = async_sessionmaker(
                engine, expire_on_commit=False, class_=AsyncSession
            )
            async with factory() as session:
                await persist_cycle_keys(session)
                session_paper = get_paper_session()
                if orch.paper is session_paper.paper:
                    await persist_paper_session(session, correlation_id=correlation_id)
                else:
                    equity = orch.paper.state.cash + sum(
                        p.quantity * p.current_price
                        for p in orch.paper.state.positions.values()
                    )
                    await store.save_paper_checkpoint(
                        session,
                        cash=orch.paper.state.cash,
                        positions=dict(orch.paper.state.positions),
                        realized_pnl=orch.paper.state.realized_pnl,
                        peak_equity=max(equity, orch.paper.state.cash),
                        consecutive_losses=0,
                        idempotency_index=dict(orch.paper.state.idempotency_index),
                        correlation_id=correlation_id,
                    )
                await store.append_audit_event(
                    session,
                    event_type="PAPER_CYCLE",
                    message=(
                        f"{result.signal_direction} {result.order_status or ''}".strip()
                    ),
                    correlation_id=correlation_id,
                    order_id=result.order_id,
                    payload={
                        "signal_direction": result.signal_direction,
                        "order_status": result.order_status,
                        "risk_decision": result.risk_decision,
                        "risk_reason_code": result.risk_reason_code,
                        "idempotent_replay": result.idempotent_replay,
                        "lock_status": lock_status,
                    },
                )
            await engine.dispose()
        except Exception:
            logger.warning(
                "paper_cycle_persist_failed",
                extra={"correlation_id": correlation_id},
            )

        # Post-cycle reconciliation (fail-closed on mismatch).
        try:
            from app.services.reconciliation import run_paper_reconciliation

            await run_paper_reconciliation(persist=True)
        except Exception:
            logger.warning(
                "paper_cycle_reconciliation_failed",
                extra={"correlation_id": correlation_id},
            )
        return result
    finally:
        if (
            lock_owner
            and lock_key
            and lock_session_factory is not None
            and lock_engine is not None
        ):
            try:
                from app.services.cycle_lock import release_cycle_lock

                async with lock_session_factory() as lock_db:
                    await release_cycle_lock(
                        lock_db, lock_key=lock_key, owner=lock_owner
                    )
            except Exception:
                pass
            try:
                await lock_engine.dispose()
            except Exception:
                pass


# Ensure default strategy is registered when this module loads.
_ = EMACrossoverStrategy
