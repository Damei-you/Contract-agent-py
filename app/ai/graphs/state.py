"""LangGraph 共享 state 定义。

这些 TypedDict 只描述图内节点传递的数据，不直接作为 HTTP DTO；API 响应由 service 层从
最终 state 映射，避免 LangGraph 结构泄漏到外部契约。
"""

from typing import Any, TypedDict

from app.ai.rag.retrievers import RagRetrievedDocument
from app.domain.models import Contract, RiskItem


class AgentTraceState(TypedDict, total=False):
    """对外返回的轻量执行轨迹。

    agent_name/summary 由各 LangGraph 节点按参考项目 AgentTrace 语义写入，只记录关键贡献，
    不保存 Prompt、模型原文或大段 RAG 正文，避免把 trace 变成隐式日志系统。
    """

    agent_name: str
    summary: str


class ContractQaState(TypedDict, total=False):
    """合同问答图状态。

    contract_id/question 由 workflow 入口写入；contract 由 load_contract 写入，召回节点消费；
    contract_context/policy_context 分别由两个 RAG 节点写入，generate_answer 消费；answer 由
    generate_answer 写入，format_response 消费；response 由 format_response 写入并由 service
    映射为 HTTP 响应。
    """

    contract_id: str
    question: str
    contract: Contract
    contract_context: list[RagRetrievedDocument]
    policy_context: list[RagRetrievedDocument]
    answer: str
    retrieved_chunk_ids: list[str]
    retrieved_policy_ids: list[str]
    response: dict[str, Any]


class RiskCheckState(TypedDict, total=False):
    """风险检查图状态。

    contract_id/broad_query 由 workflow 入口写入；contract 由 load_contract 写入并被召回、
    prompt 生成和响应节点消费；contract_context/policy_context 由 retrieve_context 写入；
    approval_history 由 load_approval_history 写入；raw_risk_output 由 generate_risk_json 写入；
    risk_summary/risk_items 由 validate_risk_output 写入；agent_trace 在节点完成业务角色后追加，
    response 由 format_response 写入并由 service 映射为 HTTP DTO。
    """

    contract_id: str
    broad_query: str
    contract: Contract
    contract_context: list[RagRetrievedDocument]
    policy_context: list[RagRetrievedDocument]
    approval_history: str
    raw_risk_output: str
    risk_summary: str
    risk_items: list[RiskItem]
    agent_trace: list[AgentTraceState]
    response: dict[str, Any]


class ApprovalAssistState(TypedDict, total=False):
    """审批辅助图状态。

    contract_id/approver_role/focus/query 由 workflow 入口写入；contract 由 load_contract 写入；
    contract_context/policy_context 由 retrieve_role_related_context 写入并供生成建议与回填命中 ID；
    approval_history 由 load_approval_history 写入；raw_advice_output 由 generate_advice 写入；
    suggestion/checklist 由同节点解析后写入；agent_trace 在合同事实、制度依据和审批建议节点后
    追加，response 由 format_response 写入并由 service 映射为 HTTP DTO。
    """

    contract_id: str
    approver_role: str
    focus: str
    query: str
    contract: Contract
    contract_context: list[RagRetrievedDocument]
    policy_context: list[RagRetrievedDocument]
    approval_history: str
    raw_advice_output: str
    suggestion: str
    checklist: list[str]
    retrieved_chunk_ids: list[str]
    retrieved_policy_ids: list[str]
    agent_trace: list[AgentTraceState]
    response: dict[str, Any]
