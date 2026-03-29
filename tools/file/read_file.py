import os

from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:read_file")


class ReadFileTool(BaseTool):

    name = "read_file"
    description = "Читает содержимое файла"
    required_args = ["path"]

    category = "file"
    risk_level = "low"

    def run(self, path: str):
        logger.info(f"READ FILE: {path}")

        # -------------------------
        # 🔥 проверки
        # -------------------------
        if not path:
            return {
                "status": "error",
                "error": "Не передан путь"
            }

        if not os.path.exists(path):
            return {
                "status": "error",
                "error": f"Файл не найден: {path}"
            }

        if not os.path.isfile(path):
            return {
                "status": "error",
                "error": f"Это не файл: {path}"
            }

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            return {
                "status": "success",
                "data": content
            }

        except Exception as e:
            logger.exception("read_file error")

            return {
                "status": "error",
                "error": str(e)
            }