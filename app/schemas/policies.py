from pydantic import Field, field_validator

from app.domain.enums import RiskSeverity
from app.schemas.base import ApiModel


class PolicyKnowledgeItemDto(ApiModel):
    policy_id: str
    policy_domain: str
    applies_to_contract_type: str
    severity: RiskSeverity
    trigger_keywords: str = ""
    control_objective: str = ""
    policy_text_for_embedding: str
    required_evidence: str = ""
    escalation_role: str = ""
    vector_doc_id: str | None = None

    @field_validator("severity", mode="before")
    @classmethod
    def parse_severity(cls, value: object) -> RiskSeverity:
        return RiskSeverity.from_flexible(value)


class ImportPolicyKnowledgeRequest(ApiModel):
    policies: list[PolicyKnowledgeItemDto] = Field(default_factory=list)


class ImportPolicyKnowledgeResponse(ApiModel):
    imported_count: int
    policy_ids: list[str]
    vector_ingestion_warning: str | None = None

