# AI Agent Framework

一个通用、可扩展的 AI Agent 框架，内置完整的 RAG（检索增强生成）能力。设计目标是作为未来各类 Agent 应用的基础底座，支持通过插件、配置与 Protocol 抽象进行定制化开发。

## 特性

- **模块化架构**：核心控制、RAG、知识库、工具、配置、用户交互六大模块，职责清晰、单向依赖。
- **完整 RAG 管线**：加载 → 分块 → 嵌入 → 入库 → 检索 → 生成，每一步均可替换。
- **混合检索**：向量相似度 + BM25 关键词检索，加权 RRF 融合，效果优于单一策略。
- **Protocol 抽象**：7 类核心组件面向 `typing.Protocol` 编程，运行时 `isinstance` 可校验。
- **插件机制**：扫描目录自动加载 Tool，支持 `register()` 钩子做更复杂的注册。
- **配置分层**：环境变量 > .env > YAML > 默认值，YAML 内支持 `${VAR}` 引用环境变量。
- **双交互入口**：CLI（`aiagent` 命令）+ FastAPI（`/ask`、`/ingest`、`/sources`、`/health`）。
- **安全加固**：API Key 鉴权 + 路径白名单防穿越 + 常量时间比较防时序攻击。
- **并发安全**：`KnowledgeBase`、`ToolRegistry`、`ComponentRegistry`、`HybridRetriever` 均用 `RLock` 保护。
- **离线可测**：内置 `_FakeLLM` 与 `_FakeEmbeddings`，测试无需任何外部 API。

## 技术栈

| 层 | 选型 |
|---|---|
| 语言 | Python 3.10+（推荐 3.11） |
| LLM 抽象 | langchain-core / langchain-openai |
| 文本分块 | langchain-text-splitters |
| 向量数据库 | ChromaDB |
| 关键词检索 | rank-bm25 |
| 中文分词（可选） | jieba |
| API 服务 | FastAPI + Uvicorn |
| 配置管理 | Pydantic v2 + pydantic-settings + YAML |
| 文档解析 | pypdf（PDF）+ 内置 Text/Markdown loader |
| 测试 | pytest |

## 目录结构

```
ai_agent_framework/
├── src/ai_agent_framework/
│   ├── core/                # 核心层：Protocol、注册表、Agent 主循环、LLM 工厂
│   │   ├── base.py          # 7 个 runtime_checkable Protocol
│   │   ├── registry.py      # ComponentRegistry 线程安全单例
│   │   ├── agent.py         # ReAct 风格 Agent 主循环
│   │   └── llm.py           # get_llm 工厂 + _FakeLLM（离线测试用）
│   ├── rag/                 # RAG 五段式管线
│   │   ├── loaders.py       # Text/Markdown/PDF/AutoLoader
│   │   ├── splitters.py     # Recursive/Character/Token 三种分块器
│   │   ├── embeddings.py    # OpenAI 兼容 + _FakeEmbeddings（确定性 hash）
│   │   ├── vectorstore.py   # ChromaVectorStore + VectorStoreBase
│   │   ├── retrievers.py    # VectorRetriever + HybridRetriever（加权 RRF）
│   │   └── generator.py     # ResponseGenerator
│   ├── knowledge/           # 知识库门面
│   │   └── manager.py       # 摄入/检索/源管理，跨进程语料重建
│   ├── tools/               # 工具调用
│   │   ├── base.py          # Tool ABC + ToolRegistry（线程安全）
│   │   └── builtin.py       # CalculatorTool（AST 安全求值）+ KnowledgeSearchTool
│   ├── plugins/             # 插件加载
│   │   └── loader.py        # 目录扫描 + register() 钩子
│   ├── api/                 # 用户交互层
│   │   ├── cli.py           # argparse CLI（ingest/ask/list/rebuild/serve）
│   │   └── server.py        # FastAPI 服务
│   └── config/              # 配置层
│       └── settings.py      # Pydantic Settings + YAML 源 + reload
├── tests/                   # 99 个 pytest 用例（单元 + 集成 + API 端到端 + 并发 + 边界）
├── examples/
│   ├── demo_rag.py          # 端到端离线演示
│   └── sample_docs/         # 示例文档
├── docs/
│   ├── API.md               # API 参考
│   ├── EXTENSION.md         # 扩展指南
│   └── plans/               # 实施计划归档
├── config.yaml              # 默认配置
├── pyproject.toml
└── requirements.txt
```

## 快速开始

### 1. 安装

```bash
cd ai_agent_framework
pip install -e .[dev]
```

### 2. 配置

复制 `config.yaml` 并按需修改。最关键的几项：

```yaml
llm:
  provider: openai
  model: deepseek-chat
  api_key: ${DEEPSEEK_API_KEY}   # 从环境变量读取
  base_url: https://api.deepseek.com/v1

embedding:
  provider: openai
  model: embedding-3
  api_key: ${ZHIPUAI_API_KEY}
  base_url: https://open.bigmodel.cn/api/paas/v4
  dimensions: 1024
```

或在 `.env` 中设置：

```bash
DEEPSEEK_API_KEY=sk-xxx
ZHIPUAI_API_KEY=xxx
```

### 3. 摄入文档

```bash
aiagent ingest examples/sample_docs/rag_intro.md
aiagent ingest examples/sample_docs/usage.txt
aiagent list
```

### 4. 提问

```bash
aiagent ask "什么是 RAG？"
```

### 5. 启动 API 服务

```bash
aiagent serve --host 0.0.0.0 --port 8000
```

调用示例：

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是 RAG？"}'

curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"path": "examples/sample_docs/usage.txt"}'

curl http://localhost:8000/sources
```

若 `config.yaml` 中 `api.api_key` 非空，所有请求需携带 `X-API-Key` 头。

## 离线测试

框架内置 `_FakeLLM` 与 `_FakeEmbeddings`，测试无需任何外部 API：

```bash
pytest tests/ -q
```

预期输出：`99 passed, 4 warnings`（仅 DeprecationWarning）。

## 配置优先级

从高到低：

1. **代码显式入参**（如 `Settings(llm=...)`）
2. **环境变量**：前缀 `AAF_`，嵌套用 `__`，如 `AAF_LLM__MODEL=xxx`
3. **`.env` 文件**：通过 `python-dotenv` 加载
4. **YAML 配置文件**：默认 `config.yaml`，可通过 `AAF_CONFIG_FILE` 环境变量或 `--config` 参数指定
5. **代码默认值**

YAML 内可使用 `${VAR}` 引用环境变量（如 `api_key: ${DEEPSEEK_API_KEY}`）。

## 安全说明

- **API Key 鉴权**：`api.api_key` 非空时，所有 API 请求必须携带 `X-API-Key` 头。比较使用 `secrets.compare_digest` 防时序攻击。
- **路径白名单**：`knowledge.allowed_roots` 配置允许摄入的根目录；为空时仅允许相对路径，拒绝绝对路径与 `..` 穿越。生产部署务必显式配置白名单。
- **AST 求值**：`CalculatorTool` 使用 `ast.parse` + 白名单运算符，禁止任意函数调用与属性访问。

## 已知限制

- 插件机制目前主要支持注册 `Tool`；自定义 `Loader`/`Splitter`/`Retriever`/`Embeddings` 需通过修改工厂函数 mapping 扩展（详见 [docs/EXTENSION.md](docs/EXTENSION.md)）。
- `langchain_community.vectorstores.Chroma` 已被官方标记 deprecated，未来需迁移到 `langchain-chroma` 独立包。

## 文档

- [API 参考](docs/API.md)
- [扩展指南](docs/EXTENSION.md)
- [实施计划归档](docs/plans/)

## License

MIT
