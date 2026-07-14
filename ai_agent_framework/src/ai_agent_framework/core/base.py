"""核心协议定义：所有可替换组件面向 Protocol 编程，避免硬耦合。"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from langchain_core.documents import Document


@runtime_checkable
class DocumentLoaderProtocol(Protocol):
    """文档加载器协议。"""

    def load(self, source: str) -> list[Document]: ...


@runtime_checkable
class SplitterProtocol(Protocol):
    """文本分块器协议。"""

    def split(self, documents: list[Document]) -> list[Document]: ...


@runtime_checkable
class EmbeddingsProtocol(Protocol):
    """嵌入模型协议（兼容 langchain Embeddings 接口）。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@runtime_checkable
class VectorStoreProtocol(Protocol):
    """向量存储协议。"""

    def add_documents(self, documents: list[Document]) -> list[str]: ...

    def similarity_search(self, query: str, top_k: int = 4) -> list[Document]: ...

    def delete_by_source(self, source: str) -> None: ...


@runtime_checkable
class RetrieverProtocol(Protocol):
    """检索器协议。"""

    def retrieve(self, query: str, top_k: int | None = None) -> list[Document]: ...


@runtime_checkable
class LLMProtocol(Protocol):
    """LLM 协议（兼容 langchain Runnable 的 invoke）。"""

    def invoke(self, input: Any) -> Any: ...


@runtime_checkable
class ToolProtocol(Protocol):
    """工具协议。"""

    name: str
    description: str

    def run(self, input: str) -> str: ...
