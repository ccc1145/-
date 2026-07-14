"""文本分块器测试。"""
from langchain_core.documents import Document

from ai_agent_framework.rag.splitters import get_splitter
from ai_agent_framework.config.settings import SplitterConfig


def _long_doc() -> Document:
    text = "。".join([f"第{i}段内容" for i in range(50)])
    return Document(page_content=text, metadata={"source": "test"})


def test_recursive_splitter_chunk_count():
    cfg = SplitterConfig(type="recursive", chunk_size=50, chunk_overlap=10, separators=["。", " "])
    splitter = get_splitter(cfg)
    chunks = splitter.split([_long_doc()])
    assert len(chunks) > 1
    assert all(c.page_content for c in chunks)
    # 元数据应保留
    assert all(c.metadata.get("source") == "test" for c in chunks)


def test_character_splitter():
    cfg = SplitterConfig(type="character", chunk_size=30, chunk_overlap=5, separators=["。"])
    splitter = get_splitter(cfg)
    chunks = splitter.split([_long_doc()])
    assert len(chunks) > 1


def test_token_splitter():
    cfg = SplitterConfig(type="token", chunk_size=20, chunk_overlap=4)
    splitter = get_splitter(cfg)
    chunks = splitter.split([_long_doc()])
    assert len(chunks) > 1


def test_unknown_type_raises():
    cfg = SplitterConfig(type="unknown")
    import pytest

    with pytest.raises(ValueError, match="未知的分块器类型"):
        get_splitter(cfg)
