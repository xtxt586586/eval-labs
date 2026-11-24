from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DEMO_DATA = ROOT / "demo" / "data"
DEMO_RUNS = ROOT / "demo" / "runs"
DEMO_STATE = ROOT / "demo" / "state"
DEMO_RUNS.mkdir(parents=True, exist_ok=True)
DEMO_STATE.mkdir(parents=True, exist_ok=True)

# Override local dotenv and shell settings so this script always uses an isolated,
# credential-free database and never routes deterministic metrics to an LLM.
os.environ["DATABASE_URL"] = f"sqlite:///{(DEMO_STATE / 'eval_demo.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(DEMO_STATE / "uploads")
os.environ["SEED_ON_STARTUP"] = "true"
os.environ["RUN_EVAL_ON_CREATE"] = "true"
os.environ["EVAL_QUEUE_WORKERS"] = "1"
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_ENDPOINT"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
os.environ["LLM_MODEL"] = "qwen-plus"
sys.path.insert(0, str(BACKEND))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def require(response, expected: int = 200):
    if response.status_code != expected:
        raise RuntimeError(f"API {response.request.method} {response.request.url} returned {response.status_code}: {response.text}")
    return response.json()


def find_or_create_metrics(client, scenario_config: dict) -> dict[str, int]:
    existing = {item["name"]: item for item in require(client.get("/api/metrics"))}
    result = {}
    for definition in scenario_config["metrics"]:
        metric = existing.get(definition["name"])
        if metric is None:
            metric = require(client.post("/api/metrics", json={
                **definition,
                "config": {"description": f"Deterministic demo metric: {definition['display_name']}"},
                "category": "agent",
            }), 201)
        if metric["metric_type"] != definition["metric_type"]:
            raise RuntimeError(f"Metric {definition['name']} exists with unexpected type {metric['metric_type']}")
        result[definition["name"]] = metric["id"]
    return result


def ensure_demo_dataset(client, records: list[dict]) -> tuple[int, dict]:
    name = "Eval Labs Five Agent Cases"
    datasets = require(client.get("/api/datasets"))
    dataset = next((item for item in datasets if item["name"] == name), None)
    if dataset is None:
        schema = [
            {"name": "case_id", "type": "text", "required": True},
            {"name": "case_name", "type": "text", "required": True},
            {"name": "user_input", "type": "conversation", "required": True},
            {"name": "reference_tool_calls", "type": "tool_call_list"},
            {"name": "tool_results", "type": "json"},
            {"name": "reference_tool_results", "type": "json"},
            {"name": "actual_state", "type": "json"},
            {"name": "expected_state", "type": "json"},
            {"name": "safety_policy", "type": "json"},
        ]
        dataset = require(client.post("/api/datasets", json={
            "name": name,
            "description": "固定的五类 Agent 工具轨迹。仅含确定性指标。",
            "sample_type": "multi_turn",
            "field_schema": schema,
        }), 201)
        imported = require(client.post(
            f"/api/datasets/{dataset['id']}/import",
            files={"file": ("agent_trajectories.json", json.dumps(records, ensure_ascii=False).encode("utf-8"), "application/json")},
        ))
        if imported["imported_count"] != 5:
            raise RuntimeError(f"Expected to import 5 cases; API imported {imported['imported_count']}")
    else:
        rows = require(client.get(f"/api/datasets/{dataset['id']}/rows", params={"page_size": 100}))
        if rows["total"] != 5:
            raise RuntimeError(f"Existing demo dataset must have 5 rows; found {rows['total']}")
    return dataset["id"], dataset


def ensure_demo_scenario(client, config: dict, metric_ids: dict[str, int]) -> int:
    existing = require(client.get("/api/scenarios"))
    scenario = next((item for item in existing if item["name"] == config["name"]), None)
    if scenario is not None:
        return scenario["id"]
    scenario = require(client.post("/api/scenarios", json={
        "name": config["name"],
        "description": config["description"],
        "scene_type": config["scene_type"],
        "sample_type": config["sample_type"],
        "metrics": [
            {"metric_definition_id": metric_ids[item["name"]], "weight": 1.0, "pass_threshold": config["metric_threshold"]}
            for item in config["metrics"]
        ],
    }), 201)
    return scenario["id"]


def maybe_run_real_calibration(client, config: dict, llm_config_id: int, metric_ids: dict[str, int]) -> dict:
    samples_path = DEMO_DATA / "calibration_samples.json"
    fixture = json.loads(samples_path.read_text(encoding="utf-8"))
    if os.environ.get("RUN_REAL_JUDGE_CALIBRATION") != "1":
        return {
            "status": "not_run",
            "reason": "Calibration is an external paid LLM call and requires RUN_REAL_JUDGE_CALIBRATION=1 plus a real provider key.",
            "judge_model": config["model"],
            "key_present": bool(os.environ.get("LLM_API_KEY")),
            "annotation_status": fixture["annotation_status"],
            "sample_count": len(fixture["examples"]),
            "mae": None,
            "score_range": None,
            "repeat_score_variance": None,
            "samples": [],
        }
    if not os.environ.get("LLM_API_KEY"):
        raise RuntimeError("RUN_REAL_JUDGE_CALIBRATION=1 requires a real LLM_API_KEY")
    config_id = llm_config_id
    metric_id = metric_ids[fixture["metric_name"]]
    result = require(client.post("/api/calibration/judge", json={
        "llm_config_id": config_id,
        "metric_definition_id": metric_id,
        "examples": [{"sample": item["sample"], "expected_score": item["expected_score"]} for item in fixture["examples"]],
        "repeats": fixture["repeats"],
    }))
    observed = [score for sample in result["samples"] for score in sample.get("observed_scores", [])]
    return {
        "status": "completed_real_provider_diagnostic",
        "judge_model": config["model"],
        "annotation_status": fixture["annotation_status"],
        "mae": result["mean_absolute_error"],
        "score_range": [min(observed), max(observed)] if observed else None,
        "repeat_score_variance": result["score_variance"],
        "failed_samples": [sample for sample in result["samples"] if "error" in sample],
        "samples": result["samples"],
        "ci_threshold_enforced": False,
    }


def main() -> None:
    records = json.loads((DEMO_DATA / "agent_trajectories.json").read_text(encoding="utf-8"))
    scenario_config = json.loads((DEMO_DATA / "scenario.json").read_text(encoding="utf-8"))
    metrics_config = json.loads((DEMO_DATA / scenario_config["metrics_config"]).read_text(encoding="utf-8"))
    scenario_config["metrics"] = metrics_config["metrics"]
    scenario_config["metric_threshold"] = metrics_config["pass_threshold"]
    judge_config = json.loads((DEMO_DATA / "judge_config.json").read_text(encoding="utf-8"))
    if len(records) != 5 or {item["case_id"] for item in records} != {"success", "wrong_tool", "wrong_arguments", "state_not_reached", "safety_violation"}:
        raise RuntimeError("Demo fixture must contain exactly the five required cases")

    with TestClient(app) as client:
        llm_configs = require(client.get("/api/llm-configs"))
        if not llm_configs:
            raise RuntimeError("Startup did not seed the default Judge configuration")
        llm = next((item for item in llm_configs if item["is_default"]), llm_configs[0])
        metric_ids = find_or_create_metrics(client, scenario_config)
        dataset_id, dataset = ensure_demo_dataset(client, records)
        scenario_id = ensure_demo_scenario(client, scenario_config, metric_ids)

        created = require(client.post("/api/evaluations", json={
            "name": f"Eval Labs Deterministic Demo {int(time.time())}",
            "dataset_id": dataset_id,
            "scenario_id": scenario_id,
            "llm_config_id": llm["id"],
        }), 201)
        task_id = created["id"]
        deadline = time.monotonic() + 60
        task = created
        while time.monotonic() < deadline:
            task = require(client.get(f"/api/evaluations/{task_id}"))
            if task["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.1)
        if task["status"] != "completed":
            raise RuntimeError(f"Demo task ended in state {task['status']}: {task.get('error_message')}")

        rows_response = require(client.get(f"/api/reports/{task_id}/rows", params={"page_size": 100}))
        rows = rows_response["items"]
        if len(rows) != 5:
            raise RuntimeError(f"Expected 5 result rows, got {len(rows)}")
        results = []
        for row in rows:
            data = (row.get("dataset_row") or {}).get("data") or {}
            results.append({
                "case_id": data.get("case_id"),
                "case_name": data.get("case_name"),
                "is_pass": row["is_pass"],
                "metric_scores": row["metric_scores"],
            })
        expected_pass = {"success": True, "wrong_tool": False, "wrong_arguments": False, "state_not_reached": False, "safety_violation": False}
        for row in results:
            if row["is_pass"] != expected_pass[row["case_id"]]:
                raise RuntimeError(f"Unexpected pass/fail for {row['case_id']}: {row['is_pass']}")

        calibration = maybe_run_real_calibration(client, judge_config, llm["id"], metric_ids)
        calibration_calls = sum(
            item.get("attempted_requests", 0) for item in calibration.get("samples", [])
        )
        report = {
            "status": "completed",
            "deterministic_demo": True,
            "external_judge_invocations": calibration_calls,
            "dataset_id": dataset_id,
            "dataset_name": dataset["name"],
            "imported_case_count": 5,
            "task_id": task_id,
            "task_status": task["status"],
            "queue_attempts": task["queue_attempts"],
            "trace_id": task["trace_id"],
            "passed_case_count": sum(1 for row in results if row["is_pass"]),
            "failed_case_count": sum(1 for row in results if not row["is_pass"]),
            "cases": results,
            "judge_calibration": calibration,
        }
    output_path = DEMO_RUNS / "latest.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nSaved demo report: {output_path}")


if __name__ == "__main__":
    main()
