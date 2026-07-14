"""RAG 模块：加载、分块、嵌入、向量存储、检索、生成。"""
from ai_agent_framework.rag.loaders import (
    DocumentLoader,
    TextLoader,
    MarkdownLoader,
    PDFLoader,
    AutoLoader,
    get_loader,
)
from ai_agent_framework.rag.splitters import (
    RecursiveSplitter,
    CharacterSplitterAdapter,
    TokenSplitterAdapter,
    get_splitter,
)
from ai_agent_framework.core.base import SplitterProtocol as Splitter
from ai_agent_framework.rag.embeddings import get_embeddings
from ai_agent_framework.rag.vectorstore import (
    VectorStoreBase,
    ChromaVectorStore,
    get_vectorstore,
)
from ai_agent_framework.rag.retrievers import (
    VectorRetriever,
    HybridRetriever,
    get_retriever,
)
from ai_agent_framework.rag.generator import ResponseGenerator, GenerationResult

__all__ = [
    "DocumentLoader",
    "TextLoader",
    "MarkdownLoader",
    "PDFLoader",
    "AutoLoader",
    "get_loader",
    "Splitter",
    "RecursiveSplitter",
    "CharacterSplitterAdapter",
    "TokenSplitterAdapter",
    "get_splitter",
    "get_embeddings",
    "VectorStoreBase",
    "ChromaVectorStore",
    "get_vectorstore",
    "VectorRetriever",
    "HybridRetriever",
    "get_retriever",
    "ResponseGenerator",
    "GenerationResult",
]
