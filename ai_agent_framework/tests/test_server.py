"""API 服务端到端测试：覆盖 /health、/ask、/ingest、/sources 及鉴权与路径校验。"""
import pytest
from fastapi.testclient import TestClient

from ai_agent_framework.api import server


def _make_settings(tmp_path, api_key="", allowed_roots=None):
    from ai_agent_framework.config.settings import (
        Settings, LLMConfig, EmbeddingConfig, VectorStoreConfig,
        RAGConfig, SplitterConfig, RetrievalConfig, AgentConfig,
        APIConfig, KnowledgeConfig, PluginsConfig,
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
        knowledge=KnowledgeConfig(allowed_roots=allowed_roots or []),
        agent=AgentConfig(max_tool_calls=2),
        api=APIConfig(api_key=api_key),
        plugins=PluginsConfig(enabled=False, path=""),
    )


@pytest.fixture()
def make_client(tmp_path, monkeypatch):
    """工厂 fixture：按需构建 API 客户端 + kb，可指定 api_key 与 allowed_roots。"""
    def _make(api_key="", allowed_roots=None):
        settings = _make_settings(tmp_path, api_key=api_key, allowed_roots=allowed_roots)
        from ai_agent_framework.api.cli import _build_agent
        agent, kb = _build_agent(settings)
        # 替换 server 模块级名字，使端点调用使用测试 bundle
        monkeypatch.setattr(server, "get_settings", lambda: settings)
        monkeypatch.setattr(server, "_get_agent_bundle", lambda: (agent, kb))
        return TestClient(server.create_app()), kb
    return _make


# ---- /health ----

def test_health_no_auth(make_client):
    client, _ = make_client()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---- /ask 鉴权 ----

def test_ask_no_api_key_required(make_client):
    """未配置 api_key 时 /ask 无需鉴权。"""
    client, _ = make_client(api_key="")
    r = client.post("/ask", json={"query": "什么是 RAG"})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert "sources" in data
    assert "tool_calls" in data


def test_ask_with_correct_api_key(make_client):
    client, _ = make_client(api_key="secret123")
    r = client.post("/ask", json={"query": "hello"}, headers={"X-API-Key": "secret123"})
    assert r.status_code == 200


def test_ask_missing_api_key_returns_401(make_client):
    client, _ = make_client(api_key="secret123")
    r = client.post("/ask", json={"query": "hello"})
    assert r.status_code == 401


def test_ask_wrong_api_key_returns_401(make_client):
    client, _ = make_client(api_key="secret123")
    r = client.post("/ask", json={"query": "hello"}, headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


# ---- /ingest 路径校验 ----

def test_ingest_absolute_path_in_whitelist(make_client, tmp_path):
    """白名单内的绝对路径摄入成功。"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    f = docs_dir / "a.txt"
    f.write_text("测试内容用于摄入", encoding="utf-8")

    client, _ = make_client(allowed_roots=[str(docs_dir)])
    r = client.post("/ingest", json={"path": str(f)})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["chunks"] > 0


def test_ingest_absolute_path_rejected_without_whitelist(make_client, tmp_path):
    """无白名单时，绝对路径被拒绝。"""
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    client, _ = make_client(allowed_roots=[])
    r = client.post("/ingest", json={"path": str(f)})
    assert r.status_code == 403


def test_ingest_dotdot_traversal_rejected(make_client, tmp_path):
    """.. 路径穿越被拒绝。"""
    client, _ = make_client(allowed_roots=[str(tmp_path)])
    r = client.post("/ingest", json={"path": "../etc/passwd"})
    assert r.status_code == 403


def test_ingest_path_outside_whitelist_rejected(make_client, tmp_path):
    """白名单外的绝对路径被拒绝。"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    f = other_dir / "secret.txt"
    f.write_text("secret", encoding="utf-8")

    client, _ = make_client(allowed_roots=[str(docs_dir)])
    r = client.post("/ingest", json={"path": str(f)})
    assert r.status_code == 403


def test_ingest_nonexistent_path_returns_404(make_client, tmp_path):
    """白名单内但路径不存在返回 404。"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    client, _ = make_client(allowed_roots=[str(docs_dir)])
    nonexistent = str(docs_dir / "missing.txt")
    r = client.post("/ingest", json={"path": nonexistent})
    assert r.status_code == 404


def test_ingest_requires_api_key(make_client, tmp_path):
    """配置 api_key 后 /ingest 也需要鉴权。"""
    client, _ = make_client(api_key="secret123", allowed_roots=[str(tmp_path)])
    r = client.post("/ingest", json={"path": "x.txt"})
    assert r.status_code == 401


# ---- /sources ----

def test_sources_empty_initially(make_client):
    """初始 /sources 返回空 dict。"""
    client, _ = make_client()
    r = client.get("/sources")
    assert r.status_code == 200
    assert r.json() == {}


def test_sources_after_ingest(make_client, tmp_path):
    """摄入后 /sources 列出已摄入源。"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    f = docs_dir / "a.txt"
    f.write_text("测试内容用于摄入", encoding="utf-8")

    client, _ = make_client(allowed_roots=[str(docs_dir)])
    client.post("/ingest", json={"path": str(f)})
    r = client.get("/sources")
    assert r.status_code == 200
    sources = r.json()
    assert any("a.txt" in s for s in sources)


def test_sources_requires_api_key(make_client):
    """配置 api_key 后 /sources 需要鉴权。"""
    client, _ = make_client(api_key="secret123")
    r = client.get("/sources")
    assert r.status_code == 401


# ---- 端到端：摄入 → 提问 ----

def test_end_to_end_ingest_then_ask(make_client, tmp_path):
    """摄入文档后通过 /ask 检索到相关上下文。"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    f = docs_dir / "rag.md"
    f.write_text(
        "# RAG 简介\n检索增强生成结合了检索与生成。\n它包含加载、分块、嵌入、检索、生成五个步骤。",
        encoding="utf-8",
    )

    client, _ = make_client(allowed_roots=[str(docs_dir)])
    # 1. 摄入
    r1 = client.post("/ingest", json={"path": str(f)})
    assert r1.status_code == 200
    # 2. 提问
    r2 = client.post("/ask", json={"query": "什么是 RAG？"})
    assert r2.status_code == 200
    data = r2.json()
    assert len(data["answer"]) > 0
    # FakeLLM 不一定引用 sources，但 sources 字段结构应正确
    assert isinstance(data["sources"], list)
