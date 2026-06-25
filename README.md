# 财务合同审批 Agent Python 版

本项目是对 `contract-agent-mvp` 的 Python 技术栈重构，目标是构建一个面向财务、法务和业务审批场景的合同审批 Agent MVP。

当前已完成阶段 0-2：项目脚手架、领域模型与数据库表结构、合同/审批记录/制度知识库导入 API。后续阶段会继续接入 LangChain PGVector、双通道 RAG、LangGraph 问答/风险检查/审批辅助工作流。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| Web API | FastAPI、Uvicorn |
| 数据校验 | Pydantic v2 |
| 配置 | pydantic-settings、`.env` |
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
├── .env.example                      # 本地环境变量示例
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
│   │   └── policy_application.py     # 制度知识库应用服务
│   └── ai/
│       ├── langchain_factory.py      # LangChain ChatModel/Embeddings 工厂
│       ├── chains/                   # 后续 LangChain chain 实现位置
│       ├── graphs/                   # 后续 LangGraph workflow 实现位置
│       └── rag/                      # 后续 PGVector/RAG 实现位置
├── docs/
│   ├── PROJECT_REQUIREMENTS.md       # 需求与实施计划
│   └── CODE_COMMENT_GUIDELINES.md    # 代码注释规范
├── tests/
│   ├── conftest.py                   # 测试数据库和 TestClient fixture
│   ├── test_health.py                # 健康检查测试
│   └── test_import_apis.py           # 导入类 API 测试
├── main.py                           # 兼容入口，导出 app.main:app
└── test_main.http                    # 手工接口请求示例
```

## 分层说明

- `api`：只处理 HTTP 入参、依赖注入、响应模型和错误映射。
- `services`：编排业务用例，负责事务提交/回滚和业务错误语义。
- `repositories`：封装业务表读写，不调用模型服务，不处理 Prompt。
- `domain`：保存与框架无关的业务对象和值解析。
- `schemas`：定义 API 请求/响应 DTO，对外兼容 camelCase 字段。
- `db`：保存 ORM 模型和数据库 Session 管理。
- `ai`：预留 LangChain/LangGraph/RAG 相关能力，后续阶段逐步实现。
- `alembic`：管理数据库 schema 迁移。
- `tests`：覆盖当前阶段的健康检查、合同导入、审批记录导入和制度导入。

## 当前接口

| 功能 | 方法 | 路径 |
| --- | --- | --- |
| 健康检查 | GET | `/health` |
| 导入合同 | POST | `/api/contracts/import` |
| 导入审批记录 | POST | `/api/contracts/{contract_id}/approval-records/import` |
| 导入制度知识库 | POST | `/api/policies/import` |

接口示例见 [test_main.http](test_main.http)。

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

复制 `.env.example` 为 `.env`，按需修改：

```powershell
Copy-Item .env.example .env
```

默认数据库连接为：

```text
postgresql+psycopg://postgres:123456@localhost:5432/contract_agent
```

### 3. 执行数据库迁移

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### 4. 启动 API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

启动后访问：

- OpenAPI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## 测试与代码检查

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

当前测试使用 SQLite 内存库，主要验证阶段 0-2 的业务 API 和仓储行为。PostgreSQL/pgvector 集成测试会在向量阶段补充。

## 数据库表

初始迁移创建四张业务权威表：

- `contracts`：合同主数据。
- `clause_chunks`：合同条款分块。
- `approval_records`：合同审批历史。
- `policy_knowledge`：制度/政策知识库。

后续 `vector_store` 会作为派生检索索引接入，不作为业务事实来源。

## 后续计划

1. 阶段 3：接入 LangChain PGVector，完成合同条款和制度知识向量入库。
2. 阶段 4：实现合同通道和制度通道双通道 RAG 检索。
3. 阶段 5：实现合同问答 LangGraph workflow。
4. 阶段 6：实现结构化风险检查 LangGraph workflow。
5. 阶段 7：实现审批辅助 LangGraph workflow。
6. 阶段 8：联调前端、补充演示数据和 Docker Compose。

详细计划见 [docs/PROJECT_REQUIREMENTS.md](docs/PROJECT_REQUIREMENTS.md)。

## 代码注释规范

本项目已设置注释规则：

- Codex 指令：[AGENTS.md](AGENTS.md)
- 团队规范：[docs/CODE_COMMENT_GUIDELINES.md](docs/CODE_COMMENT_GUIDELINES.md)

注释重点解释业务规则、边界条件、事务语义、外部依赖假设、异常兜底和 LangGraph 状态流转，不机械逐行注释。

