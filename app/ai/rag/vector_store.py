"""LangChain PGVector 初始化。

本模块只负责把项目配置转换为 LangChain PGVector 实例；具体业务对象如何映射为
Document、何时写入，由 ingestion 层处理。
"""

from typing import Any

from langchain_postgres import PGVector
from langchain_postgres.vectorstores import DistanceStrategy

from app.ai.langchain_factory import create_embeddings
from app.ai.rag.ingestion import (
    ContractVectorIngestionService,
    PolicyVectorIngestionService,
    VectorBatchWriter,
)
from app.ai.rag.retrievers import ContractRagRetriever, PolicyRagRetriever
from app.core.config import Settings, get_settings


def create_pgvector_store(
    settings: Settings | None = None,
    embeddings: Any | None = None,
) -> PGVector:
    """创建 PGVector store。

    collection_name 用于把本项目的向量数据和同库其他 LangChain collection 隔离开。
    """

    resolved = settings or get_settings()
    return PGVector(
        embeddings=embeddings or create_embeddings(resolved),
        connection=resolved.database_url,
        embedding_length=resolved.openai_embedding_dimensions,
        collection_name=resolved.vector_collection_name,
        distance_strategy=DistanceStrategy.COSINE,
        use_jsonb=True,
        create_extension=True,
    )


def build_contract_vector_ingestion_service(
    settings: Settings | None = None,
) -> ContractVectorIngestionService | None:
    """创建合同条款向量入库服务。

    未配置 OPENAI_API_KEY 时返回 None，让导入接口以 warning 形式降级，而不是阻断业务表写入。
    """

    resolved = settings or get_settings()
    if not resolved.openai_api_key:
        return None
    store = create_pgvector_store(resolved)
    return ContractVectorIngestionService(VectorBatchWriter(store, resolved.embedding_batch_size))


def build_policy_vector_ingestion_service(
    settings: Settings | None = None,
) -> PolicyVectorIngestionService | None:
    """创建制度知识向量入库服务。"""

    resolved = settings or get_settings()
    if not resolved.openai_api_key:
        return None
    store = create_pgvector_store(resolved)
    return PolicyVectorIngestionService(VectorBatchWriter(store, resolved.embedding_batch_size))


def build_contract_rag_retriever(settings: Settings | None = None) -> ContractRagRetriever | None:
    """创建合同通道 RAG retriever。

    检索 query 也需要 embedding；没有模型 key 时返回 None，让后续 API 能明确降级或报依赖未配置。
    """

    resolved = settings or get_settings()
    if not resolved.openai_api_key:
        return None
    store = create_pgvector_store(resolved)
    return ContractRagRetriever(store, resolved.rag_contract_top_k)


def build_policy_rag_retriever(settings: Settings | None = None) -> PolicyRagRetriever | None:
    """创建制度通道 RAG retriever。"""

    resolved = settings or get_settings()
    if not resolved.openai_api_key:
        return None
    store = create_pgvector_store(resolved)
    return PolicyRagRetriever(store, resolved.rag_policy_top_k)
