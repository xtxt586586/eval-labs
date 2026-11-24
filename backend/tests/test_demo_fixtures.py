import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from app.core.evaluation_engine import build_metric


ROOT = Path(__file__).resolve().parents[2]


def test_five_agent_demo_cases_import_and_score_deterministically(client):
    records = json.loads((ROOT / "demo/data/agent_trajectories.json").read_text(encoding="utf-8"))
    scenario = json.loads((ROOT / "demo/data/scenario.json").read_text(encoding="utf-8"))
    metrics_config = json.loads((ROOT / "demo/data/metrics.json").read_text(encoding="utf-8"))
    assert {item["case_id"] for item in records} == {
        "success", "wrong_tool", "wrong_arguments", "state_not_reached", "safety_violation"
    }

    created = client.post("/api/datasets", json={
        "name": "five-agent-demo-test",
        "description": "Deterministic fixture import test",
        "sample_type": "multi_turn",
        "field_schema": [],
    })
    assert created.status_code == 201
    imported = client.post(
        f"/api/datasets/{created.json()['id']}/import",
        files={"file": ("agent_trajectories.json", json.dumps(records).encode(), "application/json")},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["imported_count"] == 5

    saved = client.get(f"/api/datasets/{created.json()['id']}/rows", params={"page_size": 100})
    assert saved.status_code == 200
    rows = {item["data"]["case_id"]: item["data"] for item in saved.json()["items"]}
    assert len(rows) == 5

    metrics = {item["name"]: item for item in metrics_config["metrics"]}
    expected = {
        "success": {"tool_call_accuracy": 1.0, "argument_correctness": 1.0, "state_change_accuracy": 1.0, "safety_policy": 1.0},
        "wrong_tool": {"tool_call_accuracy": 0.0, "argument_correctness": 0.0, "state_change_accuracy": 0.0, "safety_policy": 1.0},
        "wrong_arguments": {"tool_call_accuracy": 0.0, "argument_correctness": 0.0, "state_change_accuracy": 0.0, "safety_policy": 1.0},
        "state_not_reached": {"tool_call_accuracy": 1.0, "argument_correctness": 1.0, "state_change_accuracy": 0.0, "safety_policy": 1.0},
        "safety_violation": {"tool_call_accuracy": 1.0, "argument_correctness": 1.0, "state_change_accuracy": 1.0, "safety_policy": 0.0},
    }
    for case_id, metric_scores in expected.items():
        for metric_name, score in metric_scores.items():
            definition = metrics[metric_name]
            kind, metric = build_metric(SimpleNamespace(
                name=metric_name,
                metric_type=definition["metric_type"],
                config={},
            ), llm=None)
            assert kind == "simple"
            result = asyncio.run(metric.ascore(rows[case_id], None))
            assert result.value == score, (case_id, metric_name, result)
