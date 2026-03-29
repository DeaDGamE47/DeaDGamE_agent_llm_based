import os
import shutil

from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:delete")


class DeleteTool(BaseTool):

    name = "delete"
    description = "Удаляет файл или папку"
    required_args = ["path"]

    category = "file"
    risk_level = "high"
    requires_confirmation = True

    def run(self, path: str):
        logger.info(f"DELETE: {path}")

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

        try:
            # -------------------------
            # 🔥 файл
            # -------------------------
            if os.path.isfile(path):
                os.remove(path)

                return {
                    "status": "success",
                    "data": path
                }

            # -------------------------
            # 🔥 папка
            # -------------------------
            elif os.path.isdir(path):
                shutil.rmtree(path)

                return {
                    "status": "success",
                    "data": path
                }

            else:
                return {
                    "status": "error",
                    "error": "Неизвестный тип объекта"
                }

        except Exception as e:
            logger.exception("delete error")

            return {
                "status": "error",
                "error": str(e)
            }