from shannon_py.agent import (
    AgentAction,
    AgentActionType,
    AgentLoop,
    AgentMailbox,
    AgentMessage,
    AgentPolicy,
    AgentRole,
    AgentRuntime,
    AgentSpec,
    AgentState,
    AgentStatus,
)
from shannon_py.llm.providers import MockProvider
from shannon_py.tools import CalculatorTool, ToolExecutor, ToolRegistry


def test_agent_loop_transitions_through_tool_call_and_final_answer() -> None:
    policy = AgentPolicy(max_loop_count=3, max_tool_calls=2)
    loop = AgentLoop(policy)
    state = AgentState(
        workflow_id="workflow_1",
        task_id="task_1",
        agent_id="agent_1",
        session_id="session_1",
        query="2 + 2",
    )

    loop.step(
        state,
        AgentAction(
            type=AgentActionType.TOOL_CALL,
            metadata={"tool_name": "calculator", "arguments": {"expression": "2 + 2"}},
        ),
    )
    loop.step(state, AgentAction(type=AgentActionType.FINAL_ANSWER, content="Calculator result: 4"))

    assert state.status == AgentStatus.COMPLETED
    assert state.tool_calls[0]["tool_name"] == "calculator"
    assert state.final_response == "Calculator result: 4"


async def test_agent_runtime_runs_react_with_calculator() -> None:
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    runtime = AgentRuntime(provider=MockProvider(), tool_executor=ToolExecutor(registry))

    result = await runtime.run_react(
        AgentSpec(role=AgentRole.ASSISTANT, name="react"),
        workflow_id="workflow_1",
        task_id="task_1",
        session_id="session_1",
        query="2 + 3 * 4",
    )

    assert result.status == AgentStatus.COMPLETED
    assert result.output == "Calculator result: 14"
    assert result.metadata["tool_success"] is True


def test_agent_mailbox_delivers_messages() -> None:
    mailbox = AgentMailbox()
    message = AgentMessage(sender="agent_a", recipient="agent_b", content="findings")

    mailbox.send(message)

    assert mailbox.inbox("agent_b")[0].content == "findings"
