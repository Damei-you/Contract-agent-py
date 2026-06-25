"""制度/政策知识库 HTTP 路由。

制度条目是跨合同共享的规则来源，后续风险检查和审批辅助会通过 policyId 引用这里
导入的权威业务数据。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.policies import PolicyKnowledgeRepository
from app.schemas.policies import ImportPolicyKnowledgeRequest, ImportPolicyKnowledgeResponse
from app.services.policy_application import PolicyKnowledgeApplicationService

router = APIRouter(prefix="/api/policies", tags=["policies"])

DbSession = Annotated[Session, Depends(get_db)]


def get_policy_service(db: DbSession) -> PolicyKnowledgeApplicationService:
    """为单次请求创建制度知识库应用服务。"""

    return PolicyKnowledgeApplicationService(
        db=db,
        policy_repository=PolicyKnowledgeRepository(db),
    )


PolicyService = Annotated[PolicyKnowledgeApplicationService, Depends(get_policy_service)]


@router.post("/import", response_model=ImportPolicyKnowledgeResponse)
def import_policies(
    request: ImportPolicyKnowledgeRequest,
    service: PolicyService,
) -> ImportPolicyKnowledgeResponse:
    """按 policyId 幂等导入制度条目。

    同一请求或多次请求中重复的 policyId 采用 last-wins 覆盖语义，保证后续风险项
    引用的 policyId 始终能回查到最新制度内容。
    """

    return service.import_policies(request)
