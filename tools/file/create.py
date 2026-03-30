import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:create")


class CreateTool(BaseTool):

    name = "create"
    description = "Создаёт файл или папку с возможностью отката"

    required_args = ["path"]
    optional_args = ["content", "overwrite", "is_directory"]

    category = "file"
    risk_level = "medium"

    def __init__(self):
        self.backup_dir = Path(tempfile.gettempdir()) / "agent_undo" / "created"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"CreateTool backup dir: {self.backup_dir}")

    def run(self, **kwargs):
        path = kwargs.get("path")
        content = kwargs.get("content", "")
        overwrite = kwargs.get("overwrite", False)
        is_directory = kwargs.get("is_directory", False)

        logger.info(f"CREATE: {path} (is_directory={is_directory})")

        try:
            if not path:
                return self.error("Path not specified")

            path = os.path.abspath(path)

            if is_directory or path.endswith(('/', '\\')):
                return self._create_directory(path, overwrite)

            return self._create_file(path, content, overwrite)

        except Exception as e:
            logger.exception("Create failed")
            return self.error(str(e))

    def _create_directory(self, path: str, overwrite: bool):
        try:
            clean_path = path.rstrip('/\\')

            if os.path.exists(clean_path):
                if not overwrite:
                    return self.error(f"Directory already exists: {clean_path}")

                return self.success(
                    data={"path": clean_path, "type": "directory"},
                    message=f"Папка уже существует: {clean_path}",
                    undo_data=None
                )

            os.makedirs(clean_path, exist_ok=True)

            return self.success(
                data={"path": clean_path, "type": "directory"},
                message=f"Создана папка: {clean_path}",
                undo_data={
                    "path": clean_path,
                    "is_directory": True,
                    "backup_path": None
                }
            )

        except Exception as e:
            logger.exception("Create directory failed")
            return self.error(str(e))

    def _create_file(self, path: str, content: str, overwrite: bool):
        try:
            folder = os.path.dirname(path)

            if folder and not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)

            backup_info = None
            if os.path.exists(path):
                if not overwrite:
                    return self.error(f"File already exists: {path}")

                backup_info = self._backup_existing_file(path)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            ext = os.path.splitext(path)[1].lower()
            file_type = {
                ".txt": "text",
                ".py": "python",
                ".json": "json",
                ".md": "markdown",
                ".docx": "word"
            }.get(ext, "unknown")

            undo_data = {
                "path": path,
                "is_directory": False,
                "backup_path": backup_info["backup_path"] if backup_info else None,
                "had_existing_file": backup_info is not None
            }

            return self.success(
                data={"path": path, "type": file_type},
                message=f"Создан файл: {path}",
                undo_data=undo_data
            )

        except Exception as e:
            logger.exception("Create file failed")
            return self.error(str(e))