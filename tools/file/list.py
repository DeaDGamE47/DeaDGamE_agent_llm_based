import os

from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:list")


class ListTool(BaseTool):

    name = "list"
    description = "Показывает содержимое папки"
    required_args = ["path"]

    category = "file"
    risk_level = "low"

    def run(self, path: str):
        logger.info(f"LIST: {path}")

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
                "error": f"Путь не существует: {path}"
            }

        if not os.path.isdir(path):
            return {
                "status": "error",
                "error": f"Это не папка: {path}"
            }

        try:
            items = os.listdir(path)

            folders = []
            files = []

            for item in items:
                full_path = os.path.join(path, item)

                if os.path.isdir(full_path):
                    folders.append(item)
                else:
                    files.append(item)

            # -------------------------
            # 🔥 сортировка
            # -------------------------
            folders.sort()
            files.sort()

            # -------------------------
            # 🔥 форматированный вывод
            # -------------------------
            result = []

            if folders:
                result.append("📁 Папки:")
                result.extend(f"  {f}" for f in folders)

            if files:
                result.append("\n📄 Файлы:")
                result.extend(f"  {f}" for f in files)

            if not result:
                result.append("Папка пустая")

            return {
                "status": "success",
                "data": "\n".join(result)
            }

        except Exception as e:
            logger.exception("list error")

            return {
                "status": "error",
                "error": str(e)
            }