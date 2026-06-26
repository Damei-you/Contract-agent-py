"""合同相关 HTTP 路由。

当前阶段只实现导入类接口：合同导入和审批记录导入。问答、风险检查、审批辅助
会在 LangGraph 工作流阶段接入，但 URL 设计保持与参考项目兼容。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.rag.ingestion import ContractVectorIngestionService
from app.ai.rag.vector_store import build_contract_vector_ingestion_service
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


def get_contract_vector_ingestion_service() -> ContractVectorIngestionService | None:
    """创建合同条款向量入库服务。

    缺少模型配置时返回 None，由应用服务把向量同步降级为 warning，不影响业务表导入。
    """

    return build_contract_vector_ingestion_service()


ContractVectorIngestion = Annotated[
    ContractVectorIngestionService | None,
    Depends(get_contract_vector_ingestion_service),
]


def get_contract_service(
    db: DbSession,
    vector_ingestion: ContractVectorIngestion,
) -> ContractApplicationService:
    """为单次请求创建应用服务。

    repository 与 Session 共享同一个事务边界，由 service 决定 commit/rollback。
    """

    return ContractApplicationService(
        db=db,
        contract_repository=ContractRepository(db),
        vector_ingestion=vector_ingestion,
    )


ContractService = Annotated[ContractApplicationService, Depends(get_contract_service)]


@router.post("/import", response_model=ImportContractResponse, response_model_exclude_none=True)
def import_contract(
    request: ImportContractRequest,
    service: ContractService,
) -> ImportContractResponse:
    """导入合同主数据和条款分块。

    该接口语义是“导入快照”，同一合同 ID 重复提交会先删除旧事实再写入本次内容；
    向量入库作为派生索引流程接在业务表提交之后。
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
