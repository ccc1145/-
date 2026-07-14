"""FastAPI 服务接口。

安全说明：
- 当 settings.api.api_key 非空时，所有写接口需携带 `X-API-Key` 头。
- 摄入路径受 settings.knowledge.allowed_roots 白名单约束（为空时仅允许相对路径，拒绝绝对路径与..）。
- 生产部署务必配置 api_key 与 allowed_roots。
"""
from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from ai_agent_framework.config import get_settings


class AskRequest(BaseModel):
    query: str
    top_k: int | None = None


class IngestRequest(BaseModel):
    path: str


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]]
    tool_calls: list[dict[str, str]]


class IngestResponse(BaseModel):
    source: str
    chunks: int
    status: str


@lru_cache(maxsize=1)
def _get_agent_bundle():
    """惰性构建 Agent + KB（避免 import 时副作用）。"""
    from ai_agent_framework.api.cli import _build_agent

    return _build_agent(get_settings())


def _check_api_key(x_api_key: str | None) -> None:
    api_key = get_settings().api.api_key
    if api_key and not secrets.compare_digest(x_api_key or "", api_key):
        raise HTTPException(status_code=401, detail="无效或缺失的 API Key")


def _validate_ingest_path(path: str) -> str:
    """校验摄入路径在白名单内，防止路径遍历读取敏感文件。"""
    settings = get_settings()
    raw = path
    # 解析为绝对路径（相对 cwd）
    p = Path(raw).resolve()
    # 拒绝显式绝对路径与 .. 穿越（除非白名单显式允许）
    if os.path.isabs(raw) or ".." in Path(raw).parts:
        allowed = False
    else:
        allowed = True
    roots = [Path(r).resolve() for r in settings.knowledge.allowed_roots]
    if roots:
        # 配置了白名单：必须在某个根之下
        allowed = any(p == r or r in p.parents for r in roots)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="路径不在允许的根目录白名单内，已拒绝摄入以防止读取敏感文件。",
        )
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"路径不存在: {raw}")
    return str(p)


def create_app() -> FastAPI:
    app = FastAPI(title="AI Agent Framework API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ask", response_model=AskResponse)
    def ask(req: AskRequest, x_api_key: str | None = Header(default=None)) -> AskResponse:
        _check_api_key(x_api_key)
        agent, _ = _get_agent_bundle()
        result = agent.run(req.query)
        sources = [
            {"source": d.metadata.get("source", ""), "snippet": d.page_content[:200]}
            for d in result.source_documents
        ]
        return AskResponse(
            answer=result.answer,
            sources=sources,
            tool_calls=result.tool_calls,
        )

    @app.post("/ingest", response_model=IngestResponse)
    def ingest(
        req: IngestRequest, x_api_key: str | None = Header(default=None)
    ) -> IngestResponse:
        _check_api_key(x_api_key)
        safe_path = _validate_ingest_path(req.path)
        _, kb = _get_agent_bundle()
        r = kb.add_documents(safe_path)
        return IngestResponse(source=r["source"], chunks=r["chunks"], status=r["status"])

    @app.get("/sources")
    def sources(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
        _check_api_key(x_api_key)
        _, kb = _get_agent_bundle()
        return kb.list_sources()

    return app


# 便于 `uvicorn ai_agent_framework.api.server:app` 直接启动
app = create_app()
