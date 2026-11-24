from fastapi import APIRouter

from app.core.agent_sandbox import run_fixture_sandbox
from app.schemas.evaluation import AgentSandboxRequest, AgentSandboxResponse

router = APIRouter(prefix="/agent-sandbox", tags=["Agent Sandbox"])


@router.post("/run", response_model=AgentSandboxResponse)
def run_agent_sandbox(payload: AgentSandboxRequest):
    return run_fixture_sandbox(
        trajectory=payload.trajectory,
        tools=payload.tools,
        initial_state=payload.initial_state,
        safety_policy=payload.safety_policy,
        expected_state=payload.expected_state,
        expected_tool_results=payload.expected_tool_results,
        expected_side_effects=payload.expected_side_effects,
    )
