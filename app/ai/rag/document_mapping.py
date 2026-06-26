"""领域对象到 LangChain Document 的映射。

向量库是派生索引，不能成为业务事实来源；因此 Document 的 id 和 metadata 必须能稳定
回指业务表中的合同条款或制度条目。
"""

from langchain_core.documents import Document

from app.domain.models import ClauseChunk, PolicyKnowledgeItem


def contract_chunk_document_id(chunk: ClauseChunk) -> str:
    """生成合同条款向量文档 ID。

    命名空间前缀避免合同条款 ID 与制度 policyId 在同一个 collection 中冲突。
    """

    return f"contract:{chunk.contract_id}:{chunk.chunk_id}"


def policy_document_id(item: PolicyKnowledgeItem) -> str:
    """生成制度知识向量文档 ID。"""

    return f"policy:{item.policy_id}"


def chunk_to_document(chunk: ClauseChunk) -> Document:
    """将合同条款分块转换为 LangChain Document。

    metadata 中的 contractId 是后续合同通道 RAG 的强过滤条件，不能缺失。
    """

    title = chunk.clause_title or chunk.clause_code or chunk.chunk_id
    return Document(
        id=contract_chunk_document_id(chunk),
        page_content=f"【{title}】\n{chunk.text_for_embedding}",
        metadata={
            "docType": "contract_clause",
            "contractId": chunk.contract_id,
            "chunkId": chunk.chunk_id,
            "clauseTitle": chunk.clause_title,
            "clauseCode": chunk.clause_code,
            "clauseCategory": chunk.clause_category,
            "partyFocus": chunk.party_focus,
            "riskFlag": chunk.risk_flag.value,
            "sourceSection": chunk.source_section,
            "relatedAmountField": chunk.related_amount_field,
            "reviewPriority": chunk.review_priority,
        },
    )


def policy_to_document(item: PolicyKnowledgeItem) -> Document:
    """将制度知识条目转换为 LangChain Document。

    metadata 保留风险检查和审批辅助所需的 evidence/escalation 信息，方便模型输出可追溯。
    """

    title = "/".join(part for part in [item.policy_domain, item.control_objective] if part)
    return Document(
        id=policy_document_id(item),
        page_content=f"【{title or item.policy_id}】\n{item.policy_text_for_embedding}",
        metadata={
            "docType": "policy",
            "policyId": item.policy_id,
            "policyDomain": item.policy_domain,
            "appliesToContractType": item.applies_to_contract_type,
            "severity": item.severity.value,
            "triggerKeywords": item.trigger_keywords,
            "controlObjective": item.control_objective,
            "requiredEvidence": item.required_evidence,
            "escalationRole": item.escalation_role,
        },
    )
