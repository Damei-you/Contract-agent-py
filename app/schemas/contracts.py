"""合同相关 API DTO。

字段设计优先兼容参考项目 Vue 前端和 Java DTO；内部服务层再映射到领域对象。
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from app.domain.enums import ApprovalDecision, ContractType, RiskSeverity
from app.schemas.base import ApiModel


class ClauseChunkDto(ApiModel):
    """合同条款分块导入 DTO，是后续合同 RAG 的最小文本单元。"""

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
        """支持中文/英文风险等级，降低示例数据和人工录入的格式敏感度。"""

        return RiskSeverity.from_flexible(value)


class ImportContractRequest(ApiModel):
    """合同导入请求。

    `type` 是参考项目已有入参名，内部用 `contract_type` 避免覆盖 Python 内置概念。
    """

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
        """兼容英文别名和中文显示名。"""

        return ContractType.from_flexible(value)

    @field_validator("risk_tier", mode="before")
    @classmethod
    def parse_risk_tier(cls, value: object) -> RiskSeverity:
        """兼容中文风险等级输入。"""

        return RiskSeverity.from_flexible(value)


class ImportContractResponse(ApiModel):
    """合同导入响应。

    vector_ingestion_warning 表示业务表已成功提交，但派生向量索引未同步成功，可用同一
    请求重试导入或后续补偿任务重建。
    """

    contract_id: str
    vector_ingestion_warning: str | None = None


class ContractQaRequest(ApiModel):
    """合同问答请求。

    对齐 contract-agent-mvp ContractQaRequest，仅接收用户自然语言问题。
    """

    question: str = Field(min_length=1)


class ContractQaResponse(ApiModel):
    """合同问答响应。

    对齐 contract-agent-mvp ContractQaResponse：模型回答与双通道 RAG 命中 ID。
    """

    answer: str
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    retrieved_policy_ids: list[str] = Field(default_factory=list)


class RiskItemDto(ApiModel):
    """结构化风险项 DTO。

    该结构同时用于审批历史导入和风险检查响应，字段对齐 contract-agent-mvp RiskItem。
    """

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
        """风险项严重度与合同风险等级共用同一套解析规则。"""

        return RiskSeverity.from_flexible(value)


class ImportApprovalRecordDto(ApiModel):
    """单条审批记录导入 DTO。"""

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
        """审批结论支持中文别名，方便迁移历史审批数据。"""

        return ApprovalDecision.from_flexible(value)


class ImportApprovalRecordsRequest(ApiModel):
    """审批记录全量导入请求。"""

    records: list[ImportApprovalRecordDto] = Field(default_factory=list)


class ImportApprovalRecordsResponse(ApiModel):
    """审批记录导入响应。"""

    contract_id: str
    imported_count: int


class AgentTraceDto(ApiModel):
    """风险检查/审批辅助返回的轻量 Agent 执行轨迹。"""

    agent_name: str
    summary: str


class ContractRiskCheckResponse(ApiModel):
    """结构化风险检查响应。

    对齐 contract-agent-mvp ContractRiskCheckResponse：解析失败时 summary 可为模型原文，
    risk_items 为空；agent_trace 描述本轮合同事实、制度依据和风险审查节点产出。
    """

    summary: str = ""
    risk_items: list[RiskItemDto] = Field(default_factory=list)
    agent_trace: list[AgentTraceDto] = Field(default_factory=list)
