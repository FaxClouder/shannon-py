from fastapi import FastAPI

from shannon_py.api.routes import router
from shannon_py.application.tasks import InMemoryTaskRepository, TaskService
from shannon_py.application.tools import ToolService
from shannon_py.config import Settings, get_settings
from shannon_py.llm.providers import MockProvider
from shannon_py.memory.session import InMemorySessionRepository
from shannon_py.observability.logging import configure_logging
from shannon_py.orchestration.checkpoints import InMemoryCheckpointManager
from shannon_py.orchestration.react_graph import ReactGraph
from shannon_py.orchestration.simple_graph import SimpleGraph
from shannon_py.sandbox.python_worker import PythonSandboxWorker
from shannon_py.sandbox.workspace import WorkspaceManager
from shannon_py.streaming.events import InMemoryEventBus
from shannon_py.streaming.sse import SSEBroker
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
    event_bus = InMemoryEventBus()
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
    app.state.tool_service = ToolService(tool_registry, tool_executor)
    app.state.task_service = TaskService(
        repository=InMemoryTaskRepository(),
        simple_graph=SimpleGraph(MockProvider(model=resolved_settings.default_model)),
        react_graph=ReactGraph(tool_executor),
        session_repository=InMemorySessionRepository(),
        event_bus=event_bus,
        checkpoint_manager=InMemoryCheckpointManager(),
        sse_broker=SSEBroker(event_bus),
    )
    app.include_router(router)
    return app


app = create_app()
