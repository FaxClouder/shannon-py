from shannon_py.policy import (
    ApprovalStatus,
    InMemoryApprovalGate,
    PolicyDecisionStatus,
    PolicyEngine,
)
from shannon_py.tools import ToolSpec


def test_policy_engine_denies_overlong_task_input() -> None:
    engine = PolicyEngine(max_input_chars=3)

    decision = engine.validate_task_input("abcd")

    assert decision.status == PolicyDecisionStatus.DENIED
    assert decision.allowed is False


def test_policy_engine_requires_approval_for_dangerous_tool() -> None:
    engine = PolicyEngine()
    spec = ToolSpec(
        name="danger",
        description="dangerous test tool",
        dangerous=True,
    )

    decision = engine.evaluate_tool_execution(spec)
    approved = engine.evaluate_tool_execution(spec, approved=True)

    assert decision.status == PolicyDecisionStatus.APPROVAL_REQUIRED
    assert approved.status == PolicyDecisionStatus.ALLOWED


async def test_approval_gate_tracks_decisions() -> None:
    gate = InMemoryApprovalGate()

    approval = await gate.request_approval("tool", "python_exec", "needs approval")
    decided = await gate.decide(approval.approval_id, approved=True)

    assert decided is not None
    assert decided.status == ApprovalStatus.APPROVED
    assert len(await gate.list_requests()) == 1
