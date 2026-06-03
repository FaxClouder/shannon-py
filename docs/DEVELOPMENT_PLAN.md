# 全 Python 版 Shannon 开发计划

## 1. 项目目标

本项目在 `D:\WorkSpace\Shannon-py` 中独立实现一个全 Python agent 平台内核，参考 Shannon 的设计思想和架构编排，但不迁移 Go/Rust 服务，也不在 `D:\WorkSpace\Shannon-main` 中继续开发。

核心目标是构建一个模块边界清晰、可测试、可扩展的 Python 版本 Shannon：

- 用 FastAPI 提供任务、流式事件、会话、工具、模型和健康检查接口。
- 用 LangGraph 表达 Simple、ReAct、DAG、Research、Swarm 等编排策略。
- 用 LangChain-compatible 工具接口管理内置工具、MCP 工具、OpenAPI 工具和后续扩展工具。
- 用 PostgreSQL、Redis、Qdrant 支撑任务状态、事件流、会话记忆和语义记忆。
- 用独立 sandbox worker 承载 Python 代码执行，避免在 API 进程中直接执行不可信代码。
- 用 pytest 建立从单元测试到端到端测试的基础回归集。

第一阶段优先交付 Simple 和 ReAct 可用内核；Swarm、深度 Research、OPA 兼容和完整 replay 在基础稳定后再推进。

## 2. 技术栈

默认技术栈如下：

- API 服务：FastAPI、uvicorn
- 数据模型：Pydantic、pydantic-settings
- 工作流编排：LangGraph `StateGraph` 与 checkpoint
- 工具接口：LangChain-compatible tool registry，优先兼容 `langchain-core`
- 模型接入：OpenAI、Anthropic、LiteLLM、OpenAI-compatible provider、MockProvider
- 数据库：PostgreSQL、SQLAlchemy async、asyncpg、Alembic
- 缓存与事件流：Redis
- 向量数据库：Qdrant
- HTTP 客户端：httpx、tenacity
- 配置与模板：PyYAML、Jinja2
- 可观测性：prometheus-client、OpenTelemetry
- 测试：pytest、pytest-asyncio

Python 版本要求为 `>=3.11,<3.15`，不要使用 Python 3.14 专属语法。

## 3. 目标目录结构

```text
D:\WorkSpace\Shannon-py
  pyproject.toml
  README.md
  .env.example
  alembic.ini
  AGENTS.md
  docs/
    DEVELOPMENT_PLAN.md
  shannon_py/
    api/
    application/
    orchestration/
    agent/
    llm/
    tools/
    sandbox/
    memory/
    streaming/
    persistence/
    policy/
    templates/
    research/
    swarm/
    observability/
    config/
    cli/
  tests/
    unit/
    integration/
    e2e/
  migrations/
  config/
    models.yaml
    features.yaml
    roles/
    templates/
```

## 4. 模块职责

### `api`

API 接入层，包含任务、流式响应、会话、工具、模型、健康检查和 OpenAI 兼容接口。

职责：

- 接收 HTTP 请求并做基础参数校验。
- 调用 `application` 层服务，不直接执行业务逻辑。
- 暴露 Shannon-style API 和 OpenAI-compatible API。

第一版接口：

- `POST /api/v1/tasks`
- `POST /api/v1/tasks/stream`
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/tasks/{task_id}/cancel`
- `GET /api/v1/stream/sse?workflow_id=...`
- `GET /api/v1/sessions/{session_id}`
- `GET /api/v1/tools`
- `POST /api/v1/tools/{tool_name}/execute`
- `GET /health`

### `application`

应用用例层，包含 `TaskService`、`WorkflowService`、`SessionService`、`ToolService`、`ApprovalService`、`ScheduleService`。

职责：

- 统一任务创建、任务状态变更、工作流启动、会话读写、工具调用。
- 屏蔽 API 层和底层编排、存储、工具之间的细节。
- 维护任务生命周期：`queued`、`running`、`completed`、`failed`、`cancelled`、`paused`。

### `orchestration`

编排层，基于 LangGraph 实现 Shannon-style 多策略工作流。

组件：

- `WorkflowRouter`
- `ComplexityAnalyzer`
- `StrategySelector`
- `GraphFactory`
- `SimpleGraph`
- `ReactGraph`
- `DAGGraph`
- `ResearchGraph`
- `SwarmGraph`
- `SynthesisGraph`
- `CheckpointManager`

默认路由规则：

- 显式 `mode=simple` 使用 `SimpleGraph`。
- 显式 `mode=react` 使用 `ReactGraph`。
- `context.force_research=true` 使用 `ResearchGraph`。
- `context.force_swarm=true` 使用 `SwarmGraph`。
- 复杂度 `<0.3` 使用 `SimpleGraph`。
- 其他情况默认使用 `DAGGraph`。

### `agent`

智能体运行时层，定义 agent 的最小运行单元。

组件：

- `AgentRuntime`
- `AgentState`
- `AgentLoop`
- `AgentRole`
- `AgentMailbox`
- `AgentWorkspace`
- `AgentResult`
- `AgentPolicy`

`AgentState` 必须包含：

- `workflow_id`
- `task_id`
- `agent_id`
- `session_id`
- `query`
- `messages`
- `context`
- `selected_tools`
- `tool_calls`
- `observations`
- `final_response`
- `token_usage`
- `status`
- `metadata`

第一版 action：

- `tool_call`
- `final_answer`
- `request_clarification`
- `error`

Swarm 阶段再扩展：

- `send_message`
- `publish_data`
- `claim_task`
- `complete_task`
- `spawn_agent`
- `idle`

### `llm`

模型层，统一管理 provider、模型路由、token 统计和费用计算。

组件：

- `ProviderManager`
- `LLMProvider`
- `MockProvider`
- `OpenAIProvider`
- `AnthropicProvider`
- `LiteLLMProvider`
- `OpenAICompatibleProvider`
- `ModelRegistry`
- `TokenCounter`
- `CostCalculator`

Provider 选择优先级：

1. 请求中的 `provider/model`
2. `context.model_override`
3. `model_tier`
4. 环境变量默认 provider
5. 测试模式下使用 `MockProvider`

### `tools`

工具层，负责工具注册、工具选择、工具执行和结果标准化。

组件：

- `ToolRegistry`
- `ToolExecutor`
- `ToolSelector`
- `ToolPermissionManager`
- `ToolResultFormatter`
- `BuiltinTools`
- `MCPToolAdapter`
- `OpenAPIToolAdapter`
- `LangChainToolAdapter`

第一批内置工具：

- `calculator`
- `web_search`
- `web_fetch`
- `file_read`
- `file_write`
- `session_file`
- `python_exec`

所有工具必须声明：

- `name`
- `description`
- `args_schema`
- `permissions`
- `dangerous`
- `timeout_seconds`

工具返回统一 `ToolResult`：`success`、`content`、`artifact_refs`、`metadata`、`error`。

### `sandbox`

沙箱层，负责不可信代码执行和文件访问隔离。

组件：

- `SandboxManager`
- `WorkspaceManager`
- `SandboxWorker`
- `ResourceLimiter`
- `FileGuard`
- `CommandGuard`
- `ArtifactStore`

默认策略：

- `python_exec` 只能通过独立 sandbox worker 执行。
- 禁止在 API 进程中直接执行用户代码。
- 第一版默认禁用 shell 执行。
- 文件访问只能发生在 session workspace 内。
- 必须限制 wall time、CPU time、内存、输出大小和文件大小。

### `memory`

记忆层，负责会话记忆、语义记忆、摘要记忆和上下文压缩。

组件：

- `SessionMemory`
- `ConversationStore`
- `SemanticMemory`
- `SummaryMemory`
- `UserMemory`
- `MemoryRetriever`
- `MemoryWriter`
- `ContextCompressor`

演进阶段：

1. 会话历史。
2. 上下文压缩。
3. Qdrant 语义检索。
4. supervisor memory：分解模式、策略表现、失败模式。

### `streaming`

事件流层，负责事件发布、SSE、WebSocket、事件持久化和调试时间线。

组件：

- `EventBus`
- `SSEBroker`
- `WebSocketBroker`
- `EventStore`
- `EventSerializer`
- `TimelineBuilder`

事件类型：

- `WORKFLOW_STARTED`
- `WORKFLOW_COMPLETED`
- `WORKFLOW_FAILED`
- `AGENT_STARTED`
- `AGENT_COMPLETED`
- `AGENT_FAILED`
- `LLM_PARTIAL`
- `LLM_OUTPUT`
- `TOOL_INVOKED`
- `TOOL_OBSERVATION`
- `TOOL_ERROR`
- `APPROVAL_REQUESTED`
- `APPROVAL_DECIDED`
- `STREAM_END`

持久化规则：

- Redis 保存全部近期实时事件。
- PostgreSQL 只保存关键事件。
- `LLM_PARTIAL` 不写 PostgreSQL。
- SSE 必须支持 `last_event_id` 续传。

### `persistence`

持久化层，隔离所有数据库访问。

组件：

- `Database`
- `TaskRepository`
- `SessionRepository`
- `MessageRepository`
- `AgentExecutionRepository`
- `ToolExecutionRepository`
- `TokenUsageRepository`
- `EventRepository`
- `ApprovalRepository`
- `ArtifactRepository`
- `MigrationManager`

Repository 返回领域模型，不向上层泄漏 ORM 对象。

### `policy`

策略层，负责预算、限流、熔断、审批和输入输出校验。

组件：

- `PolicyEngine`
- `BudgetManager`
- `RateLimiter`
- `CircuitBreaker`
- `ApprovalGate`
- `InputValidator`
- `OutputFilter`

默认限制：

- 每个 task 最多 15 次 agent loop。
- 每个 task 最多 20 次 tool call。
- 每个工具默认 timeout 30 秒。
- 每个 task 默认 timeout 10 分钟。
- 危险工具默认需要 approval。
- 输入默认最大 100k characters，附件另设限制。

### `templates`

模板层，管理角色模板、工作流模板和结果合成模板。

组件：

- `PromptRegistry`
- `RoleRegistry`
- `WorkflowTemplateRegistry`
- `SynthesisTemplateRegistry`
- `TemplateRenderer`
- `TemplateValidator`

第一版模板格式使用 YAML 与 Jinja2。

### `research`

研究工作流模块，供 `ResearchGraph` 调用。

组件：

- `ResearchPlanner`
- `QueryExpander`
- `SourceCollector`
- `CitationManager`
- `ClaimVerifier`
- `ResearchSynthesizer`

第一版做 basic research；第二版再做 deep research 和 domain discovery。

### `swarm`

群体智能模块，后续实现 Shannon-style swarm。

组件：

- `LeadAgent`
- `SwarmCoordinator`
- `TaskBoard`
- `Mailbox`
- `SharedWorkspace`
- `ConvergenceDetector`
- `DynamicSpawnManager`

Swarm 不进入第一版 MVP。

### `observability`

可观测性层，负责日志、指标、链路追踪、运行记录和调试时间线。

组件：

- `Logger`
- `Metrics`
- `Tracer`
- `RunRecorder`
- `DebugTimeline`
- `ReplayExporter`

第一版指标：

- task 数量、耗时、状态。
- LLM 调用次数、tokens、费用。
- tool 调用次数、耗时、错误。
- 当前活跃 workflow 数。
- 事件投递延迟。

### `config`

配置层，统一环境变量、YAML 配置、功能开关、模型配置、工具配置和策略配置。

组件：

- `Settings`
- `ConfigLoader`
- `FeatureFlags`
- `ModelConfig`
- `ToolConfig`
- `PolicyConfig`

配置优先级：request override > env > YAML > default。

业务模块不得直接读取环境变量。

### `cli`

命令行入口，服务本地开发和维护。

组件：

- `serve`
- `migrate`
- `worker`
- `submit`
- `replay`
- `tools`

第一版提供 `serve`、`migrate`、`submit`。

## 5. 公开接口与核心类型

核心公开类型：

- `TaskRequest`
- `TaskHandle`
- `TaskStatus`
- `TaskResult`
- `AgentState`
- `AgentSpec`
- `ToolSpec`
- `ToolCall`
- `ToolResult`
- `StreamEvent`
- `TokenUsage`
- `Session`
- `ConversationMessage`
- `ApprovalRequest`
- `WorkflowCheckpoint`

核心扩展接口：

- `LLMProvider.complete(...)`
- `LLMProvider.stream(...)`
- `ShannonTool.ainvoke(...)`
- `WorkflowGraph.build(...)`
- `PolicyRule.evaluate(...)`
- `MemoryRetriever.retrieve(...)`
- `EventBus.publish(...)`

API response 字段尽量沿用 Shannon 风格：`task_id`、`workflow_id`、`session_id`、`status`、`result`、`metadata`、`error`。

## 6. 开发里程碑

### 里程碑 1：项目骨架

交付内容：

- 正式 `pyproject.toml`
- `README.md`
- `.env.example`
- FastAPI app
- config 与 logging
- health route
- pytest 基础配置

验收标准：

- 服务可从 `D:\WorkSpace\Shannon-py` 启动。
- 无外部服务时基础测试可运行。

当前状态（2026-06-03）：已完成基础交付。

已落地内容：

- `pyproject.toml` 已替换为正式项目配置，Python 版本范围调整为 `>=3.11,<3.15`。
- 已新增 `README.md`、`.env.example`、`.gitignore`。
- 已创建 `shannon_py` 包和 `api`、`application`、`orchestration`、`agent`、`llm`、`tools`、`sandbox`、`memory`、`streaming`、`persistence`、`policy`、`templates`、`research`、`swarm`、`observability`、`config`、`cli` 基础模块目录。
- 已实现 FastAPI 应用工厂、基础日志初始化、配置层和 `/health` 健康检查接口。
- 已添加 pytest 基础测试：配置默认值测试和 health route 测试。
- 已创建 `tests/unit`、`tests/integration`、`tests/e2e`、`migrations`、`config/roles`、`config/templates` 入口。

验证记录：

- 已使用 Codex 内置 Python `3.12.13` 安装项目开发依赖并执行 `pytest`，结果为 `2 passed`。
- 已执行 `ruff check .`，结果为 `All checks passed!`。
- 当前机器 PATH 中没有可用 `python` 或 `py` 命令；现有 `.venv\Scripts\python.exe` 无法创建进程，且按项目约束未重建 `.venv`。
- 后续本地开发前建议先恢复项目 `.venv` 或配置可用 Python，再运行 `pytest` 和 `uvicorn shannon_py.api.main:app`。

uv 验证记录：

- 系统已安装 `uv 0.11.16`。
- 默认 uv 缓存和 Python 安装目录可能访问用户目录；在沙箱内已通过 `UV_CACHE_DIR=.uv-cache`、`UV_PYTHON_INSTALL_DIR=.uv-python`、`UV_PROJECT_ENVIRONMENT=.uv-verify-venv` 将相关路径限制在项目内。
- 已使用 Codex 内置 Python `3.12.13` 执行 `uv sync --python <python.exe> --extra dev`，成功解析并安装 31 个包，生成 `uv.lock`。
- 已执行 `uv run pytest`，结果为 `2 passed`。

GitHub 版本管理记录：

- 已初始化本地 Git 仓库，主分支为 `main`。
- 已绑定远端仓库 `origin`：`https://github.com/FaxClouder/shannon-py.git`。
- GitHub 仓库地址：`https://github.com/FaxClouder/shannon-py`。
- 已完成首轮项目骨架上传，远端 `origin/main` 与本地 `main` 对齐。
- 当前 GitHub CLI 授权账号应为 `FaxClouder`；推送前可用 `gh auth status` 验证。
- 本地忽略规则已覆盖 `.env`、`.venv`、`.idea`、`.uv-cache`、`.uv-python`、`.uv-verify-venv`、缓存、日志、本地数据库文件和临时产物。

### 里程碑 2：任务 MVP

交付内容：

- task submit/query
- in-memory repository
- `MockProvider`
- `SimpleGraph`

验收标准：

- `POST /api/v1/tasks` 可返回 mock result。
- task 状态能从 `queued` 进入 `completed` 或 `failed`。

当前状态（2026-06-03）：已完成最小可用链路。

已落地内容：

- 已修复 `README.md` 中文乱码，恢复为 UTF-8 中文说明。
- 已实现 `TaskRequest`、`TaskHandle`、`TaskStatus`、`TaskResult` 等任务核心类型。
- 已新增 `InMemoryTaskRepository`，支持任务创建、查询和状态更新。
- 已新增 `TaskService`，负责提交任务、执行 Simple 工作流并保存结果。
- 已实现 `MockProvider`，无外部 API key 时可返回稳定 mock 响应。
- 已实现 `SimpleGraph`，通过统一 provider 接口完成单次模型调用。
- 已新增 `POST /api/v1/tasks` 和 `GET /api/v1/tasks/{task_id}`。
- 已补充任务服务和任务 API 测试。
- 已将 `TaskService.submit` 调整为只创建 `queued` 任务，任务执行通过 `run_task` 单独推进到 `running`、`completed` 或 `failed`。
- API 层已通过 FastAPI `BackgroundTasks` 触发任务执行，提交接口返回任务句柄，查询接口读取当前结果。
- 已将 `TaskRequest.mode` 收紧为枚举，仅支持 `simple` 和 `react`。
- 已新增 `POST /api/v1/tasks/{task_id}/cancel`，queued 任务可进入 `cancelled` 状态。
- 已新增 in-memory session history 基础，同一 `session_id` 的后续任务可读取前序 user/assistant 消息。
- 已新增 in-memory event bus 基础，任务执行会发布 `workflow_started`、`llm_output`、`workflow_completed`、`workflow_failed` 和 `stream_end` 等事件。
- 已新增 `GET /api/v1/stream/events/{workflow_id}`，作为 SSE 落地前的事件调试查询入口。

验证记录：

- 已执行 `uv run pytest`，结果为 `23 passed`。
- 已执行 `uv run ruff check .`，结果为 `All checks passed!`。
- pytest 当前仍有 FastAPI TestClient 依赖链的 `StarletteDeprecationWarning`，不影响当前 MVP 功能。

### 里程碑 3：会话与 checkpoint

交付内容：

- session history
- LangGraph checkpoint manager
- PostgreSQL repository

验收标准：

- 同一个 `session_id` 可连续多轮对话。
- checkpoint 可按 `workflow_id` 查询。

当前状态（2026-06-03）：已完成 in-memory 基础。

已落地内容：

- 已新增 `Session` 与 `ConversationMessage` 基础模型。
- 已新增 `InMemorySessionRepository`，支持同一 `session_id` 的消息追加和查询。
- 已新增 `WorkflowCheckpoint` 与 `InMemoryCheckpointManager`。
- `TaskService` 已在任务进入 `running`、`completed`、`failed` 时保存 checkpoint。
- 已新增 `GET /api/v1/sessions/{session_id}` 查询会话消息。
- 已新增 `GET /api/v1/checkpoints/{workflow_id}` 查询 workflow checkpoint 列表。
- 已新增 `GET /api/v1/checkpoints/{workflow_id}/latest` 查询最新 checkpoint。

验证记录：

- 已执行 `uv run pytest`，结果为 `10 passed`。
- 已执行 `uv run ruff check .`，结果为 `All checks passed!`。
- PostgreSQL repository 和 LangGraph 原生 checkpoint 仍未接入，当前为 MVP in-memory 实现。

### 里程碑 4：事件流

交付内容：

- `EventBus`
- `SSEBroker`
- Redis event stream
- event ordering tests

验收标准：

- SSE 可收到 started、partial/output、completed、stream_end。
- SSE 断线后可用 `last_event_id` resume。

当前状态（2026-06-03）：已完成 in-memory SSE 基础。

已落地内容：

- 已新增 `SSEBroker` 和 SSE 事件序列化函数。
- `InMemoryEventBus` 已支持按 `last_event_id` 查询后续事件。
- 已新增 `GET /api/v1/stream/sse?workflow_id=...&last_event_id=...`。
- 当前 SSE 会 replay 已持久在内存中的 workflow 事件，事件包括 `workflow_started`、`llm_output`、`workflow_completed`、`workflow_failed` 和 `stream_end`。
- `SSEBroker` 已支持 live 模式，会等待后续事件并在 `stream_end` 后关闭。
- 已补充 SSE 序列化、resume 和 API 响应测试。

验证记录：

- 已执行 `uv run pytest`，结果为 `23 passed`。
- 已执行 `uv run ruff check .`，结果为 `All checks passed!`。
- Redis event stream、断线续传持久化和 `LLM_PARTIAL` 仍未接入，当前为 MVP in-memory 实现。

### 里程碑 5：工具与 ReAct

交付内容：

- `ToolRegistry`
- `calculator`
- `web_search` mock/live adapter
- `ReactGraph`

验收标准：

- ReAct 任务能调用 calculator。
- 工具失败会进入 observation，不直接崩溃 workflow。

当前状态（2026-06-03）：已完成 calculator 与最小 ReAct 链路。

已落地内容：

- 已新增 `ToolSpec`、`ToolResult`、`ToolRegistry`、`ToolExecutor` 和 `ToolService`。
- 已新增 `CalculatorTool`，通过 AST 白名单解析基础算术表达式，不执行任意 Python。
- 已新增 `GET /api/v1/tools` 和 `POST /api/v1/tools/{tool_name}/execute`。
- 已新增 `ReactGraph`，当前支持通过 `calculator` 处理 `mode=react` 的基础算术任务。
- `TaskService` 已支持 `mode=simple` 和 `mode=react` 路由。
- ReAct 任务执行会发布 `tool_invoked`、`tool_observation` 或 `tool_error` 事件。
- 已补充工具层、ReactGraph 服务链路和工具 API 测试。

验证记录：

- 已执行 `uv run pytest`，结果为 `23 passed`。
- 已执行 `uv run ruff check .`，结果为 `All checks passed!`。
- 当前 ReAct 仍是 MVP 规则路由，尚未实现 LLM 驱动的多轮 action/observation loop。

### 里程碑 6：沙箱

交付内容：

- session workspace
- isolated Python worker
- file guard
- `python_exec`

验收标准：

- 代码执行不在 API 进程内发生。
- 路径穿越被拒绝。
- timeout、输出过大、内存过大可控失败。

### 里程碑 7：DAG 与 Research

交付内容：

- `ComplexityAnalyzer`
- `StrategySelector`
- `DAGGraph`
- `ResearchGraph`
- synthesis templates

验收标准：

- 复杂任务可拆分为多个 agent task。
- DAG 支持 parallel fan-out 和 synthesis fan-in。
- research 输出包含 source metadata。

### 里程碑 8：策略与审批

交付内容：

- `BudgetManager`
- `RateLimiter`
- `CircuitBreaker`
- `ApprovalGate`
- task pause/resume/cancel

验收标准：

- token/tool/timeout 超限会停止 workflow。
- dangerous tool 可触发 approval。
- pause/resume/cancel 影响运行中的 graph。

### 里程碑 9：Swarm

交付内容：

- `LeadAgent`
- `TaskBoard`
- `Mailbox`
- `SharedWorkspace`
- `DynamicSpawnManager`
- `ConvergenceDetector`

验收标准：

- Lead 能分配任务。
- agent 能互发消息和发布 findings。
- swarm 能收敛并生成最终答案。

### 里程碑 10：生产加固

交付内容：

- OpenAI-compatible API
- metrics
- tracing
- e2e tests
- deployment docs

验收标准：

- 支持基础生产部署。
- 核心接口有回归测试。
- 常见失败路径有明确错误和事件记录。

## 7. 测试计划

单元测试：

- config loading
- provider selection
- mock provider
- model registry
- token/cost accounting
- tool schema validation
- tool execution result shape
- policy decisions
- budget accounting
- event serialization
- repository CRUD

集成测试：

- simple task
- streaming simple task
- session continuity
- ReAct calculator
- tool failure observation
- file workspace isolation
- sandbox timeout
- PostgreSQL persistence
- Redis SSE resume
- Qdrant semantic memory smoke test

端到端测试：

- no API key mock mode
- OpenAI live smoke test
- task cancellation
- task pause/resume
- dangerous tool approval
- DAG fan-out/fan-in
- research with citations
- OpenAI-compatible chat completions
- concurrent simple tasks

第一版可用验收标准：

- `uvicorn shannon_py.api.main:app` 可启动。
- `POST /api/v1/tasks` 可通过 `MockProvider` 返回结果。
- `mode=simple` 和 `mode=react` 都可用。
- 同一个 `session_id` 的连续请求能读取历史。
- SSE 可发出 started、partial/output、completed、stream_end。
- calculator 工具可通过 ReAct 调用。
- 文件工具不能逃逸 session workspace。
- 无外部 API key 时 pytest 通过。

## 8. 默认假设

- 目标目录固定为 `D:\WorkSpace\Shannon-py`。
- `.idea` 保留，不主动修改。
- `.venv` 视为本地环境，不纳入项目维护。
- 当前极简 `pyproject.toml` 后续会在项目骨架阶段替换。
- 不在 `D:\WorkSpace\Shannon-main` 中实现新功能。
- 不依赖 Go/Rust 服务。
- 第一版优先保证模块边界和 Simple/ReAct 基础能力。
- Swarm、deep research、OPA 兼容、完整 replay 在基础稳定后实现。
