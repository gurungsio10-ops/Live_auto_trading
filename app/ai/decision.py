"""
Advisory AI decision engine — scores opportunities; never submits orders.

Deterministic for identical inputs. Fully logged via return payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.ai.analyst import ADVISORY_LABEL
from app.core.time import utc_now
from app.models.domain.enums import SignalDirection
from app.models.domain.trading import TradeSignal


@dataclass(frozen=True)
class AdvisoryDecision:
    direction: str
    score: Decimal
    confidence: Decimal
    risk_reward: Decimal
    recommended_stop: Decimal | None
    recommended_target: Decimal | None
    recommended_size_fraction: Decimal
    explanation: str
    reject_reason: str | None
    inputs_used: list[str]
    advisory: bool = True
    label: str = ADVISORY_LABEL
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "advisory": True,
            "direction": self.direction,
            "score": str(self.score),
            "confidence": str(self.confidence),
            "risk_reward": str(self.risk_reward),
            "recommended_stop": str(self.recommended_stop)
            if self.recommended_stop is not None
            else None,
            "recommended_target": str(self.recommended_target)
            if self.recommended_target is not None
            else None,
            "recommended_size_fraction": str(self.recommended_size_fraction),
            "explanation": self.explanation,
            "reject_reason": self.reject_reason,
            "inputs_used": self.inputs_used,
            "timestamp": self.timestamp or utc_now().isoformat(),
            "forbidden": list(AdvisoryDecisionEngine.FORBIDDEN_ACTIONS),
        }


class AdvisoryDecisionEngine:
    """
    Scores strategy signals using deterministic heuristics.

    Structurally cannot submit orders (no execution imports).
    """

    FORBIDDEN_ACTIONS = (
        "order_submission",
        "risk_engine_bypass",
        "leverage_change",
        "live_config_change",
    )
    MIN_SCORE = Decimal("0.55")

    def evaluate(
        self,
        signal: TradeSignal,
        *,
        volatility: Decimal | None = None,
        funding_rate: Decimal | None = None,
        open_interest: Decimal | None = None,
        trend_strength: Decimal | None = None,
    ) -> AdvisoryDecision:
        inputs = ["signal", "indicators"]
        indicators = dict(signal.metadata.get("indicators") or {})
        conf = Decimal(str(signal.confidence))
        score = conf

        # Multi-factor adjustments (deterministic, bounded).
        if trend_strength is not None:
            inputs.append("trend_strength")
            score += (trend_strength - Decimal("0.5")) * Decimal("0.2")
        if volatility is not None:
            inputs.append("volatility")
            # Prefer moderate vol; penalize extremes.
            if volatility > Decimal("0.05"):
                score -= Decimal("0.1")
            elif volatility < Decimal("0.005"):
                score -= Decimal("0.05")
        if funding_rate is not None:
            inputs.append("funding_rate_advisory")
            # Crowded long funding slightly reduces long score.
            if signal.direction == SignalDirection.BUY and funding_rate > Decimal(
                "0.0005"
            ):
                score -= Decimal("0.05")
        if open_interest is not None:
            inputs.append("open_interest_advisory")

        score = max(Decimal("0"), min(Decimal("1"), score))
        stop = signal.suggested_stop
        target = signal.suggested_target
        entry = signal.suggested_entry or Decimal(str(indicators.get("close") or "0"))
        rr = Decimal("0")
        if stop and target and entry and entry > 0:
            risk = abs(entry - stop)
            reward = abs(target - entry)
            if risk > 0:
                rr = (reward / risk).quantize(Decimal("0.01"))

        reject = None
        direction = signal.direction.value
        if signal.direction == SignalDirection.HOLD:
            reject = "HOLD_SIGNAL"
            size = Decimal("0")
        elif score < self.MIN_SCORE:
            reject = "LOW_QUALITY_SETUP"
            direction = SignalDirection.HOLD.value
            size = Decimal("0")
        else:
            # Size scales with score; capped — risk engine still final authority.
            size = (Decimal("0.05") + score * Decimal("0.15")).quantize(
                Decimal("0.0001")
            )

        explanation = (
            f"Advisory score={score} confidence={conf} rr={rr}. "
            f"Signal={signal.direction.value} rationale='{signal.entry_rationale}'. "
            f"This module never submits orders."
        )
        return AdvisoryDecision(
            direction=direction,
            score=score,
            confidence=conf,
            risk_reward=rr,
            recommended_stop=stop,
            recommended_target=target,
            recommended_size_fraction=size,
            explanation=explanation,
            reject_reason=reject,
            inputs_used=inputs,
            timestamp=utc_now().isoformat(),
        )
