from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

from shannon_py.application.tasks import TaskHandle, TaskRequest, TaskResult
from shannon_py.streaming.events import StreamEvent


class HealthResponse(BaseModel):
    status: str = Field(description="Service health status.")
    service: str = Field(description="Configured service name.")
    environment: str = Field(description="Runtime environment name.")
    version: str = Field(description="Application version.")


router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.environment,
        version="0.1.0",
    )


@router.post("/api/v1/tasks", response_model=TaskHandle, tags=["tasks"])
async def submit_task(
    task_request: TaskRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> TaskHandle:
    task_service = request.app.state.task_service
    handle = await task_service.submit(task_request)
    background_tasks.add_task(task_service.run_task, handle.task_id)
    return handle


@router.get("/api/v1/tasks/{task_id}", response_model=TaskResult, tags=["tasks"])
async def get_task(task_id: str, request: Request) -> TaskResult:
    task_service = request.app.state.task_service
    result = await task_service.get_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return result


@router.get(
    "/api/v1/stream/events/{workflow_id}",
    response_model=list[StreamEvent],
    tags=["stream"],
)
async def list_workflow_events(workflow_id: str, request: Request) -> list[StreamEvent]:
    task_service = request.app.state.task_service
    return await task_service.list_events(workflow_id)
