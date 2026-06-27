"""合同问答 LangGraph workflow。

执行逻辑对齐参考项目 `AiContractAssistant#answerQuestion`：加载合同、用固定 topK=4
召回合同条款和制度依据、按 `ContractPrompts` 生成回答、返回命中 ID。
"""

from typing import Any, Protocol

from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph

from app.ai.chains.qa import build_contract_qa_chain, build_qa_prompt_input
from app.ai.graphs.state import ContractQaState
from app.ai.rag.retrievers import RagRetrievedDocument
from app.core.exceptions import NotFoundError
from app.domain.enums import ContractType
from app.domain.models import Contract

RAG_TOP_K = 4
POLICY_TOP_K = 4


class ContractRepositoryPort(Protocol):
    """合同问答图需要的最小仓储接口。"""

    def get(self, contract_id: str) -> Contract | None:
        """按合同 ID 读取合同和条款分块。"""


class ContractContextRetrieverPort(Protocol):
    """合同条款召回接口，生产环境由 ContractRagRetriever 实现。"""

    def retrieve(
        self,
        contract_id: str,
        query: str,
        top_k: int | None = None,
    ) -> list[RagRetrievedDocument]:
        """召回指定合同下与问题相关的条款。"""


class PolicyContextRetrieverPort(Protocol):
    """制度依据召回接口，生产环境由 PolicyRagRetriever 实现。"""

    def retrieve(
        self,
        contract_type: ContractType | str,
        query: str,
        top_k: int | None = None,
    ) -> list[RagRetrievedDocument]:
        """召回适用于合同类型的问题相关制度。"""


class ContractQaWorkflow:
    """编译后的合同问答 workflow 门面。"""

    def __init__(self, graph_app: Runnable[ContractQaState, ContractQaState]) -> None:
        self.graph_app = graph_app

    def invoke(
        self,
        contract_id: str,
        question: str,
    ) -> ContractQaState:
        """执行合同问答图并返回最终 state。"""

        initial_state: ContractQaState = {
            "contract_id": contract_id,
            "question": question,
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


class _ContractQaNodes:
    """合同问答图节点集合。"""

    def __init__(
        self,
        contract_repository: ContractRepositoryPort,
        contract_retriever: ContractContextRetrieverPort,
        policy_retriever: PolicyContextRetrieverPort,
        answer_chain: Runnable[dict[str, Any], str],
    ) -> None:
        self.contract_repository = contract_repository
        self.contract_retriever = contract_retriever
        self.policy_retriever = policy_retriever
        self.answer_chain = answer_chain

    def load_contract(self, state: ContractQaState) -> ContractQaState:
        """加载合同事实。

        输入依赖 contract_id；输出 contract。合同不存在属于稳定业务错误，直接抛 404。
        """

        contract_id = state["contract_id"]
        contract = self.contract_repository.get(contract_id)
        if contract is None:
            raise NotFoundError(f"Contract not found: {contract_id}")

        return {"contract": contract}

    def retrieve_contract_context(self, state: ContractQaState) -> ContractQaState:
        """召回当前合同条款。

        输入依赖 contract_id/question；输出 contract_context。topK 固定为参考项目 RAG_TOP_K=4。
        """

        documents = self.contract_retriever.retrieve(
            contract_id=state["contract_id"],
            query=state["question"],
            top_k=RAG_TOP_K,
        )
        return {"contract_context": documents or []}

    def retrieve_policy_context(self, state: ContractQaState) -> ContractQaState:
        """召回适用制度依据。

        输入依赖 contract/question；输出 policy_context。topK 固定为参考项目 POLICY_TOP_K=4。
        """

        contract = state["contract"]
        documents = self.policy_retriever.retrieve(
            contract_type=contract.contract_type,
            query=state["question"],
            top_k=POLICY_TOP_K,
        )
        return {"policy_context": documents or []}

    def generate_answer(self, state: ContractQaState) -> ContractQaState:
        """调用 LangChain chain 生成回答。

        输入依赖合同、两类召回和 question；输出 answer。Prompt 文本与参考项目保持一致。
        """

        prompt_input = build_qa_prompt_input(
            contract=state["contract"],
            question=state["question"],
            contract_context=state.get("contract_context", []),
            policy_context=state.get("policy_context", []),
        )
        answer = self.answer_chain.invoke(prompt_input)
        return {"answer": "" if answer is None else str(answer).strip()}

    def format_response(self, state: ContractQaState) -> ContractQaState:
        """整理 API 层需要的响应字段。"""

        retrieved_chunk_ids = [
            document.chunk_id for document in state.get("contract_context", []) if document.chunk_id
        ]
        retrieved_policy_ids = [
            document.policy_id for document in state.get("policy_context", []) if document.policy_id
        ]
        response = {
            "answer": state.get("answer", ""),
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "retrieved_policy_ids": retrieved_policy_ids,
        }
        return {
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "retrieved_policy_ids": retrieved_policy_ids,
            "response": response,
        }


def build_contract_qa_workflow(
    contract_repository: ContractRepositoryPort,
    contract_retriever: ContractContextRetrieverPort,
    policy_retriever: PolicyContextRetrieverPort,
    chat_model: Runnable[Any, Any] | None = None,
    answer_chain: Runnable[dict[str, Any], str] | None = None,
) -> ContractQaWorkflow:
    """构建并编译合同问答 LangGraph workflow。

    测试可以直接传 answer_chain；生产环境传 chat_model，由本函数组合标准 QA prompt。
    """

    resolved_answer_chain = answer_chain
    if resolved_answer_chain is None:
        if chat_model is None:
            raise ValueError("chat_model or answer_chain is required")
        resolved_answer_chain = build_contract_qa_chain(chat_model)

    nodes = _ContractQaNodes(
        contract_repository=contract_repository,
        contract_retriever=contract_retriever,
        policy_retriever=policy_retriever,
        answer_chain=resolved_answer_chain,
    )
    graph = StateGraph(ContractQaState)
    graph.add_node("load_contract", nodes.load_contract)
    graph.add_node("retrieve_contract_context", nodes.retrieve_contract_context)
    graph.add_node("retrieve_policy_context", nodes.retrieve_policy_context)
    graph.add_node("generate_answer", nodes.generate_answer)
    graph.add_node("format_response", nodes.format_response)

    graph.add_edge(START, "load_contract")
    graph.add_edge("load_contract", "retrieve_contract_context")
    graph.add_edge("load_contract", "retrieve_policy_context")
    graph.add_edge(["retrieve_contract_context", "retrieve_policy_context"], "generate_answer")
    graph.add_edge("generate_answer", "format_response")
    graph.add_edge("format_response", END)
    return ContractQaWorkflow(graph.compile())
