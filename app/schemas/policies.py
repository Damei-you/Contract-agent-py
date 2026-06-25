"""制度知识库 API DTO。

制度条目会被后续 RAG 写入向量库，因此请求模型保留了用于 metadata 和 evidence 的字段。
"""

from pydantic import Field, field_validator

from app.domain.enums import RiskSeverity
from app.schemas.base import ApiModel


class PolicyKnowledgeItemDto(ApiModel):
    """单条制度知识导入 DTO。"""

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
        """制度严重度支持中文/英文输入，便于从表格数据批量导入。"""

        return RiskSeverity.from_flexible(value)


class ImportPolicyKnowledgeRequest(ApiModel):
    """制度知识批量导入请求。"""

    policies: list[PolicyKnowledgeItemDto] = Field(default_factory=list)


class ImportPolicyKnowledgeResponse(ApiModel):
    """制度知识导入响应。

    vector_ingestion_warning 预留给阶段 3：业务表成功但向量索引同步失败时提醒调用方重试。
    """

    imported_count: int
    policy_ids: list[str]
    vector_ingestion_warning: str | None = None
