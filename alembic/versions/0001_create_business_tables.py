"""create business tables.

本迁移创建阶段 0-2 所需的业务权威表。向量索引表不在这里创建，后续阶段会交给
LangChain PGVector/pgvector 集成管理。

Revision ID: 0001_create_business_tables
Revises:
Create Date: 2026-06-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_create_business_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建合同、条款、审批记录和制度知识库表。"""

    op.create_table(
        "contracts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("contract_type", sa.String(length=32), nullable=False),
        sa.Column("party_a_name", sa.String(length=255), nullable=False),
        sa.Column("party_b_name", sa.String(length=255), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="CNY"),
        sa.Column("amount_ex_tax", sa.Numeric(19, 2), nullable=False),
        sa.Column("tax_rate_pct", sa.Numeric(10, 4), nullable=False),
        sa.Column("amount_inc_tax", sa.Numeric(19, 2), nullable=False),
        sa.Column("sign_date", sa.Date(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("performance_site", sa.Text(), nullable=False, server_default=""),
        sa.Column("payment_terms_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("business_owner_dept", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("risk_tier", sa.String(length=16), nullable=False),
        sa.Column("vector_doc_id", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "clause_chunks",
        sa.Column("contract_id", sa.String(length=64), nullable=False),
        sa.Column("chunk_id", sa.String(length=64), nullable=False),
        sa.Column("clause_code", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("clause_title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("clause_category", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("party_focus", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("risk_flag", sa.String(length=16), nullable=False, server_default="LOW"),
        sa.Column("source_section", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("text_for_embedding", sa.Text(), nullable=False),
        sa.Column("related_amount_field", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("review_priority", sa.String(length=32), nullable=False, server_default=""),
        # 条款必须随合同删除，防止后续合同通道 RAG 召回孤儿条款。
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("contract_id", "chunk_id"),
    )
    op.create_index("idx_clause_chunks_contract_id", "clause_chunks", ["contract_id"])
    op.create_table(
        "approval_records",
        sa.Column("contract_id", sa.String(length=64), nullable=False),
        sa.Column("approval_record_id", sa.String(length=64), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("approver_role", sa.String(length=255), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("decision_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment_summary", sa.Text(), nullable=False, server_default=""),
        # 这些 JSON 字段保留外部导入和模型输出结构，查询需求明确后再拆明细表。
        sa.Column("linked_policy_ids_json", sa.JSON(), nullable=False),
        sa.Column("linked_clause_chunk_ids_json", sa.JSON(), nullable=False),
        sa.Column("risk_items_json", sa.JSON(), nullable=False),
        sa.Column("vector_doc_id", sa.String(length=128), nullable=True),
        # 审批记录依附于合同生命周期，不作为独立长期事实保存。
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("contract_id", "approval_record_id"),
    )
    op.create_index("idx_approval_records_contract_id", "approval_records", ["contract_id"])
    op.create_index(
        "idx_approval_records_contract_step",
        "approval_records",
        ["contract_id", "step_no"],
    )
    op.create_table(
        "policy_knowledge",
        sa.Column("policy_id", sa.String(length=64), primary_key=True),
        sa.Column("policy_domain", sa.String(length=64), nullable=False),
        sa.Column("applies_to_contract_type", sa.String(length=255), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("trigger_keywords", sa.Text(), nullable=False, server_default=""),
        sa.Column("control_objective", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("policy_text_for_embedding", sa.Text(), nullable=False),
        sa.Column("required_evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("escalation_role", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("vector_doc_id", sa.String(length=128), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_policy_knowledge_domain", "policy_knowledge", ["policy_domain"])
    op.create_index("idx_policy_knowledge_severity", "policy_knowledge", ["severity"])
    op.create_index(
        "idx_policy_knowledge_contract_type",
        "policy_knowledge",
        ["applies_to_contract_type"],
    )


def downgrade() -> None:
    """按依赖关系逆序删除业务表。"""

    op.drop_index("idx_policy_knowledge_contract_type", table_name="policy_knowledge")
    op.drop_index("idx_policy_knowledge_severity", table_name="policy_knowledge")
    op.drop_index("idx_policy_knowledge_domain", table_name="policy_knowledge")
    op.drop_table("policy_knowledge")
    op.drop_index("idx_approval_records_contract_step", table_name="approval_records")
    op.drop_index("idx_approval_records_contract_id", table_name="approval_records")
    op.drop_table("approval_records")
    op.drop_index("idx_clause_chunks_contract_id", table_name="clause_chunks")
    op.drop_table("clause_chunks")
    op.drop_table("contracts")
