"""
Durable paper-session persistence (kill switch, portfolio, cycle keys).

Uses ``system_state``, ``balances``, ``positions``, ``portfolio_snapshots``,
and ``trade_journal`` tables from Alembic ``0004``, plus first-class
``paper_accounts`` / ``risk_state`` / ``strategy_state`` tables from ``0006``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.time import ensure_utc, utc_now
from app.models.database.portfolio import (
    BalanceORM,
    EquitySnapshotORM,
    KillSwitchEventORM,
    PaperAccountORM,
    PortfolioSnapshotORM,
    PositionORM,
    ProcessedCycleKeyORM,
    RiskStateORM,
    StrategyRunORM,
    StrategyStateORM,
    SystemStateORM,
    TradeJournalORM,
)
from app.models.domain.trading import Position

logger = get_logger("paper.persistence")

DEFAULT_ACCOUNT_ID = "paper-default"

KEY_KILL_SWITCH = "kill_switch"
KEY_PAPER_CHECKPOINT = "paper_checkpoint"
KEY_CYCLE_KEYS = "processed_cycle_keys"
KEY_RUNTIME = "runtime_mode"
KEY_TRADING_ENABLED = "trading_enabled"
KEY_TRADING_PAUSED = "trading_paused"
KEY_RECON_HALT = "reconciliation_halt"


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def _parse_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _dec(value: object) -> Decimal:
    return Decimal(str(value))


async def get_system_value(session: AsyncSession, key: str) -> dict[str, Any] | None:
    row = await session.get(SystemStateORM, key)
    return None if row is None else dict(row.value or {})


async def set_system_value(
    session: AsyncSession, key: str, value: dict[str, Any]
) -> None:
    row = await session.get(SystemStateORM, key)
    now = utc_now()
    if row is None:
        session.add(SystemStateORM(key=key, value=value, updated_at=now))
    else:
        row.value = value
        row.updated_at = now
    await session.commit()


async def save_kill_switch(
    session: AsyncSession, *, enabled: bool, reason: str = ""
) -> None:
    await set_system_value(
        session,
        KEY_KILL_SWITCH,
        {
            "enabled": enabled,
            "updated_at": utc_now().isoformat(),
            "reason": reason,
        },
    )


async def record_kill_switch_event(
    session: AsyncSession,
    *,
    enabled: bool,
    reason: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        KillSwitchEventORM(
            id=uuid4().hex,
            enabled=_bool_str(enabled),
            reason=reason or ("enabled" if enabled else "disabled"),
            created_at=utc_now(),
            payload=payload or {},
        )
    )
    await session.commit()


async def load_kill_switch(session: AsyncSession) -> bool | None:
    value = await get_system_value(session, KEY_KILL_SWITCH)
    if value is None:
        return None
    return bool(value.get("enabled"))


async def save_trading_enabled(session: AsyncSession, *, enabled: bool) -> None:
    await set_system_value(
        session,
        KEY_TRADING_ENABLED,
        {"enabled": enabled, "updated_at": utc_now().isoformat()},
    )


async def load_trading_enabled(session: AsyncSession) -> bool | None:
    value = await get_system_value(session, KEY_TRADING_ENABLED)
    if value is None:
        return None
    return bool(value.get("enabled"))


async def save_trading_paused(session: AsyncSession, *, paused: bool) -> None:
    await set_system_value(
        session,
        KEY_TRADING_PAUSED,
        {"paused": paused, "updated_at": utc_now().isoformat()},
    )


async def load_trading_paused(session: AsyncSession) -> bool | None:
    value = await get_system_value(session, KEY_TRADING_PAUSED)
    if value is None:
        return None
    return bool(value.get("paused"))


async def save_reconciliation_halt(
    session: AsyncSession, *, halted: bool, detail: str = ""
) -> None:
    await set_system_value(
        session,
        KEY_RECON_HALT,
        {
            "halted": halted,
            "detail": detail,
            "updated_at": utc_now().isoformat(),
        },
    )


async def load_reconciliation_halt(session: AsyncSession) -> dict[str, Any] | None:
    return await get_system_value(session, KEY_RECON_HALT)


async def save_cycle_keys(
    session: AsyncSession,
    keys: set[tuple[str, str, str, str]],
    *,
    account_id: str = DEFAULT_ACCOUNT_ID,
) -> None:
    """Persist processed cycle keys (system_state + normalized table)."""
    now = utc_now()
    payload = {
        "keys": [list(k) for k in sorted(keys)],
        "updated_at": now.isoformat(),
    }
    await set_system_value(session, KEY_CYCLE_KEYS, payload)

    # Dual-write normalized uniqueness table (idempotent upserts).
    for symbol, version, timeframe, open_iso in keys:
        try:
            open_time = ensure_utc(datetime.fromisoformat(open_iso))
        except (TypeError, ValueError):
            continue
        existing = (
            await session.execute(
                select(ProcessedCycleKeyORM).where(
                    ProcessedCycleKeyORM.account_id == account_id,
                    ProcessedCycleKeyORM.strategy_version == version,
                    ProcessedCycleKeyORM.symbol == symbol,
                    ProcessedCycleKeyORM.timeframe == timeframe,
                    ProcessedCycleKeyORM.candle_open_time == open_time,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                ProcessedCycleKeyORM(
                    id=uuid4().hex,
                    account_id=account_id,
                    strategy_version=version,
                    symbol=symbol,
                    timeframe=timeframe,
                    candle_open_time=open_time,
                    created_at=now,
                )
            )
    await session.commit()


async def load_cycle_keys(session: AsyncSession) -> set[tuple[str, str, str, str]]:
    value = await get_system_value(session, KEY_CYCLE_KEYS)
    out: set[tuple[str, str, str, str]] = set()
    if value:
        for item in value.get("keys") or []:
            if isinstance(item, (list, tuple)) and len(item) == 4:
                out.add((str(item[0]), str(item[1]), str(item[2]), str(item[3])))
    if out:
        return out
    # Fallback: normalized table
    rows = (await session.execute(select(ProcessedCycleKeyORM))).scalars().all()
    for row in rows:
        out.add(
            (
                row.symbol,
                row.strategy_version,
                row.timeframe,
                ensure_utc(row.candle_open_time).isoformat(),
            )
        )
    return out


async def save_paper_checkpoint(
    session: AsyncSession,
    *,
    cash: Decimal,
    positions: dict[str, Position],
    realized_pnl: Decimal,
    peak_equity: Decimal,
    consecutive_losses: int,
    idempotency_index: dict[str, str],
    fees_paid: Decimal = Decimal("0"),
    daily_start_equity: Decimal | None = None,
    correlation_id: str | None = None,
    fills: list[Any] | None = None,
    orders: list[Any] | dict[str, Any] | None = None,
) -> None:
    now = utc_now()
    # Upsert USDT balance
    bal = (
        await session.execute(select(BalanceORM).where(BalanceORM.asset == "USDT"))
    ).scalar_one_or_none()
    if bal is None:
        session.add(
            BalanceORM(
                id=uuid4().hex,
                asset="USDT",
                free=cash,
                locked=Decimal("0"),
                as_of=now,
            )
        )
    else:
        bal.free = cash
        bal.as_of = now

    # Replace positions
    existing = (await session.execute(select(PositionORM))).scalars().all()
    for row in existing:
        await session.delete(row)
    for symbol, pos in positions.items():
        session.add(
            PositionORM(
                id=uuid4().hex,
                symbol=symbol,
                quantity=pos.quantity,
                entry_price=pos.entry_price,
                current_price=pos.current_price,
                unrealized_pnl=pos.unrealized_pnl,
                realized_pnl=getattr(pos, "realized_pnl", Decimal("0")) or Decimal("0"),
                opened_at=pos.opened_at or now,
                strategy_name=pos.strategy_name,
                updated_at=now,
            )
        )

    equity = cash + sum((p.quantity * p.current_price) for p in positions.values())
    unrealized = equity - cash
    session.add(
        PortfolioSnapshotORM(
            id=uuid4().hex,
            cash_balance=cash,
            equity=equity,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized,
            daily_pnl=equity - cash,  # relative; refined by session daily start
            peak_equity=peak_equity,
            drawdown=(
                (peak_equity - equity) / peak_equity
                if peak_equity > 0
                else Decimal("0")
            ),
            fees_paid=fees_paid,
            exposure=unrealized,
            correlation_id=correlation_id,
            payload={"source": "paper_checkpoint"},
            created_at=now,
        )
    )

    daily_start = daily_start_equity if daily_start_equity is not None else peak_equity
    await set_system_value(
        session,
        KEY_PAPER_CHECKPOINT,
        {
            "cash": str(cash),
            "realized_pnl": str(realized_pnl),
            "peak_equity": str(peak_equity),
            "daily_start_equity": str(daily_start),
            "fees_paid": str(fees_paid),
            "consecutive_losses": consecutive_losses,
            "idempotency_index": dict(idempotency_index),
            "positions": {
                symbol: {
                    "quantity": str(pos.quantity),
                    "entry_price": str(pos.entry_price),
                    "current_price": str(pos.current_price),
                    "unrealized_pnl": str(pos.unrealized_pnl),
                    "opened_at": (pos.opened_at or now).isoformat(),
                    "strategy_name": pos.strategy_name,
                }
                for symbol, pos in positions.items()
            },
            "fills": [
                {
                    "id": f.id,
                    "order_id": f.order_id,
                    "symbol": f.symbol,
                    "side": f.side.value if hasattr(f.side, "value") else str(f.side),
                    "quantity": str(f.quantity),
                    "price": str(f.price),
                    "fee": str(f.fee),
                    "timestamp": (
                        f.timestamp.isoformat()
                        if getattr(f, "timestamp", None) is not None
                        else now.isoformat()
                    ),
                }
                for f in (fills or [])
            ],
            "orders": _serialize_orders(orders),
            "updated_at": now.isoformat(),
        },
    )
    await session.commit()


def _serialize_orders(
    orders: list[Any] | dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not orders:
        return []
    values = list(orders.values()) if isinstance(orders, dict) else list(orders)
    out: list[dict[str, Any]] = []
    for order in values:
        if hasattr(order, "model_dump"):
            raw = order.model_dump(mode="json")
            out.append(raw)
        elif isinstance(order, dict):
            out.append(dict(order))
    return out


async def load_paper_checkpoint(session: AsyncSession) -> dict[str, Any] | None:
    return await get_system_value(session, KEY_PAPER_CHECKPOINT)


async def append_audit_event(
    session: AsyncSession,
    *,
    event_type: str,
    message: str,
    severity: str = "info",
    correlation_id: str | None = None,
    order_id: str | None = None,
    idempotency_key: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        TradeJournalORM(
            id=uuid4().hex,
            event_type=event_type,
            severity=severity,
            message=message,
            correlation_id=correlation_id,
            strategy_run_id=None,
            order_id=order_id,
            idempotency_key=idempotency_key,
            payload=payload or {},
            created_at=utc_now(),
        )
    )
    await session.commit()


async def list_audit_events(
    session: AsyncSession, *, limit: int = 50
) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                select(TradeJournalORM)
                .order_by(TradeJournalORM.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "event_type": r.event_type,
            "severity": r.severity,
            "message": r.message,
            "correlation_id": r.correlation_id,
            "order_id": r.order_id,
            "idempotency_key": r.idempotency_key,
            "payload": r.payload,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


def checkpoint_to_positions(payload: dict[str, Any]) -> dict[str, Position]:
    from datetime import datetime

    positions: dict[str, Position] = {}
    raw = payload.get("positions") or {}
    for symbol, data in raw.items():
        opened = data.get("opened_at")
        opened_at = (
            datetime.fromisoformat(opened.replace("Z", "+00:00"))
            if isinstance(opened, str)
            else utc_now()
        )
        positions[symbol] = Position(
            symbol=symbol,
            quantity=_dec(data["quantity"]),
            entry_price=_dec(data["entry_price"]),
            current_price=_dec(data["current_price"]),
            unrealized_pnl=_dec(data.get("unrealized_pnl") or "0"),
            opened_at=opened_at,
            strategy_name=data.get("strategy_name"),
        )
    return positions


def checkpoint_to_fills(payload: dict[str, Any]) -> list[Any]:
    """Restore fill ledger from checkpoint when journal tables are empty."""
    from app.models.domain.enums import OrderSide
    from app.models.domain.trading import Fill

    out: list[Fill] = []
    for raw in payload.get("fills") or []:
        if not isinstance(raw, dict):
            continue
        ts = raw.get("timestamp")
        timestamp = (
            datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if isinstance(ts, str)
            else utc_now()
        )
        out.append(
            Fill(
                id=str(raw.get("id") or uuid4().hex),
                order_id=str(raw.get("order_id") or ""),
                symbol=str(raw.get("symbol") or ""),
                side=OrderSide(str(raw.get("side") or "buy").lower()),
                quantity=_dec(raw.get("quantity") or "0"),
                price=_dec(raw.get("price") or "0"),
                fee=_dec(raw.get("fee") or "0"),
                timestamp=timestamp,
            )
        )
    return out


def checkpoint_to_orders(payload: dict[str, Any]) -> dict[str, Any]:
    """Restore order map from checkpoint when journal tables are empty."""
    from app.models.domain.enums import (
        OrderSide,
        OrderStatus,
        OrderType,
        RiskDecision,
        RiskReasonCode,
    )
    from app.models.domain.trading import Order

    out: dict[str, Order] = {}
    for raw in payload.get("orders") or []:
        if not isinstance(raw, dict):
            continue
        try:
            created = raw.get("created_at")
            updated = raw.get("updated_at")
            order = Order(
                id=str(raw["id"]),
                client_order_id=str(raw.get("client_order_id") or raw["id"][:12]),
                idempotency_key=str(raw.get("idempotency_key") or raw["id"]),
                symbol=str(raw["symbol"]),
                side=OrderSide(str(raw.get("side") or "buy").lower()),
                order_type=OrderType(str(raw.get("order_type") or "market").lower()),
                quantity=_dec(raw.get("quantity") or "0"),
                filled_quantity=_dec(raw.get("filled_quantity") or "0"),
                price=(_dec(raw["price"]) if raw.get("price") is not None else None),
                average_fill_price=(
                    _dec(raw["average_fill_price"])
                    if raw.get("average_fill_price") is not None
                    else None
                ),
                status=OrderStatus(str(raw.get("status") or "FILLED")),
                strategy_name=raw.get("strategy_name"),
                signal_id=raw.get("signal_id"),
                risk_decision=(
                    RiskDecision(str(raw["risk_decision"]))
                    if raw.get("risk_decision")
                    else None
                ),
                risk_reason_code=(
                    RiskReasonCode(str(raw["risk_reason_code"]))
                    if raw.get("risk_reason_code")
                    else None
                ),
                created_at=(
                    datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                    if isinstance(created, str)
                    else utc_now()
                ),
                updated_at=(
                    datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
                    if isinstance(updated, str)
                    else utc_now()
                ),
                fees=_dec(raw.get("fees") or "0"),
                metadata=dict(raw.get("metadata") or {}),
            )
            out[order.id] = order
        except Exception:
            logger.warning("checkpoint_order_restore_skipped")
            continue
    return out


async def save_paper_account(
    session: AsyncSession,
    *,
    account_id: str = DEFAULT_ACCOUNT_ID,
    cash: Decimal,
    realized_pnl: Decimal,
    peak_equity: Decimal,
    daily_start_equity: Decimal,
    consecutive_losses: int,
    fees_paid: Decimal,
    reserved_capital: Decimal = Decimal("0"),
    idempotency_index: dict[str, str] | None = None,
) -> None:
    now = utc_now()
    row = await session.get(PaperAccountORM, account_id)
    if row is None:
        session.add(
            PaperAccountORM(
                id=account_id,
                cash=cash,
                realized_pnl=realized_pnl,
                peak_equity=peak_equity,
                daily_start_equity=daily_start_equity,
                consecutive_losses=consecutive_losses,
                fees_paid=fees_paid,
                reserved_capital=reserved_capital,
                idempotency_index=dict(idempotency_index or {}),
                updated_at=now,
            )
        )
    else:
        row.cash = cash
        row.realized_pnl = realized_pnl
        row.peak_equity = peak_equity
        row.daily_start_equity = daily_start_equity
        row.consecutive_losses = consecutive_losses
        row.fees_paid = fees_paid
        row.reserved_capital = reserved_capital
        row.idempotency_index = dict(idempotency_index or {})
        row.updated_at = now
    await session.commit()


async def load_paper_account(
    session: AsyncSession, *, account_id: str = DEFAULT_ACCOUNT_ID
) -> dict[str, Any] | None:
    row = await session.get(PaperAccountORM, account_id)
    if row is None:
        return None
    return {
        "id": row.id,
        "cash": row.cash,
        "realized_pnl": row.realized_pnl,
        "peak_equity": row.peak_equity,
        "daily_start_equity": row.daily_start_equity,
        "consecutive_losses": row.consecutive_losses,
        "fees_paid": row.fees_paid,
        "reserved_capital": row.reserved_capital,
        "idempotency_index": dict(row.idempotency_index or {}),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def save_risk_state(
    session: AsyncSession,
    *,
    account_id: str = DEFAULT_ACCOUNT_ID,
    circuit_breaker_open: bool = False,
    circuit_breaker_reason: str = "",
    seen_idempotency_keys: list[str] | None = None,
    reconciliation_healthy: bool = True,
    risk_engine_healthy: bool = True,
    database_healthy: bool = True,
    market_data_healthy: bool = True,
    peak_equity: Decimal = Decimal("0"),
    daily_start_equity: Decimal = Decimal("0"),
    consecutive_losses: int = 0,
    kill_switch_enabled: bool = False,
    halt_reason: str = "",
) -> None:
    now = utc_now()
    keys = list(seen_idempotency_keys or [])
    # Cap persisted keys to keep row size bounded.
    if len(keys) > 5000:
        keys = keys[-5000:]
    row = await session.get(RiskStateORM, account_id)
    if row is None:
        session.add(
            RiskStateORM(
                account_id=account_id,
                circuit_breaker_open=_bool_str(circuit_breaker_open),
                circuit_breaker_reason=circuit_breaker_reason or "",
                seen_idempotency_keys=keys,
                reconciliation_healthy=_bool_str(reconciliation_healthy),
                risk_engine_healthy=_bool_str(risk_engine_healthy),
                database_healthy=_bool_str(database_healthy),
                market_data_healthy=_bool_str(market_data_healthy),
                peak_equity=peak_equity,
                daily_start_equity=daily_start_equity,
                consecutive_losses=consecutive_losses,
                kill_switch_enabled=_bool_str(kill_switch_enabled),
                halt_reason=halt_reason or "",
                updated_at=now,
            )
        )
    else:
        row.circuit_breaker_open = _bool_str(circuit_breaker_open)
        row.circuit_breaker_reason = circuit_breaker_reason or ""
        row.seen_idempotency_keys = keys
        row.reconciliation_healthy = _bool_str(reconciliation_healthy)
        row.risk_engine_healthy = _bool_str(risk_engine_healthy)
        row.database_healthy = _bool_str(database_healthy)
        row.market_data_healthy = _bool_str(market_data_healthy)
        row.peak_equity = peak_equity
        row.daily_start_equity = daily_start_equity
        row.consecutive_losses = consecutive_losses
        row.kill_switch_enabled = _bool_str(kill_switch_enabled)
        row.halt_reason = halt_reason or ""
        row.updated_at = now
    await session.commit()


async def load_risk_state(
    session: AsyncSession, *, account_id: str = DEFAULT_ACCOUNT_ID
) -> dict[str, Any] | None:
    row = await session.get(RiskStateORM, account_id)
    if row is None:
        return None
    return {
        "account_id": row.account_id,
        "circuit_breaker_open": _parse_bool(row.circuit_breaker_open),
        "circuit_breaker_reason": row.circuit_breaker_reason or "",
        "seen_idempotency_keys": list(row.seen_idempotency_keys or []),
        "reconciliation_healthy": _parse_bool(row.reconciliation_healthy, True),
        "risk_engine_healthy": _parse_bool(row.risk_engine_healthy, True),
        "database_healthy": _parse_bool(row.database_healthy, True),
        "market_data_healthy": _parse_bool(row.market_data_healthy, True),
        "peak_equity": row.peak_equity,
        "daily_start_equity": row.daily_start_equity,
        "consecutive_losses": int(row.consecutive_losses or 0),
        "kill_switch_enabled": _parse_bool(row.kill_switch_enabled),
        "halt_reason": row.halt_reason or "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def save_strategy_state(
    session: AsyncSession,
    *,
    account_id: str = DEFAULT_ACCOUNT_ID,
    selected_strategy_id: str | None,
    running_strategies: list[str] | None = None,
    param_overrides: dict[str, Any] | None = None,
) -> None:
    now = utc_now()
    row = await session.get(StrategyStateORM, account_id)
    if row is None:
        session.add(
            StrategyStateORM(
                account_id=account_id,
                selected_strategy_id=selected_strategy_id,
                running_strategies=list(running_strategies or []),
                param_overrides=dict(param_overrides or {}),
                updated_at=now,
            )
        )
    else:
        row.selected_strategy_id = selected_strategy_id
        row.running_strategies = list(running_strategies or [])
        row.param_overrides = dict(param_overrides or {})
        row.updated_at = now
    await session.commit()


async def load_strategy_state(
    session: AsyncSession, *, account_id: str = DEFAULT_ACCOUNT_ID
) -> dict[str, Any] | None:
    row = await session.get(StrategyStateORM, account_id)
    if row is None:
        return None
    return {
        "account_id": row.account_id,
        "selected_strategy_id": row.selected_strategy_id,
        "running_strategies": list(row.running_strategies or []),
        "param_overrides": dict(row.param_overrides or {}),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def save_equity_snapshot(
    session: AsyncSession,
    *,
    account_id: str = DEFAULT_ACCOUNT_ID,
    equity: Decimal,
    cash: Decimal,
    drawdown: Decimal,
) -> None:
    session.add(
        EquitySnapshotORM(
            id=uuid4().hex,
            account_id=account_id,
            equity=equity,
            cash=cash,
            drawdown=drawdown,
            created_at=utc_now(),
        )
    )
    await session.commit()


async def save_strategy_run(
    session: AsyncSession,
    *,
    run_id: str,
    strategy_name: str,
    strategy_version: str,
    symbol: str,
    timeframe: str,
    candle_open_time: datetime,
    correlation_id: str,
    direction: str,
    payload: dict[str, Any] | None = None,
) -> None:
    existing = await session.get(StrategyRunORM, run_id)
    if existing is not None:
        return
    # Unique on candle identity — skip if already recorded.
    dup = (
        await session.execute(
            select(StrategyRunORM).where(
                StrategyRunORM.strategy_name == strategy_name,
                StrategyRunORM.strategy_version == strategy_version,
                StrategyRunORM.symbol == symbol,
                StrategyRunORM.timeframe == timeframe,
                StrategyRunORM.candle_open_time == ensure_utc(candle_open_time),
            )
        )
    ).scalar_one_or_none()
    if dup is not None:
        return
    session.add(
        StrategyRunORM(
            id=run_id,
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            symbol=symbol,
            timeframe=timeframe,
            candle_open_time=ensure_utc(candle_open_time),
            correlation_id=correlation_id,
            direction=direction,
            payload=payload or {},
            created_at=utc_now(),
        )
    )
    await session.commit()


async def list_equity_snapshots(
    session: AsyncSession,
    *,
    account_id: str = DEFAULT_ACCOUNT_ID,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                select(EquitySnapshotORM)
                .where(EquitySnapshotORM.account_id == account_id)
                .order_by(EquitySnapshotORM.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "account_id": r.account_id,
            "equity": str(r.equity),
            "cash": str(r.cash),
            "drawdown": str(r.drawdown),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
