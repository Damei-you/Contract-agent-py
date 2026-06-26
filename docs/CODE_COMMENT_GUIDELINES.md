# 代码注释规范

本文档用于统一本项目后续由 Codex 或人工编写代码时的注释风格。

## 1. 写什么

- 写业务规则：例如合同导入是否幂等、审批记录为什么全量替换。
- 写边界条件：例如合同 RAG 必须按 `contractId` 过滤，制度 RAG 必须按 `docType=policy` 过滤。
- 写外部依赖假设：例如 OpenAI-compatible API、pgvector 维度、LangChain/PGVector metadata 行为。
- 写异常兜底：例如 LLM JSON 解析失败、向量写入失败、数据库不可用。
- 写流程关系：例如 LangGraph 节点之间的状态传递和 `agentTrace` 来源。

## 2. 不写什么

- 不写重复代码含义的注释，例如“给变量赋值”“返回响应”。
- 不为简单字段逐个解释，字段名已经足够清楚时保持代码干净。
- 不写过期计划或主观评价，例如“以后可能重构”“这里很复杂”。

## 3. Python 具体规则

- 模块级 docstring：核心模块必须有，用一两句话说明职责。
- 类 docstring：领域对象、仓储、服务、AI chain、LangGraph graph 必须有。
- 方法 docstring：公开方法必须有；私有小函数按复杂度决定。
- 行内注释：只用于解释非显然约束，尽量放在代码块上方。
- 测试注释：测试名优先表达意图，复杂 fixture 再写注释。

## 4. 示例

推荐：

```python
"""合同导入应用服务。

负责把 API DTO 映射为领域对象，并保证合同主数据和条款分块在同一事务内落库。
向量入库属于后续阶段的派生索引，不在当前事务中处理。
"""
```

不推荐：

```python
# 创建合同对象
contract = Contract(...)

# 返回合同 ID
return ImportContractResponse(contract_id=contract.id)
```

## 5. Codex 执行要求

后续 Codex 修改代码时，应优先遵守根目录 `AGENTS.md` 中的项目指令。新增核心代码如果缺少必要注释，应在同次变更中补齐。

