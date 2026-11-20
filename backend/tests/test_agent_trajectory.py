from app.core.agent_trajectory import (
    canonical_trajectory,
    compare_state,
    compare_tool_calls,
    extract_tool_calls,
    validate_safety,
)
from app.core.agent_sandbox import run_fixture_sandbox


def test_endpoint_trace_tool_calls_are_read_even_without_conversation_list():
    row = {
        "user_input": "查询订单",
        "tool_calls": [{"name": "query_order", "args": {"order_id": "A-1"}}],
    }
    calls = extract_tool_calls(row)
    assert calls[0]["name"] == "query_order"
    assert calls[0]["args"] == {"order_id": "A-1"}


def test_tool_comparison_penalizes_extra_calls_and_order_changes():
    result = compare_tool_calls(
        [{"name": "query_order", "args": {"id": "A"}}],
        [
            {"name": "send_message", "args": {}},
            {"name": "query_order", "args": {"id": "A"}},
        ],
    )
    assert result["recall"] == 1.0
    assert result["precision"] == 0.5
    assert result["extra"] == 1
    assert result["order_score"] == 0.0


def test_state_and_safety_checks_are_deterministic():
    assert compare_state({"status": "returned"}, {"status": "returned"})["score"] == 1.0
    safety = validate_safety(
        {"tool_calls": [{"name": "delete_order", "args": {}}], "safety_events": []},
        {"forbidden_tools": ["delete_order"]},
    )
    assert safety["passed"] is False
    assert "forbidden_tool:delete_order" in safety["violations"]


def test_canonical_trajectory_preserves_state_and_tool_results():
    result = canonical_trajectory(
        {
            "user_input": [{"role": "assistant", "tool_calls": [{"name": "lookup", "arguments": {"q": "x"}}]}],
            "tool_results": [{"ok": True}],
            "actual_state": {"ticket": "closed"},
        }
    )
    assert result["schema_version"] == "agent-trajectory/v1"
    assert result["tool_calls"][0]["name"] == "lookup"
    assert result["actual_state"] == {"ticket": "closed"}


def test_fixture_sandbox_replays_tools_and_applies_state_patch():
    result = run_fixture_sandbox(
        trajectory=[{"type": "ai", "tool_calls": [{"name": "close_ticket", "args": {"id": "T-1"}}]}],
        tools=[
            {
                "name": "close_ticket",
                "result": {"ok": True},
                "state_patch": {"ticket_status": "closed"},
                "side_effect": {"name": "ticket_write"},
            }
        ],
        safety_policy={"allowed_side_effects": ["ticket_write"]},
    )
    assert result["passed"] is True
    assert result["tool_results"][0]["result"] == {"ok": True}
    assert result["actual_state"] == {"ticket_status": "closed"}
