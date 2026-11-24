from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DEMO_DATA = ROOT / "demo" / "data"
DEMO_RUNS = ROOT / "demo" / "runs"
DEMO_STATE = ROOT / "demo" / "state"

load_dotenv(BACKEND / ".env", override=False)
api_key = (os.environ.get("LLM_API_KEY") or "").strip()
if not api_key:
    raise SystemExit("Calibration requires a real LLM_API_KEY in the environment or backend/.env.")
if not (DEMO_STATE / "eval_demo.db").exists():
    raise SystemExit("Run scripts/setup.ps1 or scripts/setup.sh first to create the demo database.")

config = json.loads((DEMO_DATA / "judge_config.json").read_text(encoding="utf-8"))
fixture = json.loads((DEMO_DATA / "calibration_samples.json").read_text(encoding="utf-8"))
provider_endpoint = (os.environ.get("LLM_ENDPOINT") or config["endpoint"]).strip()
provider_model = (os.environ.get("LLM_MODEL") or config["model"]).strip()
provider_name = os.environ.get("LLM_PROVIDER") or config.get("provider", "openai-compatible")
os.environ["DATABASE_URL"] = f"sqlite:///{(DEMO_STATE / 'eval_demo.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(DEMO_STATE / "uploads")
os.environ["SEED_ON_STARTUP"] = "true"
os.environ["RUN_EVAL_ON_CREATE"] = "false"
os.environ["EVAL_QUEUE_WORKERS"] = "1"
sys.path.insert(0, str(BACKEND))

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def require(response, expected: int = 200):
    if response.status_code != expected:
        raise RuntimeError(f"API returned {response.status_code}: {response.text[:1000]}")
    return response.json()


def main() -> None:
    with TestClient(app) as client:
        configs = require(client.get("/api/llm-configs"))
        name = "Eval Labs Paid Judge Calibration"
        existing = next((item for item in configs if item["name"] == name), None)
        payload = {
            "name": name,
            "provider": provider_name,
            "api_base_url": provider_endpoint,
            "api_key": api_key,
            "model_name": provider_model,
            "temperature": 0.01,
            "max_tokens": 1024,
            "is_default": False,
        }
        if existing:
            llm = require(client.put(f"/api/llm-configs/{existing['id']}", json=payload))
        else:
            llm = require(client.post("/api/llm-configs", json=payload), 201)

        metrics = require(client.get("/api/metrics"))
        metric = next((item for item in metrics if item["name"] == fixture["metric_name"]), None)
        if metric is None:
            raise RuntimeError(f"Seed metric not found: {fixture['metric_name']}")

        result = require(client.post("/api/calibration/judge", json={
            "llm_config_id": llm["id"],
            "metric_definition_id": metric["id"],
            "examples": [
                {"sample": item["sample"], "expected_score": item["expected_score"]}
                for item in fixture["examples"]
            ],
            "repeats": fixture["repeats"],
        }))

    observed = [score for item in result["samples"] for score in item.get("observed_scores", [])]
    request_count = sum(item.get("attempted_requests", 0) for item in result["samples"])
    report = {
        "status": (
            "completed_real_provider_diagnostic"
            if result["sample_count"] == result["requested_sample_count"] and not result["error_count"]
            else "failed_provider_authentication"
            if any("401" in str(item.get("error", "")) for item in result["samples"])
            else "partial_or_failed"
        ),
        "judge_provider": provider_endpoint,
        "judge_model": provider_model,
        "request_count": request_count,
        "request_count_upper_bound": len(fixture["examples"]) * fixture["repeats"],
        "annotation_status": fixture["annotation_status"],
        "human_annotation_requirement_met": fixture["annotation_status"] == "human_reviewed",
        "diagnostic_only_ci_threshold_enforced": False,
        "sample_count": result["sample_count"],
        "requested_sample_count": result["requested_sample_count"],
        "error_count": result["error_count"],
        "repeats": result["repeats"],
        "mean_absolute_error": result["mean_absolute_error"],
        "score_range": [min(observed), max(observed)] if observed else None,
        "repeat_score_variance": result["score_variance"],
        "mean_per_sample_repeat_score_variance": result["score_variance"],
        "failed_samples": [item for item in result["samples"] if "error" in item],
        "samples": result["samples"],
        "raw_sample_text_persisted": False,
    }
    DEMO_RUNS.mkdir(parents=True, exist_ok=True)
    output = DEMO_RUNS / "calibration.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Saved calibration report: {output}")


if __name__ == "__main__":
    main()
