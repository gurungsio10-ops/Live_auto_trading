"""Backend-driven decision feed — strategy outcomes with risk and execution results."""

from __future__ import annotations

from typing import Any, Literal

from app.core.time import utc_now
from app.services import paper_cycle
from app.services.paper_session import get_paper_session

DecisionOutcome = Literal["EXECUTED", "REJECTED", "SKIPPED", "FAILED", "NO_ACTION"]


def _outcome_from_cycle(cycle: Any) -> DecisionOutcome:
    if cycle.idempotent_replay:
        return "SKIPPED"
    if cycle.order_id and cycle.accepted:
        return "EXECUTED"
    if cycle.risk_decision in {"REJECTED", "HALTED"}:
        return "REJECTED"
    if cycle.reject_reason in {"NO_CANDLES"}:
        return "FAILED"
    if cycle.reject_reason:
        return "REJECTED"
    direction = (cycle.signal_direction or "").lower()
    if direction in {"hold", "neutral", ""}:
        return "NO_ACTION"
    if not cycle.accepted and not cycle.order_id:
        return "NO_ACTION"
    return "SKIPPED"


def build_decision_feed(*, limit: int = 50) -> list[dict[str, Any]]:
    """Merge cycle runs, session signals and risk events into one chronological feed."""
    session = get_paper_session()
    rows: list[dict[str, Any]] = []

    for run in paper_cycle.strategy_runs(limit=limit):
        outcome_meta = (run.metadata or {}).get("outcome", {})
        direction = run.direction.value if hasattr(run.direction, "value") else str(run.direction)
        accepted = bool(outcome_meta.get("accepted"))
        order_id = outcome_meta.get("order_id")
        risk_decision = outcome_meta.get("risk_decision")
        risk_code = outcome_meta.get("risk_reason_code")
        reject = outcome_meta.get("reject_reason")
        if order_id and accepted:
            outcome: DecisionOutcome = "EXECUTED"
        elif risk_decision in {"REJECTED", "HALTED"} or reject:
            outcome = "REJECTED"
        elif direction.lower() in {"hold"}:
            outcome = "NO_ACTION"
        else:
            outcome = "SKIPPED"
        rows.append(
            {
                "id": run.id,
                "timestamp": run.candle_open_time.isoformat()
                if run.candle_open_time
                else utc_now().isoformat(),
                "strategy": run.strategy_name,
                "strategy_version": run.strategy_version,
                "symbol": run.symbol,
                "action": direction.upper(),
                "confidence": None,  # never invent — filled below if signal has it
                "rationale": None,
                "risk_checks": {
                    "decision": risk_decision,
                    "reason_code": risk_code,
                },
                "outcome": outcome,
                "rejection_reason": reject or risk_code,
                "order_id": order_id,
                "execution_result": outcome_meta.get("order_status"),
                "correlation_id": run.correlation_id,
                "source": "strategy_run",
            }
        )

    last = paper_cycle.last_cycle_result()
    signal = paper_cycle.last_signal()
    if last is not None:
        conf = None
        rationale = last.signal_reason
        if signal is not None:
            try:
                raw = signal.confidence
                if raw is not None and str(raw) not in {"", "0", "0.0"} and float(raw) > 0:
                    conf = str(raw)
            except Exception:
                conf = None
            rationale = signal.entry_rationale or rationale
        rows.insert(
            0,
            {
                "id": f"cycle-{last.correlation_id}",
                "timestamp": utc_now().isoformat(),
                "strategy": last.strategy_name,
                "strategy_version": last.strategy_version,
                "symbol": last.symbol,
                "action": (last.signal_direction or "hold").upper(),
                "confidence": conf,
                "rationale": rationale,
                "risk_checks": {
                    "decision": last.risk_decision,
                    "reason_code": last.risk_reason_code,
                },
                "outcome": _outcome_from_cycle(last),
                "rejection_reason": last.reject_reason or last.risk_reason_code,
                "order_id": last.order_id,
                "execution_result": last.order_status,
                "correlation_id": last.correlation_id,
                "source": "last_cycle",
            },
        )

    for ev in list(getattr(session, "risk_event_log", []))[:limit]:
        decision = str(ev.get("decision") or "")
        outcome = "REJECTED" if decision in {"REJECTED", "HALTED"} else "SKIPPED"
        rows.append(
            {
                "id": f"risk-{ev.get('id')}",
                "timestamp": ev.get("timestamp") or utc_now().isoformat(),
                "strategy": ev.get("strategy_name"),
                "strategy_version": None,
                "symbol": ev.get("symbol"),
                "action": decision,
                "confidence": None,
                "rationale": ev.get("message"),
                "risk_checks": {
                    "decision": decision,
                    "reason_code": ev.get("reason_code"),
                },
                "outcome": outcome,
                "rejection_reason": ev.get("reason_code"),
                "order_id": ev.get("order_id"),
                "execution_result": None,
                "correlation_id": None,
                "source": "risk_event",
            }
        )

    # Dedupe by id, newest first
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: str(r.get("timestamp") or ""), reverse=True):
        rid = str(row.get("id"))
        if rid in seen:
            continue
        seen.add(rid)
        unique.append(row)
        if len(unique) >= limit:
            break
    return unique
