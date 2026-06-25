from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import ApprovalRecordModel, ClauseChunkModel, ContractModel
from app.domain.enums import ContractType, RiskSeverity
from app.domain.models import ApprovalRecord, ClauseChunk, Contract


class ContractRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def exists(self, contract_id: str) -> bool:
        return self.db.get(ContractModel, contract_id) is not None

    def get(self, contract_id: str) -> Contract | None:
        stmt = (
            select(ContractModel)
            .options(selectinload(ContractModel.chunks))
            .where(ContractModel.id == contract_id)
        )
        model = self.db.scalars(stmt).first()
        return self._to_domain(model) if model else None

    def add(self, contract: Contract) -> None:
        self.db.add(
            ContractModel(
                id=contract.id,
                contract_type=contract.contract_type.value,
                party_a_name=contract.party_a_name,
                party_b_name=contract.party_b_name,
                currency=contract.currency,
                amount_ex_tax=contract.amount_ex_tax,
                tax_rate_pct=contract.tax_rate_pct,
                amount_inc_tax=contract.amount_inc_tax,
                sign_date=contract.sign_date,
                effective_date=contract.effective_date,
                end_date=contract.end_date,
                performance_site=contract.performance_site,
                payment_terms_summary=contract.payment_terms_summary,
                business_owner_dept=contract.business_owner_dept,
                risk_tier=contract.risk_tier.value,
                vector_doc_id=contract.vector_doc_id,
                notes=contract.notes,
            )
        )
        for chunk in contract.chunks:
            self.db.add(
                ClauseChunkModel(
                    contract_id=chunk.contract_id,
                    chunk_id=chunk.chunk_id,
                    clause_code=chunk.clause_code,
                    clause_title=chunk.clause_title,
                    clause_category=chunk.clause_category,
                    party_focus=chunk.party_focus,
                    risk_flag=chunk.risk_flag.value,
                    source_section=chunk.source_section,
                    text_for_embedding=chunk.text_for_embedding,
                    related_amount_field=chunk.related_amount_field,
                    review_priority=chunk.review_priority,
                )
            )
        self.db.flush()

    def replace_approval_records(self, contract_id: str, records: list[ApprovalRecord]) -> None:
        self.db.execute(
            delete(ApprovalRecordModel).where(ApprovalRecordModel.contract_id == contract_id)
        )
        for record in records:
            self.db.add(
                ApprovalRecordModel(
                    contract_id=record.contract_id,
                    approval_record_id=record.approval_record_id,
                    step_no=record.step_no,
                    approver_role=record.approver_role,
                    decision=record.decision.value,
                    decision_time=record.decision_time,
                    comment_summary=record.comment_summary,
                    linked_policy_ids_json=record.linked_policy_ids,
                    linked_clause_chunk_ids_json=record.linked_clause_chunk_ids,
                    risk_items_json=[
                        {
                            "code": item.code,
                            "severity": item.severity.value,
                            "detail": item.detail,
                            "relatedClauseChunkIds": item.related_clause_chunk_ids,
                            "relatedPolicyIds": item.related_policy_ids,
                            "requiredEvidence": item.required_evidence,
                            "escalationRole": item.escalation_role,
                        }
                        for item in record.risk_items
                    ],
                    vector_doc_id=record.vector_doc_id,
                )
            )
        self.db.flush()

    def approval_record_count(self, contract_id: str) -> int:
        stmt = select(ApprovalRecordModel).where(ApprovalRecordModel.contract_id == contract_id)
        return len(list(self.db.scalars(stmt)))

    def _to_domain(self, model: ContractModel) -> Contract:
        chunks = [
            ClauseChunk(
                contract_id=chunk.contract_id,
                chunk_id=chunk.chunk_id,
                clause_code=chunk.clause_code,
                clause_title=chunk.clause_title,
                clause_category=chunk.clause_category,
                party_focus=chunk.party_focus,
                risk_flag=RiskSeverity.from_flexible(chunk.risk_flag),
                source_section=chunk.source_section,
                text_for_embedding=chunk.text_for_embedding,
                related_amount_field=chunk.related_amount_field,
                review_priority=chunk.review_priority,
            )
            for chunk in model.chunks
        ]
        return Contract(
            id=model.id,
            contract_type=ContractType.from_flexible(model.contract_type),
            party_a_name=model.party_a_name,
            party_b_name=model.party_b_name,
            currency=model.currency,
            amount_ex_tax=model.amount_ex_tax,
            tax_rate_pct=model.tax_rate_pct,
            amount_inc_tax=model.amount_inc_tax,
            sign_date=model.sign_date,
            effective_date=model.effective_date,
            end_date=model.end_date,
            performance_site=model.performance_site,
            payment_terms_summary=model.payment_terms_summary,
            business_owner_dept=model.business_owner_dept,
            risk_tier=RiskSeverity.from_flexible(model.risk_tier),
            vector_doc_id=model.vector_doc_id,
            notes=model.notes,
            chunks=chunks,
        )
