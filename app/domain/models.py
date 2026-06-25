from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from app.domain.enums import ApprovalDecision, ContractType, RiskSeverity


@dataclass(slots=True)
class ClauseChunk:
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
    code: str
    severity: RiskSeverity
    detail: str
    related_clause_chunk_ids: list[str] = field(default_factory=list)
    related_policy_ids: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    escalation_role: str = ""


@dataclass(slots=True)
class ApprovalRecord:
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

