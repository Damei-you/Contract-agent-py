from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import ServiceUnavailableError
from app.domain.models import PolicyKnowledgeItem
from app.repositories.policies import PolicyKnowledgeRepository
from app.schemas.policies import ImportPolicyKnowledgeRequest, ImportPolicyKnowledgeResponse


class PolicyKnowledgeApplicationService:
    def __init__(self, db: Session, policy_repository: PolicyKnowledgeRepository) -> None:
        self.db = db
        self.policy_repository = policy_repository

    def import_policies(
        self,
        request: ImportPolicyKnowledgeRequest,
    ) -> ImportPolicyKnowledgeResponse:
        deduped = {policy.policy_id: policy for policy in request.policies}
        items = [
            PolicyKnowledgeItem(
                policy_id=policy.policy_id,
                policy_domain=policy.policy_domain,
                applies_to_contract_type=policy.applies_to_contract_type,
                severity=policy.severity,
                trigger_keywords=policy.trigger_keywords,
                control_objective=policy.control_objective,
                policy_text_for_embedding=policy.policy_text_for_embedding,
                required_evidence=policy.required_evidence,
                escalation_role=policy.escalation_role,
                vector_doc_id=policy.vector_doc_id,
            )
            for policy in deduped.values()
        ]
        try:
            self.policy_repository.upsert_many(items)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ServiceUnavailableError(f"Database write failed: {exc}") from exc
        return ImportPolicyKnowledgeResponse(
            imported_count=len(items),
            policy_ids=[item.policy_id for item in items],
        )

