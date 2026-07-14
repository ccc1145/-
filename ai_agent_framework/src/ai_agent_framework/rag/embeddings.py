"""嵌入模型工厂：默认 OpenAI 兼容接口，可扩展本地模型。"""
from __future__ import annotations

from langchain_core.embeddings import Embeddings

from ai_agent_framework.config.settings import EmbeddingConfig


def get_embeddings(config: EmbeddingConfig | None = None) -> Embeddings:
    """工厂函数：返回嵌入模型实例。

    默认走 OpenAI 兼容接口（智谱 embedding-3 / DeepSeek / OpenAI 均可）。
    provider 为 'fake' 时返回确定性假嵌入，供离线测试。
    """
    if config is None:
        from ai_agent_framework.config import get_settings

        config = get_settings().embedding

    if config.provider == "fake":
        return _FakeEmbeddings(dim=config.dimensions)

    if config.provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        kwargs: dict = {
            "model": config.model,
            "api_key": config.api_key,
            "base_url": config.base_url,
        }
        # embedding-3 等模型支持 dimensions 参数
        if config.dimensions:
            kwargs["dimensions"] = config.dimensions
        return OpenAIEmbeddings(**kwargs)

    raise ValueError(f"未知的 embedding provider: {config.provider}")


class _FakeEmbeddings(Embeddings):
    """确定性假嵌入，用于离线/测试场景。

    基于 hashlib（非内置 hash()），跨进程可复现，避免 PYTHONHASHSEED 随机化
    导致持久化向量库与重启后查询向量不一致的问题。
    """

    def __init__(self, dim: int = 64):
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        import hashlib

        h = hashlib.md5(text.encode("utf-8")).digest()
        # 拉伸到目标维度
        out = []
        i = 0
        while len(out) < self.dim:
            h = hashlib.md5(h + i.to_bytes(4, "big")).digest()
            for b in h:
                if len(out) < self.dim:
                    out.append(b / 255.0)
            i += 1
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)
