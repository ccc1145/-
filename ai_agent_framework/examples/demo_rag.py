"""端到端 RAG 演示：加载 → 分块 → 入库 → 检索 → 生成。

使用 FakeLLM + FakeEmbeddings，无需任何 API Key 即可运行，
验证框架全链路可用性。如需真实 LLM，修改 config.yaml 中的 provider。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 确保可导入开发中的包
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_agent_framework.config.settings import (
    Settings,
    LLMConfig,
    EmbeddingConfig,
    VectorStoreConfig,
    RAGConfig,
    SplitterConfig,
    RetrievalConfig,
    AgentConfig,
    APIConfig,
    KnowledgeConfig,
    PluginsConfig,
)
from ai_agent_framework.knowledge import KnowledgeBase
from ai_agent_framework.rag.retrievers import get_retriever
from ai_agent_framework.rag.generator import ResponseGenerator
from ai_agent_framework.core.llm import get_llm
from ai_agent_framework.tools import ToolRegistry, CalculatorTool, KnowledgeSearchTool
from ai_agent_framework.core import Agent


def _offline_settings() -> Settings:
    """构造离线运行配置（fake provider）。"""
    return Settings(
        llm=LLMConfig(provider="fake", model="fake"),
        embedding=EmbeddingConfig(provider="fake", model="fake", dimensions=64),
        vectorstore=VectorStoreConfig(type="chroma", path="./data/demo_store", collection="demo"),
        rag=RAGConfig(
            splitter=SplitterConfig(type="recursive", chunk_size=200, chunk_overlap=20),
            retrieval=RetrievalConfig(strategy="hybrid", top_k=3, candidate_k=10),
        ),
        knowledge=KnowledgeConfig(allowed_roots=[]),
        agent=AgentConfig(max_tool_calls=2),
        api=APIConfig(),
        plugins=PluginsConfig(enabled=False, path=""),
    )


def main() -> int:
    settings = _offline_settings()
    kb = KnowledgeBase(settings)

    # 摄入示例文档
    docs_dir = ROOT / "examples" / "sample_docs"
    print(f"[1/4] 摄入文档: {docs_dir}")
    for f in sorted(docs_dir.iterdir()):
        r = kb.add_documents(f)
        print(f"   - {r['source']}: {r['chunks']} 个分块")

    # 构建检索器与 Agent
    print("\n[2/4] 构建混合检索器")
    retriever = get_retriever(kb.vectorstore, settings.rag.retrieval, corpus=kb.corpus)

    tools = ToolRegistry()
    tools.register(CalculatorTool())
    tools.register(KnowledgeSearchTool(retriever))

    agent = Agent(get_llm(settings.llm), retriever, tools, settings)

    # 检索单独演示
    print("\n[3/4] 检索演示")
    query = "RAG 包含哪些组件？"
    docs = retriever.retrieve(query)
    for i, d in enumerate(docs, 1):
        print(f"   [{i}] ({d.metadata.get('source', '?')}) {d.page_content[:60]}...")

    # Agent 问答
    print(f"\n[4/4] Agent 问答: {query}")
    result = agent.run(query)
    print("--- 回答 ---")
    print(result.answer)
    print(f"--- 来源数: {len(result.source_documents)} | 工具调用: {len(result.tool_calls)} ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
