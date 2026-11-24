from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env", override=False)

from app.core.config import settings  # noqa: E402
from app.core.evaluation_engine import OpenAIJudgeClient, build_metric  # noqa: E402
from app.core.snapshots import METRIC_ENGINE_VERSION  # noqa: E402


def canonical_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_experiment() -> tuple[dict, dict[str, str]]:
    dataset = json.loads((HERE / "samples.json").read_text(encoding="utf-8"))
    prompts = {
        "A": (HERE / "prompt_a.txt").read_text(encoding="utf-8").strip(),
        "B": (HERE / "prompt_b.txt").read_text(encoding="utf-8").strip(),
    }
    return dataset, prompts


def make_report_skeleton(dataset: dict, prompts: dict[str, str]) -> dict:
    return {
        "status": "dry_run_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "annotation_status": dataset["annotation_status"],
        "human_annotation_requirement_met": False,
        "dataset_hash": canonical_hash(dataset),
        "dataset_sample_count": len(dataset["examples"]),
        "score_scale": dataset["score_scale"],
        "provider": settings.LLM_PROVIDER,
        "endpoint": settings.LLM_ENDPOINT,
        "model": settings.LLM_MODEL,
        "temperature": settings.LLM_TEMPERATURE,
        "max_tokens": min(settings.LLM_MAX_TOKENS, 1200),
        "metric_engine_version": METRIC_ENGINE_VERSION,
        "pricing_reference": {
            "url": "https://api-docs.deepseek.com/quick_start/pricing",
            "checked_date": "2026-11-24",
            "configured_model_listed": settings.LLM_MODEL in {"deepseek-flash", "deepseek-v4-pro"},
            "configured_model_note": "The configured alias deepseek-chat is not listed on the current pricing page; actual route and exact bill rate are unverified.",
            "flash_per_million_usd": {"input_cache_miss_off_peak": 0.15, "input_cache_miss_peak": 0.30, "output_off_peak": 0.60, "output_peak": 1.20},
            "pro_per_million_usd": {"input_cache_miss_off_peak": 0.66, "input_cache_miss_peak": 1.32, "output_off_peak": 1.98, "output_peak": 3.96},
        },
        "repeats_per_sample": 2,
        "planned_logical_calls": len(dataset["examples"]) * 2 * len(prompts),
        "variants": {
            key: {
                "prompt_hash": canonical_hash(prompt),
                "configuration_hash": canonical_hash({
                    "metric_type": "numeric",
                    "allowed_values": [0.0, 1.0],
                    "prompt": prompt,
                    "engine_version": METRIC_ENGINE_VERSION,
                    "model": settings.LLM_MODEL,
                    "temperature": settings.LLM_TEMPERATURE,
                    "max_tokens": min(settings.LLM_MAX_TOKENS, 1200),
                }),
                "prompt": prompt,
                "results": [],
            }
            for key, prompt in prompts.items()
        },
        "notes": [
            "The bundled scores and rationales are illustrative rubric labels, not human annotations.",
            "This run is diagnostic only; it is not a CI threshold or production accuracy claim.",
        ],
    }


async def run_variant(dataset: dict, prompt: str, variant: str, repeats: int) -> dict:
    metric_def = SimpleNamespace(
        id=None,
        name="rag_factual_correctness_prompt_comparison",
        display_name="RAG Factual Correctness",
        metric_type="numeric",
        config={
            "description": "Score factual correctness against the reference and retrieved evidence.",
            "allowed_values": [0.0, 1.0],
            "prompt": prompt,
        },
    )
    _, metric = build_metric(metric_def)
    config = SimpleNamespace(
        provider=settings.LLM_PROVIDER,
        api_base_url=settings.LLM_ENDPOINT,
        api_key=settings.LLM_API_KEY,
        model_name=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )
    judge = OpenAIJudgeClient(config)
    result = {
        "variant": variant,
        "prompt_hash": canonical_hash(prompt),
        "configuration_hash": canonical_hash({
            "metric_type": "numeric",
            "allowed_values": [0.0, 1.0],
            "prompt": prompt,
            "engine_version": METRIC_ENGINE_VERSION,
            "model": settings.LLM_MODEL,
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": min(settings.LLM_MAX_TOKENS, 1200),
        }),
        "results": [],
    }

    for example in dataset["examples"]:
        calls = []
        for repeat in range(1, repeats + 1):
            started = time.perf_counter()
            judge.last_api_attempts = 0
            judge.last_usage = None
            try:
                scored = await metric.ascore(dict(example["sample"]), judge)
                calls.append({
                    "repeat": repeat,
                    "score": float(scored.value),
                    "reason": scored.reason,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                    "sdk_create_calls_observed": judge.last_create_attempts,
                    "usage": judge.last_usage,
                })
            except Exception as exc:
                calls.append({
                    "repeat": repeat,
                    "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                    "sdk_create_calls_observed": judge.last_create_attempts,
                    "usage": judge.last_usage,
                })
        successful = [call["score"] for call in calls if "score" in call]
        complete = len(successful) == repeats
        sample_result = {
            "sample_id": example["id"],
            "sample_hash": canonical_hash(example["sample"]),
            "reference_score": example["reference_score"],
            "reference_rationale": example["annotation_rationale"],
            "calls": calls,
            "successful_repeats": len(successful),
            "failed_repeats": repeats - len(successful),
            "sample_complete": complete,
        }
        if complete:
            sample_mean = sum(successful) / repeats
            squared = [(score - sample_mean) ** 2 for score in successful]
            sample_result["mean_score"] = round(sample_mean, 4)
            sample_result["absolute_error"] = round(abs(sample_mean - example["reference_score"]), 4)
            sample_result["repeat_population_variance"] = round(sum(squared) / repeats, 8)
            sample_result["repeat_range"] = round(max(successful) - min(successful), 4)
        result["results"].append(sample_result)

    return result


def summarize_variant(variant: dict) -> dict:
    completed = [item for item in variant["results"] if item.get("sample_complete")]
    return {
        "requested_samples": len(variant["results"]),
        "successful_samples": len(completed),
        "failed_samples": len(variant["results"]) - len(completed),
        "mean_absolute_error": (
            round(sum(item["absolute_error"] for item in completed) / len(completed), 4)
            if completed else None
        ),
        "mean_within_sample_population_variance": (
            round(sum(item["repeat_population_variance"] for item in completed) / len(completed), 8)
            if completed else None
        ),
        "mean_within_sample_range": (
            round(sum(item["repeat_range"] for item in completed) / len(completed), 4)
            if completed else None
        ),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Make the paid external Judge calls")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    if args.repeats < 1 or args.repeats > 3:
        raise SystemExit("--repeats must be between 1 and 3")

    dataset, prompts = load_experiment()
    report = make_report_skeleton(dataset, prompts)
    report["repeats_per_sample"] = args.repeats
    report["planned_logical_calls"] = len(dataset["examples"]) * args.repeats * len(prompts)
    if not args.execute:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if not settings.LLM_API_KEY.strip():
        raise SystemExit("LLM_API_KEY is missing; no Judge calls were made.")

    report["status"] = "completed_real_provider_diagnostic"
    report["started_at"] = datetime.now(timezone.utc).isoformat()
    for variant, prompt in prompts.items():
        report["variants"][variant] = await run_variant(dataset, prompt, variant, args.repeats)
        report["variants"][variant]["summary"] = summarize_variant(report["variants"][variant])
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["failed_samples"] = sum(
        item["summary"]["failed_samples"] for item in report["variants"].values()
    )
    report["successful_samples"] = sum(
        item["summary"]["successful_samples"] for item in report["variants"].values()
    )
    report["logical_calls_attempted"] = sum(
        len(sample["calls"])
        for variant in report["variants"].values()
        for sample in variant["results"]
    )
    report["observed_sdk_create_calls"] = sum(
        call["sdk_create_calls_observed"]
        for variant in report["variants"].values()
        for sample in variant["results"]
        for call in sample["calls"]
    )
    report["usage"] = {
        key: sum(
            (call.get("usage") or {}).get(key, 0)
            for variant in report["variants"].values()
            for sample in variant["results"]
            for call in sample["calls"]
        )
        for key in ("input_tokens", "output_tokens", "total_tokens")
    }
    input_tokens = report["usage"]["input_tokens"]
    output_tokens = report["usage"]["output_tokens"]
    report["cost_estimates_usd"] = {
        "deepseek_v4_flash_off_peak": round(input_tokens * 0.15 / 1_000_000 + output_tokens * 0.60 / 1_000_000, 8),
        "deepseek_v4_flash_peak": round(input_tokens * 0.30 / 1_000_000 + output_tokens * 1.20 / 1_000_000, 8),
        "deepseek_v4_pro_off_peak": round(input_tokens * 0.66 / 1_000_000 + output_tokens * 1.98 / 1_000_000, 8),
        "deepseek_v4_pro_peak": round(input_tokens * 1.32 / 1_000_000 + output_tokens * 3.96 / 1_000_000, 8),
        "warning": "Estimates use listed model rates and assume cache-miss input. They do not confirm how the unlisted deepseek-chat alias is billed.",
    }
    report["raw_sample_text_persisted"] = False
    output = HERE / "latest_run.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Saved report: {output}")


if __name__ == "__main__":
    asyncio.run(main())
