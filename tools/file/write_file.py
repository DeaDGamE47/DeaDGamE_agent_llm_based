import os

from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:write_file")


class WriteFileTool(BaseTool):

    name = "write_file"
    description = "Записывает данные в файл"
    required_args = ["path"]
    optional_args = ["content"]

    category = "file"
    risk_level = "medium"

    def run(self, path, content="", **kwargs):

        logger.info(f"WRITE FILE: {path}")

        if not path:
            return {
                "status": "error",
                "error": "Путь не передан"
            }

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content or "")

            return {
                "status": "success",
                "data": f"Файл записан: {path}"
            }

        except Exception as e:
            logger.exception("write_file error")

            return {
                "status": "error",
                "error": str(e)
            }