"""合同审批辅助应用服务。

本服务是 HTTP 层和 LangGraph 审批辅助 workflow 之间的门面：路由只感知请求/响应 DTO，
审批建议生成、双通道召回和 trace 细节保留在 app.ai.graphs 内。
"""

from typing import Protocol

from app.ai.graphs.state import ApprovalAssistState
from app.schemas.contracts import ApprovalAssistRequest, ApprovalAssistResponse


class ApprovalAssistWorkflowPort(Protocol):
    """审批辅助服务依赖的最小 workflow 接口。"""

    def invoke(
        self,
        contract_id: str,
        approver_role: str,
        focus: str = "",
    ) -> ApprovalAssistState:
        """执行审批辅助图并返回最终 state。"""


class ContractApprovalAssistApplicationService:
    """审批辅助用例编排入口。"""

    def __init__(self, approval_workflow: ApprovalAssistWorkflowPort) -> None:
        self.approval_workflow = approval_workflow

    def assist(
        self,
        contract_id: str,
        request: ApprovalAssistRequest,
    ) -> ApprovalAssistResponse:
        """为指定合同和审批角色生成建议。

        合同不存在由 workflow 抛出项目级 404；模型 JSON 解析失败时按 MVP 语义返回原文
        suggestion 和空 checklist，RAG 命中 ID 仍保留在响应中。
        """

        state = self.approval_workflow.invoke(
            contract_id=contract_id,
            approver_role=request.approver_role,
            focus=request.focus,
        )
        response = state.get("response")
        if not response:
            raise RuntimeError("Approval assist workflow did not produce a response.")
        return ApprovalAssistResponse.model_validate(response)
