"""
Single application service coordinating one paper-trading cycle.

    Market data → candle validation → strategy → signal → risk → paper fill
    → portfolio update → journal → structured cycle result

Every actionable order still flows through ``OrderGateway`` → ``RiskEngine``.
AI modules are never imported here.
"""

from __future__ import annotations

import asyncio
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

# Prevent overlapping manual/scheduled cycles in-process.
_CYCLE_LOCK = asyncio.Lock()
_CYCLE_IN_FLIGHT = False


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


# Process-local cycle registry for dashboard/API (one shared orchestrator).
_CYCLE_ORCHESTRATORS: dict[str, TradingOrchestrator] = {}
_LAST_CYCLE: CycleResult | None = None
_LAST_SIGNAL: TradeSignal | None = None
_STRATEGY_RUNS: list[StrategyRun] = []
_PROCESSED_CYCLE_KEYS: set[tuple[str, str, str, datetime]] = set()


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
        return existing
    strategy = get_strategy(strategy_id)
    paper = paper_engine or PaperTradingEngine(
        PaperConfig(
            initial_cash=settings.paper_starting_balance,
            fee_rate=settings.paper_fee_rate,
            slippage_rate=settings.paper_slippage_rate,
        )
    )
    orch = TradingOrchestrator(
        strategy=strategy,
        session_id=f"cycle-{uuid4().hex[:12]}",
        settings=settings,
        paper_engine=paper,
        journal=journal,
        strategy_params=dict(strategy.default_config().params),
        kill_switch_enabled=settings.kill_switch_enabled,
    )
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


def cycle_in_flight() -> bool:
    return _CYCLE_IN_FLIGHT


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
) -> CycleResult:
    """
    Run one end-to-end paper cycle for the latest closed candle.

    Idempotent for the same (symbol, strategy version, candle close/open time):
    reprocessing the same closed bar does not create a second trade.
    Concurrent callers are rejected while a cycle is in flight.
    """
    global _LAST_CYCLE, _LAST_SIGNAL, _CYCLE_IN_FLIGHT

    if _CYCLE_LOCK.locked() or _CYCLE_IN_FLIGHT:
        return CycleResult(
            correlation_id=correlation_id or uuid4().hex,
            symbol=symbol,
            timeframe=timeframe,
            strategy_name=strategy_id,
            strategy_version="",
            strategy_run_id="",
            candle_open_time=None,
            signal_direction=SignalDirection.HOLD.value,
            signal_reason="cycle already in progress",
            accepted=False,
            reject_reason="CYCLE_IN_FLIGHT",
            message="Duplicate cycle prevented — wait for the in-flight run to finish",
        )

    async with _CYCLE_LOCK:
        _CYCLE_IN_FLIGHT = True
        try:
            return await _run_paper_trading_cycle_locked(
                symbol=symbol,
                timeframe=timeframe,
                correlation_id=correlation_id,
                strategy_id=strategy_id,
                candle_source=candle_source,
                settings=settings,
                journal=journal,
                orchestrator=orchestrator,
                candle_limit=candle_limit,
            )
        finally:
            _CYCLE_IN_FLIGHT = False


async def _run_paper_trading_cycle_locked(
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
) -> CycleResult:
    global _LAST_CYCLE, _LAST_SIGNAL

    settings = settings or get_settings()
    correlation_id = correlation_id or uuid4().hex

    # Readiness: paper mode only; kill switch / pause block actionable cycles.
    if settings.trading_mode != "paper":
        result = CycleResult(
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            strategy_name=strategy_id,
            strategy_version="",
            strategy_run_id="",
            candle_open_time=None,
            signal_direction=SignalDirection.HOLD.value,
            signal_reason="paper mode required",
            accepted=False,
            reject_reason="LIVE_TRADING_DISABLED",
            message="Paper cycle requires TRADING_MODE=paper",
        )
        _LAST_CYCLE = result
        return result

    source: CandleSource = candle_source or OfflineCandleSource()
    orch = orchestrator or get_or_create_orchestrator(
        symbol=symbol,
        strategy_id=strategy_id,
        settings=settings,
        journal=journal,
    )

    logger.info(
        "paper_cycle_start",
        extra={
            "correlation_id": correlation_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy_id": strategy_id,
        },
    )

    candles = await source.load_closed_candles(symbol, timeframe, limit=candle_limit)
    if not candles:
        result = CycleResult(
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            strategy_name=orch.strategy.name,
            strategy_version=orch.strategy.version,
            strategy_run_id="",
            candle_open_time=None,
            signal_direction=SignalDirection.HOLD.value,
            signal_reason="no closed candles available",
            accepted=False,
            reject_reason="NO_CANDLES",
            message="No closed candles to evaluate",
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
        snap = orch.snapshot()
        result = CycleResult(
            correlation_id=correlation_id,
            symbol=symbol,
            timeframe=timeframe,
            strategy_name=orch.strategy.name,
            strategy_version=orch.strategy.version,
            strategy_run_id="",
            candle_open_time=ensure_utc(target.open_time),
            signal_direction=SignalDirection.HOLD.value,
            signal_reason="idempotent: candle already processed for this strategy version",
            accepted=True,
            idempotent_replay=True,
            portfolio=snap,
            message="Cycle skipped — same symbol/strategy/candle already processed",
        )
        _LAST_CYCLE = result
        return result

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
    )
    _LAST_CYCLE = result
    logger.info(
        "paper_cycle_complete",
        extra={
            "correlation_id": correlation_id,
            "direction": result.signal_direction,
            "order_id": result.order_id,
            "risk_decision": result.risk_decision,
        },
    )
    return result


# Ensure default strategy is registered when this module loads.
_ = EMACrossoverStrategy
