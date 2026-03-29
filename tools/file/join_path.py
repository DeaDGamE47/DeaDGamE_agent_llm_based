import os

from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:join_path")


class JoinPathTool(BaseTool):

    name = "join_path"
    description = "Объединяет путь папки и имя файла"
    required_args = ["folder_path", "file_name"]

    category = "system"
    risk_level = "low"

    def run(self, folder_path: str = None, file_name: str = None, **kwargs):
        logger.info(f"JOIN PATH: folder_path={folder_path}, file_name={file_name}")

        if not folder_path:
            return {
                "status": "error",
                "error": "folder_path не указан"
            }

        if not file_name:
            return {
                "status": "error",
                "error": "file_name не указан"
            }

        full_path = os.path.join(folder_path, file_name)

        logger.info(f"RESULT PATH: {full_path}")

        return {
            "status": "success",
            "data": full_path
        }