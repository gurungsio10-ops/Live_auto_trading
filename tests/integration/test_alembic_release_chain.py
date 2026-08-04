"""Alembic chain: blank DB → head, downgrade 0006, re-upgrade; main→head path."""

from __future__ import annotations

import os
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.core.config import get_settings


def _run(cfg: Config, db_path: Path, revision: str) -> None:
    url = f"sqlite+aiosqlite:///{db_path}"
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, revision) if not revision.startswith("-") else None


def test_sqlite_upgrade_downgrade_upgrade(tmp_path: Path):
    db = tmp_path / "release.db"
    url = f"sqlite+aiosqlite:///{db}"
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    sync = f"sqlite:///{db}"
    eng = create_engine(sync)
    tables = set(inspect(eng).get_table_names())
    for required in {
        "paper_accounts",
        "risk_state",
        "strategy_state",
        "processed_cycle_keys",
        "equity_snapshots",
        "kill_switch_events",
        "cycle_locks",
        "orders",
        "fills",
        "system_state",
    }:
        assert required in tables, required
    command.downgrade(cfg, "0005_cycle_ops")
    tables_mid = set(inspect(eng).get_table_names())
    assert "paper_accounts" not in tables_mid
    assert "cycle_locks" in tables_mid
    command.upgrade(cfg, "head")
    with eng.connect() as conn:
        ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert ver == "0006_paper_durable"
    eng.dispose()


def test_upgrade_from_main_schema_0004(tmp_path: Path):
    """Simulate main branch head (0004) then upgrade through 0005/0006."""
    db = tmp_path / "from_main.db"
    url = f"sqlite+aiosqlite:///{db}"
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0004_paper_slice")
    sync = f"sqlite:///{db}"
    eng = create_engine(sync)
    assert "paper_accounts" not in set(inspect(eng).get_table_names())
    command.upgrade(cfg, "head")
    tables = set(inspect(eng).get_table_names())
    assert "paper_accounts" in tables
    assert "cycle_locks" in tables
    eng.dispose()
