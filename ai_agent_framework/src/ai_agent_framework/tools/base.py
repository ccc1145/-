"""工具调用接口：Tool 基类与工具注册中心。"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """工具基类。子类实现 run()。"""

    name: str = ""
    description: str = ""

    @abstractmethod
    def run(self, input: str) -> str:
        """执行工具，返回字符串结果。"""

    def __call__(self, input: str) -> str:
        return self.run(input)


class ToolRegistry:
    """工具注册中心：注册/调用/列举工具，线程安全。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._lock = threading.RLock()

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("工具必须定义非空 name")
        with self._lock:
            self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        with self._lock:
            if name not in self._tools:
                raise KeyError(f"工具未注册: {name}")
            return self._tools[name]

    def list(self) -> list[dict[str, str]]:
        with self._lock:
            return [
                {"name": t.name, "description": t.description}
                for t in self._tools.values()
            ]

    def call(self, name: str, input: str) -> str:
        return self.get(name).run(input)

    def has(self, name: str) -> bool:
        with self._lock:
            return name in self._tools

    def names(self) -> list[str]:
        with self._lock:
            return list(self._tools.keys())
