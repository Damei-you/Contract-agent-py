"""制度知识库应用服务。

制度条目是风险检查和审批辅助的权威规则来源；向量库只保存由这些条目派生的检索索引。
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import ServiceUnavailableError
from app.domain.models import PolicyKnowledgeItem
from app.repositories.policies import PolicyKnowledgeRepository
from app.schemas.policies import ImportPolicyKnowledgeRequest, ImportPolicyKnowledgeResponse


class PolicyKnowledgeApplicationService:
    """制度知识库导入用例编排入口。"""

    def __init__(self, db: Session, policy_repository: PolicyKnowledgeRepository) -> None:
        self.db = db
        self.policy_repository = policy_repository

    def import_policies(
        self,
        request: ImportPolicyKnowledgeRequest,
    ) -> ImportPolicyKnowledgeResponse:
        """按 policyId 幂等导入制度条目。

        同一批请求内重复 policyId 采用 last-wins 语义，和参考项目保持一致；这样调用方
        重试导入时不会制造重复规则。
        """

        # Python dict 保留插入顺序；重复 key 会被最后一条覆盖，正好表达 last-wins。
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
            # 业务表是权威数据，后续向量写入失败时也应能基于业务表重建索引。
            self.policy_repository.upsert_many(items)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ServiceUnavailableError(f"Database write failed: {exc}") from exc
        return ImportPolicyKnowledgeResponse(
            imported_count=len(items),
            policy_ids=[item.policy_id for item in items],
        )
