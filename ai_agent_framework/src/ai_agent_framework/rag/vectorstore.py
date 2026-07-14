"""向量存储：抽象基类 + Chroma 实现。"""
from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from ai_agent_framework.config.settings import VectorStoreConfig

logger = logging.getLogger(__name__)


class VectorStoreBase(ABC):
    """向量存储抽象基类。"""

    @abstractmethod
    def add_documents(self, documents: list[Document]) -> list[str]:
        """写入文档并返回生成的 ID 列表。"""

    @abstractmethod
    def similarity_search(self, query: str, top_k: int = 4) -> list[Document]:
        """相似度搜索。"""

    @abstractmethod
    def similarity_search_with_scores(
        self, query: str, top_k: int = 4
    ) -> list[tuple[Document, float]]:
        """带分数的相似度搜索。"""

    @abstractmethod
    def delete_by_source(self, source: str) -> None:
        """按 source 元数据删除文档。"""

    @abstractmethod
    def get_all_documents(self) -> list[Document]:
        """返回向量库中所有文档（用于重建内存语料）。"""

    def persist(self) -> None:
        """持久化（部分实现可不支持）。"""
        return None


class ChromaVectorStore(VectorStoreBase):
    """基于 ChromaDB 的向量存储实现。

    使用 langchain_community 的 Chroma 封装，支持本地持久化。
    每个文档分配唯一 id；source 元数据用于按源删除。
    """

    def __init__(self, config: VectorStoreConfig, embeddings: Embeddings):
        self._config = config
        self._embeddings = embeddings
        self._store = self._init_store()

    def _init_store(self) -> Any:
        from langchain_community.vectorstores import Chroma

        Path(self._config.path).mkdir(parents=True, exist_ok=True)
        collection = _sanitize_collection_name(self._config.collection)
        return Chroma(
            collection_name=collection,
            embedding_function=self._embeddings,
            persist_directory=self._config.path,
        )

    @property
    def _collection(self):
        """底层 Chroma collection（用于元数据级查询/删除）。"""
        return self._store._collection  # type: ignore[attr-defined]

    def add_documents(self, documents: list[Document]) -> list[str]:
        ids = [str(uuid.uuid4()) for _ in documents]
        for d in documents:
            d.metadata.setdefault("source", "unknown")
        self._store.add_documents(documents=documents, ids=ids)
        return ids

    def similarity_search(self, query: str, top_k: int = 4) -> list[Document]:
        return self._store.similarity_search(query, k=top_k)

    def similarity_search_with_scores(
        self, query: str, top_k: int = 4
    ) -> list[tuple[Document, float]]:
        return self._store.similarity_search_with_score(query, k=top_k)

    def delete_by_source(self, source: str) -> None:
        results = self._collection.get(where={"source": source})
        ids = results.get("ids", []) if results else []
        if ids:
            self._collection.delete(ids=ids)

    def get_all_documents(self) -> list[Document]:
        """拉取向量库中所有文档，用于重建 BM25 语料。"""
        try:
            results = self._collection.get(include=["documents", "metadatas"])
        except Exception as e:  # noqa: BLE001
            logger.warning("get_all_documents 失败: %s", e)
            return []
        ids = results.get("ids", []) if results else []
        docs = results.get("documents", []) if results else []
        metas = results.get("metadatas", []) if results else []
        if not docs:
            return []
        return [
            Document(page_content=t, metadata=m or {})
            for t, m in zip(docs, metas)
        ]

    def persist(self) -> None:
        try:
            self._store.persist()
        except Exception as e:  # noqa: BLE001
            logger.debug("persist 跳过: %s", e)


def get_vectorstore(
    config: VectorStoreConfig | None = None,
    embeddings: Embeddings | None = None,
) -> VectorStoreBase:
    """工厂函数。"""
    if config is None:
        from ai_agent_framework.config import get_settings

        config = get_settings().vectorstore
    if embeddings is None:
        from ai_agent_framework.rag.embeddings import get_embeddings

        embeddings = get_embeddings()

    if config.type == "chroma":
        return ChromaVectorStore(config, embeddings)
    raise ValueError(f"未知的向量库类型: {config.type}")


def _sanitize_collection_name(name: str) -> str:
    """规范化 Chroma 集合名：3-512 字符，仅 [a-zA-Z0-9._-]，首尾为字母数字。"""
    import re

    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", name or "default")
    cleaned = re.sub(r"^[._-]+", "", cleaned) or "default"
    cleaned = re.sub(r"[._-]+$", "", cleaned) or "default"
    if len(cleaned) < 3:
        cleaned = (cleaned + "default")[:8]
    return cleaned
