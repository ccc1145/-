"""文本分块器：基于 langchain_text_splitters 封装，策略可配置。"""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
    TokenTextSplitter,
)

from ai_agent_framework.config.settings import SplitterConfig
from ai_agent_framework.core.base import SplitterProtocol


class RecursiveSplitter:
    """递归字符分块器（默认推荐，按分隔符层级递归切分）。"""

    def __init__(self, config: SplitterConfig):
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separators=config.separators,
            keep_separator=True,
        )

    def split(self, documents: list[Document]) -> list[Document]:
        return self._splitter.split_documents(documents)


class CharacterSplitterAdapter:
    """字符分块器（单一分隔符）。"""

    def __init__(self, config: SplitterConfig):
        sep = config.separators[0] if config.separators else "\n\n"
        self._splitter = CharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separator=sep,
        )

    def split(self, documents: list[Document]) -> list[Document]:
        return self._splitter.split_documents(documents)


class TokenSplitterAdapter:
    """Token 分块器（按 token 数切分，适合精确控制上下文窗口）。"""

    def __init__(self, config: SplitterConfig):
        self._splitter = TokenTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )

    def split(self, documents: list[Document]) -> list[Document]:
        return self._splitter.split_documents(documents)


def get_splitter(config: SplitterConfig | None = None) -> SplitterProtocol:
    """工厂函数：按配置返回分块器实例。"""
    if config is None:
        from ai_agent_framework.config import get_settings

        config = get_settings().rag.splitter

    mapping = {
        "recursive": RecursiveSplitter,
        "character": CharacterSplitterAdapter,
        "token": TokenSplitterAdapter,
    }
    cls = mapping.get(config.type)
    if cls is None:
        raise ValueError(f"未知的分块器类型: {config.type}，可选: {list(mapping)}")
    return cls(config)
