"""组件注册中心：统一管理可插拔组件（工具、加载器、检索器等）。"""
from __future__ import annotations

from threading import RLock
from typing import Any


class ComponentRegistry:
    """线程安全的组件注册中心单例。

    组件按 (category, name) 注册与查找，例如：
        registry.register("tool", "calculator", CalculatorTool())
        registry.get("tool", "calculator")

    所有读写操作受实例级 RLock 保护，支持运行时动态注册。
    """

    _instance: "ComponentRegistry | None" = None
    _instance_lock = RLock()

    def __new__(cls) -> "ComponentRegistry":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._components = {}  # type: ignore[attr-defined]
                    inst._lock = RLock()  # type: ignore[attr-defined]
                    cls._instance = inst
        return cls._instance

    @property
    def components(self) -> dict[str, dict[str, Any]]:
        return self._components  # type: ignore[attr-defined]

    def register(self, category: str, name: str, component: Any) -> None:
        """注册一个组件。同名覆盖。"""
        with self._lock:  # type: ignore[attr-defined]
            self.components.setdefault(category, {})[name] = component

    def get(self, category: str, name: str) -> Any:
        """获取组件，不存在则抛出 KeyError。"""
        with self._lock:  # type: ignore[attr-defined]
            try:
                return self.components[category][name]
            except KeyError:
                raise KeyError(f"组件未注册: {category}/{name}")

    def list(self, category: str) -> list[str]:
        """列出某类别下所有组件名。"""
        with self._lock:  # type: ignore[attr-defined]
            return list(self.components.get(category, {}).keys())

    def categories(self) -> list[str]:
        with self._lock:  # type: ignore[attr-defined]
            return list(self.components.keys())

    def unregister(self, category: str, name: str) -> None:
        with self._lock:  # type: ignore[attr-defined]
            self.components.get(category, {}).pop(name, None)

    def clear(self) -> None:
        """清空所有注册（测试用）。"""
        with self._lock:  # type: ignore[attr-defined]
            self.components.clear()


def get_registry() -> ComponentRegistry:
    """获取全局注册中心单例。"""
    return ComponentRegistry()
