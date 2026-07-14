# 通用 AI Agent 框架（含 RAG）实施计划

> **执行方式：** 内联执行 + subagent 审查循环（/loop 模式）

**目标：** 搭建一个模块化、可扩展的通用 AI Agent 框架，内置完整 RAG 能力，作为未来具体应用方向的基座。

**架构：** 采用"协议抽象 + 插件注册 + 依赖注入"范式。core 模块负责 Agent 主循环与组件编排；rag 模块以 langchain_core 抽象为基础，封装加载/分块/嵌入/检索/生成五段式管线；知识库、工具、配置、交互层各自独立可替换。所有跨模块依赖面向 Protocol 编程，避免硬耦合。

**技术栈：**
- Python 3.11 + langchain_core/langchain_openai/langchain_text_splitters（已装）
- ChromaDB（向量库，待装）
- FastAPI + Uvicorn（API 层，待装）
- pypdf（PDF 解析，待装）、rank_bm25（混合检索，待装）
- Pydantic Settings + YAML（配置）
- pytest（测试）

---

## 文件结构与职责

```
ai_agent_framework/
├── src/ai_agent_framework/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── base.py          # Protocol/ABC 定义：LLM、Retriever、Tool 等协议
│   │   ├── agent.py         # Agent 主循环（query → 检索 → 生成 → 工具）
│   │   └── registry.py      # 插件/工具注册中心
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── loaders.py       # 文档加载器（PDF/TXT/MD/自动识别）
│   │   ├── splitters.py     # 文本分块（递归/字符/token，可配置）
│   │   ├── embeddings.py    # 嵌入模型工厂（OpenAI/本地）
│   │   ├── vectorstore.py   # 向量存储抽象 + Chroma 实现
│   │   ├── retrievers.py    # 检索器（向量/混合 BM25+向量）
│   │   └── generator.py     # 响应生成器（结合检索上下文）
│   ├── knowledge/
│   │   ├── __init__.py
│   │   └── manager.py       # 知识库 CRUD、索引构建
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py          # Tool 基类
│   │   └── builtin.py       # 内置工具（计算器、检索工具等）
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py      # Pydantic Settings + YAML 加载
│   ├── plugins/
│   │   ├── __init__.py
│   │   └── loader.py        # 插件动态加载（entry_points / 目录扫描）
│   └── api/
│       ├── __init__.py
│       ├── cli.py           # CLI 交互
│       └── server.py        # FastAPI 服务
├── tests/
│   ├── conftest.py
│   ├── test_loaders.py
│   ├── test_splitters.py
│   ├── test_vectorstore.py
│   ├── test_retrievers.py
│   ├── test_generator.py
│   ├── test_agent.py
│   ├── test_tools.py
│   └── test_config.py
├── examples/
│   ├── sample_docs/         # 示例文档
│   └── demo_rag.py          # 端到端演示
├── config.yaml              # 默认配置
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 任务分解

### Task 1: 项目骨架与依赖

**Files:** `pyproject.toml`, `requirements.txt`, `src/ai_agent_framework/__init__.py`, `config.yaml`

- 安装缺失依赖：chromadb、fastapi、uvicorn、pypdf、rank_bm25、pydantic-settings
- 创建包目录与 `__init__.py`
- 编写 `config.yaml` 默认配置
- 验证：`python -c "import ai_agent_framework"` 成功

### Task 2: 配置管理模块

**Files:** `src/ai_agent_framework/config/settings.py`

- 用 Pydantic Settings 定义 `Settings`：LLM 配置、Embedding 配置、向量库配置、RAG 参数（chunk_size/overlap/top_k）、API 配置
- 支持从 YAML + 环境变量加载
- 提供 `get_settings()` 单例
- 验证：测试加载 `config.yaml` 并能被环境变量覆盖

### Task 3: 核心协议与注册中心

**Files:** `src/ai_agent_framework/core/base.py`, `core/registry.py`

- `base.py`：定义 `LLMProtocol`、`RetrieverProtocol`、`ToolProtocol`、`DocumentLoaderProtocol` 等协议
- `registry.py`：`ComponentRegistry` 单例，支持 `register`/`get`/`list`，按名称存取组件
- 验证：注册并取回一个模拟组件

### Task 4: 文档加载器

**Files:** `src/ai_agent_framework/rag/loaders.py`, `tests/test_loaders.py`

- `DocumentLoader` 基类 + `PDFLoader`/`TextLoader`/`MarkdownLoader`/`AutoLoader`（按扩展名分发）
- 返回统一的 `Document` 列表（content + metadata）
- 验证：加载 TXT/MD/PDF 样例，检查内容与 metadata

### Task 5: 文本分块

**Files:** `src/ai_agent_framework/rag/splitters.py`, `tests/test_splitters.py`

- 基于 langchain_text_splitters 封装：`RecursiveSplitter`、`CharacterSplitter`、`TokenSplitter`
- 通过 `SplitterConfig` 配置 chunk_size/overlap/separators
- 工厂函数 `get_splitter(config)`
- 验证：分块后 chunk 数与重叠正确

### Task 6: 嵌入与向量存储

**Files:** `src/ai_agent_framework/rag/embeddings.py`, `rag/vectorstore.py`, `tests/test_vectorstore.py`

- `embeddings.py`：`get_embeddings(config)` 工厂，默认 OpenAI embeddings，可扩展本地模型
- `vectorstore.py`：`VectorStoreBase` 抽象 + `ChromaVectorStore` 实现（add/search/delete/persist）
- 验证：写入若干文档，相似度搜索返回正确 top_k

### Task 7: 检索器（向量 + 混合）

**Files:** `src/ai_agent_framework/rag/retrievers.py`, `tests/test_retrievers.py`

- `VectorRetriever`：基于向量库
- `HybridRetriever`：BM25 + 向量加权融合（RRF 或线性加权）
- 统一 `retrieve(query, top_k)` 接口返回 `Document` 列表
- 验证：混合检索结果优于纯向量检索（关键词命中场景）

### Task 8: 响应生成器

**Files:** `src/ai_agent_framework/rag/generator.py`, `tests/test_generator.py`

- `ResponseGenerator`：将检索上下文 + 查询构造 prompt，调用 LLM 生成回答
- 支持自定义 prompt 模板
- 返回 `(answer, source_documents)`
- 验证：mock LLM 时返回包含上下文信息的回答

### Task 9: 知识库管理

**Files:** `src/ai_agent_framework/knowledge/manager.py`

- `KnowledgeBase`：`add_documents(path_or_docs)`、`search(query)`、`list_sources()`、`delete_source(name)`、`rebuild_index()`
- 串联 loader → splitter → embeddings → vectorstore
- 维护 source 元数据
- 验证：添加/检索/删除文档源

### Task 10: 工具调用接口

**Files:** `src/ai_agent_framework/tools/base.py`, `tools/builtin.py`, `tests/test_tools.py`

- `Tool` 基类：`name`、`description`、`run(input)` 抽象方法
- `ToolRegistry`：注册/调用/列表
- 内置工具：`CalculatorTool`、`KnowledgeSearchTool`（封装 retriever）
- 验证：注册并调用计算器与检索工具

### Task 11: Agent 主循环

**Files:** `src/ai_agent_framework/core/agent.py`, `tests/test_agent.py`

- `Agent`：持有 LLM、retriever、tool_registry
- `run(query)` 流程：① 检索知识 → ② 判断是否需要工具 → ③ 调用工具/生成回答 → ④ 返回结果与溯源
- 支持单轮（多轮对话留扩展点）
- 验证：mock 组件下端到端跑通

### Task 12: 插件加载器

**Files:** `src/ai_agent_framework/plugins/loader.py`

- `PluginLoader`：扫描 `plugins/` 目录，动态导入实现 `Tool`/`Retriever` 协议的模块并注册
- 提供 `load_plugins(path)` 接口
- 验证：放一个示例插件能被加载注册

### Task 13: 用户交互接口

**Files:** `src/ai_agent_framework/api/cli.py`, `api/server.py`

- `cli.py`：基于 argparse/typer 的命令行：`ingest <path>`、`ask <query>`、`serve`
- `server.py`：FastAPI 提供 `/ask`、`/ingest`、`/health`、`/sources` 端点
- 验证：CLI 可问可答；API 启动后 curl 通过

### Task 14: 端到端集成测试与示例

**Files:** `examples/demo_rag.py`, `examples/sample_docs/*`, `tests/test_integration.py`

- 提供示例文档（md/txt）
- `demo_rag.py` 演示：加载→分块→入库→检索→生成
- 集成测试验证全链路
- 验证：`python examples/demo_rag.py` 跑通

### Task 15: 文档

**Files:** `README.md`, `docs/API.md`, `docs/EXTENSION.md`

- README：快速开始、架构图、模块说明
- API.md：各模块公开接口
- EXTENSION.md：如何添加新工具/加载器/检索器/插件

---

## 自检（Spec 覆盖）

| 需求 | 覆盖任务 |
|------|----------|
| 模块化架构（6 模块） | Task 2/3/9/10/13/11 |
| 文档加载（PDF/TXT/MD） | Task 4 |
| 可配置分块 | Task 5 |
| 向量存储 + 主流向量库 | Task 6（Chroma，抽象可扩展） |
| 相似性 + 混合检索 | Task 7 |
| 响应生成器 | Task 8 |
| 插件化机制 | Task 12 |
| 清晰 API 接口 | Task 13 |
| 配置文件 + 环境变量 | Task 2 |
| 主流技术栈 | 全程 |
| 基础架构 → RAG → 集成测试 → 文档 | Task 1-3 → 4-8 → 9-14 → 15 |
| 可运行代码 + 测试 + API 文档 + 扩展指南 | 全部 |

无占位符；类型/方法名跨任务一致（如 `retrieve(query, top_k)`、`run(query)`）。
