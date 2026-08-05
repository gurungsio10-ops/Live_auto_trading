"""Release invariant coverage: hydrate fallbacks, durable persist, journal bounds."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.database.market  # noqa: F401 — register market ORM tables
from app.core.config import get_settings
from app.core.time import utc_now
from app.db.base import Base
from app.journal.store import JournalStore, SignalORM
from app.models.database.portfolio import PositionORM
from app.models.domain.enums import OrderStatus, RiskDecision, SignalDirection
from app.models.domain.trading import TradeSignal
from app.services import paper_persistence as store
from app.services.paper_session import (
    get_paper_session,
    hydrate_paper_session_from_db,
    reset_paper_session,
)
from app.services.reconciliation import clear_reconciliation_halt


@pytest.fixture(autouse=True)
def _iso(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("ENABLE_RECONCILIATION", "false")
    monkeypatch.setenv("ENABLE_TRADING_SCHEDULER", "false")
    get_settings.cache_clear()
    clear_reconciliation_halt()
    reset_paper_session()
    yield
    reset_paper_session()
    clear_reconciliation_halt()
    get_settings.cache_clear()


async def _file_db(tmp_path: Path, name: str):
    db_path = tmp_path / name
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine, factory, url


@pytest.mark.asyncio
async def test_hydrate_from_paper_account_and_positions_table(tmp_path: Path):
    engine, factory, _ = await _file_db(tmp_path, "hydrate-account.db")

    async with factory() as db:
        await store.save_paper_account(
            db,
            cash=Decimal("8800"),
            reserved_capital=Decimal("0"),
            realized_pnl=Decimal("12.5"),
            peak_equity=Decimal("10000"),
            daily_start_equity=Decimal("10000"),
            consecutive_losses=1,
            fees_paid=Decimal("1"),
            idempotency_index={"k1": "o1"},
            commit=False,
        )
        db.add(
            PositionORM(
                id="pos1",
                symbol="BTC/USDT",
                quantity=Decimal("0.01"),
                entry_price=Decimal("50000"),
                current_price=Decimal("51000"),
                unrealized_pnl=Decimal("10"),
                realized_pnl=Decimal("0"),
                opened_at=utc_now(),
                strategy_name="manual",
                updated_at=utc_now(),
            )
        )
        await db.commit()

    reset_paper_session()
    async with factory() as db:
        await hydrate_paper_session_from_db(db)

    paper = get_paper_session()
    assert paper.paper.state.cash == Decimal("8800")
    assert paper.paper.state.realized_pnl == Decimal("12.5")
    assert "BTC/USDT" in paper.paper.state.positions
    assert paper.paper.state.positions["BTC/USDT"].quantity == Decimal("0.01")
    assert paper._consecutive_losses == 1
    assert paper.paper.state.idempotency_index.get("k1") == "o1"
    await engine.dispose()


@pytest.mark.asyncio
async def test_hydrate_legacy_system_state_fallback(tmp_path: Path):
    engine, factory, _ = await _file_db(tmp_path, "hydrate-legacy.db")

    async with factory() as db:
        await store.set_system_value(
            db,
            "paper_account",
            {"cash": "7654.32", "realized_pnl": "3.21"},
            commit=False,
        )
        await store.set_system_value(
            db,
            "paper_session_flags",
            {
                "peak_equity": "10000",
                "daily_start_equity": "9000",
                "consecutive_losses": 2,
                "selected_strategy_id": "ema_crossover",
            },
            commit=True,
        )

    reset_paper_session()
    async with factory() as db:
        await hydrate_paper_session_from_db(db)

    paper = get_paper_session()
    assert paper.paper.state.cash == Decimal("7654.32")
    assert paper.paper.state.realized_pnl == Decimal("3.21")
    assert paper._peak_equity == Decimal("10000")
    assert paper._daily_start_equity == Decimal("9000")
    assert paper._consecutive_losses == 2
    assert paper.selected_strategy_id == "ema_crossover"
    await engine.dispose()


@pytest.mark.asyncio
async def test_place_order_persists_checkpoint(tmp_path: Path, monkeypatch):
    engine, _factory, url = await _file_db(tmp_path, "place-persist.db")
    await engine.dispose()

    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()

    session = reset_paper_session()
    session.risk_engine.state.last_market_data_ts = datetime.now(UTC)
    session.risk_engine.state.market_data_healthy = True
    session.risk_engine.state.database_healthy = True

    order = await session.place_order(
        {
            "symbol": "BTC/USDT",
            "side": "buy",
            "order_type": "market",
            "quantity": "0.01",
        }
    )
    assert order["status"] in (
        OrderStatus.FILLED.value,
        OrderStatus.REJECTED.value,
        OrderStatus.APPROVED.value,
        OrderStatus.PARTIALLY_FILLED.value,
    )
    if order["status"] == OrderStatus.FILLED.value:
        engine2 = create_async_engine(url)
        factory2 = async_sessionmaker(
            engine2, expire_on_commit=False, class_=AsyncSession
        )
        async with factory2() as db:
            ckpt = await store.load_paper_checkpoint(db)
            acct = await store.load_paper_account(db)
        await engine2.dispose()
        assert ckpt is not None or acct is not None
        assert session.risk_engine.state.database_healthy is True


@pytest.mark.asyncio
async def test_journal_fingerprint_truncated_to_256(tmp_path: Path):
    engine, factory, _ = await _file_db(tmp_path, "journal.db")

    long_fp = "x" * 500
    signal = TradeSignal(
        strategy_name="ema_crossover",
        strategy_version="1.0.0",
        symbol="BTC/USDT",
        direction=SignalDirection.BUY,
        confidence=Decimal("0.5"),
        entry_rationale="test",
        invalidation_condition="test",
        input_data_fingerprint=long_fp,
    )
    async with factory() as db:
        store_j = JournalStore(db)
        sid = await store_j.record_signal(signal)
        orm = (
            await db.execute(select(SignalORM).where(SignalORM.id == sid))
        ).scalar_one()
        assert len(orm.input_data_fingerprint) == 256
        assert orm.input_data_fingerprint == long_fp[:256]
        await db.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_kill_switch_blocks_orders_but_portfolio_readable():
    session = reset_paper_session()
    session.set_kill_switch(True)
    summary = session.portfolio_summary()
    assert summary["kill_switch_enabled"] is True
    assert "cash_balance" in summary
    assert "equity" in summary

    order = await session.place_order(
        {
            "symbol": "BTC/USDT",
            "side": "buy",
            "order_type": "market",
            "quantity": "0.01",
        }
    )
    assert order["status"] == OrderStatus.REJECTED.value
    assert order["risk_decision"] == RiskDecision.HALTED.value
    assert session.portfolio_summary()["open_position_count"] == 0


def test_frontend_client_bundle_has_no_admin_or_exchange_secrets():
    """Static guard: browser-facing sources must not embed server secrets."""
    root = Path(__file__).resolve().parents[2] / "frontend"
    forbidden = (
        "ADMIN_API_TOKEN",
        "EXCHANGE_API_KEY",
        "EXCHANGE_API_SECRET",
        "LIVE_APPROVAL_TOKEN",
    )
    client_globs = [
        *root.glob("app/**/*.tsx"),
        *root.glob("components/**/*.tsx"),
        *root.glob("lib/*.ts"),
    ]
    # Server-only modules may reference ADMIN_API_TOKEN.
    server_ok = {
        root / "lib" / "backend.ts",
        root / "lib" / "auth.ts",
        root / "lib" / "runtime.ts",
    }
    offenders: list[str] = []
    for path in client_globs:
        if path in server_ok or "/api/" in str(path):
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text and "never exposed" not in text.lower():
                if f"Requires server-side {token}" in text:
                    continue
                offenders.append(f"{path.relative_to(root)}:{token}")
    assert not offenders, offenders


def test_trading_mode_defaults_to_paper():
    get_settings.cache_clear()
    settings = get_settings()
    assert str(settings.trading_mode).lower() == "paper"
    assert settings.live_trading_enabled is False
