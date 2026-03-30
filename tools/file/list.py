import os
from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:list")


class ListTool(BaseTool):

    name = "list"
    description = "Показывает содержимое папки (текущей или указанной)"
    required_args = []  # 🔥 path теперь не обязательный
    optional_args = ["path"]  # 🔥 можно не указывать (используется текущая)

    category = "file"
    risk_level = "low"

    def run(self, path: str = None):
        logger.info(f"LIST: {path}")

        # -------------------------
        # 🔥 если путь не указан — используем текущую директорию
        # -------------------------
        if not path:
            path = os.getcwd()
            logger.debug(f"Using current directory: {path}")

        # -------------------------
        # 🔥 проверки
        # -------------------------
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
            result_lines = []

            if folders:
                result_lines.append("📁 Папки:")
                result_lines.extend(f"  {f}" for f in folders)

            if files:
                result_lines.append("\n📄 Файлы:")
                result_lines.extend(f"  {f}" for f in files)

            if not result_lines:
                result_lines.append("Папка пустая")

            return {
                "status": "success",
                "data": {
                    "path": path,
                    "type": "folder",
                    "folders": folders,
                    "files": files,
                    "message": "\n".join(result_lines),
                    "total_count": len(folders) + len(files)
                }
            }

        except Exception as e:
            logger.exception("list error")

            return {
                "status": "error",
                "error": str(e)
            }