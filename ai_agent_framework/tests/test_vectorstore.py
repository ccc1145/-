"""向量存储与嵌入测试。"""
import pytest
from langchain_core.documents import Document

from ai_agent_framework.rag.embeddings import get_embeddings, _FakeEmbeddings
from ai_agent_framework.rag.vectorstore import get_vectorstore
from ai_agent_framework.config.settings import EmbeddingConfig, VectorStoreConfig


def test_fake_embeddings():
    emb = _FakeEmbeddings(dim=32)
    v1 = emb.embed_query("hello")
    v2 = emb.embed_query("hello")
    assert len(v1) == 32
    assert v1 == v2  # 确定性
    docs = emb.embed_documents(["a", "b"])
    assert len(docs) == 2


def test_get_embeddings_factory():
    emb = get_embeddings(EmbeddingConfig(provider="fake", model="fake", dimensions=16))
    assert isinstance(emb, _FakeEmbeddings)
    assert len(emb.embed_query("x")) == 16


def test_chroma_vectorstore_add_and_search(tmp_path):
    emb = get_embeddings(EmbeddingConfig(provider="fake", model="fake", dimensions=32))
    cfg = VectorStoreConfig(type="chroma", path=str(tmp_path / "vs"), collection="t")
    store = get_vectorstore(cfg, emb)
    docs = [
        Document(page_content="机器学习是人工智能的分支", metadata={"source": "a.txt"}),
        Document(page_content="今天天气真好，适合出门散步", metadata={"source": "b.txt"}),
        Document(page_content="深度学习使用神经网络", metadata={"source": "a.txt"}),
    ]
    ids = store.add_documents(docs)
    assert len(ids) == 3

    results = store.similarity_search("人工智能", top_k=2)
    assert len(results) == 2

    with_scores = store.similarity_search_with_scores("神经网络", top_k=1)
    assert len(with_scores) == 1


def test_chroma_delete_by_source(tmp_path):
    emb = get_embeddings(EmbeddingConfig(provider="fake", model="fake", dimensions=32))
    cfg = VectorStoreConfig(type="chroma", path=str(tmp_path / "vs2"), collection="t2")
    store = get_vectorstore(cfg, emb)
    store.add_documents(
        [
            Document(page_content="内容A", metadata={"source": "a.txt"}),
            Document(page_content="内容B", metadata={"source": "b.txt"}),
        ]
    )
    store.delete_by_source("a.txt")
    # 删除后仍能搜索（只剩 b）
    results = store.similarity_search("内容", top_k=5)
    sources = {d.metadata.get("source") for d in results}
    assert "a.txt" not in sources
