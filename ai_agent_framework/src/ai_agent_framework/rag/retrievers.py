"""检索器：向量检索 + 混合检索（BM25 + 向量，加权 RRF 融合）。"""
from __future__ import annotations

import hashlib
import logging
import threading
from typing import Iterable

from langchain_core.documents import Document

from ai_agent_framework.config.settings import RetrievalConfig
from ai_agent_framework.core.base import RetrieverProtocol
from ai_agent_framework.rag.vectorstore import VectorStoreBase

logger = logging.getLogger(__name__)


def _doc_key(doc: Document) -> str:
    """用内容哈希 + source 作为去重键，避免前缀碰撞。"""
    src = doc.metadata.get("source", "")
    h = hashlib.sha1(doc.page_content.encode("utf-8")).hexdigest()[:16]
    return f"{src}::{h}"


class VectorRetriever(RetrieverProtocol):
    """纯向量检索器。"""

    def __init__(self, vectorstore: VectorStoreBase, config: RetrievalConfig | None = None):
        self._store = vectorstore
        self._config = config or RetrievalConfig()

    def retrieve(self, query: str, top_k: int | None = None) -> list[Document]:
        k = top_k or self._config.top_k
        return self._store.similarity_search(query, top_k=k)


class HybridRetriever(RetrieverProtocol):
    """混合检索器：BM25（关键词）+ 向量（语义），用加权 RRF 融合。

    BM25 索引基于内存文档集合构建；通过 `update_corpus` 同步（线程安全）。
    加权 RRF：score(d) = w_vec * Σ 1/(k+rank_vec) + w_bm25 * Σ 1/(k+rank_bm25)，
    其中 w_vec = vector_weight, w_bm25 = 1 - vector_weight。
    """

    def __init__(
        self,
        vectorstore: VectorStoreBase,
        config: RetrievalConfig | None = None,
        corpus: list[Document] | None = None,
        rrf_k: int = 60,
    ):
        self._store = vectorstore
        self._config = config or RetrievalConfig()
        self._rrf_k = rrf_k
        self._corpus: list[Document] = []
        self._bm25 = None
        self._lock = threading.RLock()
        if corpus:
            self.update_corpus(corpus)

    def update_corpus(self, documents: Iterable[Document]) -> None:
        """重建 BM25 索引（增删文档后调用），线程安全。"""
        with self._lock:
            self._corpus = list(documents)
            if not self._corpus:
                self._bm25 = None
                return
            from rank_bm25 import BM25Okapi

            tokenized = [self._tokenize(d.page_content) for d in self._corpus]
            self._bm25 = BM25Okapi(tokenized)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """简单分词：英文按空格/标点，中文按字符（可选 jieba 增强）。"""
        try:
            import jieba  # 可选依赖，提升中文 BM25 质量

            return [t for t in jieba.cut(text.lower()) if t.strip()]
        except ImportError:
            import re

            return re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fa5]", text.lower())

    def _bm25_search(self, query: str, top_k: int) -> list[Document]:
        with self._lock:
            if self._bm25 is None or not self._corpus:
                return []
            scores = self._bm25.get_scores(self._tokenize(query))
            bm25 = self._bm25
            corpus = list(self._corpus)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [corpus[i] for i in ranked if scores[i] > 0]

    def retrieve(self, query: str, top_k: int | None = None) -> list[Document]:
        k = top_k or self._config.top_k
        candidate_k = max(self._config.candidate_k, k)

        vec_docs = self._store.similarity_search(query, top_k=candidate_k)
        bm25_docs = self._bm25_search(query, top_k=candidate_k)

        w_vec = self._config.vector_weight
        w_bm25 = 1.0 - w_vec

        scores: dict[str, float] = {}
        docs_by_key: dict[str, Document] = {}
        for rank, d in enumerate(vec_docs):
            key = _doc_key(d)
            scores[key] = scores.get(key, 0.0) + w_vec / (self._rrf_k + rank + 1)
            docs_by_key.setdefault(key, d)
        for rank, d in enumerate(bm25_docs):
            key = _doc_key(d)
            scores[key] = scores.get(key, 0.0) + w_bm25 / (self._rrf_k + rank + 1)
            docs_by_key.setdefault(key, d)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [docs_by_key[key] for key, _ in ranked[:k]]


def get_retriever(
    vectorstore: VectorStoreBase,
    config: RetrievalConfig | None = None,
    corpus: list[Document] | None = None,
) -> RetrieverProtocol:
    """工厂函数：按配置返回检索器。"""
    if config is None:
        from ai_agent_framework.config import get_settings

        config = get_settings().rag.retrieval

    if config.strategy == "vector":
        return VectorRetriever(vectorstore, config)
    if config.strategy == "hybrid":
        return HybridRetriever(vectorstore, config, corpus=corpus)
    raise ValueError(f"未知的检索策略: {config.strategy}")
