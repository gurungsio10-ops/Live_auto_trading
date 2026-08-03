"""Phase 12: advisory AI layer — no order submission paths."""

from __future__ import annotations

import ast
from pathlib import Path

from app.ai import ADVISORY_LABEL, TradingAnalyst


def test_advisory_label_in_payload():
    analyst = TradingAnalyst()
    resp = analyst.explain_trade({"entry_rationale": "ema cross", "risk_decision": "APPROVED"})
    payload = resp.to_api_dict()
    assert payload["label"] == ADVISORY_LABEL
    assert payload["advisory"] is True
    assert "Advisory" in payload["content"] or "advisory" in payload["content"]


def test_all_methods_labeled():
    analyst = TradingAnalyst()
    responses = [
        analyst.summarize_session([{"decision": "REJECTED"}, {"decision": "APPROVED"}]),
        analyst.analyze_strategy({"strategy_id": "ema_trend", "trade_count": 3, "win_rate": "0.5", "max_drawdown": "0.1"}),
        analyst.suggest_experiment({"params": {"fast_ema": 12}}),
    ]
    for r in responses:
        assert r.label == ADVISORY_LABEL
        assert r.to_api_dict()["advisory"] is True


def test_analyst_module_has_no_order_imports():
    src = Path("app/ai/analyst.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    joined = " ".join(imports)
    assert "execution" not in joined
    assert "app.execution" not in src
    assert "create_order" not in src
