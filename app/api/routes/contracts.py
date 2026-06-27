"""合同相关 HTTP 路由。

当前包含合同导入、审批记录导入，以及问答、风险检查、审批辅助三个 LangGraph 能力接口；
URL 设计保持与参考项目兼容。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.graphs.approval_assist_graph import (
    EmptyContractContextRetriever as ApprovalEmptyContractContextRetriever,
)
from app.ai.graphs.approval_assist_graph import (
    EmptyPolicyContextRetriever as ApprovalEmptyPolicyContextRetriever,
)
from app.ai.graphs.approval_assist_graph import build_approval_assist_workflow
from app.ai.graphs.contract_qa_graph import (
    EmptyContractContextRetriever,
    EmptyPolicyContextRetriever,
    build_contract_qa_workflow,
)
from app.ai.graphs.risk_check_graph import (
    EmptyContractContextRetriever as RiskEmptyContractContextRetriever,
)
from app.ai.graphs.risk_check_graph import (
    EmptyPolicyContextRetriever as RiskEmptyPolicyContextRetriever,
)
from app.ai.graphs.risk_check_graph import build_risk_check_workflow
from app.ai.langchain_factory import create_chat_model
from app.ai.rag.ingestion import ContractVectorIngestionService
from app.ai.rag.vector_store import (
    build_contract_rag_retriever,
    build_contract_vector_ingestion_service,
    build_policy_rag_retriever,
)
from app.core.config import get_settings
from app.core.exceptions import ServiceUnavailableError
from app.db.session import get_db
from app.repositories.contracts import ContractRepository
from app.schemas.contracts import (
    ApprovalAssistRequest,
    ApprovalAssistResponse,
    ContractQaRequest,
    ContractQaResponse,
    ContractRiskCheckResponse,
    ImportApprovalRecordsRequest,
    ImportApprovalRecordsResponse,
    ImportContractRequest,
    ImportContractResponse,
)
from app.services.contract_application import ContractApplicationService
from app.services.contract_approval_assist import ContractApprovalAssistApplicationService
from app.services.contract_qa import ContractQaApplicationService
from app.services.contract_risk_check import ContractRiskCheckApplicationService

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


def get_contract_qa_service(db: DbSession) -> ContractQaApplicationService:
    """创建合同问答应用服务。

    QA 依赖 ChatModel 和两个 RAG retriever；这些外部依赖只在问答接口中创建，避免影响导入类接口。
    """

    settings = get_settings()
    if not settings.openai_api_key:
        raise ServiceUnavailableError("Contract QA requires OPENAI_API_KEY.")
    contract_retriever = build_contract_rag_retriever(settings)
    policy_retriever = build_policy_rag_retriever(settings)

    workflow = build_contract_qa_workflow(
        contract_repository=ContractRepository(db),
        contract_retriever=contract_retriever or EmptyContractContextRetriever(),
        policy_retriever=policy_retriever or EmptyPolicyContextRetriever(),
        chat_model=create_chat_model(settings),
    )
    return ContractQaApplicationService(workflow)


ContractQaService = Annotated[ContractQaApplicationService, Depends(get_contract_qa_service)]


def get_contract_risk_check_service(db: DbSession) -> ContractRiskCheckApplicationService:
    """创建合同风险检查应用服务。

    风险检查依赖 ChatModel；RAG retriever 按参考项目软依赖处理，缺失时使用空上下文。
    """

    settings = get_settings()
    if not settings.openai_api_key:
        raise ServiceUnavailableError("Contract risk check requires OPENAI_API_KEY.")
    contract_retriever = build_contract_rag_retriever(settings)
    policy_retriever = build_policy_rag_retriever(settings)

    workflow = build_risk_check_workflow(
        contract_repository=ContractRepository(db),
        contract_retriever=contract_retriever or RiskEmptyContractContextRetriever(),
        policy_retriever=policy_retriever or RiskEmptyPolicyContextRetriever(),
        chat_model=create_chat_model(settings),
    )
    return ContractRiskCheckApplicationService(workflow)


ContractRiskCheckService = Annotated[
    ContractRiskCheckApplicationService,
    Depends(get_contract_risk_check_service),
]


def get_contract_approval_assist_service(db: DbSession) -> ContractApprovalAssistApplicationService:
    """创建合同审批辅助应用服务。

    审批辅助依赖 ChatModel；RAG retriever 按参考项目软依赖处理，缺失时使用空上下文。
    """

    settings = get_settings()
    if not settings.openai_api_key:
        raise ServiceUnavailableError("Contract approval assist requires OPENAI_API_KEY.")
    contract_retriever = build_contract_rag_retriever(settings)
    policy_retriever = build_policy_rag_retriever(settings)

    workflow = build_approval_assist_workflow(
        contract_repository=ContractRepository(db),
        contract_retriever=contract_retriever or ApprovalEmptyContractContextRetriever(),
        policy_retriever=policy_retriever or ApprovalEmptyPolicyContextRetriever(),
        chat_model=create_chat_model(settings),
    )
    return ContractApprovalAssistApplicationService(workflow)


ContractApprovalAssistService = Annotated[
    ContractApprovalAssistApplicationService,
    Depends(get_contract_approval_assist_service),
]


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


@router.post("/{contract_id}/qa", response_model=ContractQaResponse)
def answer_contract_question(
    contract_id: str,
    request: ContractQaRequest,
    service: ContractQaService,
) -> ContractQaResponse:
    """基于当前合同条款和适用制度回答问题。

    该接口是读模型能力，不修改业务表；合同不存在返回 404，缺少模型配置时返回 503。
    """

    return service.answer_question(contract_id, request)


@router.post("/{contract_id}/risk-check", response_model=ContractRiskCheckResponse)
def check_contract_risk(
    contract_id: str,
    service: ContractRiskCheckService,
) -> ContractRiskCheckResponse:
    """对指定合同执行结构化风险检查。

    该接口是读模型能力，不修改业务表；合同不存在返回 404，缺少模型配置时返回 503。
    """

    return service.check_risk(contract_id)


@router.post("/{contract_id}/approval-assist", response_model=ApprovalAssistResponse)
def assist_contract_approval(
    contract_id: str,
    request: ApprovalAssistRequest,
    service: ContractApprovalAssistService,
) -> ApprovalAssistResponse:
    """为当前审批角色生成建议和核对清单。

    该接口是读模型能力，不修改业务表；合同不存在返回 404，缺少模型配置时返回 503。
    """

    return service.assist(contract_id, request)


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
