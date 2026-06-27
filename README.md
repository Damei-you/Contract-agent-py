# 财务合同审批 Agent Python 版

本项目是对 `contract-agent-mvp` 的 Python 技术栈重构，目标是构建一个面向财务、法务和业务审批场景的合同审批 Agent MVP。

当前已完成阶段 0-7：项目脚手架、领域模型与数据库表结构、合同/审批记录/制度知识库导入 API、基于 LangChain PGVector 的合同条款/制度知识向量入库、合同/制度双通道 RAG 检索、合同问答 LangGraph workflow、结构化风险检查 LangGraph workflow，以及审批辅助 LangGraph workflow。后续阶段会继续联调前端和补充演示部署能力。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| Web API | FastAPI、Uvicorn |
| 数据校验 | Pydantic v2 |
| 配置 | 环境变量、pydantic-settings |
| ORM | SQLAlchemy 2.x |
| 迁移 | Alembic |
| 数据库 | PostgreSQL，测试阶段可用 SQLite |
| AI/RAG | LangChain、LangGraph、langchain-openai、langchain-postgres |
| 测试 | pytest、FastAPI TestClient |
| 代码质量 | ruff |

## 项目结构

```text
.
├── AGENTS.md                         # Codex 编码与注释规则
├── README.md                         # 项目说明
├── pyproject.toml                    # Python 依赖、测试和 lint 配置
├── alembic.ini                       # Alembic 配置
├── alembic/
│   ├── env.py                        # Alembic 运行环境
│   └── versions/
│       └── 0001_create_business_tables.py
│                                      # 初始业务表迁移
├── app/
│   ├── main.py                       # FastAPI 应用入口
│   ├── api/
│   │   ├── errors.py                 # 全局异常到 HTTP 响应的映射
│   │   └── routes/
│   │       ├── health.py             # 健康检查接口
│   │       ├── contracts.py          # 合同和审批记录导入接口
│   │       └── policies.py           # 制度知识库导入接口
│   ├── core/
│   │   ├── config.py                 # 应用配置
│   │   └── exceptions.py             # 项目级业务异常
│   ├── db/
│   │   ├── models.py                 # SQLAlchemy ORM 模型
│   │   └── session.py                # 数据库 Engine/Session 管理
│   ├── domain/
│   │   ├── enums.py                  # 合同类型、风险等级、审批结论枚举
│   │   └── models.py                 # 领域对象
│   ├── schemas/
│   │   ├── base.py                   # API DTO 基类和 camelCase 配置
│   │   ├── contracts.py              # 合同/审批记录请求响应模型
│   │   └── policies.py               # 制度知识库请求响应模型
│   ├── repositories/
│   │   ├── contracts.py              # 合同、条款、审批记录仓储
│   │   └── policies.py               # 制度知识库仓储
│   ├── services/
│   │   ├── contract_application.py   # 合同应用服务
│   │   ├── contract_approval_assist.py
│   │   │                              # 合同审批辅助应用服务
│   │   ├── contract_qa.py            # 合同问答应用服务
│   │   ├── contract_risk_check.py    # 合同风险检查应用服务
│   │   └── policy_application.py     # 制度知识库应用服务
│   └── ai/
│       ├── langchain_factory.py      # LangChain ChatModel/Embeddings 工厂
│       ├── chains/                   # LangChain prompt 与生成 chain
│       ├── graphs/                   # LangGraph workflow 和 state
│       └── rag/
│           ├── document_mapping.py   # 领域对象到 LangChain Document 的映射
│           ├── ingestion.py          # 向量入库与幂等覆盖写入
│           ├── retrievers.py         # 合同/制度双通道 RAG 检索
│           └── vector_store.py       # PGVector store 与 RAG 组件构建
├── docs/
│   ├── PROJECT_REQUIREMENTS.md       # 需求与实施计划
│   └── CODE_COMMENT_GUIDELINES.md    # 代码注释规范
├── tests/
│   ├── test_approval_assist_api.py   # 审批辅助 API 测试
│   ├── test_approval_assist_workflow.py
│   │                                  # 审批辅助 LangGraph 测试
│   ├── test_contract_qa_api.py       # 合同问答 API 测试
│   ├── test_contract_qa_workflow.py  # 合同问答 LangGraph 测试
│   ├── test_risk_check_api.py        # 风险检查 API 测试
│   ├── test_risk_check_workflow.py   # 风险检查 LangGraph 测试
│   └── test_rag_retrievers.py        # 双通道 RAG 检索测试
├── main.py                           # 本地启动入口
└── test_main.http                    # 手工接口请求示例
```

## 分层说明

- `api`：只处理 HTTP 入参、依赖注入、响应模型和错误映射。
- `services`：编排业务用例，负责事务提交/回滚和业务错误语义。
- `repositories`：封装业务表读写，不调用模型服务，不处理 Prompt。
- `domain`：保存与框架无关的业务对象和值解析。
- `schemas`：定义 API 请求/响应 DTO，对外兼容 camelCase 字段。
- `db`：保存 ORM 模型和数据库 Session 管理。
- `ai`：封装 LangChain/LangGraph/RAG 相关能力，当前已具备向量入库、双通道检索、合同问答、结构化风险检查和审批辅助 workflow。
- `alembic`：管理数据库 schema 迁移。
- `tests`：覆盖当前阶段的健康检查、合同导入、审批记录导入和制度导入。

## 当前接口

| 功能 | 方法 | 路径 |
| --- | --- | --- |
| 健康检查 | GET | `/health` |
| 导入合同 | POST | `/api/contracts/import` |
| 合同问答 | POST | `/api/contracts/{contract_id}/qa` |
| 风险检查 | POST | `/api/contracts/{contract_id}/risk-check` |
| 审批辅助 | POST | `/api/contracts/{contract_id}/approval-assist` |
| 导入审批记录 | POST | `/api/contracts/{contract_id}/approval-records/import` |
| 导入制度知识库 | POST | `/api/policies/import` |


## 本地启动

### 1. 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

如未创建虚拟环境，可先执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### 2. 配置环境变量

Python 版直接读取环境变量，默认值写在 [app/core/config.py](app/core/config.py) 的 `Settings` 里。常用变量如下：

```powershell
$env:DATABASE_URL="postgresql+psycopg://postgres:123456@localhost:5432/contract-agent-py"
$env:OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode"
$env:OPENAI_API_KEY="your_api_key"
$env:OPENAI_CHAT_MODEL="qwen-plus"
$env:OPENAI_EMBEDDING_MODEL="text-embedding-v3"
$env:OPENAI_EMBEDDING_DIMENSIONS="1024"
$env:EMBEDDING_BATCH_SIZE="10"
$env:VECTOR_COLLECTION_NAME="contract_agent"
```

如需调试 LangChain/LangGraph 调用链，可额外开启 LangSmith tracing：

```powershell
$env:LANGSMITH_TRACING="true"
$env:LANGSMITH_API_KEY="your_langsmith_api_key"
$env:LANGSMITH_PROJECT="contract-agent-python"
```

本地也可以使用 `.env` 文件承载这些变量；`.env` 只放在本机，不提交到 Git。

默认数据库连接为：

```text
postgresql+psycopg://postgres:123456@localhost:5432/contract-agent-py
```

### 3. 执行数据库迁移

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### 4. 启动 API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8088
```

也可以直接运行入口脚本，端口读取 `APP_PORT`，默认 `8088`：

```powershell
.\.venv\Scripts\python.exe main.py
```

如果使用 PyCharm 的 FastAPI/Uvicorn 运行配置，需要在附加参数里写上 `--port 8088`；
否则 uvicorn 命令行会使用自己的默认端口 `8000`。

启动后访问：

- OpenAPI: `http://127.0.0.1:8088/docs`
- Health: `http://127.0.0.1:8088/health`

## LangChain/LangGraph 本地调试

本项目的 AI 调用链集中在 `app/ai`：

- `chains/`：维护 prompt、模型输出解析和输入上下文格式化。
- `graphs/`：维护 LangGraph 节点、状态流转和最终响应组装。
- `rag/`：维护合同条款和制度知识的向量入库、检索和 metadata 边界。
- `langchain_factory.py`：统一创建 ChatModel、Embeddings，并按配置开启 LangSmith tracing。

本地排查时可以按这个顺序定位：

1. 先确认导入接口没有返回 `vectorIngestionWarning`，否则业务表已写入但向量索引可能没同步。
2. 调用 `/api/contracts/{id}/qa` 查看 `retrievedChunkIds` 和 `retrievedPolicyIds`，确认双通道 RAG 是否命中预期材料。
3. 调用 `/api/contracts/{id}/risk-check` 或 `/approval-assist` 查看 `agentTrace`，确认失败或异常结果发生在合同事实、制度依据还是模型生成阶段。
4. 如果模型回答、风险 JSON 或审批 checklist 不稳定，再开启 LangSmith tracing 查看完整 LangChain 调用链。

开启 LangSmith tracing 后，重启 API 并重新调用问答、风险检查或审批辅助接口。LangSmith 项目页会记录本次模型调用的 prompt、模型输入输出和 runnable 执行链，便于检查：

- prompt 变量是否完整，例如合同摘要、条款上下文、制度依据上下文、审批历史是否为空。
- RAG 命中是否正确，例如合同通道是否只命中当前合同，制度通道是否匹配当前合同类型。
- 模型是否返回合法 JSON，例如风险检查的 `riskItems` 或审批辅助的 `checklist`。

LangSmith 是可选调试能力；不配置 `LANGSMITH_API_KEY` 或保持 `LANGSMITH_TRACING=false` 时，项目仍按普通本地模式运行。

## 测试与代码检查

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

当前测试使用 fake vector store 验证双通道 RAG 的 metadata filter、合同类型二次过滤和 LangChain Runnable 接口，并使用 fake workflow/model 验证合同问答、风险检查、审批辅助 LangGraph 状态流转和 API 响应契约。PostgreSQL/pgvector 与真实 embedding/chat model 需要本地数据库和模型服务启动后做端到端验收。

## 数据库表

初始迁移创建四张业务权威表：

- `contracts`：合同主数据。
- `clause_chunks`：合同条款分块。
- `approval_records`：合同审批历史。
- `policy_knowledge`：制度/政策知识库。

向量索引通过 LangChain PGVector collection 接入，是可重建的派生检索索引，不作为业务事实来源。导入接口会先提交业务表，再同步向量；同步失败时返回 `vectorIngestionWarning`。

## 后续计划

1. 阶段 8：联调前端、补充演示数据和 Docker Compose。

详细计划见 [docs/PROJECT_REQUIREMENTS.md](docs/PROJECT_REQUIREMENTS.md)。

## 代码注释规范

本项目已设置注释规则：

- Codex 指令：[AGENTS.md](AGENTS.md)
- 团队规范：[docs/CODE_COMMENT_GUIDELINES.md](docs/CODE_COMMENT_GUIDELINES.md)

注释重点解释业务规则、边界条件、事务语义、外部依赖假设、异常兜底和 LangGraph 状态流转，不机械逐行注释。
