from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError
from app.domain.models import ApprovalRecord, ClauseChunk, Contract, RiskItem
from app.repositories.contracts import ContractRepository
from app.schemas.contracts import (
    ImportApprovalRecordsRequest,
    ImportApprovalRecordsResponse,
    ImportContractRequest,
    ImportContractResponse,
)


class ContractApplicationService:
    def __init__(self, db: Session, contract_repository: ContractRepository) -> None:
        self.db = db
        self.contract_repository = contract_repository

    def import_contract(self, request: ImportContractRequest) -> ImportContractResponse:
        if self.contract_repository.exists(request.id):
            raise ConflictError(f"Contract already exists: {request.id}")

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
            self.contract_repository.add(contract)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ServiceUnavailableError(f"Database write failed: {exc}") from exc
        return ImportContractResponse(contract_id=contract.id)

    def import_approval_records(
        self,
        contract_id: str,
        request: ImportApprovalRecordsRequest,
    ) -> ImportApprovalRecordsResponse:
        if not self.contract_repository.exists(contract_id):
            raise NotFoundError(f"Contract not found: {contract_id}")

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
            self.contract_repository.replace_approval_records(contract_id, records)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ServiceUnavailableError(f"Database write failed: {exc}") from exc
        return ImportApprovalRecordsResponse(contract_id=contract_id, imported_count=len(records))

