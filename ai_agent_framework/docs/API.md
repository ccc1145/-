# API 参考

本文档列出 AI Agent Framework 的核心 Python API 与 HTTP API。

## 目录

- [Python API](#python-api)
  - [config](#config)
  - [core](#core)
  - [rag](#rag)
  - [knowledge](#knowledge)
  - [tools](#tools)
  - [plugins](#plugins)
  - [api](#api)
- [HTTP API](#http-api)
- [CLI](#cli)

---

## Python API

### config

#### `Settings`

```python
from ai_agent_framework.config import Settings, get_settings, reload_settings
```

Pydantic Settings 模型，包含 `llm`、`embedding`、`vectorstore`、`rag`、`knowledge`、`agent`、`api`、`plugins` 八个子配置。

| 方法 | 说明 |
|---|---|
| `get_settings(config_file: str \| None = None) -> Settings` | 全局单例，惰性加载。`config_file` 仅用于测试。 |
| `reload_settings(config_file: str \| None = None) -> Settings` | 强制重新加载，联动清除 `lru_cache`（包括 API 层 agent bundle 缓存）。 |

#### 子配置结构

```python
LLMConfig(provider, model, api_key, base_url, temperature, max_tokens)
EmbeddingConfig(provider, model, api_key, base_url, dimensions)
VectorStoreConfig(type, path, collection)
SplitterConfig(type, chunk_size, chunk_overlap, separators)
RetrievalConfig(strategy, top_k, vector_weight, candidate_k)
RAGConfig(splitter, retrieval)
AgentConfig(answer_when_no_context, max_tool_calls)
APIConfig(host, port, api_key)
KnowledgeConfig(allowed_roots)
PluginsConfig(enabled, path)
```

#### 配置优先级

```
代码入参 > 环境变量 (AAF_ 前缀, __ 嵌套) > .env > YAML > 默认值
```

YAML 中可用 `${VAR}` 引用环境变量。

---

### core

#### Protocols (`core.base`)

7 个 `@runtime_checkable` Protocol，所有可替换组件面向 Protocol 编程：

```python
DocumentLoaderProtocol.load(source: str) -> list[Document]
SplitterProtocol.split(documents: list[Document]) -> list[Document]
EmbeddingsProtocol.embed_documents(texts) / embed_query(text)
VectorStoreProtocol.add_documents / similarity_search / delete_by_source
RetrieverProtocol.retrieve(query, top_k=None) -> list[Document]
LLMProtocol.invoke(input) -> Any
ToolProtocol.name / description / run(input) -> str
```

#### `ComponentRegistry` (`core.registry`)

```python
from ai_agent_framework.core.registry import ComponentRegistry, get_registry
```

线程安全的组件注册中心单例。组件按 `(category, name)` 注册。

| 方法 | 说明 |
|---|---|
| `register(category, name, component)` | 注册组件，同名覆盖 |
| `get(category, name) -> Any` | 获取组件，不存在抛 `KeyError` |
| `list(category) -> list[str]` | 列出某类下所有组件名 |
| `categories() -> list[str]` | 列出所有类别 |
| `unregister(category, name)` | 注销组件 |
| `clear()` | 清空所有（测试用） |

#### `Agent` (`core.agent`)

```python
from ai_agent_framework.core.agent import Agent, AgentResult
```

ReAct 风格的 Agent 主循环。

```python
agent = Agent(llm, retriever, tool_registry, settings)
result: AgentResult = agent.run("你的问题")
```

`AgentResult` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `answer` | `str` | 最终回答 |
| `source_documents` | `list[Document]` | 检索到的上下文 |
| `tool_calls` | `list[dict]` | 工具调用历史，每项含 `tool/input/result` |
| `raw` | `str` | LLM 最后一轮原始输出 |

**行为说明**：

- `max_tool_calls` 控制最大工具调用次数；达到上限时追加 `FINALIZE_HINT` 强制收尾。
- 最后一轮若 LLM 仍输出工具 JSON，剥离 JSON 后保留剩余正文作为兜底；若剥离后为空，按"无工具"或"达上限"分别给出对应文案。
- `agent.answer_when_no_context=False` 且检索为空时，直接返回兜底答案，不调用 LLM。
- LLM 调用异常被捕获，返回 `AgentResult(answer="LLM 调用失败：...")`，不抛出。

#### `get_llm` (`core.llm`)

```python
from ai_agent_framework.core.llm import get_llm
```

| provider | 返回 |
|---|---|
| `"openai"` | `langchain_openai.ChatOpenAI`（兼容 DeepSeek/智谱/OpenAI） |
| `"fake"` | `_FakeLLM`（基于关键词的离线测试 LLM） |

---

### rag

#### Loaders (`rag.loaders`)

```python
from ai_agent_framework.rag import TextLoader, MarkdownLoader, PDFLoader, AutoLoader, get_loader
```

| 类 | 支持扩展名 | 说明 |
|---|---|---|
| `TextLoader` | `.txt` | UTF-8 纯文本 |
| `MarkdownLoader` | `.md` `.markdown` | 保留原文 |
| `PDFLoader` | `.pdf` | 基于 pypdf，按页切分 |
| `AutoLoader` | 全部 | 按扩展名自动分发；支持目录递归 |

`AutoLoader(loaders: dict | None)` 可传入自定义 `{ext: LoaderClass}` 映射覆盖默认。

#### Splitters (`rag.splitters`)

```python
from ai_agent_framework.rag import RecursiveSplitter, CharacterSplitterAdapter, TokenSplitterAdapter, get_splitter
```

| type | 类 | 底层 |
|---|---|---|
| `"recursive"`（推荐） | `RecursiveSplitter` | `RecursiveCharacterTextSplitter` |
| `"character"` | `CharacterSplitterAdapter` | `CharacterTextSplitter` |
| `"token"` | `TokenSplitterAdapter` | `TokenTextSplitter` |

#### Embeddings (`rag.embeddings`)

```python
from ai_agent_framework.rag import get_embeddings
```

| provider | 返回 |
|---|---|
| `"openai"` | `langchain_openai.OpenAIEmbeddings`（兼容智谱 embedding-3） |
| `"fake"` | `_FakeEmbeddings`（基于 `hashlib.md5` 的确定性向量，跨进程可复现） |

#### VectorStore (`rag.vectorstore`)

```python
from ai_agent_framework.rag import VectorStoreBase, ChromaVectorStore, get_vectorstore
```

`VectorStoreBase` 抽象方法：

| 方法 | 说明 |
|---|---|
| `add_documents(documents) -> list[str]` | 写入并返回 ID 列表 |
| `similarity_search(query, top_k=4) -> list[Document]` | 相似度搜索 |
| `similarity_search_with_scores(query, top_k=4)` | 带分数搜索 |
| `delete_by_source(source)` | 按 source 元数据删除 |
| `get_all_documents() -> list[Document]` | 拉取全量（用于重建 BM25 语料） |
| `persist()` | 持久化（Chroma 0.4+ 自动持久化） |

`ChromaVectorStore` 是默认实现，集合名通过 `_sanitize_collection_name` 规范化（3-512 字符）。

#### Retrievers (`rag.retrievers`)

```python
from ai_agent_framework.rag import VectorRetriever, HybridRetriever, get_retriever
```

| strategy | 类 | 行为 |
|---|---|---|
| `"vector"` | `VectorRetriever` | 纯向量相似度 |
| `"hybrid"`（推荐） | `HybridRetriever` | BM25 + 向量，加权 RRF 融合 |

`HybridRetriever` 关键方法：

| 方法 | 说明 |
|---|---|
| `update_corpus(documents)` | 重建 BM25 索引，线程安全 |
| `retrieve(query, top_k=None)` | 加权 RRF：`w_vec * Σ 1/(k+rank_vec) + w_bm25 * Σ 1/(k+rank_bm25)` |

权重：`w_vec = vector_weight`，`w_bm25 = 1 - vector_weight`，`rrf_k = 60`（可构造时传入）。

中文分词可选 `jieba`（未安装时回退到正则按字符切分）。

#### Generator (`rag.generator`)

```python
from ai_agent_framework.rag import ResponseGenerator, GenerationResult
```

```python
gen = ResponseGenerator(llm, system_prompt=..., user_template=...)
result: GenerationResult = gen.generate("问题", documents)
```

`GenerationResult` 含 `answer: str` 与 `source_documents: list[Document]`。

---

### knowledge

#### `KnowledgeBase` (`knowledge.manager`)

```python
from ai_agent_framework.knowledge import KnowledgeBase
```

```python
kb = KnowledgeBase(settings)               # 启动时从向量库重建 corpus
kb.attach_retriever(retriever)             # 增删文档后自动同步 BM25
```

| 方法 | 说明 |
|---|---|
| `add_documents(source) -> dict` | 加载→分块→入库；幂等：先加载新数据成功后再删旧 |
| `add_text(text, source="inline") -> dict` | 直接摄入文本 |
| `search(query, top_k=None) -> list[Document]` | 纯向量搜索 |
| `list_sources() -> dict` | 列出所有源及其统计 |
| `delete_source(source) -> dict` | 删除源及其所有 chunk |
| `rebuild_index() -> dict` | 清空并按 meta 重新摄入；清理失效源 |

返回值示例：`{"source": "...", "chunks": 12, "status": "ok"}`

**并发安全**：所有写操作通过 `threading.RLock` 串行化，API 并发摄入安全。

**跨进程持久化**：`__init__` 从 `vectorstore.get_all_documents()` 重建内存 corpus，BM25 索引随之重建。

---

### tools

#### `Tool` 与 `ToolRegistry` (`tools.base`)

```python
from ai_agent_framework.tools import Tool, ToolRegistry
```

```python
class MyTool(Tool):
    name = "my_tool"
    description = "描述"
    def run(self, input: str) -> str:
        return "结果"

reg = ToolRegistry()
reg.register(MyTool())
reg.call("my_tool", "输入")  # -> "结果"
```

`ToolRegistry` 线程安全（`RLock` 保护所有读写）。

#### 内置工具 (`tools.builtin`)

| 工具 | 说明 |
|---|---|
| `CalculatorTool` | AST 安全求值，支持 `+ - * / ** % // ()`，禁止函数调用 |
| `KnowledgeSearchTool(retriever, top_k=4)` | 封装检索器，供 Agent 主动查知识库 |

---

### plugins

#### `load_plugins` (`plugins.loader`)

```python
from ai_agent_framework.plugins import load_plugins
```

```python
load_plugins(path, tool_registry=reg, component_registry=get_registry())
```

扫描目录下所有 `.py` 文件（跳过 `_` 前缀），按以下顺序加载：

1. **`register(tool_registry, component_registry)` 钩子**：若模块定义了 `register` 函数，优先调用，由插件自主注册。
2. **自动扫描 Tool 实例**：扫描模块顶层 `Tool` 子类实例，同时注册到 `tool_registry` 与 `component_registry`。

加载失败时记录 `logger.warning` 而非静默吞掉。

插件示例：

```python
# plugins/my_plugin.py
from ai_agent_framework.tools import CalculatorTool

def register(tool_registry, component_registry):
    tool_registry.register(CalculatorTool())
    component_registry.register("tool", "calc", CalculatorTool())
```

或：

```python
# plugins/auto_tool.py
from ai_agent_framework.tools import Tool

class HelloTool(Tool):
    name = "hello"
    description = "打招呼"
    def run(self, input: str) -> str:
        return f"Hello, {input}!"

# 模块顶层实例会被自动扫描注册
hello = HelloTool()
```

---

### api

#### CLI (`api.cli`)

```python
from ai_agent_framework.api.cli import main
```

通过 `aiagent` 命令调用：

```
aiagent --config CONFIG ingest PATH [PATH ...]
aiagent --config CONFIG ask QUERY
aiagent --config CONFIG list
aiagent --config CONFIG rebuild
aiagent --config CONFIG serve [--host HOST] [--port PORT]
```

#### FastAPI (`api.server`)

```python
from ai_agent_framework.api.server import app, create_app
```

`app = create_app()` 已在模块顶层实例化，可直接 `uvicorn ai_agent_framework.api.server:app` 启动。

---

## HTTP API

所有写接口在 `api.api_key` 非空时需要 `X-API-Key` 头。

### `GET /health`

健康检查。

**响应**：`{"status": "ok"}`

### `POST /ask`

向 Agent 提问。

**请求体**：

```json
{"query": "什么是 RAG？", "top_k": null}
```

**响应**：

```json
{
  "answer": "...",
  "sources": [{"source": "a.md", "snippet": "..."}],
  "tool_calls": [{"tool": "calculator", "input": "2+2", "result": "4"}]
}
```

### `POST /ingest`

摄入文档到知识库。

**请求体**：

```json
{"path": "examples/sample_docs/usage.txt"}
```

**路径校验**：

- 拒绝绝对路径与 `..` 穿越（除非白名单显式允许）
- 若 `knowledge.allowed_roots` 非空，路径必须在其下
- 路径不存在返回 404

**响应**：

```json
{"source": "...", "chunks": 12, "status": "ok"}
```

### `GET /sources`

列出所有已摄入源。

**响应**：

```json
{
  "examples/sample_docs/usage.txt": {"chunks": 5, "type": ".txt"},
  "examples/sample_docs/rag_intro.md": {"chunks": 3, "type": ".md"}
}
```

---

## CLI

```
aiagent [--config CONFIG] <command> [args]
```

| 命令 | 说明 |
|---|---|
| `ingest PATH...` | 摄入文件或目录 |
| `ask QUERY` | 向 Agent 提问 |
| `list` | 列出知识库源 |
| `rebuild` | 重建索引（清理失效源） |
| `serve [--host H] [--port P]` | 启动 API 服务 |

`--config` 可指定 YAML 配置文件路径，覆盖默认 `config.yaml` 与 `AAF_CONFIG_FILE` 环境变量。
