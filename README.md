# Shannon-py

`Shannon-py` 是 Shannon 的全 Python 新内核实现。项目目标是在清晰分层的基础上逐步交付任务编排、工具执行、会话记忆、流式事件和安全沙箱能力。

当前阶段是项目骨架与基础服务准备阶段，已包含：

- FastAPI 应用入口。
- 配置层与功能开关默认值。
- 基础日志初始化。
- `/health` 健康检查接口。
- pytest 基础测试入口。

## 本地开发

建议使用项目内虚拟环境或等价隔离环境，不直接依赖全局 Python。

```powershell
python -m pip install -e ".[dev]"
uvicorn shannon_py.api.main:app --reload
```

如果使用 `uv` 管理环境，可执行：

```powershell
uv sync --extra dev
uv run pytest
uv run uvicorn shannon_py.api.main:app --reload
```

在受限环境中，可把 uv 缓存和项目环境指向工作区内的临时目录：

```powershell
$env:UV_CACHE_DIR=".uv-cache"
$env:UV_PROJECT_ENVIRONMENT=".uv-verify-venv"
uv sync --python <python.exe> --extra dev
```

健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

运行测试：

```powershell
pytest
```

## 配置

配置优先级遵循：

```text
request override > env > YAML > default
```

当前基础配置通过 `shannon_py.config.Settings` 管理，环境变量统一使用 `SHANNON_` 前缀。业务模块不得直接读取环境变量。

复制 `.env.example` 可作为本地配置参考，但不要提交真实 `.env`。

## 目录边界

开发工作只应发生在 `D:\WorkSpace\Shannon-py` 内。不要修改 `D:\WorkSpace\Shannon-main`、`.idea` 或重建 `.venv`，除非用户明确要求。
