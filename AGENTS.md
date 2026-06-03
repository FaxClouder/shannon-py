# AGENTS.md

## 项目边界

本文件约束 `D:\WorkSpace\Shannon-py` 下的所有后续开发和维护工作。

必须遵守：

- 只在 `D:\WorkSpace\Shannon-py` 中开发全 Python 版 Shannon。
- 不修改 `D:\WorkSpace\Shannon-main`，除非用户明确要求参考或迁移某个文件。
- 不初始化 Git，除非用户明确要求。
- 不修改 `.idea`，除非用户明确要求调整 IDE 配置。
- 不删除、不重建、不提交 `.venv`；它只是本地虚拟环境。
- 不提交 `.env`、缓存、日志、本地数据库文件、临时产物。

## 语言与命名规范

- 文档、计划、维护说明和复杂注释优先使用中文。
- 代码标识符、模块名、目录名、类名、函数名、API 路径使用英文。
- 避免文档出现前半段中文、后半段全英文的割裂结构。
- 技术名词可保留英文，例如 FastAPI、LangGraph、ToolRegistry、ProviderManager。
- 注释只解释不显然的设计意图，不写机械复述代码行为的注释。

## 架构原则

本项目参考 Shannon 的设计思想，但实现为全 Python 新内核。

必须保持以下分层：

- `api` 只处理 HTTP 接入、参数校验和响应转换，不直接执行业务逻辑。
- `application` 承载用例编排，例如任务提交、工作流启动、会话读写、工具调用。
- `orchestration` 只表达 LangGraph 工作流和策略路由。
- `agent` 只处理单个 agent 的状态、循环、角色、消息和结果。
- `llm` 统一模型 provider 调用，业务模块不得直接调用 provider SDK。
- `tools` 统一工具注册、权限、执行和结果格式。
- `sandbox` 统一不可信代码执行和 workspace 文件访问。
- `memory` 统一会话记忆、语义记忆和上下文压缩。
- `streaming` 统一事件总线、SSE、WebSocket 和事件持久化。
- `persistence` 统一数据库连接、Repository 和 ORM 模型。
- `policy` 统一预算、限流、熔断、审批、输入输出校验。
- `config` 统一环境变量、YAML 配置和功能开关。

禁止跨层捷径：

- API 层不得直接调用 LLM provider。
- API 层不得直接执行工具。
- Graph node 不得直接读取环境变量。
- 工具不得绕过 ToolRegistry 被 agent 直接调用。
- 文件工具不得绕过 sandbox/workspace guard。
- Repository 不得向上层泄漏 ORM 对象。

## 安全规则

默认采用收紧策略：

- 危险工具默认需要 approval。
- `python_exec` 必须通过独立 sandbox worker，不得在 API 进程中执行。
- 第一版默认禁用 shell 执行。
- `file_read`、`file_write`、`session_file` 只能访问 session workspace。
- 必须拒绝路径穿越，例如 `..`、绝对路径逃逸、软链接逃逸。
- 工具必须设置 timeout。
- 工具输出必须限制大小，避免污染上下文或事件流。
- 用户输入进入 prompt 前必须经过基础长度限制和格式校验。
- 任何外部 API key 只能来自配置层，不得写死在代码或测试中。

## 测试要求

新增模块必须配套测试。测试优先级如下：

1. 单元测试覆盖核心纯逻辑。
2. 集成测试覆盖模块协作。
3. 端到端测试覆盖关键用户路径。

核心回归场景：

- Simple task 可通过 `MockProvider` 返回结果。
- ReAct task 可调用 `calculator`。
- session continuity 能跨请求读取历史。
- SSE 能发出 started、partial/output、completed、stream_end。
- tool failure 会转成 observation 或受控失败，不导致服务崩溃。
- 文件工具不能逃逸 session workspace。
- sandbox timeout、输出过大、路径穿越必须可控失败。
- 无外部 API key 时测试必须能通过。

## 依赖管理

- Python 支持范围为 `>=3.11,<3.15`。
- 不使用 Python 3.14 专属语法。
- 不直接依赖全局 Python 环境。
- 依赖通过 `pyproject.toml` 管理。
- 开发依赖和运行依赖分组维护。
- 新增重量级依赖前必须说明用途和替代方案。
- 不把 `.venv` 纳入版本管理。

## 配置规则

配置优先级：request override > env > YAML > default。

必须遵守：

- 业务模块不得直接读取环境变量。
- 所有环境变量通过 `config.Settings` 或等价配置对象访问。
- `.env.example` 只放示例键，不放真实密钥。
- feature flag 必须有默认值。
- 测试必须能在缺少真实 provider key 时使用 `MockProvider`。

## 工作流实现规则

LangGraph 工作流应保持可读、可恢复、可测试。

- 每个 graph 都必须有明确输入和输出状态。
- graph node 应该小而清晰，不混入 API 或存储细节。
- checkpoint 通过统一 `CheckpointManager` 管理。
- SimpleGraph 和 ReactGraph 是第一优先级。
- DAGGraph、ResearchGraph、SwarmGraph 必须建立在稳定的 AgentState 和 ToolRegistry 之上。
- 所有 workflow 必须发布关键事件。

## 工具实现规则

所有工具必须统一经过 `ToolRegistry` 和 `ToolExecutor`。

工具必须声明：

- `name`
- `description`
- `args_schema`
- `permissions`
- `dangerous`
- `timeout_seconds`

工具返回必须符合统一结构：

- `success`
- `content`
- `artifact_refs`
- `metadata`
- `error`

不得让工具直接返回 provider 原始响应给 agent。

## 后续 Agent 工作流

后续维护者或编码 Agent 接手任务时，应按以下顺序工作：

1. 先读本文件 `AGENTS.md`。
2. 再读 `docs/DEVELOPMENT_PLAN.md`。
3. 检查当前目录结构和已有实现。
4. 明确本次任务属于哪个模块。
5. 优先保持既有模块边界，不做无关重构。
6. 修改代码前先确认测试入口。
7. 实现后运行相关测试。
8. 最终说明修改内容、验证结果和未完成风险。

## Git 与版本管理

本项目已启用 Git 版本控制，并绑定 GitHub 远端仓库：

- 本地仓库：`D:\WorkSpace\Shannon-py`
- 主分支：`main`
- 远端：`origin`
- GitHub 仓库：`https://github.com/FaxClouder/shannon-py`
- 当前 GitHub CLI 授权账号应为：`FaxClouder`

维护规则：

- 每次功能开发或文档维护完成后，先运行相关测试，再提交。
- 提交信息使用简洁英文前缀，例如 `chore:`、`feat:`、`fix:`、`docs:`、`test:`。
- 不提交 `.env`、`.venv`、`.idea`、`.uv-cache`、`.uv-python`、`.uv-verify-venv`、缓存、日志、本地数据库文件和临时产物。
- 推送前检查 `git status --short --branch`，确认没有意外文件。
- 如 GitHub 推送失败，先检查 `gh auth status` 是否为 `FaxClouder`，再检查远端地址是否为 `https://github.com/FaxClouder/shannon-py.git`。

推荐验证命令：

```powershell
$env:UV_CACHE_DIR=".uv-cache"
$env:UV_PYTHON_INSTALL_DIR=".uv-python"
$env:UV_PROJECT_ENVIRONMENT=".uv-verify-venv"
uv run pytest
uv run ruff check .
```

## 当前项目阶段

当前阶段是任务 MVP 准备阶段。项目骨架已完成第一轮落地，后续开发应在现有包结构、配置层、FastAPI 应用工厂和测试入口基础上继续推进。

下一步建议按顺序推进：

1. 恢复或准备项目本地 `.venv`；本次已用 Codex 内置 Python 和 `uv` 验证 `pytest` 与 `ruff check .` 通过，但现有 `.venv\Scripts\python.exe` 仍无法创建进程。
2. 实现 `TaskRequest`、`TaskHandle`、`TaskStatus`、`TaskResult` 等任务核心类型。
3. 新增 `TaskService` 和 in-memory task repository。
4. 实现 `MockProvider` 与 `SimpleGraph` 最小链路。
5. 添加 `POST /api/v1/tasks`、`GET /api/v1/tasks/{task_id}` 基础接口和相关测试。
