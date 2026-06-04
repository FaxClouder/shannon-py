from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from shannon_py.agent import AgentRole, AgentRuntime, AgentSpec
from shannon_py.orchestration.simple_graph import SimpleGraph, SimpleGraphInput


class DAGGraphInput(BaseModel):
    task_id: str
    workflow_id: str
    session_id: str
    query: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class DAGGraphOutput(BaseModel):
    output: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DAGGraph:
    def __init__(
        self,
        simple_graph: SimpleGraph,
        runtime: AgentRuntime | None = None,
    ) -> None:
        self._simple_graph = simple_graph
        self._runtime = runtime or simple_graph.runtime

    async def run(self, graph_input: DAGGraphInput) -> DAGGraphOutput:
        steps = _split_steps(graph_input.query)
        result = await self._runtime.run_dag(
            AgentSpec(role=AgentRole.LEAD, name="dag-lead"),
            graph_input.workflow_id,
            graph_input.task_id,
            graph_input.session_id,
            steps,
            graph_input.context,
        )

        if result.status == "completed":
            return DAGGraphOutput(
                output=result.output or "",
                metadata={
                    **result.metadata,
                    "mode": "dag",
                    "step_count": len(steps),
                    "token_usage": result.token_usage,
                },
            )

        outputs: list[str] = []
        for index, step in enumerate(steps, start=1):
            result = await self._simple_graph.run(
                SimpleGraphInput(
                    task_id=graph_input.task_id,
                    workflow_id=graph_input.workflow_id,
                    session_id=graph_input.session_id,
                    query=step,
                    context={**graph_input.context, "dag_step": index},
                )
            )
            outputs.append(f"{index}. {result.output}")

        return DAGGraphOutput(
            output="\n".join(outputs),
            metadata={
                "mode": "dag",
                "step_count": len(steps),
            },
        )


def _split_steps(query: str) -> list[str]:
    separators_normalized = query.replace("\r\n", "\n").replace(";", "\n")
    steps = [step.strip() for step in separators_normalized.split("\n") if step.strip()]
    return steps or [query]
