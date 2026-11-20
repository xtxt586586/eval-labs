"""Canonical Agent trajectory helpers and deterministic checks.

The platform accepts traces from datasets and HTTP endpoints, but all Agent
metrics should consume the same representation.  This module deliberately
keeps the schema JSON friendly so traces can be stored in SQLite/PostgreSQL
and exported without a framework-specific dependency.
"""

from __future__ import annotations

import json
import re
from typing import Any


TRAJECTORY_SCHEMA_VERSION = "agent-trajectory/v1"
MESSAGE_TYPES = {"human", "ai", "tool", "system"}


def normalize_tool_call(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    name = value.get("name") or value.get("function", {}).get("name")
    if not name:
        return None
    args = value.get("args")
    if args is None:
        args = value.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {"_raw": args}
    if not isinstance(args, dict):
        args = {}
    result = value.get("result", value.get("output"))
    return {
        "id": value.get("id") or value.get("tool_call_id"),
        "name": str(name),
        "args": args,
        "result": result,
    }


def normalize_trajectory(value: Any) -> list[dict[str, Any]]:
    """Convert common provider/framework trace shapes to canonical messages."""
    if isinstance(value, dict):
        value = value.get("trajectory") or value.get("messages") or value.get("events") or []
    if not isinstance(value, list):
        return []

    messages: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            continue
        raw_type = raw.get("type") or raw.get("role") or raw.get("kind")
        role_map = {"user": "human", "assistant": "ai", "function": "tool"}
        message_type = role_map.get(str(raw_type), str(raw_type or "ai"))
        if message_type not in MESSAGE_TYPES:
            message_type = "ai"
        calls = []
        for item in raw.get("tool_calls") or raw.get("tools") or []:
            normalized = normalize_tool_call(item)
            if normalized:
                calls.append(normalized)
        message = {
            "index": index,
            "type": message_type,
            "content": raw.get("content", raw.get("text", raw.get("output", ""))),
            "tool_calls": calls,
        }
        if raw.get("tool_call_id"):
            message["tool_call_id"] = raw["tool_call_id"]
        if raw.get("name") and message_type == "tool":
            message["name"] = raw["name"]
        if "result" in raw or "output" in raw:
            message["result"] = raw.get("result", raw.get("output"))
        messages.append(message)
    return messages


def extract_tool_calls(row_data: dict[str, Any], endpoint_trace: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Read tool calls from a dataset trace or mapped endpoint response."""
    candidates: list[Any] = []
    trace = endpoint_trace or row_data.get("_endpoint_trace") or {}
    extracted = trace.get("extracted_fields") if isinstance(trace, dict) else {}
    for source in (
        row_data.get("tool_calls"),
        row_data.get("trajectory"),
        row_data.get("user_input"),
        extracted.get("tool_calls") if isinstance(extracted, dict) else None,
        trace.get("tool_calls") if isinstance(trace, dict) else None,
        trace.get("trajectory") if isinstance(trace, dict) else None,
    ):
        if source:
            candidates.append(source)

    for source in candidates:
        if isinstance(source, list) and all(isinstance(item, dict) and item.get("name") for item in source):
            normalized = [normalize_tool_call(item) for item in source]
        else:
            normalized = [call for message in normalize_trajectory(source) for call in message.get("tool_calls", [])]
        normalized = [call for call in normalized if call]
        if normalized:
            # Prefer the first populated source. This preserves duplicate and
            # ordered calls, which are meaningful for efficiency and safety.
            return normalized
    return []


def canonical_trajectory(row_data: dict[str, Any], endpoint_trace: dict[str, Any] | None = None) -> dict[str, Any]:
    trace = endpoint_trace or row_data.get("_endpoint_trace") or {}
    extracted = trace.get("extracted_fields") if isinstance(trace, dict) else {}
    messages = normalize_trajectory(
        row_data.get("trajectory")
        or row_data.get("user_input")
        or (extracted or {}).get("trajectory")
        or trace.get("trajectory")
    )
    tool_calls = extract_tool_calls(row_data, trace)
    tool_results = row_data.get("tool_results") or (extracted or {}).get("tool_results")
    if tool_results is None:
        tool_results = [message.get("result") for message in messages if message.get("type") == "tool"]
    return {
        "schema_version": TRAJECTORY_SCHEMA_VERSION,
        "messages": messages,
        "tool_calls": tool_calls,
        "tool_results": tool_results or [],
        "actual_state": row_data.get("actual_state") or (extracted or {}).get("actual_state"),
        "side_effects": row_data.get("side_effects") or (extracted or {}).get("side_effects") or [],
        "safety_events": row_data.get("safety_events") or (extracted or {}).get("safety_events") or [],
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compare_tool_calls(expected: list[Any], actual: list[Any]) -> dict[str, Any]:
    expected_calls = [normalize_tool_call(item) for item in expected or []]
    actual_calls = [normalize_tool_call(item) for item in actual or []]
    expected_calls = [item for item in expected_calls if item]
    actual_calls = [item for item in actual_calls if item]
    remaining = list(actual_calls)
    matched = 0
    for item in expected_calls:
        for index, candidate in enumerate(remaining):
            if candidate["name"] == item["name"] and candidate["args"] == item["args"]:
                matched += 1
                remaining.pop(index)
                break
    precision = matched / len(actual_calls) if actual_calls else (1.0 if not expected_calls else 0.0)
    recall = matched / len(expected_calls) if expected_calls else (1.0 if not actual_calls else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    order_matches = sum(
        1 for expected_item, actual_item in zip(expected_calls, actual_calls)
        if expected_item["name"] == actual_item["name"] and expected_item["args"] == actual_item["args"]
    )
    return {
        "matched": matched,
        "expected": len(expected_calls),
        "actual": len(actual_calls),
        "missing": max(len(expected_calls) - matched, 0),
        "extra": max(len(actual_calls) - matched, 0),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "order_score": round(order_matches / len(expected_calls), 4) if expected_calls else 1.0,
    }


def compare_state(expected: Any, actual: Any) -> dict[str, Any]:
    if expected in (None, "", {}, []):
        return {"score": None, "missing": [], "mismatches": [], "reason": "缺少 expected_state，无法验证状态变化。"}
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        score = 1.0 if _canonical_json(expected) == _canonical_json(actual) else 0.0
        return {"score": score, "missing": [], "mismatches": [] if score else ["state"]}
    mismatches = []
    for key, value in expected.items():
        if key not in actual or actual[key] != value:
            mismatches.append(key)
    score = 1.0 - len(mismatches) / max(len(expected), 1)
    return {"score": round(max(score, 0.0), 4), "missing": mismatches, "mismatches": mismatches}


def validate_safety(trajectory: dict[str, Any], policy: dict[str, Any] | None) -> dict[str, Any]:
    policy = policy or {}
    forbidden_tools = {str(item) for item in policy.get("forbidden_tools") or []}
    max_tool_calls = policy.get("max_tool_calls")
    violations = []
    calls = trajectory.get("tool_calls") or []
    for call in calls:
        if call.get("name") in forbidden_tools:
            violations.append(f"forbidden_tool:{call.get('name')}")
    if max_tool_calls is not None and len(calls) > int(max_tool_calls):
        violations.append(f"max_tool_calls:{len(calls)}>{max_tool_calls}")
    for event in trajectory.get("safety_events") or []:
        if isinstance(event, dict) and event.get("violation"):
            violations.append(str(event["violation"]))
        elif isinstance(event, str):
            violations.append(event)
    return {
        "score": 1.0 if not violations else 0.0,
        "violations": violations,
        "passed": not violations,
    }
