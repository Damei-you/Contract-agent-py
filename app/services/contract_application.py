"""合同应用服务。

应用服务负责把 API DTO 映射为领域对象，并控制业务事务边界。阶段 0-2 只处理
业务权威表；合同条款向量入库会在阶段 3 作为可重建的派生索引接入。
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.rag.ingestion import ContractVectorIngestionService
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.domain.models import ApprovalRecord, ClauseChunk, Contract, RiskItem
from app.repositories.contracts import ContractRepository
from app.schemas.contracts import (
    ImportApprovalRecordsRequest,
    ImportApprovalRecordsResponse,
    ImportContractRequest,
    ImportContractResponse,
)


class ContractApplicationService:
    """合同用例编排入口。

    该类不直接依赖 FastAPI，便于在测试、CLI 或未来异步任务中复用同一套业务逻辑。
    """

    def __init__(
        self,
        db: Session,
        contract_repository: ContractRepository,
        vector_ingestion: ContractVectorIngestionService | None = None,
    ) -> None:
        self.db = db
        self.contract_repository = contract_repository
        self.vector_ingestion = vector_ingestion

    def import_contract(self, request: ImportContractRequest) -> ImportContractResponse:
        """导入合同和条款分块。

        同一合同 ID 重复导入采用先删后插的快照覆盖语义，和参考项目导入流程保持一致。
        """

        # DTO 字段保持参考项目 API 命名，领域对象使用 Python 内部命名；
        # 映射集中在 service 层，避免仓储层感知 HTTP 请求结构。
        old_contract = self.contract_repository.get(request.id)
        contract = Contract(
            id=request.id,
            contract_type=request.contract_type,
            party_a_name=request.party_a_name,
            party_b_name=request.party_b_name,
            currency=request.currency,
            amount_ex_tax=request.amount_ex_tax,
            tax_rate_pct=request.tax_rate_pct,
            amount_inc_tax=request.amount_inc_tax,
            sign_date=request.sign_date,
            effective_date=request.effective_date,
            end_date=request.end_date,
            performance_site=request.performance_site,
            payment_terms_summary=request.payment_terms_summary,
            business_owner_dept=request.business_owner_dept,
            risk_tier=request.risk_tier,
            vector_doc_id=request.vector_doc_id,
            notes=request.notes,
            chunks=[
                ClauseChunk(
                    contract_id=request.id,
                    chunk_id=chunk.id,
                    clause_code=chunk.clause_code,
                    clause_title=chunk.clause_title,
                    clause_category=chunk.clause_category,
                    party_focus=chunk.party_focus,
                    risk_flag=chunk.risk_flag,
                    source_section=chunk.source_section,
                    text_for_embedding=chunk.text_for_embedding,
                    related_amount_field=chunk.related_amount_field,
                    review_priority=chunk.review_priority,
                )
                for chunk in request.chunks
            ],
        )
        try:
            # 这里按导入快照覆盖：旧审批记录、旧条款和旧合同必须在同一事务内清理，
            # 再写入新合同快照，否则重复导入会残留过期事实。
            self.contract_repository.replace_contract(contract)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ServiceUnavailableError(f"Database write failed: {exc}") from exc

        vector_warning = self._sync_contract_vectors(contract, old_contract)
        return ImportContractResponse(
            contract_id=contract.id,
            vector_ingestion_warning=vector_warning,
        )

    def import_approval_records(
        self,
        contract_id: str,
        request: ImportApprovalRecordsRequest,
    ) -> ImportApprovalRecordsResponse:
        """全量替换合同审批记录。

        审批记录是合同的附属事实，必须先确认合同存在；不存在时返回 404 而不是静默创建。
        """

        if not self.contract_repository.exists(contract_id):
            raise NotFoundError(f"Contract not found: {contract_id}")

        # 风险项当前存入 JSON 字段，保留参考项目的结构化输出形状；
        # 后续查询维度变多时再拆成明细表。
        records = [
            ApprovalRecord(
                contract_id=contract_id,
                approval_record_id=record.id,
                step_no=record.step_no,
                approver_role=record.approver_role,
                decision=record.decision,
                decision_time=record.decision_time,
                comment_summary=record.comment_summary,
                linked_policy_ids=record.linked_policy_ids,
                linked_clause_chunk_ids=record.linked_clause_chunk_ids,
                risk_items=[
                    RiskItem(
                        code=item.code,
                        severity=item.severity,
                        detail=item.detail,
                        related_clause_chunk_ids=item.related_clause_chunk_ids,
                        related_policy_ids=item.related_policy_ids,
                        required_evidence=item.required_evidence,
                        escalation_role=item.escalation_role,
                    )
                    for item in record.risk_items
                ],
                vector_doc_id=record.vector_doc_id,
            )
            for record in request.records
        ]
        try:
            # replace_approval_records 内部先删后写，commit 放在 service 层统一处理。
            self.contract_repository.replace_approval_records(contract_id, records)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ServiceUnavailableError(f"Database write failed: {exc}") from exc
        return ImportApprovalRecordsResponse(contract_id=contract_id, imported_count=len(records))

    def _sync_contract_vectors(
        self,
        contract: Contract,
        old_contract: Contract | None = None,
    ) -> str | None:
        """同步合同条款向量索引。

        向量库是派生索引，失败时只返回 warning；业务表已经提交，不应再回滚。
        """

        old_chunks = old_contract.chunks if old_contract else []
        if not contract.chunks and not old_chunks:
            return None
        if self.vector_ingestion is None:
            return "Vector ingestion skipped: OPENAI_API_KEY is not configured."
        try:
            if old_chunks:
                self.vector_ingestion.replace(old_chunks, contract.chunks)
            else:
                self.vector_ingestion.ingest(contract.chunks)
        except Exception as exc:  # noqa: BLE001
            return (
                f"Vector store sync failed: {exc}. "
                "Business table updated; retry import to re-sync."
            )
        return None
