"""插件加载器：扫描目录，动态导入实现 Tool 协议的模块并注册。

支持两种插件约定：
1. 模块级定义 `Tool` 实例（自动扫描注册）
2. 模块级定义 `register(tool_registry, component_registry)` 钩子（手动注册）

加载失败的插件会记录 warning 而非静默吞掉。
"""
from __future__ import annotations

import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Any

from ai_agent_framework.core.registry import get_registry
from ai_agent_framework.tools.base import Tool, ToolRegistry

logger = logging.getLogger(__name__)


def load_plugins(
    path: str | Path,
    tool_registry: ToolRegistry | None = None,
    component_registry=get_registry(),
) -> list[str]:
    """扫描目录下所有 .py 文件，导入其中定义的 Tool 并注册。

    - 若传入 tool_registry，Tool 实例会同时注册到该 ToolRegistry（供 Agent 使用）
      和全局 ComponentRegistry（供通用发现）。
    - 模块若定义 `register(tool_registry, component_registry)` 钩子，优先调用它。

    返回成功注册的组件名列表。
    """
    p = Path(path)
    if not p.exists():
        logger.debug("插件目录不存在: %s", p)
        return []

    registered: list[str] = []
    for f in sorted(p.glob("*.py")):
        if f.name.startswith("_"):
            continue
        mod = _import_file(f)
        if mod is None:
            continue

        # 1) 优先调用模块级 register 钩子
        register_fn = getattr(mod, "register", None)
        if callable(register_fn):
            try:
                register_fn(tool_registry, component_registry)
                registered.append(f.name)
                logger.info("插件 %s 通过 register() 钩子加载", f.name)
                continue
            except Exception as e:  # noqa: BLE001
                logger.warning("插件 %s register() 失败: %s", f.name, e, exc_info=True)
                continue

        # 2) 扫描模块中的 Tool 实例
        for attr_name, attr in inspect.getmembers(mod):
            if isinstance(attr, Tool) and attr.name:
                if tool_registry is not None:
                    tool_registry.register(attr)
                component_registry.register("tool", attr.name, attr)
                registered.append(attr.name)
                logger.info("插件 %s 注册工具: %s", f.name, attr.name)

    return registered


def _import_file(path: Path) -> Any:
    """从文件路径动态导入模块。"""
    mod_name = f"_aaf_plugin_{path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:  # noqa: BLE001
        logger.warning("插件 %s 导入失败: %s", path.name, e, exc_info=True)
        return None
