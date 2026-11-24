"""Deterministic, in-memory Agent environment for safe trajectory replay."""

from __future__ import annotations

import copy
import json
from typing import Any

from app.core.agent_trajectory import canonical_trajectory, compare_state, extract_tool_calls, validate_safety


def _path_parts(path: str) -> list[str]:
    return [part for part in str(path).replace("[", ".").replace("]", "").split(".") if part]


def _set_path(state: dict[str, Any], path: str, value: Any) -> None:
    parts = _path_parts(path)
    if not parts:
        return
    current = state
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


def _delete_path(state: dict[str, Any], path: str) -> None:
    parts = _path_parts(path)
    current: Any = state
    for part in parts[:-1]:
        current = current.get(part) if isinstance(current, dict) else None
    if isinstance(current, dict) and parts:
        current.pop(parts[-1], None)


def _get_path(value: Any, path: str) -> Any:
    current = value
    for part in _path_parts(path):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def _resolve(value: Any, args: dict[str, Any], state: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        if set(value) == {"$arg"}:
            return _get_path(args, str(value["$arg"]))
        if set(value) == {"$state"}:
            return _get_path(state, str(value["$state"]))
        return {key: _resolve(item, args, state) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, args, state) for item in value]
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        reference = value[2:-1]
        source, _, path = reference.partition(".")
        return _get_path(args if source == "args" else state, path)
    return copy.deepcopy(value)


def _validate_arguments(call: dict[str, Any], tool: dict[str, Any]) -> list[str]:
    args = call.get("args") or {}
    schema = tool.get("input_schema") or tool.get("parameters") or {}
    required = list(schema.get("required") or tool.get("required_args") or [])
    errors = [f"missing_argument:{name}" for name in required if name not in args]
    properties = schema.get("properties") or {}
    for name, definition in properties.items():
        if name not in args or not isinstance(definition, dict):
            continue
        expected = definition.get("type")
        value = args[name]
        valid = {
            "object": lambda item: isinstance(item, dict),
            "array": lambda item: isinstance(item, list),
            "string": lambda item: isinstance(item, str),
            "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
            "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
            "boolean": lambda item: isinstance(item, bool),
        }.get(expected)
        if valid and not valid(value):
            errors.append(f"invalid_argument_type:{name}:{expected}")
        if "enum" in definition and value not in definition["enum"]:
            errors.append(f"invalid_argument_value:{name}")
    return errors


def _apply_state_changes(state: dict[str, Any], tool: dict[str, Any], args: dict[str, Any]) -> None:
    patch = _resolve(tool.get("state_patch") or {}, args, state)
    if isinstance(patch, dict):
        for key, value in patch.items():
            _set_path(state, key, value)
    for operation in tool.get("state_operations") or []:
        if not isinstance(operation, dict):
            continue
        op = operation.get("op")
        path = str(operation.get("path") or "")
        current = _get_path(state, path)
        value = _resolve(operation.get("value"), args, state)
        if op == "set":
            _set_path(state, path, value)
        elif op == "delete":
            _delete_path(state, path)
        elif op == "increment":
            _set_path(state, path, (current or 0) + (value or 0))
        elif op == "append":
            _set_path(state, path, [*(current if isinstance(current, list) else []), value])


def _execute_fixture(call: dict[str, Any], tool: dict[str, Any], state: dict[str, Any]) -> Any:
    args = call.get("args") or {}
    if "result_template" in tool:
        return _resolve(tool["result_template"], args, state)
    result = tool.get("result")
    if isinstance(result, str) and result.startswith("{"):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            pass
    return _resolve(result, args, state)


def run_fixture_sandbox(
    trajectory: Any,
    tools: list[dict[str, Any]],
    initial_state: dict[str, Any] | None = None,
    safety_policy: dict[str, Any] | None = None,
    expected_state: dict[str, Any] | None = None,
    expected_tool_results: list[Any] | None = None,
    expected_side_effects: list[Any] | None = None,
) -> dict[str, Any]:
    """Replay declared tools against isolated state; never executes arbitrary code."""
    policy = safety_policy or {}
    fixtures = {str(tool.get("name")): tool for tool in tools if tool.get("name")}
    calls = extract_tool_calls({"trajectory": trajectory})
    state = copy.deepcopy(initial_state or {})
    results: list[dict[str, Any]] = []
    side_effects: list[Any] = []
    safety_events: list[dict[str, Any]] = []
    blocked_calls: list[dict[str, Any]] = []
    max_tool_calls = policy.get("max_tool_calls")
    forbidden_tools = {str(item) for item in policy.get("forbidden_tools") or []}
    allowed_effects = {str(item) for item in policy.get("allowed_side_effects") or []}

    for index, call in enumerate(calls):
        tool = fixtures.get(call["name"])
        reason = None
        effect = tool.get("side_effect") if tool else None
        effect_name = effect.get("name") if isinstance(effect, dict) else str(effect) if effect is not None else None
        if max_tool_calls is not None and index >= int(max_tool_calls):
            reason = f"max_tool_calls:{index + 1}>{max_tool_calls}"
        elif call["name"] in forbidden_tools:
            reason = f"forbidden_tool:{call['name']}"
        elif tool is None:
            reason = f"unknown_tool:{call['name']}"
        elif allowed_effects and effect_name and effect_name not in allowed_effects:
            reason = f"forbidden_side_effect:{effect_name}"
        else:
            argument_errors = _validate_arguments(call, tool)
            if argument_errors:
                reason = ";".join(argument_errors)

        if reason:
            safety_events.append({"violation": reason, "tool_name": call["name"], "call_index": index})
            blocked_calls.append({"index": index, "name": call["name"], "args": call["args"], "status": "blocked", "reason": reason})
            continue

        result = _execute_fixture(call, tool, state)
        results.append({"index": index, "name": call["name"], "args": call["args"], "result": result, "status": "completed"})
        _apply_state_changes(state, tool, call["args"])
        if effect is not None:
            effect_record = _resolve(effect, call["args"], state)
            side_effects.append({"index": index, "tool_name": call["name"], "effect": effect_record})

    canonical = canonical_trajectory({
        "trajectory": trajectory,
        "tool_results": [item["result"] for item in results],
        "actual_state": state,
        "side_effects": side_effects,
        "safety_events": safety_events,
    })
    safety = validate_safety(canonical, policy)
    violations = list(dict.fromkeys([*safety["violations"], *(event["violation"] for event in safety_events)]))
    state_check = compare_state(expected_state, state) if expected_state is not None else None
    tool_result_check = None
    if expected_tool_results is not None:
        expected_results = json.dumps(expected_tool_results, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        actual_results = json.dumps([item["result"] for item in results], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        tool_result_check = {"passed": expected_results == actual_results, "expected_count": len(expected_tool_results), "actual_count": len(results)}
    side_effect_check = None
    if expected_side_effects is not None:
        expected_effects = json.dumps(expected_side_effects, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        actual_effects = json.dumps([item["effect"] for item in side_effects], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        side_effect_check = {"passed": expected_effects == actual_effects, "expected_count": len(expected_side_effects), "actual_count": len(side_effects)}
    if state_check and state_check["score"] != 1.0:
        violations.append(f"state_mismatch:{','.join(state_check.get('mismatches') or [])}")
    if tool_result_check and not tool_result_check["passed"]:
        violations.append("tool_results_mismatch")
    if side_effect_check and not side_effect_check["passed"]:
        violations.append("side_effects_mismatch")
    return {
        "passed": not violations,
        "violations": violations,
        "tool_results": results,
        "blocked_calls": blocked_calls,
        "actual_state": state,
        "side_effects": side_effects,
        "safety_events": safety_events,
        "state_check": state_check,
        "tool_result_check": tool_result_check,
        "side_effect_check": side_effect_check,
        "trajectory": canonical,
        "safety": {"score": 1.0 if not violations else 0.0, "violations": violations},
    }
