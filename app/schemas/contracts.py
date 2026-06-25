from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from app.domain.enums import ApprovalDecision, ContractType, RiskSeverity
from app.schemas.base import ApiModel


class ClauseChunkDto(ApiModel):
    id: str
    clause_code: str = ""
    clause_title: str = ""
    clause_category: str = ""
    party_focus: str = ""
    risk_flag: RiskSeverity = RiskSeverity.LOW
    source_section: str = ""
    text_for_embedding: str
    related_amount_field: str = ""
    review_priority: str = ""

    @field_validator("risk_flag", mode="before")
    @classmethod
    def parse_risk_flag(cls, value: object) -> RiskSeverity:
        return RiskSeverity.from_flexible(value)


class ImportContractRequest(ApiModel):
    id: str
    contract_type: ContractType = Field(alias="type")
    party_a_name: str
    party_b_name: str
    currency: str = "CNY"
    amount_ex_tax: Decimal
    tax_rate_pct: Decimal
    amount_inc_tax: Decimal
    sign_date: date
    effective_date: date
    end_date: date
    performance_site: str = ""
    payment_terms_summary: str = ""
    business_owner_dept: str = ""
    risk_tier: RiskSeverity
    vector_doc_id: str | None = None
    notes: str = ""
    chunks: list[ClauseChunkDto] = Field(default_factory=list)

    @field_validator("contract_type", mode="before")
    @classmethod
    def parse_contract_type(cls, value: object) -> ContractType:
        return ContractType.from_flexible(value)

    @field_validator("risk_tier", mode="before")
    @classmethod
    def parse_risk_tier(cls, value: object) -> RiskSeverity:
        return RiskSeverity.from_flexible(value)


class ImportContractResponse(ApiModel):
    contract_id: str


class RiskItemDto(ApiModel):
    code: str
    severity: RiskSeverity
    detail: str
    related_clause_chunk_ids: list[str] = Field(default_factory=list)
    related_policy_ids: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    escalation_role: str = ""

    @field_validator("severity", mode="before")
    @classmethod
    def parse_severity(cls, value: object) -> RiskSeverity:
        return RiskSeverity.from_flexible(value)


class ImportApprovalRecordDto(ApiModel):
    id: str
    step_no: int
    approver_role: str
    decision: ApprovalDecision
    decision_time: datetime | None = None
    comment_summary: str = ""
    linked_policy_ids: list[str] = Field(default_factory=list)
    linked_clause_chunk_ids: list[str] = Field(default_factory=list)
    risk_items: list[RiskItemDto] = Field(default_factory=list)
    vector_doc_id: str | None = None

    @field_validator("decision", mode="before")
    @classmethod
    def parse_decision(cls, value: object) -> ApprovalDecision:
        return ApprovalDecision.from_flexible(value)


class ImportApprovalRecordsRequest(ApiModel):
    records: list[ImportApprovalRecordDto] = Field(default_factory=list)


class ImportApprovalRecordsResponse(ApiModel):
    contract_id: str
    imported_count: int

