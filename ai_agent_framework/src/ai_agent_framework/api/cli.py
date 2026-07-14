"""CLI 交互接口：ingest / ask / list / serve / rebuild。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ai_agent_framework.config import get_settings, reload_settings


def _build_kb(settings=None):
    from ai_agent_framework.knowledge import KnowledgeBase

    return KnowledgeBase(settings)


def _build_agent(settings=None):
    """构建 Agent + KB，并加载插件、同步检索器语料。"""
    from ai_agent_framework.core.agent import Agent
    from ai_agent_framework.core.llm import get_llm
    from ai_agent_framework.knowledge import KnowledgeBase
    from ai_agent_framework.rag.retrievers import get_retriever
    from ai_agent_framework.tools import ToolRegistry, CalculatorTool, KnowledgeSearchTool
    from ai_agent_framework.plugins import load_plugins

    settings = settings or get_settings()
    kb = KnowledgeBase(settings)
    retriever = get_retriever(kb.vectorstore, settings.rag.retrieval, corpus=kb.corpus)
    # 让知识库增删文档时自动同步检索器的 BM25 语料
    kb.attach_retriever(retriever)

    tools = ToolRegistry()
    tools.register(CalculatorTool())
    tools.register(KnowledgeSearchTool(retriever))

    # 加载外部插件到工具注册中心
    if settings.plugins.enabled and settings.plugins.path:
        load_plugins(settings.plugins.path, tool_registry=tools)

    agent = Agent(get_llm(settings.llm), retriever, tools, settings)
    return agent, kb


def cmd_ingest(args) -> int:
    settings = reload_settings(args.config)
    kb = _build_kb(settings)
    for p in args.paths:
        result = kb.add_documents(p)
        print(f"[摄入] {result['source']} -> {result['chunks']} 个分块 ({result['status']})")
    return 0


def cmd_ask(args) -> int:
    settings = reload_settings(args.config)
    agent, _ = _build_agent(settings)
    result = agent.run(args.query)
    print("=== 回答 ===")
    print(result.answer)
    if result.tool_calls:
        print("\n=== 工具调用 ===")
        for tc in result.tool_calls:
            print(f"- {tc['tool']}({tc['input']}) => {tc['result'][:120]}")
    if result.source_documents:
        print(f"\n=== 来源 ({len(result.source_documents)}) ===")
        for i, d in enumerate(result.source_documents, 1):
            print(f"[{i}] {d.metadata.get('source', '未知')}")
    return 0


def cmd_list(args) -> int:
    settings = reload_settings(args.config)
    kb = _build_kb(settings)
    sources = kb.list_sources()
    if not sources:
        print("（知识库为空）")
        return 0
    for src, info in sources.items():
        print(f"- {src}: {info}")
    return 0


def cmd_rebuild(args) -> int:
    settings = reload_settings(args.config)
    kb = _build_kb(settings)
    result = kb.rebuild_index()
    print(f"[重建] 完成，共 {result['rebuilt']} 个源，清理失效 {result['removed_stale']} 个")
    return 0


def cmd_serve(args) -> int:
    settings = reload_settings(args.config)
    import uvicorn

    uvicorn.run(
        "ai_agent_framework.api.server:create_app",
        factory=True,
        host=args.host or settings.api.host,
        port=args.port or settings.api.port,
        reload=False,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aiagent",
        description="通用 AI Agent 框架 CLI",
    )
    parser.add_argument("--config", default=None, help="配置文件路径")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="摄入文档到知识库")
    p_ingest.add_argument("paths", nargs="+", help="文件或目录路径")
    p_ingest.set_defaults(func=cmd_ingest)

    p_ask = sub.add_parser("ask", help="向 Agent 提问")
    p_ask.add_argument("query", help="问题")
    p_ask.set_defaults(func=cmd_ask)

    p_list = sub.add_parser("list", help="列出知识库源")
    p_list.set_defaults(func=cmd_list)

    p_rebuild = sub.add_parser("rebuild", help="重建索引")
    p_rebuild.set_defaults(func=cmd_rebuild)

    p_serve = sub.add_parser("serve", help="启动 API 服务")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
