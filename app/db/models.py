"""SQLAlchemy 业务表模型。

这些表保存可重启恢复的权威业务数据；pgvector/vector_store 在后续阶段只作为派生索引，
不能反向作为合同或制度事实来源。
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """所有 ORM 模型共享的声明式基类。"""

    pass


class ContractModel(Base):
    """合同主数据表。"""

    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contract_type: Mapped[str] = mapped_column(String(32), nullable=False)
    party_a_name: Mapped[str] = mapped_column(String(255), nullable=False)
    party_b_name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    amount_ex_tax: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    tax_rate_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    amount_inc_tax: Mapped[Decimal] = mapped_column(Numeric(19, 2), nullable=False)
    sign_date: Mapped[date] = mapped_column(Date, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    performance_site: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payment_terms_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    business_owner_dept: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    risk_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    vector_doc_id: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    chunks: Mapped[list["ClauseChunkModel"]] = relationship(
        back_populates="contract",
        # 条款是合同事实的一部分，删除合同后必须级联删除，避免跨合同 RAG 召回脏数据。
        cascade="all, delete-orphan",
    )
    approval_records: Mapped[list["ApprovalRecordModel"]] = relationship(
        back_populates="contract",
        # 审批记录依附于合同生命周期；合同删除后审批历史不再单独保留。
        cascade="all, delete-orphan",
    )


class ClauseChunkModel(Base):
    """合同条款分块表，是合同 RAG 的原始文本来源。"""

    __tablename__ = "clause_chunks"

    contract_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    clause_code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    clause_title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    clause_category: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    party_focus: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    risk_flag: Mapped[str] = mapped_column(String(16), nullable=False, default="LOW")
    source_section: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    text_for_embedding: Mapped[str] = mapped_column(Text, nullable=False)
    related_amount_field: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    review_priority: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    contract: Mapped[ContractModel] = relationship(back_populates="chunks")


class ApprovalRecordModel(Base):
    """审批记录表。

    关联条款、制度和风险项保存在 JSON 字段中，用于保留模型输出和外部导入结构。
    """

    __tablename__ = "approval_records"

    contract_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    approval_record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_role: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comment_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # JSON 字段保持与 API/参考项目结构接近，后续如需要按 policyId 高频查询再拆表。
    linked_policy_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    linked_clause_chunk_ids_json: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    risk_items_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    vector_doc_id: Mapped[str | None] = mapped_column(String(128))

    contract: Mapped[ContractModel] = relationship(back_populates="approval_records")


class PolicyKnowledgeModel(Base):
    """制度/政策知识库表，是制度 RAG 和风险依据引用的权威来源。"""

    __tablename__ = "policy_knowledge"

    policy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_domain: Mapped[str] = mapped_column(String(64), nullable=False)
    applies_to_contract_type: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    trigger_keywords: Mapped[str] = mapped_column(Text, nullable=False, default="")
    control_objective: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    policy_text_for_embedding: Mapped[str] = mapped_column(Text, nullable=False)
    required_evidence: Mapped[str] = mapped_column(Text, nullable=False, default="")
    escalation_role: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    vector_doc_id: Mapped[str | None] = mapped_column(String(128))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
