"""
Unified runtime mode: BACKTEST | PAPER | TESTNET | LIVE.

Resolution rules (fail-safe):
1. Prefer ``ATLAS_RUNTIME_MODE`` / ``RUNTIME_MODE`` when set.
2. Else derive from ``TRADING_MODE`` x ``EXCHANGE_ENV``.
3. Invalid / missing values never resolve to LIVE - fall back to PAPER.
4. LIVE still requires ENABLE_LIVE_TRADING + acknowledgement and remains
   hard-blocked by ``assert_startup_safe`` in this development phase.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

RuntimeModeName = Literal["BACKTEST", "PAPER", "TESTNET", "LIVE"]


class RuntimeMode(str, Enum):
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    TESTNET = "TESTNET"
    LIVE = "LIVE"


_VALID = {m.value for m in RuntimeMode}


def normalize_runtime_mode(raw: str | None) -> RuntimeMode:
    """Parse a mode string. Invalid → PAPER (never LIVE)."""
    if raw is None or not str(raw).strip():
        return RuntimeMode.PAPER
    value = str(raw).strip().upper()
    if value not in _VALID:
        return RuntimeMode.PAPER
    return RuntimeMode(value)


def derive_runtime_mode(
    *,
    explicit: str | None,
    trading_mode: str,
    exchange_env: str,
) -> RuntimeMode:
    """
    Resolve effective runtime mode.

    Explicit ATLAS_RUNTIME_MODE wins when valid. Otherwise:
    - trading_mode=live → LIVE (still hard-blocked at startup)
    - exchange_env=testnet → TESTNET
    - exchange_env=paper + trading_mode=paper → PAPER
    - anything else → PAPER
    """
    if explicit is not None and str(explicit).strip():
        return normalize_runtime_mode(explicit)

    tm = (trading_mode or "paper").lower().strip()
    ee = (exchange_env or "paper").lower().strip()
    if tm == "live":
        return RuntimeMode.LIVE
    if ee == "testnet":
        return RuntimeMode.TESTNET
    if ee == "backtest" or tm == "backtest":
        return RuntimeMode.BACKTEST
    return RuntimeMode.PAPER


def allows_simulated_orders(mode: RuntimeMode) -> bool:
    return mode in {RuntimeMode.BACKTEST, RuntimeMode.PAPER, RuntimeMode.TESTNET}


def allows_live_orders(mode: RuntimeMode) -> bool:
    return mode == RuntimeMode.LIVE
