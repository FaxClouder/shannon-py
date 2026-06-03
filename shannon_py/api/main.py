from fastapi import FastAPI

from shannon_py.api.routes import router
from shannon_py.application.tasks import InMemoryTaskRepository, TaskService
from shannon_py.config import Settings, get_settings
from shannon_py.llm.providers import MockProvider
from shannon_py.observability.logging import configure_logging
from shannon_py.orchestration.simple_graph import SimpleGraph


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
    app.state.task_service = TaskService(
        repository=InMemoryTaskRepository(),
        simple_graph=SimpleGraph(MockProvider(model=resolved_settings.default_model)),
    )
    app.include_router(router)
    return app


app = create_app()
