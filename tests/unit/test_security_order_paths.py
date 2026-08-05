"""Security: live gate hard-block and no ccxt live order placement in app code."""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.execution.live_gate import LiveTradingGate


def test_live_trading_gate_never_allows():
    settings = Settings(
        trading_mode="live",
        live_trading_enabled=True,
        kill_switch_enabled=False,
        _env_file=None,
    )
    gate = LiveTradingGate(settings)
    result = gate.evaluate()
    assert result.allowed is False


def test_no_ccxt_create_order_calls_outside_exchange_adapter():
    """Scan app/ for prohibited live placement call sites."""
    banned_call_fragments = (
        ".create_order(",
        ".createOrder(",
        ".create_market_order(",
        ".createMarketOrder(",
        ".create_limit_order(",
    )
    offenders: list[str] = []
    for path in Path("app").rglob("*.py"):
        if "pycache" in str(path):
            continue
        # Disabled/testnet adapters may mention method names; they must still
        # raise LiveTradingDisabledError before any network order call.
        if "execution/exchange" in str(path):
            continue
        text = path.read_text(encoding="utf-8")
        for frag in banned_call_fragments:
            if frag in text:
                offenders.append(f"{path}:{frag}")
    assert offenders == [], f"prohibited order placement fragments: {offenders}"


def test_default_leverage_is_one():
    settings = Settings(_env_file=None)
    assert settings.default_leverage == settings.default_leverage.__class__("1") or str(
        settings.default_leverage
    ) in {"1", "1.0"}
    from decimal import Decimal

    assert Decimal(str(settings.default_leverage)) == Decimal("1")
