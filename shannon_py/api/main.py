from fastapi import FastAPI

from shannon_py.agent import AgentRuntime
from shannon_py.api.routes import router
from shannon_py.application.chat import ChatCompletionService
from shannon_py.application.tasks import InMemoryTaskRepository, TaskService
from shannon_py.application.tools import ToolService
from shannon_py.config import Settings, get_settings
from shannon_py.llm.providers import MockProvider
from shannon_py.memory.session import InMemorySessionRepository
from shannon_py.observability import InMemoryTracer, RunRecorder
from shannon_py.observability.logging import configure_logging
from shannon_py.observability.metrics import InMemoryMetricsRegistry
from shannon_py.orchestration.checkpoints import InMemoryCheckpointManager
from shannon_py.orchestration.dag_graph import DAGGraph
from shannon_py.orchestration.react_graph import ReactGraph
from shannon_py.orchestration.research_graph import ResearchGraph
from shannon_py.orchestration.router import WorkflowRouter
from shannon_py.orchestration.simple_graph import SimpleGraph
from shannon_py.policy import InMemoryApprovalGate, PolicyEngine
from shannon_py.sandbox.python_worker import PythonSandboxWorker
from shannon_py.sandbox.workspace import WorkspaceManager
from shannon_py.streaming.events import InMemoryEventBus
from shannon_py.streaming.sse import SSEBroker
from shannon_py.swarm import SwarmCoordinator
from shannon_py.tools import CalculatorTool, PythonExecTool, ToolExecutor, ToolRegistry


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.settings = resolved_settings
    metrics = InMemoryMetricsRegistry()
    run_recorder = RunRecorder()
    tracer = InMemoryTracer()
    event_bus = InMemoryEventBus()
    policy_engine = PolicyEngine(max_input_chars=resolved_settings.max_input_chars)
    approval_gate = InMemoryApprovalGate()
    tool_registry = ToolRegistry()
    tool_registry.register(CalculatorTool())
    workspace_manager = WorkspaceManager(resolved_settings.sandbox_workspace_root)
    python_worker = PythonSandboxWorker(
        workspace_manager=workspace_manager,
        timeout_seconds=resolved_settings.python_exec_timeout_seconds,
        max_output_chars=resolved_settings.python_exec_max_output_chars,
    )
    tool_registry.register(PythonExecTool(python_worker))
    tool_executor = ToolExecutor(tool_registry)
    mock_provider = MockProvider(model=resolved_settings.default_model)
    agent_runtime = AgentRuntime(
        provider=mock_provider,
        tool_executor=tool_executor,
    )
    app.state.tool_service = ToolService(
        tool_registry,
        tool_executor,
        policy_engine,
        approval_gate,
        metrics,
        run_recorder,
        tracer,
    )
    app.state.chat_service = ChatCompletionService(mock_provider)
    simple_graph = SimpleGraph(mock_provider, runtime=agent_runtime)
    react_graph = ReactGraph(tool_executor, runtime=agent_runtime)
    dag_graph = DAGGraph(SimpleGraph(mock_provider, runtime=agent_runtime))
    research_graph = ResearchGraph(mock_provider, runtime=agent_runtime)
    app.state.task_service = TaskService(
        repository=InMemoryTaskRepository(),
        simple_graph=simple_graph,
        react_graph=react_graph,
        dag_graph=dag_graph,
        research_graph=research_graph,
        workflow_router=WorkflowRouter(),
        session_repository=InMemorySessionRepository(),
        event_bus=event_bus,
        checkpoint_manager=InMemoryCheckpointManager(),
        sse_broker=SSEBroker(event_bus),
        policy_engine=policy_engine,
        metrics=metrics,
        run_recorder=run_recorder,
        tracer=tracer,
    )
    app.state.agent_runtime = agent_runtime
    app.state.swarm_coordinator = SwarmCoordinator(runtime=agent_runtime)
    app.state.metrics = metrics
    app.state.run_recorder = run_recorder
    app.state.tracer = tracer
    app.include_router(router)
    return app


app = create_app()
