"""pytest 公共夹具：离线配置 + 临时向量库，避免依赖外部 API。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# 确保 src 在路径中（未安装时）
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _offline_settings(tmp_path: Path):
    from ai_agent_framework.config.settings import (
        Settings,
        LLMConfig,
        EmbeddingConfig,
        VectorStoreConfig,
        RAGConfig,
        SplitterConfig,
        RetrievalConfig,
        AgentConfig,
        APIConfig,
        KnowledgeConfig,
        PluginsConfig,
    )

    return Settings(
        llm=LLMConfig(provider="fake", model="fake"),
        embedding=EmbeddingConfig(provider="fake", model="fake", dimensions=64),
        vectorstore=VectorStoreConfig(
            type="chroma", path=str(tmp_path / "store"), collection="test"
        ),
        rag=RAGConfig(
            splitter=SplitterConfig(type="recursive", chunk_size=100, chunk_overlap=10),
            retrieval=RetrievalConfig(strategy="hybrid", top_k=3, candidate_k=10),
        ),
        knowledge=KnowledgeConfig(allowed_roots=[]),
        agent=AgentConfig(max_tool_calls=2),
        api=APIConfig(),
        plugins=PluginsConfig(enabled=False, path=""),
    )


@pytest.fixture()
def offline_settings(tmp_path):
    return _offline_settings(tmp_path)


@pytest.fixture()
def sample_docs_dir(tmp_path):
    """创建临时样例文档。"""
    d = tmp_path / "docs"
    d.mkdir()
    (d / "a.txt").write_text(
        "人工智能是研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统的一门技术。\n"
        "机器学习是人工智能的一个分支，通过数据训练模型。",
        encoding="utf-8",
    )
    (d / "b.md").write_text(
        "# RAG 简介\n\n检索增强生成结合了检索与生成。\n\n"
        "它包含加载、分块、嵌入、检索、生成五个步骤。",
        encoding="utf-8",
    )
    return d
