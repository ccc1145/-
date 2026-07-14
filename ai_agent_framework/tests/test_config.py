"""配置管理测试。"""
from ai_agent_framework.config.settings import (
    Settings,
    LLMConfig,
    load_yaml_config,
    reload_settings,
)


def test_default_settings():
    s = Settings()
    assert s.llm.model == "deepseek-chat"
    assert s.rag.splitter.chunk_size == 500
    assert s.rag.retrieval.strategy == "hybrid"


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("AAF_LLM__MODEL", "gpt-4o")
    monkeypatch.setenv("AAF_LLM__TEMPERATURE", "0.7")
    s = reload_settings()
    assert s.llm.model == "gpt-4o"
    assert s.llm.temperature == 0.7


def test_yaml_load_and_env_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_TEST_KEY", "sk-secret")
    cfg = tmp_path / "c.yaml"
    cfg.write_text("llm:\n  api_key: ${MY_TEST_KEY}\n  model: custom-model\n", encoding="utf-8")
    data = load_yaml_config(cfg)
    assert data["llm"]["api_key"] == "sk-secret"
    assert data["llm"]["model"] == "custom-model"


def test_settings_from_yaml(tmp_path, monkeypatch):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "llm:\n  model: yaml-model\n  temperature: 0.1\n"
        "rag:\n  retrieval:\n    top_k: 7\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AAF_CONFIG_FILE", str(cfg))
    s = reload_settings()
    assert s.llm.model == "yaml-model"
    assert s.rag.retrieval.top_k == 7
