"""并发安全测试：验证 ToolRegistry / ComponentRegistry / HybridRetriever / KnowledgeBase 的 RLock 修复。

每个测试启动多个线程并发读写，断言最终状态一致、无异常抛出、无数据丢失。
"""
import threading

import pytest
from langchain_core.documents import Document

from ai_agent_framework.tools import ToolRegistry, CalculatorTool
from ai_agent_framework.tools.base import Tool
from ai_agent_framework.core.registry import ComponentRegistry, get_registry
from ai_agent_framework.rag.retrievers import HybridRetriever
from ai_agent_framework.rag.embeddings import get_embeddings
from ai_agent_framework.rag.vectorstore import get_vectorstore
from ai_agent_framework.config.settings import (
    EmbeddingConfig, VectorStoreConfig, RetrievalConfig,
)
from ai_agent_framework.knowledge import KnowledgeBase


# ---- ToolRegistry 并发 ----

class _DummyTool(Tool):
    """每次实例化生成唯一 name 的工具。"""
    def __init__(self, n):
        self.name = f"tool_{n}"
        self.description = "test"

    def run(self, input: str) -> str:
        return f"{self.name}:{input}"


def test_tool_registry_concurrent_register():
    """多线程并发注册不同工具，最终全部可见。"""
    reg = ToolRegistry()
    n_threads = 20
    per_thread = 10

    def worker(tid):
        for i in range(per_thread):
            reg.register(_DummyTool(f"{tid}_{i}"))

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(reg.names()) == n_threads * per_thread


def test_tool_registry_concurrent_read_while_write():
    """并发读不影响写，并发写不阻塞读。"""
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    errors = []

    def reader():
        try:
            for _ in range(100):
                _ = reg.names()
                _ = reg.list()
                assert reg.has("calculator")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    def writer():
        try:
            for i in range(50):
                reg.register(_DummyTool(f"w_{i}"))
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=reader) for _ in range(5)] + [
        threading.Thread(target=writer) for _ in range(3)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    # calculator 仍在
    assert reg.has("calculator")
    assert reg.call("calculator", "1+1") == "2"


# ---- ComponentRegistry 并发 ----

def test_component_registry_concurrent_register():
    """单例 ComponentRegistry 并发注册不丢、不重。"""
    reg = ComponentRegistry()
    reg.clear()
    n_threads = 20
    per_thread = 10

    def worker(tid):
        for i in range(per_thread):
            reg.register("test_cat", f"{tid}_{i}", f"comp_{tid}_{i}")

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(reg.list("test_cat")) == n_threads * per_thread


def test_component_registry_concurrent_get_clear():
    """并发 get 与 clear 不抛异常（get 在 clear 后返回 KeyError 是允许的）。"""
    reg = ComponentRegistry()
    reg.clear()
    for i in range(100):
        reg.register("cat", f"k{i}", f"v{i}")

    errors = []

    def getter():
        try:
            for i in range(50):
                try:
                    reg.get("cat", f"k{i}")
                except KeyError:
                    pass  # 已被 clear 是允许的
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    def clearer():
        try:
            for _ in range(5):
                reg.clear()
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=getter) for _ in range(5)] + [
        threading.Thread(target=clearer) for _ in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors


# ---- HybridRetriever 并发 ----

@pytest.fixture()
def hybrid_retriever(tmp_path):
    emb = get_embeddings(EmbeddingConfig(provider="fake", model="fake", dimensions=32))
    cfg = VectorStoreConfig(type="chroma", path=str(tmp_path / "vs"), collection="t")
    store = get_vectorstore(cfg, emb)
    return HybridRetriever(store, RetrievalConfig(strategy="hybrid", top_k=3, candidate_k=10))


def test_hybrid_retriever_concurrent_update(hybrid_retriever):
    """并发 update_corpus 不损坏 BM25 索引。"""
    errors = []

    def updater(tid):
        try:
            for i in range(20):
                docs = [
                    Document(page_content=f"线程{tid} 文档{i} 关于 AI", metadata={"source": f"s{tid}_{i}"}),
                    Document(page_content=f"另一篇 thread {tid} note {i}", metadata={"source": f"s{tid}_{i}"}),
                ]
                hybrid_retriever.update_corpus(docs)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=updater, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    # 最终一次检索应能正常返回
    docs = hybrid_retriever.retrieve("AI")
    assert isinstance(docs, list)


def test_hybrid_retriever_concurrent_read_during_update(hybrid_retriever):
    """并发读 + 写：读不阻塞写，写不损坏读。"""
    initial = [
        Document(page_content="初始语料 about RAG", metadata={"source": "init1"}),
        Document(page_content="初始语料 about LLM", metadata={"source": "init2"}),
    ]
    hybrid_retriever.update_corpus(initial)
    errors = []

    def reader():
        try:
            for _ in range(50):
                _ = hybrid_retriever.retrieve("RAG")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    def writer():
        try:
            for i in range(20):
                hybrid_retriever.update_corpus([
                    Document(page_content=f"新语料 {i}", metadata={"source": f"n{i}"}),
                    Document(page_content=f"另一篇 {i}", metadata={"source": f"n{i}"}),
                ])
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=reader) for _ in range(5)] + [
        threading.Thread(target=writer) for _ in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors


# ---- KnowledgeBase 并发 ----

def test_kb_concurrent_add_documents_different_sources(offline_settings, sample_docs_dir):
    """并发摄入不同源：所有 chunks 最终都在 corpus 中，不丢失。"""
    kb = KnowledgeBase(offline_settings)
    # 先准备多个独立源文件
    files = []
    for i, name in enumerate(["a.txt", "b.md"]):
        files.append(sample_docs_dir / name)

    errors = []

    def ingest(f):
        try:
            r = kb.add_documents(f)
            assert r["status"] == "ok"
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=ingest, args=(f,)) for f in files]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    # 两个源都在 meta 中
    sources = kb.list_sources()
    assert len(sources) == 2
    # corpus 中每个源的 chunks 数与 meta 记录一致
    for src, info in sources.items():
        chunk_count = sum(1 for d in kb.corpus if d.metadata.get("source") == src)
        assert chunk_count == info["chunks"], f"源 {src} 的 corpus 数与 meta 不符"


def test_kb_concurrent_reingest_same_source(offline_settings, sample_docs_dir):
    """并发重新摄入同一源：最终 corpus 中该源的 chunks 数等于一次摄入量（幂等）。"""
    kb = KnowledgeBase(offline_settings)
    src = sample_docs_dir / "a.txt"

    errors = []

    def reingest():
        try:
            kb.add_documents(src)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=reingest) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    # 该源的 chunks 数应等于单次摄入量，不重复
    sources = kb.list_sources()
    assert str(src) in sources
    expected = sources[str(src)]["chunks"]
    actual = sum(1 for d in kb.corpus if d.metadata.get("source") == str(src))
    assert actual == expected, f"重复摄入后 chunks 数应为 {expected}，实际 {actual}"


def test_kb_concurrent_delete_during_ingest(offline_settings, sample_docs_dir):
    """并发删除与摄入：无异常，最终状态一致。"""
    kb = KnowledgeBase(offline_settings)
    src = sample_docs_dir / "a.txt"
    kb.add_documents(src)
    assert len(kb.corpus) > 0

    errors = []

    def ingester():
        try:
            for _ in range(5):
                kb.add_documents(src)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    def deleter():
        try:
            for _ in range(5):
                kb.delete_source(str(src))
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=ingester), threading.Thread(target=deleter)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    # 最终 corpus 中该源的 chunks 数与 meta 一致（要么 0 要么等于单次摄入量）
    sources = kb.list_sources()
    if str(src) in sources:
        expected = sources[str(src)]["chunks"]
        actual = sum(1 for d in kb.corpus if d.metadata.get("source") == str(src))
        assert actual == expected
    else:
        # 已被删除
        assert all(d.metadata.get("source") != str(src) for d in kb.corpus)
