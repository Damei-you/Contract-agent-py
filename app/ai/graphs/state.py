"""LangGraph 共享 state 定义。

这些 TypedDict 只描述图内节点传递的数据，不直接作为 HTTP DTO；API 响应由 service 层从
最终 state 映射，避免 LangGraph 结构泄漏到外部契约。
"""

from typing import Any, TypedDict

from app.ai.rag.retrievers import RagRetrievedDocument
from app.domain.models import Contract


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
