"""制度知识库应用服务。

制度条目是风险检查和审批辅助的权威规则来源；向量库只保存由这些条目派生的检索索引。
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.rag.ingestion import PolicyVectorIngestionService
from app.core.exceptions import ServiceUnavailableError
from app.domain.models import PolicyKnowledgeItem
from app.repositories.policies import PolicyKnowledgeRepository
from app.schemas.policies import ImportPolicyKnowledgeRequest, ImportPolicyKnowledgeResponse


class PolicyKnowledgeApplicationService:
    """制度知识库导入用例编排入口。"""

    def __init__(
        self,
        db: Session,
        policy_repository: PolicyKnowledgeRepository,
        vector_ingestion: PolicyVectorIngestionService | None = None,
    ) -> None:
        self.db = db
        self.policy_repository = policy_repository
        self.vector_ingestion = vector_ingestion

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
        vector_warning = self._sync_policy_vectors(items)
        return ImportPolicyKnowledgeResponse(
            imported_count=len(items),
            policy_ids=[item.policy_id for item in items],
            vector_ingestion_warning=vector_warning,
        )

    def _sync_policy_vectors(self, items: list[PolicyKnowledgeItem]) -> str | None:
        """同步制度知识向量索引。

        制度业务表已经提交后才执行向量写入；失败时返回 warning，调用方可安全重试导入。
        """

        if not items:
            return None
        if self.vector_ingestion is None:
            return "Vector ingestion skipped: OPENAI_API_KEY is not configured."
        try:
            self.vector_ingestion.ingest(items)
        except Exception as exc:  # noqa: BLE001
            return (
                f"Vector store sync failed: {exc}. "
                "Business table updated; retry import to re-sync."
            )
        return None
