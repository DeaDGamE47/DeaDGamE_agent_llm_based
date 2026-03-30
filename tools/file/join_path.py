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

    def run(self, folder_path=None, file_name=None, **kwargs):

        logger.info(f"JOIN PATH: folder_path={folder_path}, file_name={file_name}")

        # 🔥 FIX: Если пришел dict, извлекаем path
        if isinstance(folder_path, dict):
            folder_path = folder_path.get("path")
            
        if isinstance(file_name, dict):
            file_name = file_name.get("name") or file_name.get("path")

        if not folder_path:
            return self.error("folder_path не указан")

        if not file_name:
            return self.error("file_name не указан")

        full_path = os.path.join(folder_path, file_name)

        logger.info(f"RESULT PATH: {full_path}")

        return self.success(
            data={
                "path": full_path,
                "type": "path"
            },
            message=f"Сформирован путь: {full_path}"
        )