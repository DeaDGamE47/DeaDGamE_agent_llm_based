import os

from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:create_file")


class CreateFileTool(BaseTool):
    name = "create_file"
    description = "Создаёт файл с указанным содержимым"
    
    required_args = ["path"]
    optional_args = ["content", "overwrite"]  # ← добавил overwrite
    
    category = "file"
    risk_level = "medium"

    def run(self, **kwargs):
        # Извлекаем аргументы из kwargs (как ожидает validate)
        path = kwargs.get("path")
        content = kwargs.get("content", "")
        overwrite = kwargs.get("overwrite", False)

        logger.info(f"CREATE FILE: {path}")

        try:
            if not path:
                return {"status": "error", "error": "Path not specified"}

            # Нормализация пути
            path = os.path.abspath(path)
            folder = os.path.dirname(path)

            # Проверка папки
            if folder and not os.path.exists(folder):
                logger.error(f"Folder not found: {folder}")
                return {"status": "error", "error": f"Folder not found: {folder}"}

            # Проверка существования файла
            if os.path.exists(path):
                if not overwrite:
                    logger.warning(f"File exists (overwrite=False): {path}")
                    return {"status": "error", "error": f"File already exists: {path}"}
                logger.info(f"Overwriting: {path}")

            # Создание
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            # Тип файла
            ext = os.path.splitext(path)[1].lower()
            file_type = {
                ".txt": "text",
                ".py": "Python",
                ".json": "JSON",
                ".md": "Markdown",
                ".docx": "Word"
            }.get(ext, "unknown")

            logger.info(f"Created [{file_type}]: {path}")

            return {
                "status": "success", 
                "data": {"path": path, "type": file_type}
            }

        except Exception as e:
            logger.exception("Create file failed")
            return {"status": "error", "error": str(e)}
