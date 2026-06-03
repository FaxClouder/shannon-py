from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from shannon_py.application.tasks import TaskHandle, TaskRequest, TaskResult
from shannon_py.memory.session import Session
from shannon_py.orchestration.checkpoints import WorkflowCheckpoint
from shannon_py.policy import ApprovalRequest
from shannon_py.streaming.events import StreamEvent
from shannon_py.tools import ToolResult, ToolSpec


class HealthResponse(BaseModel):
    status: str = Field(description="Service health status.")
    service: str = Field(description="Configured service name.")
    environment: str = Field(description="Runtime environment name.")
    version: str = Field(description="Application version.")


class ToolExecuteRequest(BaseModel):
    arguments: dict[str, object] = Field(default_factory=dict)
    approved: bool = False


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


@router.post("/api/v1/tasks/{task_id}/cancel", response_model=TaskResult, tags=["tasks"])
async def cancel_task(task_id: str, request: Request) -> TaskResult:
    task_service = request.app.state.task_service
    result = await task_service.cancel(task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return result


@router.get("/api/v1/sessions/{session_id}", response_model=Session, tags=["sessions"])
async def get_session(session_id: str, request: Request) -> Session:
    task_service = request.app.state.task_service
    return await task_service.get_session(session_id)


@router.get(
    "/api/v1/checkpoints/{workflow_id}",
    response_model=list[WorkflowCheckpoint],
    tags=["checkpoints"],
)
async def list_workflow_checkpoints(
    workflow_id: str,
    request: Request,
) -> list[WorkflowCheckpoint]:
    task_service = request.app.state.task_service
    return await task_service.list_checkpoints(workflow_id)


@router.get(
    "/api/v1/checkpoints/{workflow_id}/latest",
    response_model=WorkflowCheckpoint,
    tags=["checkpoints"],
)
async def get_latest_workflow_checkpoint(
    workflow_id: str,
    request: Request,
) -> WorkflowCheckpoint:
    task_service = request.app.state.task_service
    checkpoint = await task_service.get_latest_checkpoint(workflow_id)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found.")
    return checkpoint


@router.get("/api/v1/tools", response_model=list[ToolSpec], tags=["tools"])
async def list_tools(request: Request) -> list[ToolSpec]:
    tool_service = request.app.state.tool_service
    return await tool_service.list_tools()


@router.post("/api/v1/tools/{tool_name}/execute", response_model=ToolResult, tags=["tools"])
async def execute_tool(
    tool_name: str,
    tool_request: ToolExecuteRequest,
    request: Request,
) -> ToolResult:
    tool_service = request.app.state.tool_service
    arguments = dict(tool_request.arguments)
    arguments["approved"] = tool_request.approved
    return await tool_service.execute(tool_name, arguments)


@router.get("/api/v1/approvals", response_model=list[ApprovalRequest], tags=["approvals"])
async def list_approvals(request: Request) -> list[ApprovalRequest]:
    tool_service = request.app.state.tool_service
    return await tool_service.list_approvals()


@router.get(
    "/api/v1/stream/events/{workflow_id}",
    response_model=list[StreamEvent],
    tags=["stream"],
)
async def list_workflow_events(workflow_id: str, request: Request) -> list[StreamEvent]:
    task_service = request.app.state.task_service
    return await task_service.list_events(workflow_id)


@router.get("/api/v1/stream/sse", tags=["stream"])
async def stream_workflow_events(
    workflow_id: str,
    request: Request,
    last_event_id: str | None = None,
    live: bool = True,
    idle_timeout_seconds: float = 30.0,
) -> StreamingResponse:
    task_service = request.app.state.task_service
    return StreamingResponse(
        task_service.stream_sse(
            workflow_id,
            last_event_id=last_event_id,
            live=live,
            idle_timeout_seconds=idle_timeout_seconds,
        ),
        media_type="text/event-stream",
    )
