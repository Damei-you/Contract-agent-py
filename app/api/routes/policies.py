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
    return service.import_policies(request)
