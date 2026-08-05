"""Atlas Brain — evidence-based decision summary (never invents confidence)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.time import utc_now
from app.services import paper_cycle
from app.services.paper_session import get_paper_session
from app.services.system_status import build_unified_system_status


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _regime_from_indicators(indicators: dict[str, Any]) -> dict[str, str]:
    """Derive coarse regime labels only from present indicator values."""
    fast = _as_decimal(indicators.get("ema_fast") or indicators.get("ema_9"))
    slow = _as_decimal(indicators.get("ema_slow") or indicators.get("ema_21"))
    close = _as_decimal(indicators.get("close") or indicators.get("last_close"))
    atr = _as_decimal(indicators.get("atr") or indicators.get("atr_14"))
    rsi = _as_decimal(indicators.get("rsi") or indicators.get("rsi_14"))

    trend = "unknown"
    if fast is not None and slow is not None:
        if fast > slow:
            trend = "uptrend"
        elif fast < slow:
            trend = "downtrend"
        else:
            trend = "neutral"
    if close is not None and fast is not None and slow is not None:
        if close > fast > slow:
            trend = "uptrend"
        elif close < fast < slow:
            trend = "downtrend"

    volatility = "unknown"
    if atr is not None and close is not None and close > 0:
        ratio = atr / close
        if ratio >= Decimal("0.03"):
            volatility = "elevated"
        elif ratio >= Decimal("0.015"):
            volatility = "moderate"
        else:
            volatility = "low"

    momentum = "unknown"
    if rsi is not None:
        if rsi >= 60:
            momentum = "positive"
        elif rsi <= 40:
            momentum = "negative"
        else:
            momentum = "neutral"

    if trend == "uptrend":
        regime = "trend_following_bullish"
    elif trend == "downtrend":
        regime = "trend_following_bearish"
    else:
        regime = "range_or_unclear"

    return {
        "market_regime": regime,
        "volatility_state": volatility,
        "trend_state": trend,
        "momentum_state": momentum,
    }


def _explanation(regime: dict[str, str], indicators: dict[str, Any], risk_note: str) -> str:
    parts: list[str] = []
    trend = regime.get("trend_state")
    vol = regime.get("volatility_state")
    fast = indicators.get("ema_fast") or indicators.get("ema_9")
    slow = indicators.get("ema_slow") or indicators.get("ema_21")
    symbol = indicators.get("symbol") or "BTC/USDT"
    if trend == "uptrend" and fast is not None and slow is not None:
        parts.append(
            f"{symbol} remains above the fast and slow EMA (fast={fast}, slow={slow})."
        )
    elif trend == "downtrend" and fast is not None and slow is not None:
        parts.append(
            f"{symbol} remains below the fast and slow EMA (fast={fast}, slow={slow})."
        )
    elif trend != "unknown":
        parts.append(f"Trend state is {trend}.")
    else:
        parts.append("Insufficient indicator evidence to classify trend.")

    if vol == "elevated":
        parts.append("Volatility is elevated.")
    elif vol == "moderate":
        parts.append("Volatility is moderate.")
    elif vol == "low":
        parts.append("Volatility is low.")

    if risk_note:
        parts.append(risk_note)
    return " ".join(parts)


async def build_atlas_brain() -> dict[str, Any]:
    status = await build_unified_system_status()
    session = get_paper_session()
    last = paper_cycle.last_cycle_result()
    signal = paper_cycle.last_signal()
    indicators: dict[str, Any] = {}
    confidence: str | None = None
    confidence_source = "unavailable"
    latest_summary = "No strategy decision yet — run a paper cycle or enable the scheduler."
    ruleset_version = "ema_crossover@unknown"
    symbol = "BTC/USDT"

    if last is not None:
        indicators = dict(last.indicators or {})
        symbol = last.symbol
        ruleset_version = f"{last.strategy_name}@{last.strategy_version}"
        latest_summary = (
            f"{last.signal_direction.upper()} {last.symbol}: {last.signal_reason}"
        )
        if last.risk_decision:
            latest_summary += f" · risk {last.risk_decision}"
            if last.risk_reason_code:
                latest_summary += f" ({last.risk_reason_code})"

    if signal is not None:
        indicators = {**indicators, **dict(signal.metadata.get("indicators") or {})}
        indicators.setdefault("symbol", signal.symbol)
        try:
            raw = signal.confidence
            if raw is not None and str(raw) not in {"", "0", "0.0"} and float(raw) > 0:
                confidence = str(raw)
                confidence_source = "strategy_output"
        except Exception:
            confidence = None
            confidence_source = "unavailable"
        if signal.strategy_version:
            ruleset_version = f"{signal.strategy_name}@{signal.strategy_version}"

    regime = _regime_from_indicators(indicators)
    portfolio = session.portfolio_summary()
    risk_note = "New entries remain subject to Atlas risk controls."
    try:
        from app.core.config import get_settings

        settings = get_settings()
        rpt = getattr(settings, "risk_per_trade_percent", None)
        if rpt is not None:
            risk_note = f"New entries are limited to {rpt}% portfolio risk per trade."
    except Exception:
        pass

    if portfolio.get("kill_switch_enabled") or status.get("kill_switch", {}).get("enabled"):
        risk_recommendation = "BLOCK — kill switch is ON"
    elif portfolio.get("trading_paused"):
        risk_recommendation = "PAUSE — new orders are paused"
    elif status.get("status") == "DEGRADED":
        risk_recommendation = "CAUTION — system degraded; resolve reasons before scaling risk"
    else:
        risk_recommendation = "ALLOW — paper entries permitted subject to risk engine"

    strategies = []
    try:
        strategies = session.strategies() if hasattr(session, "strategies") else []
    except Exception:
        strategies = []
    enabled = [
        {
            "id": s.get("strategy_id") or s.get("id"),
            "name": s.get("name"),
            "running": bool(s.get("running")),
            "selected": bool(s.get("selected")),
        }
        for s in strategies
        if s.get("running") or s.get("selected") or True
    ]

    data_freshness = "simulated_fixtures"
    md = status.get("market_data") or {}
    if md.get("mode") == "public_live_market_data":
        data_freshness = "public_live"
    elif md.get("stale"):
        data_freshness = "stale"

    return {
        "title": "Atlas Brain",
        "generated_at": utc_now().isoformat(),
        "market_regime": regime["market_regime"],
        "volatility_state": regime["volatility_state"],
        "trend_state": regime["trend_state"],
        "momentum_state": regime.get("momentum_state"),
        "enabled_strategies": enabled,
        "strongest_observed_market": symbol if regime["trend_state"] == "uptrend" else None,
        "weakest_observed_market": symbol if regime["trend_state"] == "downtrend" else None,
        "current_risk_recommendation": risk_recommendation,
        "latest_decision_summary": latest_summary,
        "confidence": confidence,
        "confidence_source": confidence_source,
        "data_freshness": data_freshness,
        "ruleset_version": ruleset_version,
        "indicators_used": indicators,
        "explanation": _explanation(regime, {**indicators, "symbol": symbol}, risk_note),
        "system_status": status.get("status"),
        "degraded_reasons": status.get("degraded_reasons") or [],
    }
