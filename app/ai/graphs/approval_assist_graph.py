"""审批辅助 LangGraph workflow。

执行逻辑对齐参考项目 `AiContractAssistant#approvalAssist`：用审批角色和关注点构造检索词，
召回当前合同条款与适用制度，拼入审批历史后生成 suggestion/checklist，并回填双通道命中 ID。
"""

from typing import Any, Protocol

from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph

from app.ai.chains.approval_assist import (
    build_approval_assist_chain,
    build_approval_assist_prompt_input,
    parse_approval_assist_response,
)
from app.ai.chains.qa import CONTRACT_TYPE_DISPLAY_NAMES
from app.ai.graphs.risk_check_graph import build_approval_history_digest
from app.ai.graphs.state import AgentTraceState, ApprovalAssistState
from app.ai.rag.retrievers import RagRetrievedDocument
from app.core.exceptions import NotFoundError
from app.domain.enums import ContractType
from app.domain.models import ApprovalRecord, Contract

RAG_TOP_K = 4
POLICY_TOP_K = 4
APPROVAL_QUERY_SUFFIX = "审批 财务 法务 发票 验收 保密 分包"
NO_APPROVAL_HISTORY_PLACEHOLDER = "（暂无审批记录）"


class ApprovalAssistRepositoryPort(Protocol):
    """审批辅助图需要的最小合同仓储接口。"""

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
        """召回当前审批角色相关的合同条款。"""


class PolicyContextRetrieverPort(Protocol):
    """制度依据召回接口。"""

    def retrieve(
        self,
        contract_type: ContractType | str,
        query: str,
        top_k: int | None = None,
    ) -> list[RagRetrievedDocument]:
        """召回当前审批角色相关且适用于合同类型的制度依据。"""


class ApprovalAssistWorkflow:
    """编译后的审批辅助 workflow 门面。"""

    def __init__(self, graph_app: Runnable[ApprovalAssistState, ApprovalAssistState]) -> None:
        self.graph_app = graph_app

    def invoke(
        self,
        contract_id: str,
        approver_role: str,
        focus: str = "",
    ) -> ApprovalAssistState:
        """执行审批辅助图并返回最终 state。"""

        normalized_focus = focus or ""
        initial_state: ApprovalAssistState = {
            "contract_id": contract_id,
            "approver_role": approver_role,
            "focus": normalized_focus,
            "query": build_approval_query(approver_role, normalized_focus),
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


class _ApprovalAssistNodes:
    """审批辅助图节点集合。"""

    def __init__(
        self,
        contract_repository: ApprovalAssistRepositoryPort,
        contract_retriever: ContractContextRetrieverPort,
        policy_retriever: PolicyContextRetrieverPort,
        advice_chain: Runnable[dict[str, str], str],
    ) -> None:
        self.contract_repository = contract_repository
        self.contract_retriever = contract_retriever
        self.policy_retriever = policy_retriever
        self.advice_chain = advice_chain

    def load_contract(self, state: ApprovalAssistState) -> ApprovalAssistState:
        """加载合同事实。

        输入依赖 contract_id；输出 contract。合同不存在属于稳定业务错误，直接抛 404。
        """

        contract_id = state["contract_id"]
        contract = self.contract_repository.get(contract_id)
        if contract is None:
            raise NotFoundError(f"Contract not found: {contract_id}")
        return {"contract": contract}

    def retrieve_role_related_context(self, state: ApprovalAssistState) -> ApprovalAssistState:
        """召回当前审批角色相关的合同条款和制度依据。

        输入依赖 contract/query；输出 contract_context、policy_context。query 拼接规则来自
        参考项目，确保角色、focus 和审批常用关键词共同影响召回。
        """

        contract = state["contract"]
        query = state["query"]
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

    def load_approval_history(self, state: ApprovalAssistState) -> ApprovalAssistState:
        """加载并压缩审批历史。

        输入依赖 contract_id 与 contract_context；输出 approval_history，并补齐 ContractFactAgent
        trace。审批历史为空时使用固定占位，保持与风险检查和参考项目一致。
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
            # 参考项目 trace 顺序为：
            # ContractFactAgent -> PolicyEvidenceAgent -> ApprovalAdviceAgent。
            # 图节点先完成召回，再加载审批历史，因此这里按对外语义重排。
            "agent_trace": [contract_trace, *state.get("agent_trace", [])],
        }

    def generate_advice(self, state: ApprovalAssistState) -> ApprovalAssistState:
        """生成并解析审批建议。

        输入依赖角色、focus、合同事实、双通道召回和审批历史；输出 suggestion/checklist。
        JSON 解析失败时 suggestion 回退为模型原文，checklist 为空，命中 ID 仍保留。
        """

        prompt_input = build_approval_assist_prompt_input(
            approver_role=state["approver_role"],
            focus=state.get("focus", ""),
            contract=state["contract"],
            contract_context=state.get("contract_context", []),
            policy_context=state.get("policy_context", []),
            approval_digest=state.get("approval_history", NO_APPROVAL_HISTORY_PLACEHOLDER),
        )
        raw = self.advice_chain.invoke(prompt_input)
        raw_text = "" if raw is None else str(raw)
        suggestion, checklist = parse_approval_assist_response(raw_text)
        trace: AgentTraceState = {
            "agent_name": "ApprovalAdviceAgent",
            "summary": f"已生成审批建议，并产出 {len(checklist)} 个核对项。",
        }
        return {
            "raw_advice_output": raw_text,
            "suggestion": suggestion,
            "checklist": checklist,
            "agent_trace": [*state.get("agent_trace", []), trace],
        }

    def format_response(self, state: ApprovalAssistState) -> ApprovalAssistState:
        """整理 API 层需要的响应字段。"""

        retrieved_chunk_ids = [
            document.chunk_id for document in state.get("contract_context", []) if document.chunk_id
        ]
        retrieved_policy_ids = [
            document.policy_id for document in state.get("policy_context", []) if document.policy_id
        ]
        response = {
            "suggestion": state.get("suggestion", ""),
            "checklist": state.get("checklist", []),
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "retrieved_policy_ids": retrieved_policy_ids,
            "agent_trace": state.get("agent_trace", []),
        }
        return {
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "retrieved_policy_ids": retrieved_policy_ids,
            "response": response,
        }


def build_approval_query(approver_role: str, focus: str = "") -> str:
    """生成审批辅助检索词。

    拼接格式对齐 `AiContractAssistant#approvalAssist`，focus 可为空但不影响固定审批关键词。
    """

    return f"{approver_role} {focus} {APPROVAL_QUERY_SUFFIX}".strip()


def build_approval_assist_workflow(
    contract_repository: ApprovalAssistRepositoryPort,
    contract_retriever: ContractContextRetrieverPort,
    policy_retriever: PolicyContextRetrieverPort,
    chat_model: Runnable[Any, Any] | None = None,
    advice_chain: Runnable[dict[str, str], str] | None = None,
) -> ApprovalAssistWorkflow:
    """构建并编译审批辅助 LangGraph workflow。

    测试可以直接传 advice_chain；生产环境传 chat_model，由本函数组合标准审批辅助 prompt。
    """

    resolved_advice_chain = advice_chain
    if resolved_advice_chain is None:
        if chat_model is None:
            raise ValueError("chat_model or advice_chain is required")
        resolved_advice_chain = build_approval_assist_chain(chat_model)

    nodes = _ApprovalAssistNodes(
        contract_repository=contract_repository,
        contract_retriever=contract_retriever,
        policy_retriever=policy_retriever,
        advice_chain=resolved_advice_chain,
    )
    graph = StateGraph(ApprovalAssistState)
    graph.add_node("load_contract", nodes.load_contract)
    graph.add_node("retrieve_role_related_context", nodes.retrieve_role_related_context)
    graph.add_node("load_approval_history", nodes.load_approval_history)
    graph.add_node("generate_advice", nodes.generate_advice)
    graph.add_node("format_response", nodes.format_response)

    graph.add_edge(START, "load_contract")
    graph.add_edge("load_contract", "retrieve_role_related_context")
    graph.add_edge("retrieve_role_related_context", "load_approval_history")
    graph.add_edge("load_approval_history", "generate_advice")
    graph.add_edge("generate_advice", "format_response")
    graph.add_edge("format_response", END)
    return ApprovalAssistWorkflow(graph.compile())


def _contract_type_display_name(contract_type: ContractType) -> str:
    return CONTRACT_TYPE_DISPLAY_NAMES.get(contract_type, contract_type.value)
