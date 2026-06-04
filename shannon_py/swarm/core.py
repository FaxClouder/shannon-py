from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from shannon_py.agent import AgentRole, AgentRuntime, AgentSpec


class SwarmTaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class SwarmTask(BaseModel):
    task_id: str = Field(default_factory=lambda: f"swarm_task_{uuid4().hex}")
    content: str
    status: SwarmTaskStatus = SwarmTaskStatus.PENDING
    assigned_to: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MailMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: f"mail_{uuid4().hex}")
    sender: str
    recipient: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class Mailbox:
    def __init__(self) -> None:
        self._messages: dict[str, list[MailMessage]] = defaultdict(list)

    def send(self, message: MailMessage) -> None:
        self._messages[message.recipient].append(message)

    def inbox(self, recipient: str) -> list[MailMessage]:
        return list(self._messages.get(recipient, []))


class TaskBoard:
    def __init__(self) -> None:
        self._tasks: dict[str, SwarmTask] = {}

    def add(self, task: SwarmTask) -> SwarmTask:
        self._tasks[task.task_id] = task
        return task

    def assign(self, task_id: str, agent_id: str) -> SwarmTask:
        task = self._tasks[task_id]
        task.assigned_to = agent_id
        task.status = SwarmTaskStatus.IN_PROGRESS
        return task

    def complete(self, task_id: str) -> SwarmTask:
        task = self._tasks[task_id]
        task.status = SwarmTaskStatus.COMPLETED
        return task

    def list_tasks(self) -> list[SwarmTask]:
        return list(self._tasks.values())


class SharedWorkspace:
    def __init__(self) -> None:
        self._artifacts: dict[str, Any] = {}

    def publish(self, key: str, value: Any) -> None:
        self._artifacts[key] = value

    def get(self, key: str) -> Any:
        return self._artifacts.get(key)


class LeadAgent:
    def __init__(self, agent_id: str = "lead") -> None:
        self.agent_id = agent_id

    def decompose(self, objective: str) -> list[SwarmTask]:
        parts = [part.strip() for part in objective.replace("\n", ";").split(";") if part.strip()]
        if not parts:
            parts = [objective]
        return [SwarmTask(content=part) for part in parts]


class DynamicSpawnManager:
    def __init__(self) -> None:
        self._spawned_agents: list[str] = []

    def spawn(self, count: int) -> list[str]:
        agents = [f"agent_{uuid4().hex}" for _ in range(count)]
        self._spawned_agents.extend(agents)
        return agents

    def list_agents(self) -> list[str]:
        return list(self._spawned_agents)


class ConvergenceDetector:
    def is_converged(self, tasks: list[SwarmTask]) -> bool:
        return bool(tasks) and all(task.status == SwarmTaskStatus.COMPLETED for task in tasks)


class SwarmCoordinator:
    def __init__(self, runtime: AgentRuntime | None = None) -> None:
        self.lead = LeadAgent()
        self.board = TaskBoard()
        self.mailbox = Mailbox()
        self.workspace = SharedWorkspace()
        self.spawn_manager = DynamicSpawnManager()
        self.detector = ConvergenceDetector()
        self.runtime = runtime or AgentRuntime()

    def create_swarm(self, objective: str) -> list[SwarmTask]:
        tasks = self.lead.decompose(objective)
        for task in tasks:
            self.board.add(task)
        self.workspace.publish("objective", objective)
        return tasks

    def assign_tasks(self, agent_id: str) -> list[SwarmTask]:
        assigned: list[SwarmTask] = []
        for task in self.board.list_tasks():
            if task.status == SwarmTaskStatus.PENDING:
                assigned.append(self.board.assign(task.task_id, agent_id))
        return assigned

    def publish_findings(self, sender: str, recipient: str, content: str) -> MailMessage:
        message = MailMessage(sender=sender, recipient=recipient, content=content)
        self.mailbox.send(message)
        return message

    def complete_task(self, task_id: str) -> SwarmTask:
        return self.board.complete(task_id)

    def converged(self) -> bool:
        return self.detector.is_converged(self.board.list_tasks())

    async def execute_pending_tasks(self, objective: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        tasks = self.create_swarm(objective)
        agents = self.spawn_manager.spawn(len(tasks))
        assigned: list[SwarmTask] = []
        for index, task in enumerate(tasks):
            agent_id = agents[index % len(agents)] if agents else "agent_1"
            assigned.append(self.board.assign(task.task_id, agent_id))
        for index, task in enumerate(assigned):
            agent_id = task.assigned_to or "agent_1"
            result = await self.runtime.run_simple(
                AgentSpec(role=AgentRole.WORKER, name=agent_id),
                workflow_id=f"swarm_{objective[:24]}",
                task_id=task.task_id,
                session_id="swarm_session",
                query=task.content,
            )
            self.complete_task(task.task_id)
            self.mailbox.send(
                MailMessage(
                    sender=agent_id,
                    recipient=self.lead.agent_id,
                    content=result.output or "",
                    metadata={"task_id": task.task_id, "index": index},
                )
            )
            results.append(result.model_dump(mode="json"))
        self.workspace.publish("results", results)
        return results
