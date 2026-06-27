"""双通道 RAG 检索。

合同通道和制度通道共享同一个 PGVector collection，但必须通过 metadata 边界隔离：
合同问题只能召回当前合同条款，制度问题只能召回制度知识并按合同类型收敛。
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from app.core.config import Settings, get_settings
from app.domain.enums import ContractType


class VectorSearchStore(Protocol):
    """阶段 4 需要的最小向量检索协议。

    使用协议而不是直接绑定 PGVector，便于测试用 fake store 验证 filter 和二次过滤语义。
    """

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
    ) -> list[tuple[Document, float]]:
        """按 query 相似度检索并返回文档与距离/分数。"""


@dataclass(slots=True)
class RagRetrievedDocument:
    """RAG 召回结果。

    score 保留底层 vector store 返回值，当前 PGVector cosine distance 越小越相似；上层只负责
    展示和调试，不在这里强行重解释为统一相关性分数。
    """

    document_id: str
    page_content: str
    metadata: dict[str, Any]
    score: float

    @property
    def chunk_id(self) -> str:
        """合同条款召回的业务 ID。"""

        return str(self.metadata.get("chunkId", ""))

    @property
    def policy_id(self) -> str:
        """制度召回的业务 ID。"""

        return str(self.metadata.get("policyId", ""))


class ContractRagRetriever:
    """合同条款通道 retriever。"""

    def __init__(self, vector_store: VectorSearchStore, default_top_k: int) -> None:
        self.vector_store = vector_store
        self.default_top_k = default_top_k

    def retrieve(
        self,
        contract_id: str,
        query: str,
        top_k: int | None = None,
    ) -> list[RagRetrievedDocument]:
        """召回指定合同的条款。

        contractId 是硬边界，不能依赖 prompt 要求模型“不要看其他合同”；必须在向量查询层
        就通过 metadata filter 阻断跨合同召回。
        """

        k = top_k or self.default_top_k
        results = self.vector_store.similarity_search_with_score(
            query=query,
            k=k,
            filter={"docType": "contract_clause", "contractId": contract_id},
        )
        return [_to_rag_document(document, score) for document, score in results]

    def as_runnable(self) -> RunnableLambda:
        """转换为 LangChain Runnable，供后续 LangGraph 节点直接组合。"""

        return RunnableLambda(
            lambda payload: self.retrieve(
                contract_id=str(payload["contractId"]),
                query=str(payload["query"]),
                top_k=payload.get("topK"),
            ),
        )


class PolicyRagRetriever:
    """制度知识通道 retriever。"""

    def __init__(
        self,
        vector_store: VectorSearchStore,
        default_top_k: int,
        candidate_multiplier: int = 4,
    ) -> None:
        self.vector_store = vector_store
        self.default_top_k = default_top_k
        self.candidate_multiplier = max(1, candidate_multiplier)

    def retrieve(
        self,
        contract_type: ContractType | str,
        query: str,
        top_k: int | None = None,
    ) -> list[RagRetrievedDocument]:
        """召回适用于当前合同类型的制度条目。

        appliesToContractType 在业务表中是分隔字符串，PGVector metadata filter 不适合表达
        “包含某个合同类型”的精确语义；因此先用 docType 缩小到制度集合，再在应用层做二次过滤。
        """

        k = top_k or self.default_top_k
        candidate_k = max(k * self.candidate_multiplier, k)
        results = self.vector_store.similarity_search_with_score(
            query=query,
            k=candidate_k,
            filter={"docType": "policy"},
        )
        contract_type_value = _normalize_contract_type(contract_type)
        filtered = [
            _to_rag_document(document, score)
            for document, score in results
            if _policy_applies_to_contract_type(
                str(document.metadata.get("appliesToContractType", "")),
                contract_type_value,
            )
        ]
        return filtered[:k]

    def as_runnable(self) -> RunnableLambda:
        """转换为 LangChain Runnable，供后续 LangGraph 节点直接组合。"""

        return RunnableLambda(
            lambda payload: self.retrieve(
                contract_type=payload["contractType"],
                query=str(payload["query"]),
                top_k=payload.get("topK"),
            ),
        )


def build_contract_rag_retriever(
    vector_store: VectorSearchStore,
    settings: Settings | None = None,
) -> ContractRagRetriever:
    """基于现有 vector store 创建合同通道 retriever。"""

    resolved = settings or get_settings()
    return ContractRagRetriever(vector_store, resolved.rag_contract_top_k)


def build_policy_rag_retriever(
    vector_store: VectorSearchStore,
    settings: Settings | None = None,
) -> PolicyRagRetriever:
    """基于现有 vector store 创建制度通道 retriever。"""

    resolved = settings or get_settings()
    return PolicyRagRetriever(vector_store, resolved.rag_policy_top_k)


def _to_rag_document(document: Document, score: float) -> RagRetrievedDocument:
    """把 LangChain Document 转为项目内部稳定结果对象。"""

    return RagRetrievedDocument(
        document_id=str(document.id or ""),
        page_content=document.page_content,
        metadata=dict(document.metadata),
        score=float(score),
    )


def _normalize_contract_type(contract_type: ContractType | str) -> str:
    """归一化合同类型，支持 API 入参别名和数据库稳定值。"""

    if isinstance(contract_type, ContractType):
        return contract_type.value
    return ContractType.from_flexible(contract_type).value


def _policy_applies_to_contract_type(applies_to: str, contract_type: str) -> bool:
    """判断制度条目是否适用于合同类型。

    参考项目示例使用 `PROCUREMENT;SERVICE` 这类分隔字符串；空值、`ALL` 和 `*` 视为通用制度。
    """

    tokens = _split_contract_type_tokens(applies_to)
    if not tokens:
        return True
    for token in tokens:
        if token in {"*", "ALL"}:
            return True
        try:
            if ContractType.from_flexible(token).value == contract_type:
                return True
        except Exception:  # noqa: BLE001
            # 历史制度数据可能存在尚未进入枚举的合同类型；这种值不能匹配当前已知类型。
            continue
    return False


def _split_contract_type_tokens(value: str) -> Sequence[str]:
    """拆分制度适用合同类型字段。"""

    normalized = value.strip().upper()
    for separator in [",", "，", "；", "|", "/", "\\"]:
        normalized = normalized.replace(separator, ";")
    return [token.strip() for token in normalized.split(";") if token.strip()]
