"""Canonical Agent trace normalization with OpenTelemetry span support."""

from __future__ import annotations

import json
from typing import Any


TRAJECTORY_SCHEMA_VERSION = "otel-agent-trajectory/v1"
MESSAGE_TYPES = {"human", "ai", "tool", "system"}
_TOOL_NAME_KEYS = ("gen_ai.tool.name", "tool.name", "tool_name", "name")
_TOOL_ARGS_KEYS = ("gen_ai.tool.call.arguments", "tool.args", "tool_arguments", "arguments")
_TOOL_RESULT_KEYS = ("gen_ai.tool.call.result", "tool.result", "tool_result", "result")


def _decode_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _otel_value(value: Any) -> Any:
    """Unwrap OpenTelemetry AnyValue and attribute-list representations."""
    if isinstance(value, dict):
        for key in ("stringValue", "boolValue", "intValue", "doubleValue", "bytesValue"):
            if key in value:
                return value[key]
        if "arrayValue" in value:
            items = value["arrayValue"]
            return [_otel_value(item) for item in items.get("values", [])] if isinstance(items, dict) else []
        if "kvlistValue" in value:
            pairs = value["kvlistValue"]
            return _otel_attributes(pairs.get("values", [])) if isinstance(pairs, dict) else {}
    return value


def _otel_attributes(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {str(key): _otel_value(item) for key, item in value.items()}
    if not isinstance(value, list):
        return {}
    attributes = {}
    for item in value:
        if isinstance(item, dict) and item.get("key") is not None:
            attributes[str(item["key"])] = _otel_value(item.get("value"))
    return attributes


def _first(mapping: dict[str, Any], names: tuple[str, ...], default: Any = None) -> Any:
    for name in names:
        value = mapping.get(name)
        if value is not None:
            return value
    return default


def normalize_tool_call(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    function = value.get("function") if isinstance(value.get("function"), dict) else {}
    attributes = _otel_attributes(value.get("attributes"))
    name = value.get("name") or function.get("name") or _first(attributes, _TOOL_NAME_KEYS)
    if not name:
        return None
    args = value.get("args")
    if args is None:
        args = value.get("arguments", function.get("arguments"))
    if args is None:
        args = _first(attributes, _TOOL_ARGS_KEYS, {})
    args = _decode_json(args)
    if not isinstance(args, dict):
        args = {"_raw": args} if args not in (None, "") else {}
    result = value.get("result", value.get("output"))
    if result is None:
        result = _first(attributes, _TOOL_RESULT_KEYS)
    result = _decode_json(result)
    return {
        "id": value.get("id") or value.get("tool_call_id") or _first(attributes, ("gen_ai.tool.call.id", "tool_call_id")),
        "name": str(name),
        "args": args,
        "result": result,
    }


def _iter_otel_spans(value: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Read OTLP JSON, flat span exports, and common trace wrapper shapes."""
    if isinstance(value, list):
        output = []
        for item in value:
            output.extend(_iter_otel_spans(item))
        return output
    if not isinstance(value, dict):
        return []
    if value.get("spanId") or value.get("span_id"):
        return [(value, _otel_attributes(value.get("resource")))]
    resource_spans = value.get("resourceSpans") or value.get("resource_spans")
    if isinstance(resource_spans, list):
        output = []
        for resource_span in resource_spans:
            if not isinstance(resource_span, dict):
                continue
            resource = _otel_attributes((resource_span.get("resource") or {}).get("attributes"))
            scopes = resource_span.get("scopeSpans") or resource_span.get("instrumentationLibrarySpans") or []
            for scope in scopes:
                if not isinstance(scope, dict):
                    continue
                scope_info = scope.get("scope") or scope.get("instrumentationLibrary") or {}
                scope_name = scope_info.get("name") if isinstance(scope_info, dict) else None
                for span in scope.get("spans") or []:
                    if isinstance(span, dict):
                        output.append(({**span, "_scope_name": scope_name}, resource))
        return output

    spans = value.get("spans")
    if spans is None:
        spans = value.get("trace")
    if isinstance(spans, dict):
        spans = spans.get("spans") or spans.get("events")
    if isinstance(spans, list) and any(isinstance(item, dict) and ("spanId" in item or "span_id" in item) for item in spans):
        resource = _otel_attributes(value.get("resource"))
        return [(span, resource) for span in spans if isinstance(span, dict)]
    return []


def normalize_otel_spans(value: Any) -> list[dict[str, Any]]:
    spans = []
    for raw, resource in _iter_otel_spans(value):
        attributes = _otel_attributes(raw.get("attributes"))
        status = raw.get("status") or {}
        kind = raw.get("kind", "internal")
        if isinstance(kind, int):
            kind = {1: "internal", 2: "server", 3: "client", 4: "producer", 5: "consumer"}.get(kind, "internal")
        events = []
        for event in raw.get("events") or []:
            if not isinstance(event, dict):
                continue
            events.append({
                "name": event.get("name") or "event",
                "time_unix_nano": event.get("timeUnixNano") or event.get("time_unix_nano"),
                "attributes": _otel_attributes(event.get("attributes")),
            })
        spans.append({
            "trace_id": raw.get("traceId") or raw.get("trace_id"),
            "span_id": raw.get("spanId") or raw.get("span_id"),
            "parent_span_id": raw.get("parentSpanId") or raw.get("parent_span_id"),
            "name": raw.get("name") or attributes.get("gen_ai.operation.name") or "agent.operation",
            "kind": str(kind).lower(),
            "start_time_unix_nano": raw.get("startTimeUnixNano") or raw.get("start_time_unix_nano"),
            "end_time_unix_nano": raw.get("endTimeUnixNano") or raw.get("end_time_unix_nano"),
            "status": {"code": status.get("code", "unset"), "description": status.get("message") or status.get("description") or ""},
            "attributes": attributes,
            "events": events,
            "resource": resource,
            "scope_name": raw.get("_scope_name"),
        })
    return spans


def normalize_trajectory(value: Any) -> list[dict[str, Any]]:
    """Convert provider messages, events, and OTel spans to canonical messages."""
    spans = normalize_otel_spans(value)
    source = value
    if isinstance(value, dict):
        source = value.get("trajectory") or value.get("messages") or value.get("events") or []
    if isinstance(source, dict):
        source = source.get("messages") or source.get("events") or []

    messages: list[dict[str, Any]] = []
    if isinstance(source, list):
        for index, raw in enumerate(source):
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

    has_conversation_messages = isinstance(source, list) and any(
        isinstance(item, dict) and (item.get("role") or item.get("type"))
        for item in source
    )
    if spans and not has_conversation_messages:
        messages = []
        for index, span in enumerate(spans):
            attrs = span["attributes"]
            name = _first(attrs, _TOOL_NAME_KEYS)
            args = _first(attrs, _TOOL_ARGS_KEYS)
            result = _first(attrs, _TOOL_RESULT_KEYS)
            operation = str(attrs.get("gen_ai.operation.name") or span["name"]).lower()
            is_tool = bool(name) or "tool" in operation
            tool_calls = []
            if is_tool and name:
                call = normalize_tool_call({"name": name, "args": args, "result": result, "id": attrs.get("gen_ai.tool.call.id")})
                if call:
                    tool_calls.append(call)
            for event in span["events"]:
                event_attrs = event["attributes"]
                event_name = _first(event_attrs, _TOOL_NAME_KEYS)
                if not event_name:
                    continue
                call = normalize_tool_call({
                    "name": event_name,
                    "args": _first(event_attrs, _TOOL_ARGS_KEYS, {}),
                    "result": _first(event_attrs, _TOOL_RESULT_KEYS),
                    "id": _first(event_attrs, ("gen_ai.tool.call.id", "tool_call_id")),
                })
                if call:
                    tool_calls.append(call)
            content = _first(attrs, ("gen_ai.output.messages", "output.value", "message"), "")
            if isinstance(content, str):
                content = _decode_json(content)
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            role = str(item.get("role") or "assistant")
                            messages.append({
                                "index": len(messages),
                                "type": {"user": "human", "assistant": "ai", "tool": "tool"}.get(role, "ai"),
                                "content": item.get("content", item.get("parts", "")),
                                "tool_calls": [normalize_tool_call(call) for call in item.get("tool_calls", []) if normalize_tool_call(call)],
                            })
                    continue
            messages.append({
                "index": index,
                "type": "tool" if is_tool else "ai",
                "content": content,
                "tool_calls": tool_calls,
                **({"name": name, "result": result} if is_tool and name else {}),
            })
    return messages


def extract_tool_calls(row_data: dict[str, Any], endpoint_trace: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Read ordered tool calls from dataset data or mapped endpoint traces."""
    trace = endpoint_trace or row_data.get("_endpoint_trace") or {}
    extracted = trace.get("extracted_fields") if isinstance(trace, dict) else {}
    candidates = (
        row_data.get("tool_calls"),
        row_data.get("trajectory"),
        row_data.get("user_input"),
        extracted.get("tool_calls") if isinstance(extracted, dict) else None,
        extracted.get("trajectory") if isinstance(extracted, dict) else None,
        trace.get("tool_calls") if isinstance(trace, dict) else None,
        trace.get("trajectory") if isinstance(trace, dict) else None,
        trace.get("otel_trace") if isinstance(trace, dict) else None,
    )
    for source in candidates:
        if not source:
            continue
        if isinstance(source, list) and all(isinstance(item, dict) and item.get("name") for item in source):
            normalized = [normalize_tool_call(item) for item in source]
        else:
            normalized = [call for message in normalize_trajectory(source) for call in message.get("tool_calls", [])]
        normalized = [call for call in normalized if call]
        if normalized:
            return normalized
    return []


def canonical_trajectory(row_data: dict[str, Any], endpoint_trace: dict[str, Any] | None = None) -> dict[str, Any]:
    trace = endpoint_trace or row_data.get("_endpoint_trace") or {}
    extracted = trace.get("extracted_fields") if isinstance(trace, dict) else {}
    raw_trace = (
        row_data.get("trajectory")
        or row_data.get("user_input")
        or (extracted or {}).get("trajectory")
        or trace.get("trajectory")
        or trace.get("otel_trace")
    )
    spans = normalize_otel_spans(raw_trace)
    messages = normalize_trajectory(raw_trace)
    tool_calls = extract_tool_calls(row_data, trace)
    tool_results = row_data.get("tool_results")
    if tool_results is None and isinstance(extracted, dict):
        tool_results = extracted.get("tool_results")
    if tool_results is None:
        tool_results = [message.get("result") for message in messages if message.get("type") == "tool" and "result" in message]
        tool_results.extend(call.get("result") for call in tool_calls if call.get("result") is not None)
    return {
        "schema_version": TRAJECTORY_SCHEMA_VERSION,
        "trace_id": (
            trace.get("trace_id") if isinstance(trace, dict) else None
        ) or (spans[0].get("trace_id") if spans else None),
        "session_id": row_data.get("session_id") or row_data.get("conversation_id"),
        "messages": messages,
        "spans": spans,
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
    return {"score": 1.0 if not violations else 0.0, "violations": violations, "passed": not violations}
