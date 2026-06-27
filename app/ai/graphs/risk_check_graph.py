"""结构化风险检查 LangGraph workflow。

执行逻辑对齐参考项目 `AiContractAssistant#riskCheck`：使用固定宽检索词获取合同事实和制度依据，
拼入历史审批摘要，要求模型输出结构化 JSON，并返回多 Agent 风格 trace。
"""

from typing import Any, Protocol

from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph

from app.ai.chains.qa import CONTRACT_TYPE_DISPLAY_NAMES
from app.ai.chains.risk_check import (
    build_risk_check_chain,
    build_risk_check_prompt_input,
    parse_risk_response,
)
from app.ai.graphs.state import AgentTraceState, RiskCheckState
from app.ai.rag.retrievers import RagRetrievedDocument
from app.core.exceptions import NotFoundError
from app.domain.enums import ApprovalDecision, ContractType
from app.domain.models import ApprovalRecord, Contract, RiskItem

# 风险检查需要比问答覆盖更宽的条款与制度范围；demo 阶段不做分批压缩，
# 直接把两个通道召回上限放宽到 20，降低遗漏明显风险点的概率。
RAG_TOP_K = 20
POLICY_TOP_K = 20
BROAD_RISK_QUERY = "价格 付款 发票 税务 验收 质保 违约 责任 保密 分包 数据 驻场"
NO_APPROVAL_HISTORY_PLACEHOLDER = "（暂无审批记录）"

APPROVAL_DECISION_DISPLAY_NAMES = {
    ApprovalDecision.APPROVED: "通过",
    ApprovalDecision.CONDITIONAL_APPROVED: "附条件通过",
    ApprovalDecision.REJECTED: "退回",
    ApprovalDecision.RETURNED: "退回",
}


class RiskCheckRepositoryPort(Protocol):
    """风险检查图需要的最小合同仓储接口。"""

    def get(self, contract_id: str) -> Contract | None:
        """按合同 ID 读取合同和条款分块。"""

    def list_approval_records(self, contract_id: str) -> list[ApprovalRecord]:
        """按合同 ID 读取审批历史，供 Prompt 生成摘要。"""


class ContractContextRetrieverPort(Protocol):
    """合同条款召回接口。"""

    def retrieve(
        self,
        contract_id: str,
        query: str,
        top_k: int | None = None,
    ) -> list[RagRetrievedDocument]:
        """召回指定合同下与固定风险检索词相关的条款。"""


class PolicyContextRetrieverPort(Protocol):
    """制度依据召回接口。"""

    def retrieve(
        self,
        contract_type: ContractType | str,
        query: str,
        top_k: int | None = None,
    ) -> list[RagRetrievedDocument]:
        """召回适用于合同类型的风险相关制度。"""


class RiskCheckWorkflow:
    """编译后的结构化风险检查 workflow 门面。"""

    def __init__(self, graph_app: Runnable[RiskCheckState, RiskCheckState]) -> None:
        self.graph_app = graph_app

    def invoke(self, contract_id: str) -> RiskCheckState:
        """执行风险检查图并返回最终 state。"""

        initial_state: RiskCheckState = {
            "contract_id": contract_id,
            "broad_query": BROAD_RISK_QUERY,
            "agent_trace": [],
        }
        return self.graph_app.invoke(initial_state)


class EmptyContractContextRetriever:
    """未装配合同 RAG 时返回空列表，对齐 contract-agent-mvp 的 ObjectProvider 软依赖。"""

    def retrieve(
        self,
        contract_id: str,
        query: str,
        top_k: int | None = None,
    ) -> list[RagRetrievedDocument]:
        """返回空合同条款上下文。"""

        return []


class EmptyPolicyContextRetriever:
    """未装配制度 RAG 时返回空列表，对齐 contract-agent-mvp 的 ObjectProvider 软依赖。"""

    def retrieve(
        self,
        contract_type: ContractType | str,
        query: str,
        top_k: int | None = None,
    ) -> list[RagRetrievedDocument]:
        """返回空制度上下文。"""

        return []


class _RiskCheckNodes:
    """风险检查图节点集合。"""

    def __init__(
        self,
        contract_repository: RiskCheckRepositoryPort,
        contract_retriever: ContractContextRetrieverPort,
        policy_retriever: PolicyContextRetrieverPort,
        risk_chain: Runnable[dict[str, str], str],
    ) -> None:
        self.contract_repository = contract_repository
        self.contract_retriever = contract_retriever
        self.policy_retriever = policy_retriever
        self.risk_chain = risk_chain

    def load_contract(self, state: RiskCheckState) -> RiskCheckState:
        """加载合同事实。

        输入依赖 contract_id；输出 contract。合同不存在是稳定业务错误，直接抛 404。
        """

        contract_id = state["contract_id"]
        contract = self.contract_repository.get(contract_id)
        if contract is None:
            raise NotFoundError(f"Contract not found: {contract_id}")
        return {"contract": contract}

    def retrieve_context(self, state: RiskCheckState) -> RiskCheckState:
        """召回合同条款和制度依据。

        输入依赖 contract/broad_query；输出 contract_context、policy_context。检索词保持参考项目
        的宽风险词，topK 在 demo 阶段放宽到 20 以覆盖更多候选条款和制度依据。
        """

        contract = state["contract"]
        query = state["broad_query"]
        contract_context = self.contract_retriever.retrieve(
            contract_id=state["contract_id"],
            query=query,
            top_k=RAG_TOP_K,
        )
        policy_context = self.policy_retriever.retrieve(
            contract_type=contract.contract_type,
            query=query,
            top_k=POLICY_TOP_K,
        )
        policy_trace: AgentTraceState = {
            "agent_name": "PolicyEvidenceAgent",
            "summary": (
                f"已按合同类型「{_contract_type_display_name(contract.contract_type)}」"
                f"命中 {len(policy_context or [])} 条制度依据。"
            ),
        }
        return {
            "contract_context": contract_context or [],
            "policy_context": policy_context or [],
            "agent_trace": [*state.get("agent_trace", []), policy_trace],
        }

    def load_approval_history(self, state: RiskCheckState) -> RiskCheckState:
        """加载并压缩审批历史。

        输入依赖 contract_id 与 contract_context；输出 approval_history，并补齐 ContractFactAgent
        trace。审批历史为空时使用固定占位，确保 Prompt 对齐参考项目。
        """

        records = self.contract_repository.list_approval_records(state["contract_id"])
        approval_history = build_approval_history_digest(records)
        contract_trace: AgentTraceState = {
            "agent_name": "ContractFactAgent",
            "summary": (
                f"已加载合同事实，并命中 {len(state.get('contract_context', []))} "
                "个合同条款片段。"
            ),
        }
        return {
            "approval_history": approval_history,
            # 参考项目 trace 顺序为 ContractFactAgent -> PolicyEvidenceAgent -> RiskReviewAgent；
            # 图节点先召回制度，后加载审批历史，因此这里显式重排对外轨迹。
            "agent_trace": [contract_trace, *state.get("agent_trace", [])],
        }

    def generate_risk_json(self, state: RiskCheckState) -> RiskCheckState:
        """调用 LangChain chain 生成风险 JSON 原文。

        输入依赖合同、双通道召回和审批摘要；输出 raw_risk_output。解析延后到独立节点，
        便于区分模型生成失败和结构化解析失败。
        """

        prompt_input = build_risk_check_prompt_input(
            contract=state["contract"],
            contract_context=state.get("contract_context", []),
            policy_context=state.get("policy_context", []),
            approval_digest=state.get("approval_history", NO_APPROVAL_HISTORY_PLACEHOLDER),
        )
        raw = self.risk_chain.invoke(prompt_input)
        return {"raw_risk_output": "" if raw is None else str(raw)}

    def validate_risk_output(self, state: RiskCheckState) -> RiskCheckState:
        """解析并规范化模型风险输出。

        输入依赖 raw_risk_output；输出 risk_summary/risk_items。非法 JSON 按 MVP 兜底为
        summary=模型原文、riskItems=[]，不把解析不稳定性扩散成接口错误。
        """

        summary, risk_items = parse_risk_response(state.get("raw_risk_output"))
        trace: AgentTraceState = {
            "agent_name": "RiskReviewAgent",
            "summary": f"已生成 {len(risk_items)} 个结构化风险项。",
        }
        return {
            "risk_summary": summary,
            "risk_items": risk_items,
            "agent_trace": [*state.get("agent_trace", []), trace],
        }

    def format_response(self, state: RiskCheckState) -> RiskCheckState:
        """整理 API 层需要的响应字段。"""

        response = {
            "summary": state.get("risk_summary", ""),
            "risk_items": [_risk_item_to_dict(item) for item in state.get("risk_items", [])],
            "agent_trace": state.get("agent_trace", []),
        }
        return {"response": response}


def build_approval_history_digest(records: list[ApprovalRecord]) -> str:
    """生成与 ContractToolExecutor.approvalHistoryDigest 等价的审批摘要。"""

    if not records:
        return NO_APPROVAL_HISTORY_PLACEHOLDER
    lines = [
        f"- 步骤{record.step_no} {record.approver_role} "
        f"{_approval_decision_display_name(record.decision)}：{record.comment_summary}"
        for record in records
    ]
    return "\n".join(lines).strip()


def build_risk_check_workflow(
    contract_repository: RiskCheckRepositoryPort,
    contract_retriever: ContractContextRetrieverPort,
    policy_retriever: PolicyContextRetrieverPort,
    chat_model: Runnable[Any, Any] | None = None,
    risk_chain: Runnable[dict[str, str], str] | None = None,
) -> RiskCheckWorkflow:
    """构建并编译风险检查 LangGraph workflow。

    测试可以直接传 risk_chain；生产环境传 chat_model，由本函数组合标准风险检查 prompt。
    """

    resolved_risk_chain = risk_chain
    if resolved_risk_chain is None:
        if chat_model is None:
            raise ValueError("chat_model or risk_chain is required")
        resolved_risk_chain = build_risk_check_chain(chat_model)

    nodes = _RiskCheckNodes(
        contract_repository=contract_repository,
        contract_retriever=contract_retriever,
        policy_retriever=policy_retriever,
        risk_chain=resolved_risk_chain,
    )
    graph = StateGraph(RiskCheckState)
    graph.add_node("load_contract", nodes.load_contract)
    graph.add_node("retrieve_context", nodes.retrieve_context)
    graph.add_node("load_approval_history", nodes.load_approval_history)
    graph.add_node("generate_risk_json", nodes.generate_risk_json)
    graph.add_node("validate_risk_output", nodes.validate_risk_output)
    graph.add_node("format_response", nodes.format_response)

    graph.add_edge(START, "load_contract")
    graph.add_edge("load_contract", "retrieve_context")
    graph.add_edge("retrieve_context", "load_approval_history")
    graph.add_edge("load_approval_history", "generate_risk_json")
    graph.add_edge("generate_risk_json", "validate_risk_output")
    graph.add_edge("validate_risk_output", "format_response")
    graph.add_edge("format_response", END)
    return RiskCheckWorkflow(graph.compile())


def _risk_item_to_dict(item: RiskItem) -> dict[str, Any]:
    return {
        "code": item.code,
        "severity": item.severity.value,
        "detail": item.detail,
        "related_clause_chunk_ids": item.related_clause_chunk_ids,
        "related_policy_ids": item.related_policy_ids,
        "required_evidence": item.required_evidence,
        "escalation_role": item.escalation_role,
    }


def _contract_type_display_name(contract_type: ContractType) -> str:
    return CONTRACT_TYPE_DISPLAY_NAMES.get(contract_type, contract_type.value)


def _approval_decision_display_name(decision: ApprovalDecision) -> str:
    return APPROVAL_DECISION_DISPLAY_NAMES.get(decision, decision.value)
