from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import PolicyKnowledgeModel
from app.domain.models import PolicyKnowledgeItem


class PolicyKnowledgeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_many(self, items: list[PolicyKnowledgeItem]) -> None:
        now = datetime.now(UTC)
        for item in items:
            model = self.db.get(PolicyKnowledgeModel, item.policy_id)
            if model is None:
                model = PolicyKnowledgeModel(policy_id=item.policy_id)
                self.db.add(model)
            model.policy_domain = item.policy_domain
            model.applies_to_contract_type = item.applies_to_contract_type
            model.severity = item.severity.value
            model.trigger_keywords = item.trigger_keywords
            model.control_objective = item.control_objective
            model.policy_text_for_embedding = item.policy_text_for_embedding
            model.required_evidence = item.required_evidence
            model.escalation_role = item.escalation_role
            model.vector_doc_id = item.vector_doc_id
            model.updated_at = now
        self.db.flush()

