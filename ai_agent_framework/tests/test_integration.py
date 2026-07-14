"""端到端集成测试：全链路可用性。"""
from langchain_core.documents import Document

from ai_agent_framework.knowledge import KnowledgeBase
from ai_agent_framework.rag.retrievers import get_retriever
from ai_agent_framework.core import Agent
from ai_agent_framework.core.llm import get_llm
from ai_agent_framework.tools import ToolRegistry, CalculatorTool, KnowledgeSearchTool


def test_end_to_end_pipeline(offline_settings, sample_docs_dir):
    # 1. 知识库摄入
    kb = KnowledgeBase(offline_settings)
    for f in sorted(sample_docs_dir.iterdir()):
        kb.add_documents(f)
    assert len(kb.list_sources()) >= 2

    # 2. 检索器
    retriever = get_retriever(
        kb.vectorstore, offline_settings.rag.retrieval, corpus=kb.corpus
    )
    docs = retriever.retrieve("RAG 包含哪些步骤")
    assert len(docs) >= 1

    # 3. Agent 问答
    tools = ToolRegistry()
    tools.register(CalculatorTool())
    tools.register(KnowledgeSearchTool(retriever))
    agent = Agent(get_llm(offline_settings.llm), retriever, tools, offline_settings)
    result = agent.run("什么是 RAG？")
    assert result.answer
    assert isinstance(result.source_documents, list)


def test_autoloader_to_agent_chain(offline_settings, tmp_path):
    """模拟一个完整摄入-问答链路。"""
    f = tmp_path / "note.txt"
    f.write_text("框架支持插件化扩展，可添加新工具。", encoding="utf-8")
    kb = KnowledgeBase(offline_settings)
    kb.add_documents(f)
    retriever = get_retriever(kb.vectorstore, offline_settings.rag.retrieval, corpus=kb.corpus)
    agent = Agent(get_llm(offline_settings.llm), retriever, ToolRegistry(), offline_settings)
    r = agent.run("框架能扩展吗")
    assert r.answer
