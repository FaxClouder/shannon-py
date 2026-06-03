from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowMode(StrEnum):
    AUTO = "auto"
    SIMPLE = "simple"
    REACT = "react"
    DAG = "dag"
    RESEARCH = "research"


class WorkflowRoute(BaseModel):
    selected_mode: WorkflowMode
    complexity_score: float = Field(ge=0.0, le=1.0)
    reason: str


class ComplexityAnalyzer:
    def score(self, query: str, context: dict[str, Any]) -> float:
        if context.get("force_research") is True:
            return 0.9
        if context.get("force_dag") is True:
            return 0.7

        score = 0.1
        if len(query) > 240:
            score += 0.2
        if any(separator in query for separator in [";", "\n"]):
            score += 0.3
        if any(keyword in query.lower() for keyword in ["research", "compare", "plan", "analyze"]):
            score += 0.2
        return min(score, 1.0)


class StrategySelector:
    def select(
        self,
        requested_mode: WorkflowMode,
        complexity_score: float,
        context: dict[str, Any],
    ) -> WorkflowMode:
        if requested_mode != WorkflowMode.AUTO:
            return requested_mode
        if context.get("force_research") is True:
            return WorkflowMode.RESEARCH
        if context.get("force_dag") is True:
            return WorkflowMode.DAG
        if complexity_score < 0.3:
            return WorkflowMode.SIMPLE
        return WorkflowMode.DAG


class WorkflowRouter:
    def __init__(
        self,
        analyzer: ComplexityAnalyzer | None = None,
        selector: StrategySelector | None = None,
    ) -> None:
        self._analyzer = analyzer or ComplexityAnalyzer()
        self._selector = selector or StrategySelector()

    def route(
        self,
        query: str,
        requested_mode: WorkflowMode,
        context: dict[str, Any],
    ) -> WorkflowRoute:
        complexity_score = self._analyzer.score(query, context)
        selected_mode = self._selector.select(requested_mode, complexity_score, context)
        return WorkflowRoute(
            selected_mode=selected_mode,
            complexity_score=complexity_score,
            reason=f"selected {selected_mode} with complexity {complexity_score:.2f}",
        )
