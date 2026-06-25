# Codex Project Instructions

本项目由 Codex 协助开发时，所有新增或修改代码必须遵守以下注释规则。

## 注释总原则

- 注释解释“为什么这样做”“边界条件是什么”“和业务规则的关系是什么”，不要重复代码字面含义。
- 不为简单赋值、直观分支、普通 CRUD 逐行注释。
- 业务规则、跨模块约束、外部依赖假设、异常兜底、事务边界和兼容性处理必须补充注释。
- 注释语言默认使用中文；框架约定、协议名、字段名、异常名等技术名词保留英文。
- 代码命名优先清晰表达含义，注释用于补足命名无法表达的背景。

## Python 注释规则

- 每个对外模块、核心服务、仓储、LangChain chain、LangGraph graph 文件应包含模块级 docstring，说明该文件负责什么。
- 公开类和公开方法应包含简短 docstring，说明用途、关键入参、返回值和异常语义。
- FastAPI 路由函数应注释业务意图和幂等/错误语义；不要只写“调用 service”。
- SQLAlchemy 模型字段不需要逐字段注释，但涉及 JSON、枚举、外键级联、时间语义时必须注释。
- Alembic 迁移文件应在 revision docstring 或关键 DDL 旁说明迁移目的。
- 测试用例应通过测试名表达意图；只有复杂 fixture、mock 或边界数据需要额外注释。

## AI/RAG/LangGraph 注释规则

- Prompt、structured output、retriever filter、vector metadata mapping 必须写注释说明约束来源。
- LangGraph state 字段必须注释它在图中的生命周期：由哪个节点写入、被哪个节点消费。
- LangGraph 节点必须注释输入依赖、输出字段和失败兜底策略。
- 对模型输出解析、JSON 修复、召回为空、向量写入失败等不稳定路径必须写注释。

## 注释质量检查

- 提交前检查新增核心文件是否具备模块级 docstring。
- 提交前检查新增公开 API、service 方法、repository 方法是否有必要 docstring。
- 如果某段代码需要超过三行注释才能解释清楚，优先考虑拆函数或调整命名。

