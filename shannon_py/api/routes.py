from fastapi import APIRouter, Request
from pydantic import BaseModel, Field


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
