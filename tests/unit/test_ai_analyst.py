"""Phase 12: advisory AI layer — no order submission paths."""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi.testclient import TestClient

from app.ai import ADVISORY_LABEL, TradingAnalyst
from app.main import app


def test_advisory_label_in_payload():
    analyst = TradingAnalyst()
    resp = analyst.explain_trade(
        {"entry_rationale": "ema cross", "risk_decision": "APPROVED"}
    )
    payload = resp.to_api_dict()
    assert payload["label"] == ADVISORY_LABEL
    assert payload["advisory"] is True
    assert "Advisory" in payload["content"] or "advisory" in payload["content"]
    assert "order_submission" in payload["metadata"]["forbidden_actions"]
    assert "live_config_change" in payload["metadata"]["forbidden_actions"]


def test_all_methods_labeled():
    analyst = TradingAnalyst()
    responses = [
        analyst.summarize_session([{"decision": "REJECTED"}, {"decision": "APPROVED"}]),
        analyst.analyze_strategy(
            {
                "strategy_id": "ema_trend",
                "trade_count": 3,
                "win_rate": "0.5",
                "max_drawdown": "0.1",
            }
        ),
        analyst.suggest_experiment({"params": {"fast_ema": 12}}),
    ]
    for r in responses:
        assert r.label == ADVISORY_LABEL
        assert r.to_api_dict()["advisory"] is True
        assert r.to_api_dict()["metadata"]["forbidden_actions"] == list(
            TradingAnalyst.FORBIDDEN_ACTIONS
        )


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
    assert "OrderGateway" not in src
    assert "RiskEngine" not in src


def test_ai_package_has_no_execution_imports():
    root = Path("app/ai")
    for path in root.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert "from app.execution" not in src
        assert "import app.execution" not in src
        assert "OrderGateway" not in src
        assert "PaperTradingEngine" not in src
        assert "create_order" not in src


def test_api_ai_endpoints_mark_advisory():
    client = TestClient(app)
    explain = client.post(
        "/api/ai/explain-trade",
        json={"entry_rationale": "test", "risk_decision": "REJECTED"},
    )
    assert explain.status_code == 200
    body = explain.json()
    assert body["advisory"] is True
    assert body["label"] == ADVISORY_LABEL
    assert body["kind"] == "explain_trade"

    summary = client.post(
        "/api/ai/summarize-session",
        json=[{"decision": "APPROVED"}, {"decision": "REJECTED"}],
    )
    assert summary.status_code == 200
    sbody = summary.json()
    assert sbody["advisory"] is True
    assert sbody["label"] == ADVISORY_LABEL
    assert "No orders are placed" in sbody["content"]


def test_ai_routes_do_not_call_order_gateway():
    src = Path("app/api/routes.py").read_text(encoding="utf-8")
    # AI handlers must only return analyst dicts — no gateway/paper submission.
    assert (
        '@router.post("/ai/explain-trade")' in src
        or '@router.post("/ai/explain-trade")' in src
    )
    assert "OrderGateway" not in src
    assert "PaperTradingEngine" not in src
    assert "_analyst.explain_trade" in src
    assert "_analyst.summarize_session" in src
