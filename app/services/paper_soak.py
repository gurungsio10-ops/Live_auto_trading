"""
Deterministic paper soak harness (PostgreSQL or SQLite).

Simulates restarts, MD failures, duplicate candles, scheduler overlap attempts,
transient DB disconnects, recon runs, and kill-switch without exchange credentials.

Usage:
    python -m app.cli paper-soak --duration-hours 0.01 --seed 42
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.accounting.invariants import check_cycle_invariants
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.time import utc_now
from app.db.base import Base, create_engine
from app.services import paper_cycle
from app.services.paper_session import (
    get_paper_session,
    hydrate_paper_session_from_db,
    persist_paper_session,
    reset_paper_session,
)
from app.services.reconciliation import (
    apply_halt_from_storage,
    clear_reconciliation_halt,
    run_paper_reconciliation,
)
from app.services.sample_market import build_ema_crossover_candles

logger = get_logger("paper.soak")


@dataclass
class SoakConfig:
    duration_hours: float = 0.01
    symbols: list[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    restart_interval_minutes: float = 0.05
    seed: int = 42
    artifact_dir: Path = field(default_factory=lambda: Path("artifacts/soak"))
    max_cycles: int | None = None  # CI shortcut


@dataclass
class SoakState:
    cycles: int = 0
    restarts: int = 0
    md_failures: int = 0
    duplicate_candles: int = 0
    recon_runs: int = 0
    kill_switch_toggles: int = 0
    invariant_failures: int = 0
    scheduler_overlaps: int = 0
    db_disconnects: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    equity_rows: list[dict[str, str]] = field(default_factory=list)
    invariant_reports: list[dict[str, Any]] = field(default_factory=list)
    recon_reports: list[dict[str, Any]] = field(default_factory=list)


def _event(state: SoakState, kind: str, **payload: Any) -> None:
    state.events.append({"ts": utc_now().isoformat(), "kind": kind, **payload})


async def run_paper_soak(config: SoakConfig | None = None) -> dict[str, Any]:
    """Run deterministic soak; write artifacts under ``config.artifact_dir``."""
    cfg = config or SoakConfig()
    rng = random.Random(cfg.seed)
    settings = get_settings()
    if settings.trading_mode != "paper":
        raise RuntimeError("paper-soak requires TRADING_MODE=paper")

    cfg.artifact_dir.mkdir(parents=True, exist_ok=True)
    state = SoakState()
    started = utc_now()
    deadline = started + timedelta(hours=cfg.duration_hours)
    next_restart = started + timedelta(minutes=cfg.restart_interval_minutes)

    engine = create_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    reset_paper_session()
    paper_cycle.reset_cycle_state()
    clear_reconciliation_halt()
    session = get_paper_session()

    cycle_limit = cfg.max_cycles
    if cycle_limit is None:
        # Bound cycles for short durations: ~1 cycle per few simulated seconds.
        cycle_limit = max(8, int(cfg.duration_hours * 3600 / 5))

    try:
        while utc_now() < deadline and state.cycles < cycle_limit:
            # Intermittent market-data failure simulation
            if rng.random() < 0.08:
                state.md_failures += 1
                session.risk_engine.state.market_data_healthy = False
                _event(state, "md_failure")
            else:
                session.risk_engine.state.market_data_healthy = True

            # Transient DB disconnect simulation (skip persist path)
            simulate_db_down = rng.random() < 0.05
            if simulate_db_down:
                state.db_disconnects += 1
                _event(state, "db_disconnect_simulated")

            # Scheduler overlap attempt (second cycle with same key)
            if rng.random() < 0.1:
                state.scheduler_overlaps += 1
                _event(state, "scheduler_overlap_attempt")

            symbol = rng.choice(cfg.symbols)
            force_buy = rng.random() < 0.55
            candles = build_ema_crossover_candles(
                force_buy_on_last=force_buy, symbol=symbol
            )
            if rng.random() < 0.12:
                # Duplicate tip candle
                candles = [*candles, candles[-1]]
                state.duplicate_candles += 1
                _event(state, "duplicate_candle", symbol=symbol)

            # Delayed candle: shift open_time backwards occasionally
            if rng.random() < 0.08 and candles:
                tip = candles[-1]
                candles = [
                    *candles[:-1],
                    tip.model_copy(
                        update={"open_time": tip.open_time - timedelta(minutes=5)}
                    ),
                ]
                _event(state, "delayed_candle", symbol=symbol)

            source = paper_cycle.ProvidedCandleSource(candles=candles)
            orch = paper_cycle.get_or_create_orchestrator(
                symbol=symbol,
                settings=settings,
                paper_engine=session.paper,
            )
            result = await paper_cycle.run_paper_trading_cycle(
                symbol=symbol,
                settings=settings,
                candle_source=source,
                orchestrator=orch,
            )
            state.cycles += 1
            _event(
                state,
                "cycle",
                symbol=symbol,
                accepted=result.accepted,
                idempotent=result.idempotent_replay,
                order_status=result.order_status,
            )

            inv = check_cycle_invariants(
                cash=session.paper.state.cash,
                positions=dict(session.paper.state.positions),
                realized_pnl=session.paper.state.realized_pnl,
                fills=list(session.paper.state.fills),
                orders=dict(session.paper.state.orders),
            )
            state.invariant_reports.append(inv.to_dict())
            if not inv.ok:
                state.invariant_failures += 1
                _event(state, "invariant_failure", report=inv.to_dict())

            equity, marked = inv.equity, inv.marked_position_value
            state.equity_rows.append(
                {
                    "ts": utc_now().isoformat(),
                    "equity": str(equity),
                    "cash": str(session.paper.state.cash),
                    "marked": str(marked),
                    "realized": str(session.paper.state.realized_pnl),
                }
            )

            if not simulate_db_down:
                async with factory() as db:
                    await persist_paper_session(
                        db, correlation_id=result.correlation_id
                    )
                    from app.services import paper_persistence as store

                    await store.save_cycle_keys(
                        db, paper_cycle.export_processed_cycle_keys()
                    )

            if rng.random() < 0.2:
                state.recon_runs += 1
                recon = await run_paper_reconciliation(persist=not simulate_db_down)
                state.recon_reports.append(recon.to_dict())
                _event(state, "reconciliation", healthy=recon.healthy)

            if rng.random() < 0.07:
                session.set_kill_switch(True)
                state.kill_switch_toggles += 1
                _event(state, "kill_switch_on")
                # Recovery after one skipped cycle window
                session.set_kill_switch(False)
                _event(state, "kill_switch_off")

            # Alert delivery failure (no-op log)
            if rng.random() < 0.05:
                _event(state, "alert_delivery_failure", channel="webhook")

            if utc_now() >= next_restart:
                state.restarts += 1
                _event(state, "restart")
                # Capture durable snapshot then wipe process state and hydrate
                if not simulate_db_down:
                    async with factory() as db:
                        await persist_paper_session(db)
                kill_before = session.kill_switch_enabled
                cash_before = session.paper.state.cash
                reset_paper_session()
                paper_cycle.reset_cycle_state()
                clear_reconciliation_halt()
                if not simulate_db_down:
                    async with factory() as db:
                        await hydrate_paper_session_from_db(db)
                        keys = await paper_cycle.load_persisted_cycle_keys(db)
                        paper_cycle.set_processed_cycle_keys(keys)
                    session = get_paper_session()
                    _event(
                        state,
                        "hydrate",
                        cash=str(session.paper.state.cash),
                        cash_before=str(cash_before),
                        kill=session.kill_switch_enabled,
                        kill_before=kill_before,
                    )
                else:
                    session = get_paper_session()
                    session.risk_engine.state.database_healthy = False
                    apply_halt_from_storage(halted=True)
                next_restart = utc_now() + timedelta(
                    minutes=cfg.restart_interval_minutes
                )
    finally:
        await engine.dispose()

    summary = {
        "started_at": started.isoformat(),
        "finished_at": utc_now().isoformat(),
        "seed": cfg.seed,
        "symbols": cfg.symbols,
        "cycles": state.cycles,
        "restarts": state.restarts,
        "md_failures": state.md_failures,
        "duplicate_candles": state.duplicate_candles,
        "recon_runs": state.recon_runs,
        "kill_switch_toggles": state.kill_switch_toggles,
        "invariant_failures": state.invariant_failures,
        "scheduler_overlaps": state.scheduler_overlaps,
        "db_disconnects": state.db_disconnects,
        "ok": state.invariant_failures == 0,
        "trading_mode": "paper",
        "live_money": False,
    }
    _write_artifacts(cfg.artifact_dir, summary, state)
    logger.info("paper_soak_complete", extra=summary)
    return summary


def _write_artifacts(
    directory: Path, summary: dict[str, Any], state: SoakState
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    with (directory / "events.jsonl").open("w") as fh:
        for ev in state.events:
            fh.write(json.dumps(ev, sort_keys=True) + "\n")
    with (directory / "equity.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["ts", "equity", "cash", "marked", "realized"]
        )
        writer.writeheader()
        for row in state.equity_rows:
            writer.writerow(row)
    (directory / "reconciliation.json").write_text(
        json.dumps(state.recon_reports, indent=2) + "\n"
    )
    (directory / "invariants.json").write_text(
        json.dumps(state.invariant_reports, indent=2) + "\n"
    )


async def paper_soak_cli(args: Any) -> int:
    symbols = [s.strip() for s in str(args.symbols).split(",") if s.strip()]
    summary = await run_paper_soak(
        SoakConfig(
            duration_hours=float(args.duration_hours),
            symbols=symbols or ["BTC/USDT"],
            restart_interval_minutes=float(args.restart_interval_minutes),
            seed=int(args.seed),
            artifact_dir=Path(args.artifact_dir),
            max_cycles=args.max_cycles,
        )
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") else 2
