# 财务合同审批 Agent Python 重构需求与实施计划

## 1. 项目背景

当前项目目标是参考 `E:\code\contract-agent-mvp`，使用 Python 技术栈重构一套“财务合同审批 Agent MVP”。参考项目基于 Spring Boot + Spring AI + PostgreSQL/pgvector + Vue3，已经具备合同导入、合同问答、风险检查、审批辅助、审批记录导入和制度知识库导入等闭环能力。

本项目的重构重点不是简单翻译代码，而是在保持核心业务能力、接口语义和数据边界基本兼容的前提下，用 Python 生态重建后端服务、RAG 检索、LangChain/LangGraph 编排和测试体系。前端可以优先复用参考项目 Vue3 页面，只要 Python 后端保持 API 兼容即可。

## 2. MVP 目标

### 2.1 业务目标

- 支持导入合同主数据与条款分块，形成可查询、可检索的合同事实库。
- 支持导入制度/政策知识条目，形成跨合同共享的制度依据库。
- 支持导入合同审批记录，作为审批辅助和风险分析的历史上下文。
- 支持基于指定合同的问答，回答必须来自当前合同条款与适用制度依据。
- 支持生成结构化合同风险检查结果，包括风险摘要、风险项、关联条款、关联制度、补充材料和升级角色。
- 支持根据审批角色和关注点生成审批建议与 checklist。
- 支持在返回结果中暴露 `retrievedChunkIds`、`retrievedPolicyIds`、`agentTrace`，便于前端展示和问题排查。

### 2.2 技术目标

- 后端使用 Python/FastAPI 实现 REST API。
- 数据库使用 PostgreSQL 作为业务权威存储，pgvector 作为派生向量检索索引。
- LLM、Embedding、Retriever、Prompt 和结构化输出统一通过 LangChain 封装，底层使用 OpenAI-compatible API，默认兼容 DashScope compatible mode。
- 问答、风险检查和审批辅助工作流直接使用 LangGraph `StateGraph` 编排，不再自研 `Agent`/`MultiAgentOrchestrator` 框架。
- 可选接入 LangSmith tracing，用于调试 LangChain 调用链、LangGraph 节点状态和召回质量。
- 使用 Pydantic 模型约束请求、响应和 LLM 结构化输出。
- 使用 pytest 建立核心服务、RAG、API 的自动化测试。

## 3. 范围定义

### 3.1 In Scope

- Python 后端服务与 API。
- 合同、条款、审批记录、制度知识库的数据库模型和迁移脚本。
- 合同条款与制度知识的向量写入、删除后重建、批量 embedding。
- 合同 RAG 通道：必须按 `contractId` 限定召回范围。
- 制度 RAG 通道：必须按 `docType=policy` 和合同类型收敛召回范围。
- 问答、风险检查、审批辅助三类 AI 能力。
- 兼容参考项目主要 API 路径和响应字段。
- 本地开发配置、环境变量、测试用例和基本文档。

### 3.2 Out of Scope

- 生产级权限系统、用户登录、多租户隔离。
- 合同 PDF/Word 自动解析与条款智能切分。
- 复杂工作流引擎和真实审批流转。
- 大规模检索评测平台和模型微调。
- 前端大改版。MVP 阶段优先保持 API 兼容，复用参考项目 Vue3 前端。

## 4. 推荐技术栈

| 模块 | 技术选型 | 说明 |
| --- | --- | --- |
| Python 版本 | Python 3.12 | 兼顾新特性、生态稳定性和部署可用性 |
| Web 框架 | FastAPI + Uvicorn | 当前项目已有 FastAPI 骨架，适合异步 API 与 OpenAPI 文档 |
| 数据校验 | Pydantic v2 | 定义请求 DTO、响应 DTO、领域值对象和配置 |
| 配置管理 | pydantic-settings | 管理数据库、模型、embedding、批处理等环境变量 |
| ORM/SQL | SQLAlchemy 2.x | 显式建模业务表，便于测试和迁移 |
| 数据库迁移 | Alembic | 管理 schema 版本，替代手工同步 SQL |
| 数据库驱动 | psycopg 3 或 asyncpg | MVP 可先使用同步 SQLAlchemy + psycopg，后续再异步化 |
| 业务数据库 | PostgreSQL 16 | 保存业务权威数据 |
| 向量检索 | LangChain PGVector + PostgreSQL/pgvector | 使用 `langchain-postgres` 的 PGVector 集成，保留 PostgreSQL 作为向量后端 |
| LLM/Embedding | LangChain model/embedding abstractions + `langchain-openai` | 统一封装 ChatModel、Embeddings、Prompt 和结构化输出 |
| RAG 编排 | LangChain Retriever、Runnable、PromptTemplate | 合同通道和制度通道都封装为 LangChain retriever/runnable |
| Agent/工作流编排 | LangGraph `StateGraph` | 用显式状态、节点和边表达问答、风险检查、审批辅助流程 |
| 可观测性 | LangSmith（可选） | 调试 LangChain 调用链、LangGraph 节点状态、召回结果和模型输出 |
| HTTP 客户端 | httpx | 用于测试客户端和必要的外部调用 |
| 测试 | pytest + pytest-asyncio + httpx + testcontainers | 覆盖 API、服务层、数据库和 pgvector 冒烟测试 |
| 代码质量 | ruff + mypy | 统一格式、lint 和类型检查 |
| 前端 | 复用 Vue3 + Vite + TypeScript + Element Plus | API 兼容后可直接联调参考项目前端 |
| 部署 | Docker + docker compose | 本地一键启动 API、PostgreSQL/pgvector |

## 5. API 兼容目标

MVP 阶段保留参考项目的核心接口路径：

| 功能 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| 健康检查 | GET | `/health` | Python 后端新增，供部署和联调用 |
| 导入合同 | POST | `/api/contracts/import` | 写入合同主数据和条款分块，并触发条款向量入库 |
| 合同问答 | POST | `/api/contracts/{id}/qa` | 双通道 RAG + LLM 生成回答 |
| 风险检查 | POST | `/api/contracts/{id}/risk-check` | 返回结构化风险摘要和风险项 |
| 审批辅助 | POST | `/api/contracts/{id}/approval-assist` | 返回审批建议、checklist 和召回证据 |
| 导入审批记录 | POST | `/api/contracts/{id}/approval-records/import` | 全量替换指定合同的审批历史 |
| 导入制度知识库 | POST | `/api/policies/import` | 按 `policyId` 幂等覆盖制度条目并同步向量 |

错误语义建议：

- `400 Bad Request`：请求体缺字段、字段类型错误、枚举值无法解析。
- `404 Not Found`：指定合同不存在。
- `409 Conflict`：合同导入时 ID 已存在。
- `500 Internal Server Error`：模型、数据库或未知服务端异常。
- `503 Service Unavailable`：依赖资源未配置或不可用。

## 6. 数据模型

业务权威数据继续采用参考项目的表结构：

- `contracts`：合同主数据。
- `clause_chunks`：合同条款分块。
- `approval_records`：合同审批记录。
- `policy_knowledge`：制度/政策知识库。
- `vector_store`：pgvector 派生检索索引。

关键约束：

- `contracts.id` 是合同主键。
- `clause_chunks` 使用 `(contract_id, chunk_id)` 作为联合主键。
- `approval_records` 使用 `(contract_id, approval_record_id)` 作为联合主键。
- `policy_knowledge.policy_id` 是制度条目的稳定主键，被风险项和审批记录引用后不应随意修改。
- 业务表是事实来源，`vector_store` 只作为可重建的检索索引。

## 7. RAG 与向量映射

### 7.1 合同条款向量

- 向量文档 ID：`contract:{contractId}:{chunkId}`
- content：`【{clauseTitle}】\n{textForEmbedding}`
- metadata 最小集合：
  - `docType=contract_clause`
  - `contractId`
  - `chunkId`
  - `clauseTitle`
  - `clauseCode`
  - `clauseCategory`

合同检索必须使用 `contractId` 过滤，禁止跨合同召回。

### 7.2 制度知识向量

- 向量文档 ID：`policy:{policyId}`
- content：`【{policyDomain}/{controlObjective}】\n{policyTextForEmbedding}`
- metadata 最小集合：
  - `docType=policy`
  - `policyId`
  - `policyDomain`
  - `appliesToContractType`
  - `severity`
  - `triggerKeywords`
  - `requiredEvidence`
  - `escalationRole`

制度检索必须至少按 `docType=policy` 过滤，并结合当前合同类型进行候选收敛。

## 8. 后端模块设计

建议目录结构：

```text
app/
  main.py
  api/
    routes/
      contracts.py
      policies.py
      health.py
    errors.py
  core/
    config.py
    logging.py
  domain/
    models.py
    enums.py
  schemas/
    contracts.py
    policies.py
    common.py
  db/
    session.py
    models.py
  repositories/
    contracts.py
    policies.py
  services/
    contract_application.py
    policy_application.py
  ai/
    assistant.py
    langchain_factory.py
    prompts.py
    chains/
      qa.py
      risk_check.py
      approval_assist.py
    graphs/
      state.py
      contract_qa_graph.py
      risk_check_graph.py
      approval_assist_graph.py
    rag/
      vector_store.py
      retrievers.py
      ingestion.py
      document_mapping.py
alembic/
tests/
```

模块职责：

- `api/routes`：只处理 HTTP 入参、状态码和响应模型。
- `services`：编排业务用例，例如导入合同、问答、风险检查。
- `repositories`：封装业务表读写，不处理 prompt 和模型调用。
- `ai/langchain_factory.py`：集中创建 LangChain ChatModel、Embeddings、PGVector 和通用 runnable。
- `ai/chains`：封装 LangChain prompt、retriever 组合、结构化输出解析和响应格式化。
- `ai/graphs`：定义 LangGraph state、节点、边和编译后的工作流，生成 `agentTrace`。
- `ai/rag`：封装 LangChain PGVector、合同检索、制度检索、向量文档映射和入库。
- `ai/assistant.py`：作为服务层调用 LangGraph 的门面，避免 Controller 直接感知图实现。
- `domain`：领域对象、枚举和值解析逻辑。
- `schemas`：API DTO 和结构化输出模型。

## 9. 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `local` | 运行环境 |
| `APP_PORT` | `8000` | FastAPI 监听端口 |
| `DATABASE_URL` | - | PostgreSQL 连接串 |
| `OPENAI_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode` | OpenAI-compatible 服务地址 |
| `OPENAI_API_KEY` | - | 模型服务密钥 |
| `OPENAI_CHAT_MODEL` | `qwen-plus` | 聊天模型 |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-v3` | 向量模型 |
| `OPENAI_EMBEDDING_DIMENSIONS` | `1024` | 向量维度，必须与 pgvector 字段一致 |
| `EMBEDDING_BATCH_SIZE` | `10` | 向量批量写入大小 |
| `RAG_CONTRACT_TOP_K` | `5` | 合同通道召回数量 |
| `RAG_POLICY_TOP_K` | `5` | 制度通道召回数量 |
| `LANGSMITH_TRACING` | `false` | 是否开启 LangSmith tracing |
| `LANGSMITH_API_KEY` | - | LangSmith API Key，可选 |
| `LANGSMITH_PROJECT` | `contract-agent-python` | LangSmith 项目名，可选 |

## 10. 分阶段实施计划

### 阶段 0：项目脚手架

目标：把当前 FastAPI 骨架升级为可持续开发的 Python 项目。

- 创建 `pyproject.toml`，引入 FastAPI、Pydantic、SQLAlchemy、Alembic、LangChain、LangGraph、`langchain-openai`、`langchain-postgres`、pytest、ruff。
- 建立 `app/` 分层目录。
- 增加 `/health` 接口。
- 增加 `.env.example` 和基础配置读取。
- 建立 `langchain_factory.py`，统一创建 ChatModel、Embeddings 和可选 LangSmith tracing 配置。
- 建立最小单元测试和 lint 命令。

验收标准：

- `pytest` 可运行。
- `uvicorn app.main:app --reload` 可启动。
- `/health` 返回服务状态。
- LangChain ChatModel/Embeddings 工厂可在无真实 API Key 的测试环境中被 mock。

### 阶段 1：领域模型与数据库

目标：完成业务权威数据的 Python 建模和数据库迁移。

- 定义合同、条款、审批记录、制度知识领域模型。
- 定义 Pydantic 请求/响应 DTO。
- 使用 Alembic 创建 `contracts`、`clause_chunks`、`approval_records`、`policy_knowledge` 表。
- 实现合同仓储和制度仓储。

验收标准：

- 数据库迁移可在空库执行成功。
- 仓储测试覆盖合同保存、查询、重复 ID、审批记录替换、制度 upsert。

### 阶段 2：导入类 API

目标：先完成无 AI 依赖的业务闭环。

- 实现 `POST /api/contracts/import`。
- 实现 `POST /api/contracts/{id}/approval-records/import`。
- 实现 `POST /api/policies/import` 的业务表写入。
- 对齐参考项目请求/响应字段。

验收标准：

- 合同导入成功后业务表可查。
- 重复导入合同返回 `409`。
- 审批记录导入为全量替换。
- 制度导入按 `policyId` 幂等覆盖。

### 阶段 3：向量写入与 pgvector

目标：完成合同条款和制度条目的向量索引。

- 使用 `langchain-postgres` 的 `PGVector` 集成 PostgreSQL/pgvector。
- 使用 `langchain-openai` 的 Embeddings 适配 OpenAI-compatible embedding 服务。
- 使用 LangChain `Document` 统一表达合同条款和制度知识向量文档。
- 封装 `document_mapping.py`，将领域对象映射为带稳定 ID 和 metadata 的 LangChain `Document`。
- 实现向量入库服务，支持按 ID 分批 delete + add 或覆盖写入，并在失败时返回 warning。
- 合同导入后写入条款向量，制度导入后写入制度向量。

验收标准：

- 同一合同/制度重复导入不会产生重复向量。
- embedding 批大小可由环境变量控制。
- 向量写入失败时业务表状态清晰，并返回可重试提示。
- LangChain PGVector 查询可通过 metadata filter 命中合同和制度样例数据。

### 阶段 4：双通道 RAG 检索

目标：基于 LangChain retriever 实现合同通道和制度通道召回。

- 实现 `ContractRagRetriever.retrieve(contract_id, query, top_k)`，内部使用 LangChain PGVector similarity search 或 retriever。
- 实现 `PolicyRagRetriever.retrieve(contract_type, query, top_k)`，内部使用 LangChain PGVector metadata filter 和二次过滤。
- 将两个 retriever 封装为可在 LangGraph 节点中复用的 runnable/tool。
- 合同通道严格按 `contractId` 过滤。
- 制度通道按 `docType=policy` 和合同类型收敛。

验收标准：

- 指定合同问句只召回该合同条款。
- 制度召回可返回 `policyId`、制度领域、严重度、证据要求和升级角色。
- 检索结果包含分数和原始 ID，便于调试。

### 阶段 5：合同问答

目标：完成第一条 LangGraph + LangChain AI 生成链路。

- 定义 `ContractQaState`，包含 `contractId`、`question`、合同摘要、合同召回、制度召回、回答和 trace。
- 使用 LangGraph 建立问答图：`load_contract` -> `retrieve_contract_context` + `retrieve_policy_context` -> `generate_answer` -> `format_response`。
- 使用 LangChain `ChatPromptTemplate` 和 ChatModel 生成回答。
- 实现 `POST /api/contracts/{id}/qa`，服务层调用编译后的 LangGraph workflow。
- 返回 `answer`、`retrievedChunkIds`、`retrievedPolicyIds`。

验收标准：

- 合同不存在返回 `404`。
- 回答上下文来自当前合同条款和适用制度。
- LangGraph state 中可记录每个节点的输入摘要、输出摘要和异常。
- 前端合同问答页面可联调。

### 阶段 6：风险检查

目标：基于 LangGraph 生成结构化风险结果。

- 定义 `RiskCheckState`，包含合同事实、合同条款召回、制度召回、审批历史摘要、风险 JSON 和 trace。
- 使用 LangGraph 建立风险检查图：`load_contract` -> `retrieve_context` -> `load_approval_history` -> `generate_risk_json` -> `validate_risk_output` -> `format_response`。
- 使用 LangChain structured output 或 Pydantic output parser 约束 LLM 输出。
- 增加 JSON 解析失败兜底。
- 返回 `summary`、`riskItems`、`agentTrace`。

验收标准：

- 每个风险项尽量包含 `relatedClauseChunkIds` 和 `relatedPolicyIds`。
- 严重度只允许 `LOW`、`MEDIUM`、`HIGH`。
- 解析失败时返回可读错误或保底风险摘要，不让服务崩溃。
- LangGraph trace 能定位失败发生在召回、模型生成还是结构化解析节点。

### 阶段 7：审批辅助与 LangGraph Trace

目标：用 LangGraph 补齐审批场景和可追踪执行路径。

- 定义 `ApprovalAssistState`，包含 `contractId`、`approverRole`、`focus`、合同事实、制度依据、审批历史、建议和 checklist。
- 使用 LangGraph 建立审批辅助图：`load_contract` -> `retrieve_role_related_context` -> `load_approval_history` -> `generate_advice` -> `format_response`。
- 使用 LangChain prompt、retriever 和 ChatModel 生成审批建议。
- 实现 `POST /api/contracts/{id}/approval-assist`。
- 结合审批角色、关注点、合同事实、制度依据和审批历史生成建议。

验收标准：

- 返回 `suggestion`、`checklist`、`retrievedChunkIds`、`retrievedPolicyIds`、`agentTrace`。
- `agentTrace` 由 LangGraph 节点执行记录生成，能体现合同事实、制度依据、审批历史和审批建议等关键步骤。
- 单测覆盖 LangGraph 条件边、节点异常兜底和最终响应格式。
- 前端审批辅助页面可联调。

### 阶段 8：前端联调、文档和演示数据

目标：形成可演示 MVP。

- 复用参考项目 Vue3 前端，配置代理到 Python 后端。
- 整理 API 示例和 Apipost/HTTP 测试请求。
- 准备合同、制度、审批记录示例数据。
- 增加 docker compose 启动 PostgreSQL/pgvector。
- 补充 LangChain/LangGraph 本地调试说明，包括如何开启 LangSmith tracing。
- 补充 README 快速启动。

验收标准：

- 本地可一键启动数据库和后端。
- 主要页面能完成导入、问答、风险检查、审批辅助。
- README 写清环境变量、启动命令和常见问题。

## 11. 测试策略

- 单元测试：领域枚举解析、DTO 校验、prompt 输出解析、vector document 映射。
- 仓储测试：数据库 CRUD、事务、重复导入、制度 upsert。
- 服务测试：合同导入、审批记录替换、制度导入、合同不存在错误。
- RAG 测试：合同通道过滤、制度通道过滤、向量写入幂等。
- LangChain 测试：prompt 变量完整性、structured output 解析、retriever runnable 输入输出。
- LangGraph 测试：state schema、节点输出、边路由、异常兜底、最终响应格式。
- API 测试：使用 FastAPI TestClient/httpx 覆盖核心接口。
- 集成测试：使用 testcontainers 启动 PostgreSQL + pgvector，验证迁移和检索。

## 12. 主要风险与对策

| 风险 | 影响 | 对策 |
| --- | --- | --- |
| OpenAI-compatible 服务差异 | chat/embedding 参数不完全一致 | LLM client 独立封装，配置模型和维度 |
| embedding 维度不匹配 | pgvector 写入失败 | 启动时校验 `OPENAI_EMBEDDING_DIMENSIONS` 与表结构 |
| LangChain/LangGraph 版本演进 | API 或包拆分变化导致升级成本 | 在 `pyproject.toml` 锁定主要版本范围，LangChain 相关能力集中封装在 `ai/` 模块 |
| LLM JSON 输出不稳定 | 风险检查解析失败 | 使用 LangChain structured output/Pydantic parser + 严格 prompt + 兜底逻辑 |
| 向量写入与业务写入不一致 | 检索结果缺失或过期 | 业务表作为权威，向量表可重建，导入接口返回 warning |
| 图状态过度膨胀 | 节点耦合、调试困难 | 每个 LangGraph state 只保留必要字段，大文本以摘要和 ID 为主 |
| LangGraph 节点失败难定位 | AI 链路问题排查慢 | 每个节点产出 `agentTrace`，可选开启 LangSmith tracing |
| 前后端字段不兼容 | Vue 页面无法复用 | API DTO 优先对齐参考项目 |

## 13. 第一轮开发建议

建议按以下顺序开始：

1. 完成阶段 0，建立 Python 项目结构、LangChain/LangGraph 依赖和基础工厂。
2. 完成阶段 1 的表模型、迁移和 DTO。
3. 完成阶段 2 的三类导入 API，让前端和测试先有稳定业务数据入口。
4. 完成阶段 3 和阶段 4，用 LangChain PGVector 打通双通道 RAG。
5. 依次实现问答、风险检查和审批辅助三个 LangGraph workflow。
