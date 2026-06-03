from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SHANNON_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Shannon-py"
    environment: str = "local"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    testing: bool = False

    default_provider: str = "mock"
    default_model: str = "mock-default"

    enable_shell_tools: bool = False
    max_input_chars: int = Field(default=100_000, ge=1)
    default_tool_timeout_seconds: int = Field(default=30, ge=1)
    task_timeout_seconds: int = Field(default=600, ge=1)
    max_agent_loops: int = Field(default=15, ge=1)
    max_tool_calls: int = Field(default=20, ge=0)
    sandbox_workspace_root: str = ".sandbox-workspaces"
    python_exec_timeout_seconds: int = Field(default=5, ge=1)
    python_exec_max_output_chars: int = Field(default=20_000, ge=1)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Settings":
        config_path = Path(path)
        if not config_path.exists():
            return cls()

        with config_path.open("r", encoding="utf-8") as file:
            data: dict[str, Any] = yaml.safe_load(file) or {}
        return cls(**data)


@lru_cache
def get_settings() -> Settings:
    return Settings()
