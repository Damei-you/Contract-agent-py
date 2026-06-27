"""合同问答应用服务。

本服务是 HTTP 层和 LangGraph workflow 之间的门面：路由只感知请求/响应 DTO，AI 编排细节
保留在 app.ai.graphs 内。
"""

from typing import Protocol

from app.ai.graphs.state import ContractQaState
from app.schemas.contracts import ContractQaRequest, ContractQaResponse


class ContractQaWorkflowPort(Protocol):
    """合同问答服务依赖的最小 workflow 接口。"""

    def invoke(
        self,
        contract_id: str,
        question: str,
    ) -> ContractQaState:
        """执行合同问答图并返回最终 state。"""


class ContractQaApplicationService:
    """合同问答用例编排入口。"""

    def __init__(self, qa_workflow: ContractQaWorkflowPort) -> None:
        self.qa_workflow = qa_workflow

    def answer_question(
        self,
        contract_id: str,
        request: ContractQaRequest,
    ) -> ContractQaResponse:
        """回答指定合同的问题。

        合同不存在由 workflow 抛出项目级 404；模型或向量检索异常保持为服务端异常，
        与 contract-agent-mvp 的默认错误语义一致。
        """

        state = self.qa_workflow.invoke(
            contract_id=contract_id,
            question=request.question,
        )

        response = state.get("response")
        if not response:
            raise RuntimeError("Contract QA workflow did not produce a response.")
        return ContractQaResponse.model_validate(response)
