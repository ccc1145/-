"""文档加载器测试。"""
from pathlib import Path

import pytest

from ai_agent_framework.rag.loaders import (
    TextLoader,
    MarkdownLoader,
    AutoLoader,
    get_loader,
)


def test_text_loader(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello world\n第二行", encoding="utf-8")
    docs = TextLoader().load(f)
    assert len(docs) == 1
    assert "hello world" in docs[0].page_content
    assert docs[0].metadata["type"] == "txt"
    assert docs[0].metadata["source"] == str(f)


def test_markdown_loader(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("# 标题\n正文", encoding="utf-8")
    docs = MarkdownLoader().load(f)
    assert len(docs) == 1
    assert "正文" in docs[0].page_content
    assert docs[0].metadata["type"] == "md"


def test_autoloader_directory(sample_docs_dir):
    docs = AutoLoader().load(sample_docs_dir)
    assert len(docs) >= 2
    types = {d.metadata["type"] for d in docs}
    assert "txt" in types and "md" in types


def test_autoloader_unsupported(tmp_path):
    f = tmp_path / "a.xyz"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="不支持"):
        AutoLoader().load(f)


def test_get_loader_by_extension(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    loader = get_loader(f)
    assert isinstance(loader, TextLoader)
