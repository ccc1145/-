"""文档加载器：支持 PDF / TXT / Markdown，AutoLoader 按扩展名自动分发。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Union

from langchain_core.documents import Document


class DocumentLoader:
    """加载器基类。子类实现 `load`。"""

    def load(self, source: Union[str, Path]) -> list[Document]:
        raise NotImplementedError


class TextLoader(DocumentLoader):
    """纯文本加载器。"""

    def load(self, source: Union[str, Path]) -> list[Document]:
        p = Path(source)
        text = p.read_text(encoding="utf-8")
        return [Document(page_content=text, metadata={"source": str(p), "type": "txt"})]


class MarkdownLoader(DocumentLoader):
    """Markdown 加载器，保留原文。"""

    def load(self, source: Union[str, Path]) -> list[Document]:
        p = Path(source)
        text = p.read_text(encoding="utf-8")
        return [Document(page_content=text, metadata={"source": str(p), "type": "md"})]


class PDFLoader(DocumentLoader):
    """PDF 加载器，基于 pypdf。按页切分为多个 Document。"""

    def load(self, source: Union[str, Path]) -> list[Document]:
        from pypdf import PdfReader

        reader = PdfReader(str(source))
        docs: list[Document] = []
        for i, page in enumerate(reader.pages):
            content = page.extract_text() or ""
            docs.append(
                Document(
                    page_content=content,
                    metadata={"source": str(source), "type": "pdf", "page": i + 1},
                )
            )
        return docs


# 扩展名 -> 加载器类
_LOADER_MAP: dict[str, type[DocumentLoader]] = {
    ".txt": TextLoader,
    ".md": MarkdownLoader,
    ".markdown": MarkdownLoader,
    ".pdf": PDFLoader,
}


class AutoLoader(DocumentLoader):
    """按文件扩展名自动选择加载器；支持单文件或目录（递归）。"""

    def __init__(self, loaders: dict[str, type[DocumentLoader]] | None = None):
        self._map = loaders or _LOADER_MAP

    def load(self, source: Union[str, Path]) -> list[Document]:
        p = Path(source)
        if p.is_dir():
            docs: list[Document] = []
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix.lower() in self._map:
                    docs.extend(self._load_file(f))
            return docs
        return self._load_file(p)

    def _load_file(self, p: Path) -> list[Document]:
        ext = p.suffix.lower()
        loader_cls = self._map.get(ext)
        if loader_cls is None:
            raise ValueError(f"不支持的文件类型: {ext} ({p})")
        return loader_cls().load(p)


def get_loader(file_path: Union[str, Path]) -> DocumentLoader:
    """根据单个文件扩展名返回对应加载器实例。"""
    p = Path(file_path)
    loader_cls = _LOADER_MAP.get(p.suffix.lower())
    if loader_cls is None:
        raise ValueError(f"不支持的文件类型: {p.suffix} ({p})")
    return loader_cls()
