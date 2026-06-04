from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from shannon_py.llm.providers import LLMProvider, LLMRequest
from shannon_py.tools.core import ToolExecutor


class AgentRole(StrEnum):
    LEAD = "lead"
    WORKER = "worker"
    ASSISTANT = "assistant"
    RESEARCHER = "researcher"


class AgentStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_TOOL = "waiting_tool"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class AgentActionType(StrEnum):
    TOOL_CALL = "tool_call"
    FINAL_ANSWER = "final_answer"
    REQUEST_CLARIFICATION = "request_clarification"
    ERROR = "error"
    SEND_MESSAGE = "send_message"
    PUBLISH_DATA = "publish_data"
    CLAIM_TASK = "claim_task"
    COMPLETE_TASK = "complete_task"
    SPAWN_AGENT = "spawn_agent"
    IDLE = "idle"


class AgentAction(BaseModel):
    type: AgentActionType
    content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentSpec(BaseModel):
    agent_id: str = Field(default_factory=lambda: f"agent_{uuid4().hex}")
    role: AgentRole = AgentRole.ASSISTANT
    name: str = "agent"
    description: str = ""
    max_loop_count: int = Field(default=15, ge=1)
    max_tool_calls: int = Field(default=20, ge=0)


class AgentState(BaseModel):
    workflow_id: str
    task_id: str
    agent_id: str
    session_id: str
    query: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    selected_tools: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    final_response: str | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    status: AgentStatus = AgentStatus.IDLE
    metadata: dict[str, Any] = Field(default_factory=dict)
    loop_count: int = 0


class AgentResult(BaseModel):
    workflow_id: str
    task_id: str
    agent_id: str
    status: AgentStatus
    output: str | None = None
    observations: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class AgentPolicy(BaseModel):
    max_loop_count: int = Field(default=15, ge=1)
    max_tool_calls: int = Field(default=20, ge=0)
    allow_dangerous_tools: bool = False

    def can_continue(self, state: AgentState) -> bool:
        return (
            state.loop_count < self.max_loop_count
            and len(state.tool_calls) < self.max_tool_calls
        )


@dataclass
class AgentWorkspace:
    artifacts: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def publish(self, key: str, value: Any) -> None:
        self.artifacts[key] = value


@dataclass
class AgentMessage:
    sender: str
    recipient: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentMailbox:
    def __init__(self) -> None:
        self._messages: dict[str, list[AgentMessage]] = defaultdict(list)

    def send(self, message: AgentMessage) -> None:
        self._messages[message.recipient].append(message)

    def inbox(self, recipient: str) -> list[AgentMessage]:
        return list(self._messages.get(recipient, []))


class AgentLoop:
    def __init__(self, policy: AgentPolicy) -> None:
        self._policy = policy

    def step(self, state: AgentState, action: AgentAction) -> AgentState:
        state.loop_count += 1
        if action.type == AgentActionType.TOOL_CALL:
            state.status = AgentStatus.WAITING_TOOL
            state.tool_calls.append(
                {
                    "tool_name": action.metadata.get("tool_name"),
                    "arguments": action.metadata.get("arguments", {}),
                }
            )
        elif action.type == AgentActionType.FINAL_ANSWER:
            state.final_response = action.content
            state.status = AgentStatus.COMPLETED
        elif action.type == AgentActionType.ERROR:
            state.status = AgentStatus.FAILED
            state.metadata["error"] = action.content
        else:
            state.metadata["last_action"] = action.type.value

        if not self._policy.can_continue(state) and state.status not in {
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
        }:
            state.status = AgentStatus.FAILED
            state.metadata.setdefault("error", "Agent loop limit exceeded.")
        return state


class AgentRuntime:
    def __init__(
        self,
        provider: LLMProvider | None = None,
        tool_executor: ToolExecutor | None = None,
        policy: AgentPolicy | None = None,
        mailbox: AgentMailbox | None = None,
        workspace: AgentWorkspace | None = None,
    ) -> None:
        self._provider = provider
        self._tool_executor = tool_executor
        self._policy = policy or AgentPolicy()
        self._mailbox = mailbox or AgentMailbox()
        self._workspace = workspace or AgentWorkspace()
        self._loop = AgentLoop(self._policy)

    def build_state(
        self,
        spec: AgentSpec,
        workflow_id: str,
        task_id: str,
        session_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> AgentState:
        return AgentState(
            workflow_id=workflow_id,
            task_id=task_id,
            agent_id=spec.agent_id,
            session_id=session_id,
            query=query,
            context=context or {},
            status=AgentStatus.RUNNING,
        )

    async def run_simple(
        self,
        spec: AgentSpec,
        workflow_id: str,
        task_id: str,
        session_id: str,
        query: str,
        context: dict[str, Any] | None = None,
        provider_prompt: str | None = None,
    ) -> AgentResult:
        state = self.build_state(spec, workflow_id, task_id, session_id, query, context)
        prompt = provider_prompt or query
        if self._provider is not None:
            response = await self._provider.complete(
                LLMRequest(prompt=prompt, context=context or {})
            )
            state.final_response = response.content
            state.metadata.update(
                {
                    "provider": response.provider,
                    "model": response.model,
                    **response.metadata,
                }
            )
        else:
            state.final_response = prompt
        state.status = AgentStatus.COMPLETED
        return self._to_result(state)

    async def run_react(
        self,
        spec: AgentSpec,
        workflow_id: str,
        task_id: str,
        session_id: str,
        query: str,
        context: dict[str, Any] | None = None,
        tool_name: str = "calculator",
        tool_arguments: dict[str, Any] | None = None,
    ) -> AgentResult:
        state = self.build_state(spec, workflow_id, task_id, session_id, query, context)
        self._loop.step(
            state,
            AgentAction(
                type=AgentActionType.TOOL_CALL,
                metadata={
                    "tool_name": tool_name,
                    "arguments": tool_arguments or {"expression": query},
                },
            ),
        )
        tool_result = await self._tool_executor.execute(
            tool_name,
            tool_arguments or {"expression": query},
        )
        state.observations.append(tool_result.content or tool_result.error or "")
        self._workspace.publish("last_tool_result", tool_result.model_dump(mode="json"))
        self._loop.step(
            state,
            AgentAction(
                type=AgentActionType.FINAL_ANSWER,
                content=(
                    f"Calculator result: {tool_result.content}"
                    if tool_result.success
                    else f"Calculator failed: {tool_result.error}"
                ),
                metadata={"tool_result": tool_result.model_dump(mode="json")},
            ),
        )
        state.metadata.update(
            {
                "tool_name": tool_name,
                "tool_success": tool_result.success,
            }
        )
        return self._to_result(state)

    async def run_dag_step(
        self,
        spec: AgentSpec,
        workflow_id: str,
        task_id: str,
        session_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        return await self.run_simple(spec, workflow_id, task_id, session_id, query, context)

    async def run_research(
        self,
        spec: AgentSpec,
        workflow_id: str,
        task_id: str,
        session_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        state = self.build_state(spec, workflow_id, task_id, session_id, query, context)
        if self._provider is not None:
            response = await self._provider.complete(
                LLMRequest(
                    prompt=f"Research summary request: {query}",
                    context=context or {},
                )
            )
            state.final_response = f"Research summary:\n{response.content}"
            state.metadata.update(
                {
                    "provider": response.provider,
                    "model": response.model,
                    **response.metadata,
                }
            )
        else:
            state.final_response = f"Research summary: {query}"
        self._loop.step(
            state,
            AgentAction(
                type=AgentActionType.FINAL_ANSWER,
                content=state.final_response,
                metadata={"sources": context.get("sources", []) if context else []},
            ),
        )
        state.metadata["sources"] = context.get("sources", []) if context else []
        return self._to_result(state)

    def send_message(self, sender: str, recipient: str, content: str) -> AgentMessage:
        message = AgentMessage(sender=sender, recipient=recipient, content=content)
        self._mailbox.send(message)
        return message

    def inbox(self, recipient: str) -> list[AgentMessage]:
        return self._mailbox.inbox(recipient)

    def workspace(self) -> AgentWorkspace:
        return self._workspace

    def _to_result(self, state: AgentState) -> AgentResult:
        return AgentResult(
            workflow_id=state.workflow_id,
            task_id=state.task_id,
            agent_id=state.agent_id,
            status=state.status,
            output=state.final_response,
            observations=state.observations,
            tool_calls=state.tool_calls,
            token_usage=state.token_usage,
            metadata=state.metadata,
            error=state.metadata.get("error"),
        )
