"""检索器测试：向量 + 混合。"""
import pytest
from langchain_core.documents import Document

from ai_agent_framework.rag.embeddings import get_embeddings
from ai_agent_framework.rag.vectorstore import get_vectorstore
from ai_agent_framework.rag.retrievers import VectorRetriever, HybridRetriever, get_retriever
from ai_agent_framework.config.settings import EmbeddingConfig, VectorStoreConfig, RetrievalConfig


@pytest.fixture()
def store_with_docs(tmp_path):
    emb = get_embeddings(EmbeddingConfig(provider="fake", model="fake", dimensions=32))
    cfg = VectorStoreConfig(type="chroma", path=str(tmp_path / "vs"), collection="t")
    store = get_vectorstore(cfg, emb)
    docs = [
        Document(page_content="Python 是一种流行的编程语言", metadata={"source": "lang"}),
        Document(page_content="Java 也是一种编程语言", metadata={"source": "lang"}),
        Document(page_content="机器学习需要大量数据训练", metadata={"source": "ml"}),
        Document(page_content="深度学习是机器学习的子领域", metadata={"source": "ml"}),
    ]
    store.add_documents(docs)
    return store, docs


def test_vector_retriever(store_with_docs):
    store, _ = store_with_docs
    ret = VectorRetriever(store, RetrievalConfig(strategy="vector", top_k=2))
    docs = ret.retrieve("编程语言")
    assert len(docs) <= 2


def test_hybrid_retriever_keyword_boost(store_with_docs):
    store, corpus = store_with_docs
    ret = HybridRetriever(
        store, RetrievalConfig(strategy="hybrid", top_k=2, candidate_k=10), corpus=corpus
    )
    # 精确关键词命中应被提升
    docs = ret.retrieve("Python")
    contents = [d.page_content for d in docs]
    assert any("Python" in c for c in contents)


def test_hybrid_retriever_update_corpus(store_with_docs):
    store, _ = store_with_docs
    ret = HybridRetriever(store, RetrievalConfig(strategy="hybrid", top_k=2))
    # 空 corpus 时 BM25 无贡献，但向量检索仍工作
    docs = ret.retrieve("anything")
    assert isinstance(docs, list)
    # update_corpus 后 BM25 索引生效（多文档以避免单文档 IDF=0）
    new_docs = [
        Document(page_content="全新内容 about RAG retrieval", metadata={"source": "new1"}),
        Document(page_content="另一篇关于生成的笔记", metadata={"source": "new2"}),
        Document(page_content="第三篇关于向量库的内容", metadata={"source": "new3"}),
    ]
    ret.update_corpus(new_docs)
    bm25_only = ret._bm25_search("RAG", top_k=5)
    assert any("RAG" in d.page_content for d in bm25_only)


def test_retriever_factory(store_with_docs):
    store, corpus = store_with_docs
    r1 = get_retriever(store, RetrievalConfig(strategy="vector", top_k=1))
    assert isinstance(r1, VectorRetriever)
    r2 = get_retriever(store, RetrievalConfig(strategy="hybrid", top_k=1), corpus=corpus)
    assert isinstance(r2, HybridRetriever)
