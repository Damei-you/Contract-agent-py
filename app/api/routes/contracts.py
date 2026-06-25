from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.contracts import ContractRepository
from app.schemas.contracts import (
    ImportApprovalRecordsRequest,
    ImportApprovalRecordsResponse,
    ImportContractRequest,
    ImportContractResponse,
)
from app.services.contract_application import ContractApplicationService

router = APIRouter(prefix="/api/contracts", tags=["contracts"])

DbSession = Annotated[Session, Depends(get_db)]


def get_contract_service(db: DbSession) -> ContractApplicationService:
    return ContractApplicationService(db=db, contract_repository=ContractRepository(db))


ContractService = Annotated[ContractApplicationService, Depends(get_contract_service)]


@router.post("/import", response_model=ImportContractResponse)
def import_contract(
    request: ImportContractRequest,
    service: ContractService,
) -> ImportContractResponse:
    return service.import_contract(request)


@router.post("/{contract_id}/approval-records/import", response_model=ImportApprovalRecordsResponse)
def import_approval_records(
    contract_id: str,
    request: ImportApprovalRecordsRequest,
    service: ContractService,
) -> ImportApprovalRecordsResponse:
    return service.import_approval_records(contract_id, request)
