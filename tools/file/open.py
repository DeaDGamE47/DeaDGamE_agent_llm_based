import os
from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:open")


class OpenTool(BaseTool):

    name = "open"
    description = "Открывает файл или папку"
    required_args = ["path"]

    category = "file"
    risk_level = "low"

    def run(self, path: str):
        logger.info(f"OPEN: {path}")

        # -------------------------
        # 🔥 проверка пути
        # -------------------------
        if not path:
            return {
                "status": "error",
                "error": "Не передан путь"
            }

        if not os.path.exists(path):
            logger.error(f"Path not found: {path}")
            return {
                "status": "error",
                "error": f"Путь не существует: {path}"
            }

        try:
            # -------------------------
            # 🔥 папка
            # -------------------------
            if os.path.isdir(path):
                logger.debug("Opening folder")

                os.startfile(path)

                return {
                    "status": "success",
                    "data": {
                        "path": path,
                        "type": "folder",
                        "message": f"Открыта папка: {path}"
                    }
                }

            # -------------------------
            # 🔥 файл
            # -------------------------
            else:
                logger.debug("Opening file")

                os.startfile(path)

                return {
                    "status": "success",
                    "data": {
                        "path": path,
                        "type": "file",
                        "message": f"Открыт файл: {path}"
                    }
                }

        except Exception as e:
            logger.exception("open error")

            return {
                "status": "error",
                "error": str(e)
            }