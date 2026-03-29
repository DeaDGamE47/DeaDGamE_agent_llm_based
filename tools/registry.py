import importlib
import pkgutil
import inspect

from tools.base import BaseTool


class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def auto_register(self, package_name="tools"):
        package = importlib.import_module(package_name)

        for _, module_name, _ in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            try:
                module = importlib.import_module(module_name)

                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseTool) and obj is not BaseTool:
                        tool_instance = obj()
                        self.tools[tool_instance.name] = tool_instance

            except Exception as e:
                print(f"[ToolRegistry] Failed to load {module_name}: {e}")

    def get_tool(self, name):
        return self.tools.get(name)

    def list_tools(self):
        return list(self.tools.keys())