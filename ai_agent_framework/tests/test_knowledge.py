"""知识库管理测试。"""
import pytest

from ai_agent_framework.knowledge import KnowledgeBase


def test_kb_add_and_search(offline_settings, sample_docs_dir):
    kb = KnowledgeBase(offline_settings)
    # 摄入 txt
    r = kb.add_documents(sample_docs_dir / "a.txt")
    assert r["chunks"] > 0
    assert r["status"] == "ok"
    # 搜索
    docs = kb.search("机器学习")
    assert len(docs) >= 1


def test_kb_list_sources(offline_settings, sample_docs_dir):
    kb = KnowledgeBase(offline_settings)
    kb.add_documents(sample_docs_dir / "a.txt")
    kb.add_documents(sample_docs_dir / "b.md")
    sources = kb.list_sources()
    assert len(sources) == 2
    assert any("a.txt" in s for s in sources)


def test_kb_delete_source(offline_settings, sample_docs_dir):
    kb = KnowledgeBase(offline_settings)
    kb.add_documents(sample_docs_dir / "a.txt")
    kb.add_documents(sample_docs_dir / "b.md")
    r = kb.delete_source(str(sample_docs_dir / "a.txt"))
    assert r["removed"] is True
    assert str(sample_docs_dir / "a.txt") not in kb.list_sources()


def test_kb_add_text(offline_settings):
    kb = KnowledgeBase(offline_settings)
    r = kb.add_text("这是一段直接摄入的文本内容", source="inline-1")
    assert r["chunks"] > 0
    assert "inline-1" in kb.list_sources()


def test_kb_corpus_sync(offline_settings, sample_docs_dir):
    kb = KnowledgeBase(offline_settings)
    kb.add_documents(sample_docs_dir / "a.txt")
    assert len(kb.corpus) > 0
    kb.delete_source(str(sample_docs_dir / "a.txt"))
    assert len(kb.corpus) == 0


def test_kb_reingest_load_failure_keeps_old_data(offline_settings, sample_docs_dir, tmp_path):
    """M-2 回归：重新摄入时若 loader 加载失败，旧数据不应丢失。"""
    kb = KnowledgeBase(offline_settings)
    src = sample_docs_dir / "a.txt"
    kb.add_documents(src)
    old_count = len(kb.corpus)
    assert old_count > 0

    # 模拟 loader 抛异常
    original_load = kb._loader.load
    def _boom(_path):
        raise RuntimeError("模拟加载失败")
    kb._loader.load = _boom
    try:
        with pytest.raises(RuntimeError):
            kb.add_documents(src)
    finally:
        kb._loader.load = original_load

    # 旧数据仍在
    assert len(kb.corpus) == old_count
    assert src.name in " ".join(kb.list_sources().keys())


def test_kb_reingest_idempotent(offline_settings, sample_docs_dir):
    """重复摄入同一文件应幂等：不产生重复 chunks。"""
    kb = KnowledgeBase(offline_settings)
    src = sample_docs_dir / "a.txt"
    r1 = kb.add_documents(src)
    r2 = kb.add_documents(src)
    assert r1["chunks"] == r2["chunks"]
    # corpus 中没有重复 source 的 chunk
    sources = [d.metadata.get("source") for d in kb.corpus]
    assert sources.count(str(src)) == r1["chunks"]


# ---- M6: rebuild_index 失效源清理 ----

def test_kb_rebuild_index_cleans_stale_sources(offline_settings, sample_docs_dir, tmp_path):
    """rebuild_index 应清理已不存在的失效源元数据。"""
    kb = KnowledgeBase(offline_settings)
    # 摄入两个存在的源
    src_a = sample_docs_dir / "a.txt"
    src_b = sample_docs_dir / "b.md"
    kb.add_documents(src_a)
    kb.add_documents(src_b)

    # 创建一个临时源，摄入后删除文件
    stale_file = tmp_path / "stale.txt"
    stale_file.write_text("这个文件会被删除", encoding="utf-8")
    kb.add_documents(stale_file)
    assert str(stale_file) in kb.list_sources()

    # 删除文件，使其成为失效源
    stale_file.unlink()

    # 重建索引
    result = kb.rebuild_index()
    assert result["rebuilt"] == 2  # a.txt 和 b.md 重建成功
    assert result["removed_stale"] == 1  # stale_file 被清理

    # 失效源已从 meta 移除
    sources = kb.list_sources()
    assert str(stale_file) not in sources
    assert str(src_a) in sources
    assert str(src_b) in sources


def test_kb_rebuild_index_all_stale(offline_settings, tmp_path):
    """所有源都失效时，rebuild_index 清理所有，不抛异常。"""
    kb = KnowledgeBase(offline_settings)
    stale1 = tmp_path / "s1.txt"
    stale2 = tmp_path / "s2.txt"
    stale1.write_text("内容1", encoding="utf-8")
    stale2.write_text("内容2", encoding="utf-8")
    kb.add_documents(stale1)
    kb.add_documents(stale2)

    stale1.unlink()
    stale2.unlink()

    result = kb.rebuild_index()
    assert result["rebuilt"] == 0
    assert result["removed_stale"] == 2
    assert kb.list_sources() == {}


# ---- attach_retriever BM25 同步 ----

def test_kb_attach_retriever_syncs_bm25(offline_settings, sample_docs_dir):
    """attach_retriever 后，增删文档时 BM25 索引实际刷新。"""
    from ai_agent_framework.rag.retrievers import HybridRetriever, get_retriever

    kb = KnowledgeBase(offline_settings)
    retriever = get_retriever(
        kb.vectorstore, offline_settings.rag.retrieval, corpus=kb.corpus
    )
    kb.attach_retriever(retriever)

    # 初始 BM25 为空
    assert retriever._bm25 is None or len(retriever._corpus) == 0

    # 摄入文档后 BM25 应自动刷新
    kb.add_documents(sample_docs_dir / "a.txt")
    assert len(retriever._corpus) > 0
    assert retriever._bm25 is not None

    # 删除文档后 BM25 应再次刷新
    kb.delete_source(str(sample_docs_dir / "a.txt"))
    assert len(retriever._corpus) == 0
    assert retriever._bm25 is None


def test_kb_attach_retriever_after_adding_docs(offline_settings, sample_docs_dir):
    """先摄入文档再 attach_retriever：初始 corpus 同步过去。"""
    from ai_agent_framework.rag.retrievers import get_retriever

    kb = KnowledgeBase(offline_settings)
    kb.add_documents(sample_docs_dir / "a.txt")
    assert len(kb.corpus) > 0

    # 此时 retriever 还未 attach
    retriever = get_retriever(
        kb.vectorstore, offline_settings.rag.retrieval, corpus=[]
    )
    assert len(retriever._corpus) == 0

    # attach 后 corpus 同步
    kb.attach_retriever(retriever)
    assert len(retriever._corpus) == len(kb.corpus)


def test_kb_add_text_syncs_retriever(offline_settings):
    """add_text 也应同步 retriever 的 BM25。"""
    from ai_agent_framework.rag.retrievers import get_retriever

    kb = KnowledgeBase(offline_settings)
    retriever = get_retriever(
        kb.vectorstore, offline_settings.rag.retrieval, corpus=kb.corpus
    )
    kb.attach_retriever(retriever)

    kb.add_text("一段关于人工智能的文本内容", source="inline-1")
    assert any(d.metadata.get("source") == "inline-1" for d in retriever._corpus)
    assert retriever._bm25 is not None

    kb.delete_source("inline-1")
    assert all(d.metadata.get("source") != "inline-1" for d in retriever._corpus)
