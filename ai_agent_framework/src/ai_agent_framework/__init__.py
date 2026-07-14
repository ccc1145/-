"""通用 AI Agent 框架：模块化、可扩展，内置完整 RAG 能力。

快速开始:
    from ai_agent_framework.config import get_settings
    from ai_agent_framework.knowledge import KnowledgeBase
    from ai_agent_framework.rag import get_retriever
    from ai_agent_framework.core import Agent
    from ai_agent_framework.core.llm import get_llm

    settings = get_settings()
    kb = KnowledgeBase(settings)
    kb.add_documents("docs/")
    retriever = get_retriever(kb.vectorstore, settings.rag.retrieval, corpus=kb.corpus)
    agent = Agent(get_llm(settings.llm), retriever)
    print(agent.run("你的问题").answer)
"""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ai-agent-framework")
except PackageNotFoundError:  # 开发模式未安装
    __version__ = "0.1.0"

__all__ = ["__version__"]
