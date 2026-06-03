from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from shannon_py.application.tasks import TaskHandle, TaskRequest, TaskResult


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
async def submit_task(task_request: TaskRequest, request: Request) -> TaskHandle:
    task_service = request.app.state.task_service
    return await task_service.submit(task_request)


@router.get("/api/v1/tasks/{task_id}", response_model=TaskResult, tags=["tasks"])
async def get_task(task_id: str, request: Request) -> TaskResult:
    task_service = request.app.state.task_service
    result = await task_service.get_result(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return result
