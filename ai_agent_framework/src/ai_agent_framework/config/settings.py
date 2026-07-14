"""配置管理模块：基于 Pydantic Settings，支持 YAML + 环境变量加载。

优先级：环境变量 (AAF_ 前缀) > .env > YAML 配置文件 > 代码默认值。
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    temperature: float = 0.3
    max_tokens: int = 2048


class EmbeddingConfig(BaseModel):
    provider: str = "openai"
    model: str = "embedding-3"
    api_key: str = ""
    base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    dimensions: int = 1024


class VectorStoreConfig(BaseModel):
    type: str = "chroma"
    path: str = "./data/vectorstore"
    collection: str = "default"


class SplitterConfig(BaseModel):
    type: str = "recursive"  # recursive | character | token
    chunk_size: int = 500
    chunk_overlap: int = 50
    separators: list[str] = Field(
        default_factory=lambda: ["\n\n", "\n", "。", ".", " ", ""]
    )


class RetrievalConfig(BaseModel):
    strategy: str = "hybrid"  # vector | hybrid
    top_k: int = 4
    vector_weight: float = 0.6
    candidate_k: int = 20


class RAGConfig(BaseModel):
    splitter: SplitterConfig = Field(default_factory=SplitterConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)


class AgentConfig(BaseModel):
    answer_when_no_context: bool = True
    max_tool_calls: int = 3


class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    # 可选 API Key 鉴权；为空则不鉴权（仅适合本地开发）
    api_key: str = ""


class KnowledgeConfig(BaseModel):
    # 允许摄入的根目录白名单（绝对路径或相对 cwd）；为空表示允许任意路径（不安全）
    allowed_roots: list[str] = Field(default_factory=list)


class PluginsConfig(BaseModel):
    enabled: bool = True
    path: str = "./plugins"


def _expand_env(value: Any) -> Any:
    """递归展开字符串中的 ${ENV_VAR} 引用。"""
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def load_yaml_config(path: str | Path) -> dict:
    """加载 YAML 配置文件并展开其中的环境变量引用。"""
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data = _expand_env(data)
    data.pop("config_file", None)  # 避免循环
    return data


# 模块级配置文件覆盖（避免污染 os.environ，保证测试隔离）
_CONFIG_FILE_OVERRIDE: str | None = None


class YamlConfigSource(PydanticBaseSettingsSource):
    """自定义 YAML 配置源，优先级低于环境变量。"""

    def __init__(self, settings_cls: type[BaseSettings]):
        super().__init__(settings_cls)
        # 优先级：模块级覆盖 > 环境变量 AAF_CONFIG_FILE > 默认 config.yaml
        cfg_path = _CONFIG_FILE_OVERRIDE or os.getenv("AAF_CONFIG_FILE", "config.yaml")
        self._yaml_data: dict[str, Any] = load_yaml_config(cfg_path)

    def get_field_value(self, field, field_name: str):
        value = self._yaml_data.get(field_name)
        return value, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._yaml_data

    def prepare_field_value(self, field_name, field, value, value_is_complex):
        return value


class Settings(BaseSettings):
    """框架全局配置。优先级：环境变量 > .env > YAML > 默认值。"""

    model_config = SettingsConfigDict(
        env_prefix="AAF_",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    vectorstore: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # 优先级从高到低
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSource(settings_cls),
            file_secret_settings,
        )


@lru_cache(maxsize=1)
def get_settings(config_file: str | None = None) -> Settings:
    """获取全局配置单例。

    config_file 参数仅用于显式指定 YAML 路径（测试用）；运行时通过
    AAF_CONFIG_FILE 环境变量或默认 'config.yaml' 定位。
    不会修改 os.environ，避免测试间状态污染。
    """
    global _CONFIG_FILE_OVERRIDE
    if config_file is not None:
        _CONFIG_FILE_OVERRIDE = config_file
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass
    return Settings()


def reload_settings(config_file: str | None = None) -> Settings:
    """强制重新加载配置（测试用）。

    同时清除模块级覆盖，避免上次测试设置残留。
    也会联动清除 API 层的 agent bundle 缓存（若已导入）。
    """
    global _CONFIG_FILE_OVERRIDE
    get_settings.cache_clear()
    _CONFIG_FILE_OVERRIDE = config_file
    # 联动清除下游 lru_cache，避免停留在旧配置
    try:
        from ai_agent_framework.api.server import _get_agent_bundle

        _get_agent_bundle.cache_clear()
    except Exception:  # noqa: BLE001
        # api 模块未导入时无需清除
        pass
    return get_settings(config_file)
