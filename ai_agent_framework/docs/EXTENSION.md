# 扩展指南

本指南说明如何在 AI Agent Framework 基础上进行定制化扩展，覆盖最常见的扩展场景：添加新工具、新文档加载器、新分块器、新向量库、新检索器、新 LLM、新 API 端点，以及如何基于本框架构建垂直领域的 Agent 应用。

## 目录

- [扩展点总览](#扩展点总览)
- [1. 添加新工具（最常用）](#1-添加新工具最常用)
  - [方式 A：插件目录（推荐，无需改核心代码）](#方式-a插件目录推荐无需改核心代码)
  - [方式 B：代码内注册](#方式-b代码内注册)
- [2. 添加新文档加载器](#2-添加新文档加载器)
- [3. 添加新分块器](#3-添加新分块器)
- [4. 添加新向量库](#4-添加新向量库)
- [5. 添加新检索器](#5-添加新检索器)
- [6. 接入新 LLM Provider](#6-接入新-llm-provider)
- [7. 添加新 API 端点](#7-添加新-api-端点)
- [8. 自定义 Agent 行为](#8-自定义-agent-行为)
- [9. 构建垂直领域 Agent（完整示例）](#9-构建垂直领域-agent完整示例)
- [扩展原则](#扩展原则)

---

## 扩展点总览

| 扩展点 | 是否需改核心代码 | 推荐方式 |
|---|---|---|
| 工具（Tool） | 否 | 插件目录 |
| 文档加载器（Loader） | 否（仅传 `AutoLoader(loaders=...)`） | 自定义 dict |
| 分块器（Splitter） | 是（工厂 mapping） | 子类 + 工厂扩展 |
| 向量库（VectorStore） | 是（工厂 mapping） | 子类 + 工厂扩展 |
| 检索器（Retriever） | 是（工厂 mapping） | 子类 + 工厂扩展 |
| LLM Provider | 是（工厂分支） | `get_llm` 添加分支 |
| API 端点 | 是（`create_app` 内添加） | 装饰器添加路由 |
| Agent 行为 | 否 | 子类化 `Agent` |

所有扩展点都面向 [Protocol](../src/ai_agent_framework/core/base.py) 编程，只要满足对应 Protocol 即可被框架接受。

---

## 1. 添加新工具（最常用）

### 方式 A：插件目录（推荐，无需改核心代码）

在 `plugins/` 目录下新建 `.py` 文件（`_` 前缀的会被跳过）：

```python
# plugins/web_search.py
from ai_agent_framework.tools import Tool

class WebSearchTool(Tool):
    name = "web_search"
    description = "在网络上搜索信息。输入搜索关键词，返回相关结果摘要。"

    def run(self, input: str) -> str:
        # 这里调用你的搜索 API（如 Tavily、SerpAPI）
        # 示例：返回模拟结果
        return f"网络搜索结果：{input} 的相关信息..."

# 方式 1：模块顶层实例（自动扫描注册）
web_search = WebSearchTool()
```

或使用 `register` 钩子做更复杂的注册：

```python
# plugins/multi_tool.py
from ai_agent_framework.tools import Tool, ToolRegistry

class ToolA(Tool):
    name = "tool_a"
    description = "工具 A"
    def run(self, input: str) -> str:
        return f"A: {input}"

class ToolB(Tool):
    name = "tool_b"
    description = "工具 B"
    def run(self, input: str) -> str:
        return f"B: {input}"

def register(tool_registry: ToolRegistry, component_registry):
    """插件加载时调用。"""
    tool_registry.register(ToolA())
    tool_registry.register(ToolB())
    # 也可注册到 component_registry 供全局发现
    component_registry.register("tool", "tool_a", ToolA())
```

在 `config.yaml` 中启用插件：

```yaml
plugins:
  enabled: true
  path: ./plugins
```

启动 CLI 或 API 时，插件会自动加载并注册到 Agent 的工具注册中心。

### 方式 B：代码内注册

```python
from ai_agent_framework.api.cli import _build_agent
from ai_agent_framework.tools import ToolRegistry, CalculatorTool
from ai_agent_framework.config import get_settings

class MyTool(Tool):
    name = "my_tool"
    description = "我的工具"
    def run(self, input: str) -> str:
        return f"处理: {input}"

settings = get_settings()
agent, kb = _build_agent(settings)
agent.tools.register(MyTool())  # 直接注册到 agent 的 ToolRegistry
```

---

## 2. 添加新文档加载器

实现 `DocumentLoaderProtocol`（`load(source) -> list[Document]`），然后通过 `AutoLoader(loaders=...)` 注入：

```python
# my_loaders.py
from pathlib import Path
from langchain_core.documents import Document
from ai_agent_framework.rag.loaders import DocumentLoader

class DocxLoader(DocumentLoader):
    """Word 文档加载器（需 python-docx）。"""
    def load(self, source) -> list[Document]:
        from docx import Document as DocxDocument
        doc = DocxDocument(str(source))
        text = "\n".join(p.text for p in doc.paragraphs)
        return [Document(page_content=text, metadata={"source": str(source), "type": "docx"})]

class CSVLoader(DocumentLoader):
    """CSV 加载器，每行一个 Document。"""
    def load(self, source) -> list[Document]:
        import csv
        docs = []
        with open(source, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                docs.append(Document(
                    page_content=str(row),
                    metadata={"source": str(source), "type": "csv", "row": i},
                ))
        return docs
```

使用：

```python
from ai_agent_framework.rag.loaders import AutoLoader

custom_map = {
    ".txt": TextLoader, ".md": MarkdownLoader, ".pdf": PDFLoader,
    ".docx": DocxLoader, ".csv": CSVLoader,
}
loader = AutoLoader(loaders=custom_map)
docs = loader.load("data/report.docx")
```

要让 `KnowledgeBase` 使用自定义 loader，可以子类化或在构造后替换 `kb._loader`：

```python
kb = KnowledgeBase(settings)
kb._loader = AutoLoader(loaders=custom_map)
```

---

## 3. 添加新分块器

实现 `SplitterProtocol`（`split(documents) -> list[Document]`），并在工厂函数中注册：

```python
# my_splitters.py
from langchain_core.documents import Document
from ai_agent_framework.config.settings import SplitterConfig

class SemanticSplitter:
    """语义分块器（示例，需 embedding 模型支持）。"""
    def __init__(self, config: SplitterConfig, embeddings=None):
        self._config = config
        self._embeddings = embeddings

    def split(self, documents: list[Document]) -> list[Document]:
        # 实现你的语义分块逻辑
        ...
```

修改 `rag/splitters.py` 的 `get_splitter` 工厂：

```python
def get_splitter(config: SplitterConfig | None = None) -> SplitterProtocol:
    ...
    mapping = {
        "recursive": RecursiveSplitter,
        "character": CharacterSplitterAdapter,
        "token": TokenSplitterAdapter,
        "semantic": SemanticSplitter,  # 新增
    }
    cls = mapping.get(config.type)
    if cls is None:
        raise ValueError(f"未知的分块器类型: {config.type}")
    return cls(config)
```

在 `config.yaml` 中切换：

```yaml
rag:
  splitter:
    type: semantic
    chunk_size: 500
```

---

## 4. 添加新向量库

继承 `VectorStoreBase`，实现所有抽象方法，并在工厂中注册：

```python
# my_vectorstore.py
from ai_agent_framework.rag.vectorstore import VectorStoreBase
from langchain_core.documents import Document

class FAISSVectorStore(VectorStoreBase):
    def __init__(self, config, embeddings):
        self._config = config
        self._embeddings = embeddings
        # 初始化 FAISS 索引...

    def add_documents(self, documents: list[Document]) -> list[str]:
        ...

    def similarity_search(self, query: str, top_k: int = 4) -> list[Document]:
        ...

    def similarity_search_with_scores(self, query, top_k=4):
        ...

    def delete_by_source(self, source: str) -> None:
        ...

    def get_all_documents(self) -> list[Document]:
        ...

    def persist(self) -> None:
        # 保存到磁盘
        ...
```

修改 `rag/vectorstore.py` 的 `get_vectorstore` 工厂：

```python
def get_vectorstore(config=None, embeddings=None) -> VectorStoreBase:
    ...
    if config.type == "chroma":
        return ChromaVectorStore(config, embeddings)
    if config.type == "faiss":
        return FAISSVectorStore(config, embeddings)
    raise ValueError(f"未知的向量库类型: {config.type}")
```

配置切换：

```yaml
vectorstore:
  type: faiss
  path: ./data/faiss
```

**重要**：`get_all_documents()` 必须实现，否则 `KnowledgeBase` 无法在重启后重建 BM25 语料。

---

## 5. 添加新检索器

实现 `RetrieverProtocol`（`retrieve(query, top_k=None) -> list[Document]`），并在工厂中注册：

```python
# my_retrievers.py
from ai_agent_framework.core.base import RetrieverProtocol
from langchain_core.documents import Document

class MultiQueryRetriever(RetrieverProtocol):
    """多查询检索器：让 LLM 改写查询多次检索后融合。"""
    def __init__(self, vectorstore, llm, config=None):
        self._store = vectorstore
        self._llm = llm
        self._config = config

    def retrieve(self, query: str, top_k: int | None = None) -> list[Document]:
        # 1. 让 LLM 生成 3 个改写查询
        # 2. 分别检索
        # 3. 去重融合
        ...

    def update_corpus(self, documents):
        """可选：若想让 KnowledgeBase 自动同步，实现此方法。"""
        pass
```

修改 `rag/retrievers.py` 的 `get_retriever` 工厂：

```python
def get_retriever(vectorstore, config=None, corpus=None) -> RetrieverProtocol:
    ...
    if config.strategy == "vector":
        return VectorRetriever(vectorstore, config)
    if config.strategy == "hybrid":
        return HybridRetriever(vectorstore, config, corpus=corpus)
    if config.strategy == "multi_query":
        # 需要额外注入 llm
        from ai_agent_framework.core.llm import get_llm
        return MultiQueryRetriever(vectorstore, get_llm(), config)
    raise ValueError(f"未知的检索策略: {config.strategy}")
```

**注意**：若检索器需要 BM25 语料同步，实现 `update_corpus(documents)` 方法，`KnowledgeBase.attach_retriever()` 会自动调用。

---

## 6. 接入新 LLM Provider

修改 `core/llm.py` 的 `get_llm` 工厂：

```python
def get_llm(config: LLMConfig | None = None) -> Any:
    ...
    if config.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=config.model,
            api_key=config.api_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    if config.provider == "zhipu":
        # 智谱 GLM（也可走 openai 兼容接口）
        from langchain_community.chat_models import ChatZhipuAI
        return ChatZhipuAI(
            model=config.model,
            api_key=config.api_key,
            temperature=config.temperature,
        )

    raise ValueError(f"未知的 LLM provider: {config.provider}")
```

配置切换：

```yaml
llm:
  provider: anthropic
  model: claude-3-5-sonnet-20241022
  api_key: ${ANTHROPIC_API_KEY}
```

---

## 7. 添加新 API 端点

在 `api/server.py` 的 `create_app` 内添加路由：

```python
def create_app() -> FastAPI:
    app = FastAPI(title="AI Agent Framework API", version="0.1.0")

    # ... 既有端点 ...

    @app.delete("/sources/{source:path}")
    def delete_source(
        source: str,
        x_api_key: str | None = Header(default=None),
    ) -> dict:
        _check_api_key(x_api_key)
        _, kb = _get_agent_bundle()
        return kb.delete_source(source)

    @app.post("/ingest/text")
    def ingest_text(
        body: dict,
        x_api_key: str | None = Header(default=None),
    ) -> dict:
        _check_api_key(x_api_key)
        _, kb = _get_agent_bundle()
        return kb.add_text(body.get("text", ""), source=body.get("source", "inline"))

    return app
```

所有自定义端点都应调用 `_check_api_key` 进行鉴权。

---

## 8. 自定义 Agent 行为

子类化 `Agent`，覆盖 `run` 或添加辅助方法：

```python
from ai_agent_framework.core.agent import Agent, AgentResult
from langchain_core.documents import Document

class MultiTurnAgent(Agent):
    """支持多轮对话的 Agent（维护历史）。"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._history: list[dict] = []

    def run(self, query: str) -> AgentResult:
        # 把历史拼到 query 中
        history_str = "\n".join(
            f"用户: {h['user']}\n助手: {h['assistant']}"
            for h in self._history[-5:]  # 保留最近 5 轮
        )
        full_query = f"对话历史:\n{history_str}\n\n当前问题: {query}" if history_str else query
        result = super().run(full_query)
        self._history.append({"user": query, "assistant": result.answer})
        return result

    def reset(self):
        self._history.clear()
```

使用：

```python
agent = MultiTurnAgent(llm, retriever, tools, settings)
agent.run("什么是 RAG？")
agent.run("它有哪些步骤？")  # 自动带上历史
```

---

## 9. 构建垂直领域 Agent（完整示例）

以"客服 Agent"为例，展示如何基于本框架构建一个垂直应用。

### 步骤 1：定义领域工具

```python
# plugins/customer_service.py
from ai_agent_framework.tools import Tool, ToolRegistry

class OrderQueryTool(Tool):
    name = "order_query"
    description = "查询订单状态。输入订单号，返回订单信息和物流状态。"
    def run(self, input: str) -> str:
        # 调用你的订单系统 API
        return f"订单 {input}：已发货，预计 3 天内送达"

class RefundTool(Tool):
    name = "refund"
    description = "发起退款申请。输入订单号和原因（用空格分隔）。"
    def run(self, input: str) -> str:
        parts = input.split(" ", 1)
        order_id, reason = parts[0], parts[1] if len(parts) > 1 else "未提供"
        # 调用退款 API
        return f"已为订单 {order_id} 创建退款申请，原因: {reason}"

class FAQTool(Tool):
    name = "faq_search"
    description = "在 FAQ 知识库中检索常见问题答案。"
    def __init__(self, retriever):
        self._retriever = retriever

    def run(self, input: str) -> str:
        docs = self._retriever.retrieve(input, top_k=2)
        if not docs:
            return "未找到相关 FAQ"
        return "\n".join(f"[{i+1}] {d.page_content}" for i, d in enumerate(docs))

def register(tool_registry: ToolRegistry, component_registry):
    tool_registry.register(OrderQueryTool())
    tool_registry.register(RefundTool())
    # FAQTool 需要 retriever，通过 component_registry 获取
    retriever = component_registry.get("retriever", "default")
    tool_registry.register(FAQTool(retriever))
```

### 步骤 2：准备领域知识库

```bash
# 摄入 FAQ 文档
aiagent ingest data/faqs/*.md
aiagent ingest data/policies/*.pdf
```

### 步骤 3：自定义系统提示词

```python
# customer_service_agent.py
from ai_agent_framework.core.agent import Agent, REACT_SYSTEM_PROMPT
from ai_agent_framework.api.cli import _build_agent
from ai_agent_framework.config import get_settings

CUSTOMER_SERVICE_PROMPT = """你是一个专业的客服 Agent，负责处理用户的订单查询、退款申请和常见问题。

行为准则：
1. 始终保持礼貌和专业。
2. 涉及退款时，先确认订单号和原因。
3. 优先使用 FAQ 知识库回答常见问题。
4. 无法回答时，明确告知用户将转接人工客服。

""" + REACT_SYSTEM_PROMPT

class CustomerServiceAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 替换系统提示词
        from langchain_core.prompts import ChatPromptTemplate
        self._prompt = ChatPromptTemplate.from_messages(
            [("system", CUSTOMER_SERVICE_PROMPT), ("human", "{question}")]
        )

# 启动
settings = get_settings()
agent, kb = _build_agent(settings)
# 替换为客服 Agent（保留所有工具和检索器）
cs_agent = CustomerServiceAgent(agent._llm, agent._retriever, agent.tools, settings)
result = cs_agent.run("我的订单 A12345 到哪了？")
print(result.answer)
```

### 步骤 4：配置生产环境

`config.yaml`：

```yaml
llm:
  provider: openai
  model: deepseek-chat
  api_key: ${DEEPSEEK_API_KEY}
  base_url: https://api.deepseek.com/v1
  temperature: 0.1  # 客服场景需要确定性

agent:
  answer_when_no_context: false  # 无上下文时不胡编
  max_tool_calls: 5

knowledge:
  allowed_roots:
    - ./data/faqs
    - ./data/policies

api:
  api_key: ${SERVICE_API_KEY}  # 生产必设

plugins:
  enabled: true
  path: ./plugins
```

### 步骤 5：部署

```bash
aiagent serve --host 0.0.0.0 --port 8000
```

---

## 扩展原则

1. **优先用插件，不改核心**：工具扩展永远走插件目录，无需修改框架代码。
2. **面向 Protocol 编程**：自定义组件实现对应 Protocol 即可被框架接受，无需继承具体类。
3. **工厂函数是唯一需要改核心的地方**：添加新 Loader/Splitter/VectorStore/Retriever/LLM 时，需在对应工厂函数中添加分支。这是已知的扩展性限制，未来可通过让工厂优先查询 `ComponentRegistry` 来改进。
4. **配置驱动**：能在 `config.yaml` 切换的就不要硬编码。新增配置项时同步更新 `Settings` 模型。
5. **保持线程安全**：若组件有可变状态，用 `threading.RLock` 保护读写。
6. **写测试**：每个新组件至少一个单元测试 + 一个集成测试。框架内置 `_FakeLLM` 与 `_FakeEmbeddings` 让测试无需外部 API。

## 已知扩展性限制

- 工厂函数（`get_splitter`/`get_vectorstore`/`get_retriever`/`get_llm`）的 mapping 是硬编码的，添加新类型必须修改源码。未来可通过让工厂优先从 `ComponentRegistry` 查找再回退默认 mapping 来实现真正的"注册即用"。
- 插件目前只能注册 `Tool`，无法注册其他类型组件。可通过 `register(tool_registry, component_registry)` 钩子手动注册到 `ComponentRegistry`，但工厂函数不会消费它。
- Agent 主循环（ReAct JSON 解析）是内置的，无法通过配置切换为 Function Calling 或 Plan-and-Execute 等其他范式。可通过子类化 `Agent.run` 实现。
