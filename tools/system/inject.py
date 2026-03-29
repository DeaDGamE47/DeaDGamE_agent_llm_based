from tools.base import BaseTool


class InjectTool(BaseTool):

    name = "inject"
    description = "Вставляет значение в pipeline"
    required_args = ["path"]

    category = "system"
    risk_level = "low"

    def run(self, path):
        return {
            "status": "success",
            "data": path
        }