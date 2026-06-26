"""向量入库服务。

导入接口先写业务表，再调用这里同步 pgvector。同步失败不会改变业务事实，只会返回
warning，后续可以通过重试导入或补偿任务重建派生索引。
"""

from collections.abc import Sequence
from typing import Protocol

from langchain_core.documents import Document

from app.ai.rag.document_mapping import chunk_to_document, policy_to_document
from app.domain.models import ClauseChunk, PolicyKnowledgeItem


class VectorStore(Protocol):
    """当前阶段需要的最小 vector store 协议。

    使用协议而不是直接绑定 PGVector，方便单元测试用 fake store 验证 delete + add 语义。
    """

    def delete(self, ids: list[str] | None = None, **kwargs: object) -> None:
        """按稳定 document id 删除旧向量。"""

    def add_documents(self, documents: list[Document], **kwargs: object) -> list[str]:
        """写入新向量并返回 document id。"""


class VectorBatchWriter:
    """分批执行 delete + add 的幂等写入器。"""

    def __init__(self, vector_store: VectorStore, batch_size: int) -> None:
        self.vector_store = vector_store
        self.batch_size = max(1, batch_size)

    def upsert(self, documents: Sequence[Document]) -> None:
        """按 Document.id 幂等覆盖写入向量。

        先删后写是为了支持重复导入同一合同/制度时覆盖旧 embedding，避免召回到过期文本。
        """

        docs = [document for document in documents if document.id]
        for start in range(0, len(docs), self.batch_size):
            batch = docs[start : start + self.batch_size]
            ids = [str(document.id) for document in batch]
            self.vector_store.delete(ids=ids)
            self.vector_store.add_documents(batch, ids=ids)


class ContractVectorIngestionService:
    """合同条款向量入库服务。"""

    def __init__(self, writer: VectorBatchWriter) -> None:
        self.writer = writer

    def ingest(self, chunks: Sequence[ClauseChunk]) -> None:
        """将合同条款分块写入向量库。

        空条款列表直接跳过，避免对 vector store 发起无意义请求。
        """

        if not chunks:
            return
        self.writer.upsert([chunk_to_document(chunk) for chunk in chunks])

    def replace(self, old_chunks: Sequence[ClauseChunk], new_chunks: Sequence[ClauseChunk]) -> None:
        """覆盖合同条款向量。

        合同重复导入时可能删除了某些旧 chunk；先按旧 chunk ID 清理向量，再写入新
        chunk，避免后续检索召回到已经不属于当前合同快照的条款。
        """

        old_ids = [str(chunk_to_document(chunk).id) for chunk in old_chunks]
        if old_ids:
            self.writer.vector_store.delete(ids=old_ids)
        self.ingest(new_chunks)


class PolicyVectorIngestionService:
    """制度知识向量入库服务。"""

    def __init__(self, writer: VectorBatchWriter) -> None:
        self.writer = writer

    def ingest(self, items: Sequence[PolicyKnowledgeItem]) -> None:
        """将制度条目写入向量库。"""

        if not items:
            return
        self.writer.upsert([policy_to_document(item) for item in items])
