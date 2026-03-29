import os

from tools.base import BaseTool
from utils.logger import setup_logger


logger = setup_logger("Tool:create_file")


class CreateFileTool(BaseTool):

    name = "create_file"
    description = "Создаёт файл"
    required_args = ["path"]
    optional_args = ["content"]

    category = "file"
    risk_level = "medium"

    def run(self, path: str, content: str = "", overwrite: bool = False, **kwargs):
        logger.info(f"CREATE FILE: {path}")

        try:
            if not path:
                return {
                    "status": "error",
                    "error": "Путь не указан"
                }

            folder = os.path.dirname(path)

            logger.debug(f"TARGET FOLDER: {folder}")

            # -------------------------
            # 📁 проверка папки
            # -------------------------
            if not os.path.exists(folder):
                logger.error("Folder does not exist")

                return {
                    "status": "error",
                    "error": f"Папка не существует: {folder}"
                }

            # -------------------------
            # ⚠️ файл уже существует
            # -------------------------
            if os.path.exists(path):
                logger.warning("File already exists")

                if not overwrite:
                    return {
                        "status": "error",
                        "error": f"Файл уже существует: {path}"
                    }
                else:
                    logger.info("OVERWRITE ENABLED")

            # -------------------------
            # 🔥 создание файла
            # -------------------------
            logger.debug("Creating file...")

            with open(path, "w", encoding="utf-8") as f:
                if content:
                    logger.debug("Writing content to file")
                    f.write(content)

            # -------------------------
            # 🧠 определение типа файла
            # -------------------------
            ext = os.path.splitext(path)[1].lower()

            file_type = {
                ".txt": "текстовый файл",
                ".py": "Python файл",
                ".json": "JSON файл",
                ".md": "Markdown файл",
                ".docx": "Word файл"
            }.get(ext, "файл")

            message = f"Создан {file_type}: {path}"

            logger.info(message)

            return {
                "status": "success",
                "data": path   # 🔥 ВАЖНО: возвращаем path, а не текст
            }

        except Exception as e:
            logger.exception("create_file error")

            return {
                "status": "error",
                "error": str(e)
            }