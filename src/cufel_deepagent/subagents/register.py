"""
SubAgent 定义和注册系统

此模块包含：
1. @subagent 装饰器工厂
2. SubAgent 注册表和动态收集机制
"""

from typing import Any

from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
def subagent(
    name: str,
    description: str,
    model_config: dict[str, Any],
    system_prompt: str = "",
    skills: list[str] | None = None,
    tools: list[str] | None = None,
) -> Any:
    """SubAgent 装饰器工厂

    用于标记函数为 SubAgent 定义

    Args:
        name: SubAgent 名称（唯一标识）
        description: 功能描述，说明此 SubAgent 的用途
        model_config: 模型配置字典，包含:
            - model: 模型名称
            - base_url: API 地址
            - api_key: API 密钥
            - temperature: 温度参数
            
        system_prompt: 系统提示词，定义 SubAgent 的行为
        skills: 关联的技能名称列表（可选）
        tools: 专用工具名称列表（可选）

    Usage:
        @subagent(
            name="writer-agent",
            description="Writes articles and analysis",
            model_config={"model": "xxx", "temperature": 0.7},
            system_prompt="You are a writer..."
        )
        def writer_agent():
            pass

    Note:
        - 被装饰的函数本身不需要实现
        - 装饰器会在函数对象上添加 _subagent_config 属性
        - 实际的 SubAgent 实例由 registry 中的机制动态创建
    """

    def decorator(func: Any) -> Any:
        # 存储 subagent 配置到函数对象
        func._subagent_config = {
            "name": name,
            "description": description,
            "model_config": model_config,
            "system_prompt": system_prompt,
            "skills": skills or [],
            "tools": tools or [],
        }
        return func

    return decorator


class SubAgentRegistry:
    """SubAgent 注册表

    特性：
    - 自动发现和加载 SubAgent
    - 缓存机制提高性能
    - 支持动态编辑和热重载
    """

    def __init__(self) -> None:
        self._cached_subagents: list[dict[str, Any]] | None = None

    def _collect_all_subagents(self) -> list[dict[str, Any]]:
        """动态收集所有 SubAgent

        扫描当前模块中所有带有 @subagent 装饰的函数，
        将其转换为实际的 SubAgent 配置字典
        # 得到配置的字典，即这几个参数组成的
        Returns:
            SubAgent 配置字典列表
        """
        if self._cached_subagents is None:
            self._cached_subagents = self._scan_and_convert()
        return self._cached_subagents

    def _scan_and_convert(self) -> list[dict[str, Any]]:
        """扫描并转换 SubAgent 定义

        遍历当前包的所有模块，找到带有 _subagent_config
        属性的函数，转换为实际的 SubAgent 实例

        Returns:
            转换后的 SubAgent 列表
        """
        import sys

        subagents: list[dict[str, Any]] = []

        # 直接扫描 subagents 模块（使用字符串导入避免循环）
        try:
            subagents_module = sys.modules.get("cufel_deepagent.subagents.subagents")
            if subagents_module is None:
                # 动态导入
                import importlib

                subagents_module = importlib.import_module(
                    "cufel_deepagent.subagents.subagents"
                )

            # 扫描 subagents 模块中的所有对象
            for name in dir(subagents_module):
                obj = getattr(subagents_module, name)

                # 检查是否是函数（可调用对象）且带有 _subagent_config 属性
                if callable(obj) and hasattr(obj, "_subagent_config"):
                    config = obj._subagent_config

                    try:
                        # 创建 ChatOpenAI 模型实例
                        model = ChatOpenAI(**config["model_config"])
                        #model = ChatOllama(**config["model_config"]) # 其实只需要填写模型名称即可
                        # 转换工具名称字符串为实际的工具对象
                        tool_objects = self._resolve_tools(config.get("tools", []))

                        # 构建标准的 SubAgent 配置
                        subagent_config: dict[str, Any] = {
                            "model": model,
                            "name": config["name"],
                            "description": config["description"],
                            "system_prompt": config["system_prompt"],
                            "tools": tool_objects,
                        }

                        subagents.append(subagent_config)

                    except Exception as e:
                        print(
                            f"Warning: Failed to create SubAgent '{config.get('name', name)}': {e}"
                        )

        except Exception as e:
            print(f"Warning: Failed to scan subagents module: {e}")

        return subagents

    def _resolve_tools(self, tool_names: list[str]) -> list[Any]:
        """将工具名称字符串转换为实际的工具对象

        仅支持 NATIVE_TOOLS 中定义的自定义工具

        Args:
            tool_names: 工具名称字符串列表

        Returns:
            工具对象列表
        """
        if not tool_names:
            return []

        # 由 deepagent 后端系统处理的工具（不需要警告）
        BACKEND_TOOLS = {
            "read_file", "write_file", "edit_file", "ls", "glob", "grep",
            "mkdir", "search", "arithmetic", "calculator", "python_repl", "bash",
        }

        try:
            from cufel_deepagent.tools.registry import NATIVE_TOOLS

            native_tool_names = {t.name for t in NATIVE_TOOLS}
            tools = []
            skipped_tools = []

            for tool_name in tool_names:
                if tool_name in native_tool_names:
                    # 查找 NATIVE_TOOLS 中的工具
                    for t in NATIVE_TOOLS:
                        if t.name == tool_name:
                            tools.append(t)
                            break
                elif tool_name in BACKEND_TOOLS:
                    # 后端工具不需要单独配置，deepagent 自动处理
                    pass
                else:
                    skipped_tools.append(tool_name)

            # 只在有真正遗漏的工具时打印 Warning
            if skipped_tools:
                print(
                    f"Warning: Tools not found (skipping): {', '.join(skipped_tools)}"
                )

            return tools
        except Exception as e:
            print(f"Warning: Failed to resolve tools: {e}")
            return []

    def get_all(self) -> list[dict[str, Any]]:
        """获取所有 SubAgent 列表

        Returns:
            SubAgent 配置字典列表
        """
        return self._collect_all_subagents()

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        """根据名称获取特定 SubAgent

        Args:
            name: SubAgent 名称

        Returns:
            匹配的 SubAgent 配置，如果未找到则返回 None
        """
        for subagent in self._collect_all_subagents():
            if subagent["name"] == name:
                return subagent
        return None

    def clear_cache(self) -> None:
        """清空缓存，强制重新扫描

        用于测试或需要热重载的场景
        """
        self._cached_subagents = None

    def __iter__(self) -> Any:
        """支持迭代协议"""
        return iter(self._collect_all_subagents())

    def __len__(self) -> int:
        """支持 len() 函数"""
        return len(self._collect_all_subagents())

    def __getitem__(self, index: int) -> dict[str, Any]:
        """支持索引访问"""
        return self._collect_all_subagents()[index]

    def __repr__(self) -> str:
        """支持 repr() 函数"""
        return f"SubAgentRegistry(count={len(self)})"


# 全局注册表实例
_registry = SubAgentRegistry()


# 便捷访问函数
def get_all_subagents() -> list[dict[str, Any]]:
    """获取所有 SubAgent 列表

    Returns:
        SubAgent 配置字典列表
    """
    return _registry.get_all()


def get_subagent_by_name(name: str) -> dict[str, Any] | None:
    """根据名称获取特定 SubAgent

    Args:
        name: SubAgent 名称

    Returns:
        匹配的 SubAgent 配置，如果未找到则返回 None
    """
    return _registry.get_by_name(name)


def clear_subagents_cache() -> None:
    """清空 SubAgent 缓存

    强制重新扫描所有 SubAgent 定义
    """
    _registry.clear_cache()


def get_registry() -> SubAgentRegistry:
    """获取注册表实例

    Returns:
        SubAgentRegistry 实例
    """
    return _registry