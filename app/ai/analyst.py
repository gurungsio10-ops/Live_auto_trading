"""Advisory-only AI analysis layer. Never submits orders or changes risk config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ADVISORY_LABEL = "Advisory — not an executed action"


@dataclass(frozen=True)
class AdvisoryResponse:
    label: str
    kind: str
    content: str
    inputs_used: list[str]
    metadata: dict[str, Any]

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "advisory": True,
            "kind": self.kind,
            "content": self.content,
            "inputs_used": self.inputs_used,
            "metadata": self.metadata,
        }


class TradingAnalyst:
    """
    Read-only analyst. Structurally cannot call order submission:
    - no imports from the execution package or risk bypass helpers
    - outputs always carry the advisory label in the payload
    """

    FORBIDDEN_ACTIONS = (
        "order_submission",
        "risk_engine_bypass",
        "leverage_change",
        "stop_loss_removal",
        "live_config_change",
    )

    def explain_trade(self, journal_record: dict[str, Any]) -> AdvisoryResponse:
        rationale = (
            journal_record.get("entry_rationale")
            or journal_record.get("reason")
            or "n/a"
        )
        decision = (
            journal_record.get("risk_decision")
            or journal_record.get("decision")
            or "n/a"
        )
        content = (
            f"Trade explanation (advisory): strategy proposed action with rationale "
            f"'{rationale}'. Risk decision was '{decision}'. "
            f"This is analysis of historical journal data only."
        )
        return self._wrap("explain_trade", content, ["journal_record"])

    def summarize_session(self, events: list[dict[str, Any]]) -> AdvisoryResponse:
        approvals = sum(1 for e in events if e.get("decision") == "APPROVED")
        rejections = sum(1 for e in events if e.get("decision") == "REJECTED")
        content = (
            f"Session summary (advisory): {len(events)} events, "
            f"{approvals} approvals, {rejections} rejections. "
            f"No orders are placed by this summary."
        )
        return self._wrap("summarize_session", content, ["events"])

    def analyze_strategy(self, strategy_stats: dict[str, Any]) -> AdvisoryResponse:
        content = (
            f"Strategy analysis (advisory) for '{strategy_stats.get('strategy_id', 'unknown')}': "
            f"trade_count={strategy_stats.get('trade_count')}, "
            f"win_rate={strategy_stats.get('win_rate')}, "
            f"max_drawdown={strategy_stats.get('max_drawdown')}. "
            f"Recommendations are hypotheses only."
        )
        return self._wrap("analyze_strategy", content, ["strategy_stats"])

    def suggest_experiment(self, context: dict[str, Any]) -> AdvisoryResponse:
        content = (
            "Experiment suggestion (advisory): consider a paper-only A/B on EMA fast/slow "
            f"periods around current params {context.get('params', {})}. "
            "Do not enable live trading from this suggestion."
        )
        return self._wrap("suggest_experiment", content, ["context"])

    def _wrap(self, kind: str, content: str, inputs: list[str]) -> AdvisoryResponse:
        return AdvisoryResponse(
            label=ADVISORY_LABEL,
            kind=kind,
            content=content,
            inputs_used=inputs,
            metadata={"forbidden_actions": list(self.FORBIDDEN_ACTIONS)},
        )
