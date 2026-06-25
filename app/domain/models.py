"""领域对象。

领域对象保持与业务概念一致，不绑定 SQLAlchemy 或 FastAPI，便于服务层、仓储层和未来
LangGraph 节点共同复用。
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from app.domain.enums import ApprovalDecision, ContractType, RiskSeverity


@dataclass(slots=True)
class ClauseChunk:
    """合同条款分块，是合同 RAG 的最小事实单元。"""

    contract_id: str
    chunk_id: str
    clause_code: str
    clause_title: str
    clause_category: str
    party_focus: str
    risk_flag: RiskSeverity
    source_section: str
    text_for_embedding: str
    related_amount_field: str
    review_priority: str


@dataclass(slots=True)
class Contract:
    """合同主实体，聚合合同基本信息和条款分块。"""

    id: str
    contract_type: ContractType
    party_a_name: str
    party_b_name: str
    currency: str
    amount_ex_tax: Decimal
    tax_rate_pct: Decimal
    amount_inc_tax: Decimal
    sign_date: date
    effective_date: date
    end_date: date
    performance_site: str
    payment_terms_summary: str
    business_owner_dept: str
    risk_tier: RiskSeverity
    vector_doc_id: str | None
    notes: str
    chunks: list[ClauseChunk] = field(default_factory=list)


@dataclass(slots=True)
class RiskItem:
    """结构化风险项。

    related_* 字段用于把模型判断追溯到合同条款和制度依据，后续前端可据此展示证据。
    """

    code: str
    severity: RiskSeverity
    detail: str
    related_clause_chunk_ids: list[str] = field(default_factory=list)
    related_policy_ids: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    escalation_role: str = ""


@dataclass(slots=True)
class ApprovalRecord:
    """合同审批历史记录。"""

    contract_id: str
    approval_record_id: str
    step_no: int
    approver_role: str
    decision: ApprovalDecision
    decision_time: datetime | None
    comment_summary: str
    linked_policy_ids: list[str]
    linked_clause_chunk_ids: list[str]
    risk_items: list[RiskItem]
    vector_doc_id: str | None


@dataclass(slots=True)
class PolicyKnowledgeItem:
    """制度知识条目，是跨合同共享的规则来源。"""

    policy_id: str
    policy_domain: str
    applies_to_contract_type: str
    severity: RiskSeverity
    trigger_keywords: str
    control_objective: str
    policy_text_for_embedding: str
    required_evidence: str
    escalation_role: str
    vector_doc_id: str | None = None
