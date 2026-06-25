"""合同相关 HTTP 路由。

当前阶段只实现导入类接口：合同导入和审批记录导入。问答、风险检查、审批辅助
会在 LangGraph 工作流阶段接入，但 URL 设计保持与参考项目兼容。
"""

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
    """为单次请求创建应用服务。

    repository 与 Session 共享同一个事务边界，由 service 决定 commit/rollback。
    """

    return ContractApplicationService(db=db, contract_repository=ContractRepository(db))


ContractService = Annotated[ContractApplicationService, Depends(get_contract_service)]


@router.post("/import", response_model=ImportContractResponse)
def import_contract(
    request: ImportContractRequest,
    service: ContractService,
) -> ImportContractResponse:
    """导入合同主数据和条款分块。

    该接口当前语义是“创建”，同一合同 ID 重复提交返回 409；后续向量入库会作为
    派生索引流程接到 service 层之后。
    """

    return service.import_contract(request)


@router.post("/{contract_id}/approval-records/import", response_model=ImportApprovalRecordsResponse)
def import_approval_records(
    contract_id: str,
    request: ImportApprovalRecordsRequest,
    service: ContractService,
) -> ImportApprovalRecordsResponse:
    """全量替换指定合同的审批历史。

    参考项目采用导入型接口，调用方提交的是当前合同审批记录快照；因此这里不是追加，
    而是先删除旧记录再写入新记录。
    """

    return service.import_approval_records(contract_id, request)
