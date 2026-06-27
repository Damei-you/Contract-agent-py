"""合同风险检查应用服务。

本服务是 HTTP 层和 LangGraph 风险检查 workflow 之间的门面：路由只感知响应 DTO，
风险检查的节点状态、模型输出原文和解析兜底留在 app.ai.graphs 内。
"""

from typing import Protocol

from app.ai.graphs.state import RiskCheckState
from app.schemas.contracts import ContractRiskCheckResponse


class RiskCheckWorkflowPort(Protocol):
    """风险检查服务依赖的最小 workflow 接口。"""

    def invoke(self, contract_id: str) -> RiskCheckState:
        """执行风险检查图并返回最终 state。"""


class ContractRiskCheckApplicationService:
    """结构化风险检查用例编排入口。"""

    def __init__(self, risk_workflow: RiskCheckWorkflowPort) -> None:
        self.risk_workflow = risk_workflow

    def check_risk(self, contract_id: str) -> ContractRiskCheckResponse:
        """检查指定合同的结构化风险。

        合同不存在由 workflow 抛出项目级 404；模型 JSON 解析失败不抛错，而是按 MVP 语义
        返回原文 summary 和空 riskItems。
        """

        state = self.risk_workflow.invoke(contract_id=contract_id)
        response = state.get("response")
        if not response:
            raise RuntimeError("Risk check workflow did not produce a response.")
        return ContractRiskCheckResponse.model_validate(response)
