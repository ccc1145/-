"""插件加载器测试。"""
import textwrap

from ai_agent_framework.plugins.loader import load_plugins
from ai_agent_framework.core.registry import get_registry
from ai_agent_framework.tools import ToolRegistry, CalculatorTool


def test_load_plugin_with_register_hook(tmp_path):
    reg = get_registry()
    reg.clear()
    tools = ToolRegistry()
    plugin = tmp_path / "my_plugin.py"
    plugin.write_text(
        textwrap.dedent(
            """
            from ai_agent_framework.tools import CalculatorTool

            def register(tool_registry, component_registry):
                tool_registry.register(CalculatorTool())
                component_registry.register("tool", "calc", CalculatorTool())
            """
        ),
        encoding="utf-8",
    )
    names = load_plugins(tmp_path, tool_registry=tools, component_registry=reg)
    assert "my_plugin.py" in names
    assert tools.has("calculator")
    assert "calc" in reg.list("tool")


def test_load_plugin_with_tool_instance(tmp_path):
    reg = get_registry()
    reg.clear()
    tools = ToolRegistry()
    plugin = tmp_path / "inst_plugin.py"
    plugin.write_text(
        textwrap.dedent(
            """
            from ai_agent_framework.tools import CalculatorTool
            my_tool = CalculatorTool()
            """
        ),
        encoding="utf-8",
    )
    names = load_plugins(tmp_path, tool_registry=tools, component_registry=reg)
    assert "calculator" in names
    assert tools.call("calculator", "1+1") == "2"
    assert "calculator" in reg.list("tool")


def test_load_plugins_missing_dir(tmp_path):
    reg = get_registry()
    reg.clear()
    assert load_plugins(tmp_path / "nope", component_registry=reg) == []


def test_load_plugin_with_broken_module_logs_warning(tmp_path, caplog):
    reg = get_registry()
    reg.clear()
    plugin = tmp_path / "broken.py"
    plugin.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    names = load_plugins(tmp_path, tool_registry=ToolRegistry(), component_registry=reg)
    assert names == []
    assert any("导入失败" in r.getMessage() for r in caplog.records)


def test_load_plugin_register_hook_failure_logs_warning(tmp_path, caplog):
    """register() 钩子抛异常时记录 warning，不影响其他插件加载。"""
    import logging

    reg = get_registry()
    reg.clear()
    tools = ToolRegistry()

    # 插件 1：register 抛异常
    p1 = tmp_path / "bad_register.py"
    p1.write_text(
        textwrap.dedent(
            """
            def register(tool_registry, component_registry):
                raise RuntimeError("register 内部错误")
            """
        ),
        encoding="utf-8",
    )

    # 插件 2：正常 register
    p2 = tmp_path / "good_register.py"
    p2.write_text(
        textwrap.dedent(
            """
            from ai_agent_framework.tools import CalculatorTool

            def register(tool_registry, component_registry):
                tool_registry.register(CalculatorTool())
            """
        ),
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        names = load_plugins(tmp_path, tool_registry=tools, component_registry=reg)

    # 插件 1 失败、插件 2 成功
    assert "good_register.py" in names
    assert "bad_register.py" not in names
    assert tools.has("calculator")
    # 插件 1 的失败被记录
    assert any(
        "register()" in r.getMessage() and "失败" in r.getMessage()
        for r in caplog.records
    )


def test_load_plugin_underscore_ignored(tmp_path):
    """_ 前缀的文件应被跳过。"""
    reg = get_registry()
    reg.clear()
    underscore_file = tmp_path / "_skip.py"
    underscore_file.write_text("raise RuntimeError('should not be loaded')\n", encoding="utf-8")
    # 不应抛异常，且返回空
    names = load_plugins(tmp_path, tool_registry=ToolRegistry(), component_registry=reg)
    assert names == []


def test_load_plugin_non_py_ignored(tmp_path):
    """非 .py 文件应被跳过。"""
    reg = get_registry()
    reg.clear()
    (tmp_path / "readme.md").write_text("not a plugin", encoding="utf-8")
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    names = load_plugins(tmp_path, tool_registry=ToolRegistry(), component_registry=reg)
    assert names == []


def test_load_plugin_with_retriever_dependency_via_component_registry(tmp_path):
    """register 钩子可从 component_registry 获取已注册的依赖。"""
    reg = get_registry()
    reg.clear()
    # 预注册一个"检索器"到 component_registry
    reg.register("retriever", "default", "fake_retriever_instance")

    tools = ToolRegistry()
    plugin = tmp_path / "dep_plugin.py"
    plugin.write_text(
        textwrap.dedent(
            """
            from ai_agent_framework.tools import Tool

            class SearchTool(Tool):
                name = "search"
                description = "依赖检索器的工具"
                def __init__(self, retriever):
                    self._retriever = retriever
                def run(self, input: str) -> str:
                    return f"search with {self._retriever}"

            def register(tool_registry, component_registry):
                retriever = component_registry.get("retriever", "default")
                tool_registry.register(SearchTool(retriever))
            """
        ),
        encoding="utf-8",
    )

    names = load_plugins(tmp_path, tool_registry=tools, component_registry=reg)
    assert "dep_plugin.py" in names
    assert tools.has("search")
    assert "search with fake_retriever_instance" in tools.call("search", "x")
