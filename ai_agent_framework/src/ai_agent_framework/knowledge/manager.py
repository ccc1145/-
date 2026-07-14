"""知识库管理：串联 loader → splitter → vectorstore，维护文档源元数据。"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Union

from langchain_core.documents import Document

from ai_agent_framework.config.settings import Settings
from ai_agent_framework.rag.loaders import AutoLoader
from ai_agent_framework.rag.splitters import get_splitter
from ai_agent_framework.rag.vectorstore import VectorStoreBase, get_vectorstore
from ai_agent_framework.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """知识库：负责文档摄入、索引构建、检索与源管理。

    - 进程启动时从向量库反查所有文档重建内存语料（供 HybridRetriever BM25）。
    - 可选 attach_retriever：增删文档后自动同步 retriever 的 BM25 索引。
    - sources.json 记录每个源的摄入统计，用于 list/delete/rebuild。
    - 所有写操作通过 RLock 串行化，保证 API 并发摄入时数据一致。
    """

    def __init__(
        self,
        settings: Settings | None = None,
        vectorstore: VectorStoreBase | None = None,
    ):
        self._settings = settings or self._load_settings()
        self._embeddings = get_embeddings(self._settings.embedding)
        self._vectorstore = vectorstore or get_vectorstore(
            self._settings.vectorstore, self._embeddings
        )
        self._splitter = get_splitter(self._settings.rag.splitter)
        self._loader = AutoLoader()
        self._meta_path = Path(self._settings.vectorstore.path) / "sources.json"
        self._retriever = None  # 可选附加的检索器，用于同步 BM25 语料
        self._lock = threading.RLock()
        # 从向量库重建内存语料（持久化后跨进程可用）
        self._corpus: list[Document] = self._load_corpus_from_store()

    @staticmethod
    def _load_settings() -> Settings:
        from ai_agent_framework.config import get_settings

        return get_settings()

    def _load_corpus_from_store(self) -> list[Document]:
        try:
            return self._vectorstore.get_all_documents()
        except Exception as e:  # noqa: BLE001
            logger.warning("从向量库重建语料失败: %s", e)
            return []

    def attach_retriever(self, retriever) -> None:
        """附加检索器，后续增删文档时自动同步其 BM25 语料。"""
        self._retriever = retriever
        self._sync_retriever()

    def _sync_retriever(self) -> None:
        if self._retriever is not None and hasattr(self._retriever, "update_corpus"):
            self._retriever.update_corpus(self._corpus)

    # ---- 元数据持久化 ----
    def _load_meta(self) -> dict:
        if self._meta_path.exists():
            try:
                return json.loads(self._meta_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_meta(self, meta: dict) -> None:
        self._meta_path.parent.mkdir(parents=True, exist_ok=True)
        self._meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---- 摄入 ----
    def add_documents(self, source: Union[str, Path]) -> dict:
        """加载文件/目录 → 分块 → 写入向量库。

        幂等：若 source 已存在，先加载新文档成功后再删除旧文档，避免加载失败导致数据丢失。
        返回摄入统计：{source, chunks, status}。
        """
        src = str(source)
        # 先加载并分块（失败时直接抛出，不影响既有数据）
        docs = self._loader.load(src)
        if not docs:
            return {"source": src, "chunks": 0, "status": "empty"}
        chunks = self._splitter.split(docs)
        for c in chunks:
            c.metadata.setdefault("source", src)
        if not chunks:
            return {"source": src, "chunks": 0, "status": "empty"}

        with self._lock:
            meta = self._load_meta()
            if src in meta:  # 幂等：新数据已就绪，安全删除旧数据
                self._vectorstore.delete_by_source(src)
                self._corpus = [d for d in self._corpus if d.metadata.get("source") != src]
            self._vectorstore.add_documents(chunks)
            self._vectorstore.persist()
            meta[src] = {"chunks": len(chunks), "type": Path(src).suffix.lower() or "dir"}
            self._save_meta(meta)
            self._corpus.extend(chunks)
            self._sync_retriever()
        return {"source": src, "chunks": len(chunks), "status": "ok"}

    def add_text(self, text: str, source: str = "inline") -> dict:
        """直接摄入一段文本。"""
        doc = Document(page_content=text, metadata={"source": source, "type": "inline"})
        chunks = self._splitter.split([doc])
        for c in chunks:
            c.metadata.setdefault("source", source)
        if not chunks:
            return {"source": source, "chunks": 0, "status": "empty"}

        with self._lock:
            meta = self._load_meta()
            if source in meta:
                self._vectorstore.delete_by_source(source)
                self._corpus = [d for d in self._corpus if d.metadata.get("source") != source]
            self._vectorstore.add_documents(chunks)
            self._vectorstore.persist()
            meta[source] = {"chunks": len(chunks), "type": "inline"}
            self._save_meta(meta)
            self._corpus.extend(chunks)
            self._sync_retriever()
        return {"source": source, "chunks": len(chunks), "status": "ok"}

    # ---- 检索 ----
    def search(self, query: str, top_k: int | None = None) -> list[Document]:
        k = top_k or self._settings.rag.retrieval.top_k
        return self._vectorstore.similarity_search(query, top_k=k)

    # ---- 源管理 ----
    def list_sources(self) -> dict:
        return self._load_meta()

    def delete_source(self, source: str) -> dict:
        with self._lock:
            self._vectorstore.delete_by_source(source)
            meta = self._load_meta()
            removed = meta.pop(source, None)
            self._save_meta(meta)
            self._corpus = [d for d in self._corpus if d.metadata.get("source") != source]
            self._sync_retriever()
        return {"source": source, "removed": removed is not None}

    def rebuild_index(self) -> dict:
        """清空并按元数据重新摄入所有源；清理已失效的源记录。"""
        with self._lock:
            meta = self._load_meta()
            sources = list(meta.keys())
            for s in sources:
                self._vectorstore.delete_by_source(s)
            self._corpus = []
            results = []
            stale: list[str] = []
            for s in sources:
                if Path(s).exists():
                    results.append(self.add_documents(s))
                else:
                    stale.append(s)
            # 清理失效源元数据
            meta = self._load_meta()
            for s in stale:
                meta.pop(s, None)
            if stale:
                self._save_meta(meta)
            self._sync_retriever()
        return {"rebuilt": len(results), "removed_stale": len(stale), "details": results}

    @property
    def vectorstore(self) -> VectorStoreBase:
        return self._vectorstore

    @property
    def corpus(self) -> list[Document]:
        """当前内存中的文档语料（供 HybridRetriever）。"""
        return self._corpus
